from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from overseer.db import connect, migrate, resolve_entity, search
from overseer.config import sample_manifest_path, schemas_path
from overseer.errors import SourceResponseError
from overseer.importer import import_manifest
from overseer.sources.base import SourcePage
from overseer.sources.fallout_wiki import FalloutWikiAdapter
from overseer.validation import validate

class FakeAdapter:
    name = "fake"

    def probe(self):
        return {}

    def fetch_pages(self, titles: list[str]) -> dict[str, SourcePage]:
        return {
            title: SourcePage(
                title=title,
                canonical_title=title,
                page_id=index,
                revision_id=1000 + index,
                revision_timestamp="2026-01-01T00:00:00Z",
                url=f"https://example.invalid/wiki/{index}",
                categories=(),
                metadata={"title": title, "index": index},
            )
            for index, title in enumerate(titles, 1)
        }


class FailingAdapter(FakeAdapter):
    def fetch_pages(self, titles: list[str]) -> dict[str, SourcePage]:
        raise SourceResponseError("simulated source failure")


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "archive.db"
        self.connection = connect(self.path)
        migrate(self.connection, schemas_path())
        self.manifest = json.loads(
            sample_manifest_path().read_text(encoding="utf-8")
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_migration_and_fts_are_available(self) -> None:
        version = self.connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
        self.assertEqual(version, 1)
        self.connection.execute("CREATE VIRTUAL TABLE temp.test_fts USING fts5(value)")

    def test_manifest_import_is_idempotent_and_searches_aliases(self) -> None:
        rights = {"text": "CC BY-SA 4.0", "url": "https://example.invalid/license"}
        first = import_manifest(self.connection, FakeAdapter(), self.manifest, rights)
        second = import_manifest(self.connection, FakeAdapter(), self.manifest, rights)
        self.assertEqual(first.imported, 29)
        self.assertEqual(second.imported, 29)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM entities").fetchone()[0], 29)
        self.assertEqual(self.connection.execute("SELECT count(*) FROM claims").fetchone()[0], 30)
        self.assertEqual(search(self.connection, "Mr House")[0]["slug"], "robert-house")
        self.assertEqual(resolve_entity(self.connection, "NCR")["slug"], "new-california-republic")
        self.assertEqual(validate(self.connection), [])

    def test_source_failure_records_failed_run(self) -> None:
        with self.assertRaises(SourceResponseError):
            import_manifest(self.connection, FailingAdapter(), self.manifest, {}, minimum_records=1)
        status = self.connection.execute("SELECT status FROM ingestion_runs ORDER BY id DESC").fetchone()[0]
        self.assertEqual(status, "failed")

    def test_validation_detects_missing_provenance_and_fts_mismatch(self) -> None:
        type_id = self.connection.execute("INSERT INTO entity_types(name) VALUES ('test')").lastrowid
        self.connection.execute(
            """INSERT INTO entities(slug,name,entity_type_id,created_at,updated_at)
            VALUES ('orphan','Orphan',?,'now','now')""", (type_id,)
        )
        self.connection.commit()
        codes = {finding.code for finding in validate(self.connection)}
        self.assertIn("missing_provenance", codes)
        self.assertIn("fts_inconsistency", codes)

    def test_robots_wildcard_api_disallow_is_detected(self) -> None:
        robots = "User-agent: *\nDisallow: /api.php\nUser-agent: Example\nAllow: /\n"
        self.assertTrue(FalloutWikiAdapter.robots_disallows_api(robots))
        self.assertFalse(FalloutWikiAdapter.robots_disallows_api("User-agent: *\nDisallow: /private/\n"))


if __name__ == "__main__":
    unittest.main()
