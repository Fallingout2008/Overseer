"""Deterministic Phase 1 manifest importer with provenance."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from overseer.db import rebuild_fts, utc_now
from overseer.errors import SourceResponseError
from overseer.sources.base import SourceAdapter, SourcePage


@dataclass(frozen=True, slots=True)
class ImportResult:
    run_id: int
    requested: int
    imported: int
    missing_titles: tuple[str, ...]


def load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("entities"), list):
        raise ValueError("Manifest must contain an entities list")
    return value


def save_probe(probe: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _upsert_source(
    connection: sqlite3.Connection,
    adapter: SourceAdapter,
    page: SourcePage,
    rights: dict[str, Any],
) -> int:
    connection.execute(
        """
        INSERT INTO sources(adapter, source_key, title, url, license_name, license_url, medium)
        VALUES (?, ?, ?, ?, ?, ?, 'community_reference')
        ON CONFLICT(adapter, source_key) DO UPDATE SET
          title=excluded.title, url=excluded.url,
          license_name=excluded.license_name, license_url=excluded.license_url
        """,
        (
            adapter.name,
            str(page.page_id),
            page.canonical_title,
            page.url,
            rights.get("text"),
            rights.get("url"),
        ),
    )
    source_id = connection.execute(
        "SELECT id FROM sources WHERE adapter=? AND source_key=?",
        (adapter.name, str(page.page_id)),
    ).fetchone()[0]
    raw = json.dumps(page.metadata, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO source_revisions(
          source_id,page_id,revision_id,revision_timestamp,retrieved_at,content_hash,raw_metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, revision_id) DO UPDATE SET
          retrieved_at=excluded.retrieved_at, raw_metadata_json=excluded.raw_metadata_json,
          content_hash=excluded.content_hash
        """,
        (source_id, page.page_id, page.revision_id, page.revision_timestamp, utc_now(), content_hash, raw),
    )
    return connection.execute(
        "SELECT id FROM source_revisions WHERE source_id=? AND revision_id=?",
        (source_id, page.revision_id),
    ).fetchone()[0]


def _upsert_entity(connection: sqlite3.Connection, record: dict[str, Any]) -> int:
    entity_type = str(record["type"])
    connection.execute("INSERT OR IGNORE INTO entity_types(name) VALUES (?)", (entity_type,))
    type_id = connection.execute("SELECT id FROM entity_types WHERE name=?", (entity_type,)).fetchone()[0]
    now = utc_now()
    connection.execute(
        """
        INSERT INTO entities(slug,name,entity_type_id,summary,canon_status,confidence,created_at,updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET name=excluded.name, entity_type_id=excluded.entity_type_id,
          summary=excluded.summary, canon_status=excluded.canon_status,
          confidence=excluded.confidence, updated_at=excluded.updated_at
        """,
        (
            record["slug"], record["name"], type_id, record.get("summary", ""),
            record.get("canon_status", "canonical"), record.get("confidence", "high"), now, now,
        ),
    )
    return connection.execute("SELECT id FROM entities WHERE slug=?", (record["slug"],)).fetchone()[0]


def _make_dossier(connection: sqlite3.Connection, entity_id: int) -> None:
    entity = connection.execute(
        """SELECT e.*, et.name AS type FROM entities e
        JOIN entity_types et ON et.id=e.entity_type_id WHERE e.id=?""",
        (entity_id,),
    ).fetchone()
    claims = list(connection.execute("SELECT * FROM claims WHERE entity_id=? ORDER BY id", (entity_id,)))
    appearances = [
        row[0] for row in connection.execute(
            "SELECT w.title FROM appearances a JOIN works w ON w.id=a.work_id WHERE a.entity_id=? ORDER BY w.id",
            (entity_id,),
        )
    ]
    claim_lines = [f"- {row['predicate'].replace('_', ' ').title()}: {row['object_text']}" for row in claims]
    body = "\n".join(
        [
            f"NAME: {entity['name']}",
            f"CLASSIFICATION: {entity['type']}",
            f"CANON / CONTINUITY: {entity['canon_status']}",
            f"PRIMARY APPEARANCES: {', '.join(appearances) or 'Unknown'}",
            "",
            "OVERVIEW",
            entity["summary"],
            "",
            "EVIDENCE-BACKED FACTS",
            *(claim_lines or ["- No structured claims available."]),
            "",
            "SOURCE INDEX",
            "Use `overseer sources` and `overseer evidence` for revision-level provenance.",
        ]
    )
    connection.execute(
        """INSERT INTO dossiers(entity_id,body,generated_at,generator_version) VALUES (?, ?, ?, '1')
        ON CONFLICT(entity_id) DO UPDATE SET body=excluded.body, generated_at=excluded.generated_at,
        generator_version=excluded.generator_version""",
        (entity_id, body, utc_now()),
    )
    dossier_id = connection.execute("SELECT id FROM dossiers WHERE entity_id=?", (entity_id,)).fetchone()[0]
    connection.execute("DELETE FROM dossier_claims WHERE dossier_id=?", (dossier_id,))
    connection.executemany(
        "INSERT INTO dossier_claims(dossier_id, claim_id) VALUES (?, ?)",
        ((dossier_id, row["id"]) for row in claims),
    )


def import_manifest(
    connection: sqlite3.Connection,
    adapter: SourceAdapter,
    manifest: dict[str, Any],
    rights: dict[str, Any],
    *,
    minimum_records: int = 25,
) -> ImportResult:
    records = manifest["entities"]
    started = utc_now()
    cursor = connection.execute(
        "INSERT INTO ingestion_runs(adapter,started_at,status,records_seen) VALUES (?,?,'running',?)",
        (adapter.name, started, len(records)),
    )
    run_id = int(cursor.lastrowid)
    connection.commit()
    try:
        pages = adapter.fetch_pages([str(record["source_title"]) for record in records])
    except Exception as exc:
        connection.execute(
            "UPDATE ingestion_runs SET status='failed',completed_at=?,error=? WHERE id=?",
            (utc_now(), str(exc), run_id),
        )
        connection.commit()
        raise
    missing = tuple(str(record["source_title"]) for record in records if record["source_title"] not in pages)
    if len(records) - len(missing) < minimum_records:
        message = f"Only {len(records) - len(missing)} source pages resolved; need {minimum_records}"
        connection.execute(
            "UPDATE ingestion_runs SET status='blocked',completed_at=?,error=? WHERE id=?",
            (utc_now(), message, run_id),
        )
        connection.commit()
        raise SourceResponseError(f"{message}. Missing: {', '.join(missing)}")

    imported_ids: dict[str, int] = {}
    revision_ids: dict[str, int] = {}
    try:
        with connection:
            for work in manifest.get("works", []):
                connection.execute(
                    """INSERT INTO works(slug,title,medium,release_year) VALUES (?,?,?,?)
                    ON CONFLICT(slug) DO UPDATE SET title=excluded.title,medium=excluded.medium,
                    release_year=excluded.release_year""",
                    (work["slug"], work["title"], work["medium"], work.get("release_year")),
                )
            for record in records:
                page = pages.get(record["source_title"])
                if page is None:
                    continue
                entity_id = _upsert_entity(connection, record)
                imported_ids[record["slug"]] = entity_id
                revision_id = _upsert_source(connection, adapter, page, rights)
                revision_ids[record["slug"]] = revision_id
                connection.execute(
                    "INSERT OR IGNORE INTO entity_sources(entity_id,source_revision_id,role) VALUES (?,?,'reference')",
                    (entity_id, revision_id),
                )
                for alias in record.get("aliases", []):
                    connection.execute(
                        "INSERT OR IGNORE INTO entity_aliases(entity_id,alias) VALUES (?,?)", (entity_id, alias)
                    )
                for work_slug in record.get("appearances", []):
                    connection.execute(
                        """INSERT OR IGNORE INTO appearances(entity_id,work_id)
                        SELECT ?,id FROM works WHERE slug=?""", (entity_id, work_slug)
                    )
                for tag in record.get("tags", []):
                    connection.execute("INSERT OR IGNORE INTO tags(name) VALUES (?)", (tag,))
                    connection.execute(
                        """INSERT OR IGNORE INTO entity_tags(entity_id,tag_id)
                        SELECT ?,id FROM tags WHERE name=?""", (entity_id, tag)
                    )
                for predicate, object_text in record.get("claims", []):
                    connection.execute(
                        """INSERT OR IGNORE INTO claims(
                        entity_id,predicate,object_text,source_revision_id,canon_status,confidence
                        ) VALUES (?,?,?,?,?,?)""",
                        (entity_id, predicate, object_text, revision_id,
                         record.get("canon_status", "canonical"), record.get("confidence", "high")),
                    )
                if timeline := record.get("timeline"):
                    connection.execute(
                        """INSERT OR IGNORE INTO timeline_events(
                        entity_id,label,year_start,year_end,date_text,sort_key,source_revision_id,canon_status,confidence
                        ) VALUES (?,?,?,?,?,?,?,?,?)""",
                        (entity_id, timeline["label"], timeline.get("year_start"), timeline.get("year_end"),
                         timeline.get("date_text"), str(timeline.get("year_start", "")), revision_id,
                         record.get("canon_status", "canonical"), record.get("confidence", "high")),
                    )
            for record in records:
                subject_id = imported_ids.get(record["slug"])
                if subject_id is None:
                    continue
                for predicate, target_slug in record.get("relationships", []):
                    target_id = imported_ids.get(target_slug)
                    if target_id is None:
                        continue
                    connection.execute(
                        """INSERT OR IGNORE INTO relationships(
                        subject_entity_id,predicate,object_entity_id,source_revision_id,canon_status,confidence
                        ) VALUES (?,?,?,?,?,?)""",
                        (subject_id, predicate, target_id, revision_ids[record["slug"]],
                         record.get("canon_status", "canonical"), record.get("confidence", "high")),
                    )
            for entity_id in imported_ids.values():
                _make_dossier(connection, entity_id)
            rebuild_fts(connection)
            connection.execute(
                """UPDATE ingestion_runs SET status='complete',completed_at=?,records_written=?,checkpoint=?
                WHERE id=?""",
                (utc_now(), len(imported_ids), "complete", run_id),
            )
    except Exception as exc:
        connection.execute(
            "UPDATE ingestion_runs SET status='failed',completed_at=?,error=? WHERE id=?",
            (utc_now(), str(exc), run_id),
        )
        connection.commit()
        raise
    return ImportResult(run_id, len(records), len(imported_ids), missing)
