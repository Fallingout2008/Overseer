# OVERSEER

OVERSEER is an unofficial, non-commercial, offline terminal knowledge engine
for Fallout lore. It stores concise structured records, relationships, timeline
events, and revision-level provenance in SQLite. It is not a wiki mirror, a
terminal emulator, or an AI chatbot.

Phase 1 is a deliberately small Fallout: New Vegas vertical slice. The included
manifest describes 29 representative entities across the base game and all four
story DLCs. On 2026-09-16 the final policy review found that the Independent
Fallout Wiki's wildcard robots rules disallow `/api.php`; live acquisition is
therefore blocked by design pending operator clarification or another permitted
source path. It does not download article bodies or images.

## Requirements and quick start

- Python 3.11 or newer
- SQLite with FTS5 (included in normal current Python/SQLite builds)
- Network access only for `probe`, `import-sample`, and `update --check`

From a checkout:

```sh
./overseer init
# Currently fails closed at the source-policy gate:
./overseer import-sample
./overseer search house
./overseer open "Robert House"
./overseer related house
./overseer sources house
./overseer evidence house
./overseer timeline 2281
./overseer validate
```

After `import-sample`, search, dossiers, timeline, relationships, evidence,
statistics, and validation are fully offline. Set `NO_COLOR=1` or pass
`--no-color` for plain output. Output is automatically plain when redirected.

Optional isolated installation is supported by the standard `pyproject.toml`:

```sh
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/overseer help
```

No third-party runtime dependency, root access, daemon, account, telemetry, or
LLM is required. This host's Python lacks the optional `pip` module, so Phase 1
was verified through the checkout launcher.

## Commands

`search`, `open`, `person`, `location`, `vault`, `faction`, `event`, `timeline`,
`related`, `sources`, `evidence`, `random`, `stats`, `validate`, and
`update --check` implement the Phase 1 interface. Running `./overseer` in an
interactive terminal opens a small command loop; when piped, it prints help.

## Data and legal boundary

Original OVERSEER application code and original project documentation use the
MIT license in [LICENSE-CODE](LICENSE-CODE). Imported/source-derived lore data
is legally separate and is not relicensed under MIT. Read
[DATA-LICENSE.md](DATA-LICENSE.md),
[ATTRIBUTION.md](ATTRIBUTION.md), and [DISCLAIMER.md](DISCLAIMER.md) before
redistributing a built database. Generated databases, cache responses, and live
probe reports are intentionally excluded from Git.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/SOURCES_AND_PROVENANCE.md](docs/SOURCES_AND_PROVENANCE.md), and
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Phase 2 (full New Vegas discovery
and import) is intentionally not started.
