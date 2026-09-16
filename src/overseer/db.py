"""SQLite schema, migration, and query support."""

from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from overseer.errors import RecordNotFoundError


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def migrate(connection: sqlite3.Connection, schemas_dir: Path) -> list[int]:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
    completed: list[int] = []
    for path in sorted(schemas_dir.glob("[0-9][0-9][0-9]_*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version in applied:
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
            (version, path.name, utc_now()),
        )
        connection.commit()
        completed.append(version)
    return completed


def rebuild_fts(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM entity_fts")
    connection.execute(
        """
        INSERT INTO entity_fts(rowid, name, aliases, summary)
        SELECT e.id, e.name, COALESCE(group_concat(a.alias, ' '), ''), e.summary
        FROM entities e LEFT JOIN entity_aliases a ON a.entity_id = e.id
        GROUP BY e.id
        """
    )


def _fts_query(text: str) -> str:
    words = re.findall(r"[\w'-]+", text, flags=re.UNICODE)
    return " AND ".join(f'"{word.replace(chr(34), chr(34) * 2)}"*' for word in words)


def search(connection: sqlite3.Connection, query: str, limit: int = 20) -> list[sqlite3.Row]:
    expression = _fts_query(query)
    if not expression:
        return []
    return list(
        connection.execute(
            """
            SELECT e.id, e.slug, e.name, et.name AS type, e.summary, e.canon_status,
                   bm25(entity_fts, 5.0, 3.0, 1.0) AS rank
            FROM entity_fts
            JOIN entities e ON e.id = entity_fts.rowid
            JOIN entity_types et ON et.id = e.entity_type_id
            WHERE entity_fts MATCH ?
            ORDER BY rank, e.name LIMIT ?
            """,
            (expression, limit),
        )
    )


def resolve_entity(connection: sqlite3.Connection, value: str, entity_type: str | None = None) -> sqlite3.Row:
    filters = " AND et.name = ?" if entity_type else ""
    params: tuple[Any, ...] = (
        (value, value, value, value, entity_type)
        if entity_type
        else (value, value, value, value)
    )
    row = connection.execute(
        f"""
        SELECT DISTINCT e.*, et.name AS type
        FROM entities e JOIN entity_types et ON et.id=e.entity_type_id
        LEFT JOIN entity_aliases a ON a.entity_id=e.id
        WHERE (CAST(e.id AS TEXT)=? OR e.slug=? COLLATE NOCASE OR e.name=? COLLATE NOCASE
               OR a.alias=? COLLATE NOCASE){filters}
        LIMIT 1
        """ if entity_type else
        """
        SELECT DISTINCT e.*, et.name AS type
        FROM entities e JOIN entity_types et ON et.id=e.entity_type_id
        LEFT JOIN entity_aliases a ON a.entity_id=e.id
        WHERE CAST(e.id AS TEXT)=? OR e.slug=? COLLATE NOCASE OR e.name=? COLLATE NOCASE
              OR a.alias=? COLLATE NOCASE
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is None:
        matches = search(connection, value, 1)
        if matches:
            candidate = matches[0]
            if entity_type is None or candidate["type"] == entity_type:
                return resolve_entity(connection, str(candidate["id"]), entity_type)
        raise RecordNotFoundError(f"No matching record: {value}")
    return row


def rows(connection: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Iterator[sqlite3.Row]:
    yield from connection.execute(sql, params)
