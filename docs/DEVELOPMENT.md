# Development notes

## Layout

- `src/overseer/`: application, acquisition, import, validation, and CLI
- `src/overseer/schemas/`: packaged, ordered SQLite migrations
- `schemas/`: migration design/review notes
- `tests/`: standard-library unit tests
- `src/overseer/data/`: packaged reviewed import definitions
- `data/manifests/`: generated probe reports
- `data/generated/`: ignored local databases
- `data/attribution/`: optional generated attribution exports
- `cache/`: ignored disposable HTTP responses

The project uses a `src` package layout and PEP 621 `pyproject.toml`. Runtime is
standard-library-only. New migrations must be additive, ordered, idempotent on
recovery, and must retain source/revision history.

## Import discipline

Do not add a source merely because it is technically reachable. Implement an
adapter, policy probe, bounded tests, provenance mapping, and licensing notes.
Never execute source content. Do not make tests or CI contact community APIs;
unit tests use a fake adapter.

For a new catalog slice: review the manifest, run the live policy probe, import
to a fresh development database, re-run the same import to test idempotency,
validate, test offline use, inspect type/provenance counts, and measure both DB
and cache. Do not commit generated databases or response caches.

## Known Phase 1 limitations

- The sample uses manually reviewed named pages; there is no category catalog.
- Dossiers intentionally contain only overview, appearances, structured claims,
  continuity label, and source-index guidance.
- Source metadata is acquired, not article body text; no automatic parser exists.
- The rights URL supplied by siteinfo was malformed at the time of the probe.
- Interactive mode is intentionally small and uses shell-like whitespace rather
  than a full line editor.
- Python 3.11+ is targeted; Windows packaging is future work.

## Roadmap

Phase 2, only after explicit approval, adds a reviewed New Vegas catalog,
targeted content normalization, redirects/deduplication, broader evidence,
incremental revisions, review queues, and storage/search-quality measurement.
Fallout 3, Fallout 4, Fallout 76, television, and remaining works follow only
after their preceding acceptance gates.
