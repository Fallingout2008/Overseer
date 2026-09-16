"""Command-line interface for the OVERSEER archive."""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
import sys
from pathlib import Path
from typing import Sequence

from overseer import __version__
from overseer.config import (
    cache_path,
    database_path,
    project_root,
    sample_manifest_path,
    schemas_path,
)
from overseer.db import connect, migrate, resolve_entity, rows, search
from overseer.errors import OverseerError, RecordNotFoundError
from overseer.http import PoliteHttpClient
from overseer.importer import import_manifest, load_manifest, save_probe
from overseer.sources.fallout_wiki import FalloutWikiAdapter
from overseer.validation import validate

GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"
USER_AGENT = "OVERSEER/0.1 (+https://github.com/Fallingout2008/Overseer; contact: repository issues)"


class Output:
    def __init__(self, color: bool) -> None:
        self.color = color

    def line(self, text: str = "", *, dim: bool = False) -> None:
        if self.color and text:
            prefix = DIM if dim else GREEN
            print(f"{prefix}{text}{RESET}")
        else:
            print(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="overseer", description="Offline, source-aware Fallout lore archive")
    parser.add_argument("--version", action="version", version=f"OVERSEER {__version__}")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color")
    parser.add_argument("--db", type=Path, help="override the SQLite database path")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("init", help="initialize or migrate the local database")
    commands.add_parser("probe", help="run the bounded source capability/license probe")
    commands.add_parser("import-sample", help="probe and import the Phase 1 sample manifest")

    search_parser = commands.add_parser("search", help="full-text search")
    search_parser.add_argument("query", nargs="+")
    open_parser = commands.add_parser("open", help="open a dossier by ID, slug, name, or alias")
    open_parser.add_argument("value", nargs="+")
    for command, kind in (("person", "person"), ("location", "location"), ("vault", "vault"),
                          ("faction", "faction"), ("event", "event")):
        item = commands.add_parser(command, help=f"open a {kind} record")
        item.add_argument("value", nargs="+")
    timeline = commands.add_parser("timeline", help="show events for a year")
    timeline.add_argument("year", type=int)
    related = commands.add_parser("related", help="show relationships")
    related.add_argument("value", nargs="+")
    sources = commands.add_parser("sources", help="show page/revision provenance")
    sources.add_argument("value", nargs="+")
    evidence = commands.add_parser("evidence", help="show claims and claim-level provenance")
    evidence.add_argument("value", nargs="+")
    commands.add_parser("random", help="open a random record")
    commands.add_parser("stats", help="show local archive statistics and sizes")
    commands.add_parser("validate", help="run local integrity and provenance checks")
    update = commands.add_parser("update", help="check the source without importing changes")
    update.add_argument("--check", action="store_true", required=True)
    commands.add_parser("help", help="show this help")
    return parser


def _connection(db_path: Path, *, readonly: bool = True) -> sqlite3.Connection:
    if readonly and not db_path.exists():
        raise OverseerError("Archive is not initialized. Run `overseer init` or `overseer import-sample`.")
    return connect(db_path, readonly=readonly)


def _value(arguments: argparse.Namespace) -> str:
    return " ".join(arguments.value)


def _print_dossier(connection: sqlite3.Connection, output: Output, entity: sqlite3.Row) -> None:
    dossier = connection.execute("SELECT body FROM dossiers WHERE entity_id=?", (entity["id"],)).fetchone()
    output.line(dossier["body"] if dossier else f"{entity['name']}\n{entity['summary']}")


def _probe() -> tuple[FalloutWikiAdapter, dict[str, object]]:
    client = PoliteHttpClient(cache_path(), USER_AGENT)
    adapter = FalloutWikiAdapter(client)
    probe = adapter.probe()
    stamp = str(probe["retrieved_at"]).replace(":", "-")
    save_probe(probe, project_root() / "data" / "manifests" / f"probe-{stamp}.json")
    if probe.get("policy_status") != "allowed":
        raise OverseerError(f"Source policy blocked acquisition: {probe.get('policy_reason', 'unknown reason')}")
    return adapter, probe


def _dispatch(arguments: argparse.Namespace, parser: argparse.ArgumentParser, output: Output) -> int:
    db_path = arguments.db.resolve() if arguments.db else database_path()
    command = arguments.command
    if command in {None, "help"}:
        if command is None and sys.stdin.isatty() and db_path.exists():
            return _interactive(db_path, output)
        parser.print_help()
        return 0
    if command == "init":
        connection = connect(db_path)
        applied = migrate(connection, schemas_path())
        output.line(f"Database ready: {db_path}")
        output.line(f"Applied migrations: {applied or 'none (already current)'}")
        return 0
    if command in {"probe", "update"}:
        _, probe = _probe()
        rights = probe["siteinfo"]["rightsinfo"]  # type: ignore[index]
        output.line(f"Source API: PASS — {probe['api_url']}")
        output.line(f"Live rights: {rights.get('text')} — {rights.get('url')}")  # type: ignore[union-attr]
        output.line("Category and harmless revision probes: PASS")
        return 0
    if command == "import-sample":
        connection = connect(db_path)
        migrate(connection, schemas_path())
        adapter, probe = _probe()
        rights = probe["siteinfo"]["rightsinfo"]  # type: ignore[index]
        manifest = load_manifest(sample_manifest_path())
        result = import_manifest(connection, adapter, manifest, rights)  # type: ignore[arg-type]
        output.line(f"Import complete: {result.imported}/{result.requested} records")
        if result.missing_titles:
            output.line(f"Skipped missing pages: {', '.join(result.missing_titles)}")
        return 0

    connection = _connection(db_path)
    if command == "search":
        matches = search(connection, " ".join(arguments.query))
        for row in matches:
            output.line(f"{row['id']:>3}  {row['name']} [{row['type']}] — {row['summary']}")
        return 0 if matches else 1
    if command == "open":
        _print_dossier(connection, output, resolve_entity(connection, _value(arguments)))
        return 0
    if command in {"person", "location", "vault", "faction", "event"}:
        _print_dossier(connection, output, resolve_entity(connection, _value(arguments), command))
        return 0
    if command == "timeline":
        found = list(rows(connection, """SELECT te.*,e.name FROM timeline_events te JOIN entities e ON e.id=te.entity_id
            WHERE te.year_start<=? AND COALESCE(te.year_end,te.year_start)>=? ORDER BY te.sort_key""",
            (arguments.year, arguments.year)))
        for row in found:
            output.line(f"{row['year_start']}: {row['label']} ({row['name']})")
        return 0 if found else 1
    if command == "related":
        entity = resolve_entity(connection, _value(arguments))
        found = list(rows(connection, """SELECT r.predicate,o.name,'out' direction FROM relationships r
            JOIN entities o ON o.id=r.object_entity_id WHERE r.subject_entity_id=?
            UNION ALL SELECT r.predicate,s.name,'in' FROM relationships r
            JOIN entities s ON s.id=r.subject_entity_id WHERE r.object_entity_id=? ORDER BY 2""",
            (entity["id"], entity["id"])))
        output.line(f"RELATIONSHIPS: {entity['name']}")
        for row in found:
            arrow = "→" if row["direction"] == "out" else "←"
            output.line(f"  {arrow} {row['predicate'].replace('_', ' ')}: {row['name']}")
        return 0 if found else 1
    if command == "sources":
        entity = resolve_entity(connection, _value(arguments))
        found = rows(connection, """SELECT s.title,s.url,s.license_name,s.license_url,sr.page_id,
            sr.revision_id,sr.revision_timestamp,sr.retrieved_at FROM entity_sources es
            JOIN source_revisions sr ON sr.id=es.source_revision_id JOIN sources s ON s.id=sr.source_id
            WHERE es.entity_id=? ORDER BY s.title""", (entity["id"],))
        for row in found:
            output.line(f"{row['title']} — {row['url']}")
            output.line(f"  page {row['page_id']}, revision {row['revision_id']} @ {row['revision_timestamp']}")
            output.line(f"  retrieved {row['retrieved_at']}; {row['license_name']} ({row['license_url']})")
        return 0
    if command == "evidence":
        entity = resolve_entity(connection, _value(arguments))
        found = list(rows(connection, """SELECT c.predicate,c.object_text,c.confidence,c.canon_status,
            s.title,s.url,sr.revision_id FROM claims c JOIN source_revisions sr ON sr.id=c.source_revision_id
            JOIN sources s ON s.id=sr.source_id WHERE c.entity_id=? ORDER BY c.id""", (entity["id"],)))
        for row in found:
            output.line(f"{row['predicate']}: {row['object_text']} [{row['canon_status']}; {row['confidence']}]" )
            output.line(f"  {row['title']}, revision {row['revision_id']} — {row['url']}")
        return 0 if found else 1
    if command == "random":
        ids = [row[0] for row in connection.execute("SELECT id FROM entities")]
        if not ids:
            raise RecordNotFoundError("Archive contains no records")
        _print_dossier(connection, output, resolve_entity(connection, str(random.choice(ids))))
        return 0
    if command == "stats":
        counts = dict(
            connection.execute(
                """SELECT 'entities',count(*) FROM entities
                UNION ALL SELECT 'claims',count(*) FROM claims
                UNION ALL SELECT 'relationships',count(*) FROM relationships
                UNION ALL SELECT 'sources',count(*) FROM sources"""
            )
        )
        for label, count in counts.items():
            output.line(f"{label}: {count}")
        output.line(f"database_bytes: {db_path.stat().st_size}")
        cache_bytes = sum(path.stat().st_size for path in cache_path().glob("*") if path.is_file())
        output.line(f"cache_bytes: {cache_bytes}")
        return 0
    if command == "validate":
        findings = validate(connection)
        if not findings:
            output.line("Validation: PASS (0 findings)")
            return 0
        for finding in findings:
            output.line(f"FAIL {finding.code}: {finding.count} — {finding.detail}")
        return 1
    raise OverseerError(f"Unsupported command: {command}")


def _interactive(db_path: Path, output: Output) -> int:
    output.line("OVERSEER interactive mode. Type `help` or `quit`.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            output.line()
            return 0
        if not line:
            continue
        if line in {"quit", "exit"}:
            return 0
        if line == "help":
            output.line(
                "Commands: search, open, person, location, vault, faction, event, "
                "timeline, related, sources, evidence, random, stats, validate, quit"
            )
            continue
        try:
            arguments = _parser().parse_args(["--db", str(db_path), *line.split()])
            _dispatch(arguments, _parser(), output)
        except (OverseerError, SystemExit) as exc:
            output.line(f"Error: {exc}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    color = not arguments.no_color and "NO_COLOR" not in os.environ and sys.stdout.isatty()
    output = Output(color)
    try:
        return _dispatch(arguments, parser, output)
    except (OverseerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"overseer: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
