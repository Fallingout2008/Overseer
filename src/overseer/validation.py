"""Local database integrity and provenance validation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    count: int
    detail: str


CHECKS = (
    ("foreign_keys", "PRAGMA foreign_key_check", "Foreign-key violations"),
    ("missing_provenance", """SELECT e.id FROM entities e LEFT JOIN entity_sources es ON es.entity_id=e.id
      WHERE es.entity_id IS NULL""", "Entities without provenance"),
    ("claims_without_source", """SELECT c.id FROM claims c LEFT JOIN source_revisions sr
      ON sr.id=c.source_revision_id WHERE sr.id IS NULL""", "Claims without source revisions"),
    ("orphan_relationships", """SELECT r.id FROM relationships r LEFT JOIN entities s
      ON s.id=r.subject_entity_id LEFT JOIN entities o ON o.id=r.object_entity_id
      WHERE s.id IS NULL OR o.id IS NULL""", "Relationships with missing endpoints"),
    ("duplicate_aliases", """SELECT lower(alias) FROM entity_aliases GROUP BY lower(alias)
      HAVING count(DISTINCT entity_id)>1""", "Aliases assigned to multiple entities"),
    ("malformed_dates", """SELECT id FROM timeline_events WHERE year_start IS NULL
      OR (year_end IS NOT NULL AND year_end < year_start)""", "Malformed timeline dates"),
    ("unsupported_dossiers", """SELECT d.id FROM dossiers d JOIN claims c ON c.entity_id=d.entity_id
      LEFT JOIN dossier_claims dc ON dc.dossier_id=d.id AND dc.claim_id=c.id
      WHERE dc.claim_id IS NULL""", "Dossier claims lacking evidence links"),
    ("failed_migrations", "SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_migrations)", "No migration applied"),
    ("fts_inconsistency", """SELECT 1 WHERE
      (SELECT count(*) FROM entities)!=(SELECT count(*) FROM entity_fts)""", "FTS/entity row count mismatch"),
    ("replayed_ingestion", """SELECT entity_id,predicate,object_text,source_revision_id FROM claims
      GROUP BY entity_id,predicate,object_text,source_revision_id HAVING count(*)>1""", "Duplicate claims"),
    ("open_review_flags", "SELECT id FROM review_flags WHERE status='open'", "Records requiring review"),
)


def validate(connection: sqlite3.Connection) -> list[Finding]:
    findings: list[Finding] = []
    for code, sql, detail in CHECKS:
        count = len(list(connection.execute(sql)))
        if count:
            findings.append(Finding(code, count, detail))
    return findings
