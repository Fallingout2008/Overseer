# Architecture

## Data flow

```text
named Phase 1 manifest
        +
live source policy/revision probe
        ↓
source adapter → bounded cached HTTPS client
        ↓
normalized entities + claims + provenance
        ↓
SQLite 3 / FTS5
        ↓
deterministic dossiers + terminal CLI
```

`overseer.http` allows only explicit HTTPS GET requests, requires a descriptive
User-Agent, bounds response size, validates content type, serializes requests,
honors numeric `Retry-After`, retries with backoff, and stops after repeated
403/429/503 responses. Cache keys are SHA-256 hashes of canonicalized URLs.
Downloaded material is parsed as data and never executed.

`SourceAdapter` separates acquisition from normalization. The first adapter
targets the Independent Fallout Wiki Action API. It will not fetch entity pages
until the live capability/license probe passes.

Migration 001 defines entities, aliases, entity types, works, appearances,
claims, relationships, timeline events, sources and revisions, entity/source
links, tags, dossiers and evidence links, ingestion runs, review flags, schema
migrations, and an FTS5 index. Claims and relationships point directly to the
source revision supporting them. Canon status is an enumerated classification,
not a Boolean.

The importer is transactional and idempotent. Unique keys prevent replayed
claims, relationships, appearances, and timeline events. Ingestion runs record
complete, blocked, or failed outcomes. Generated dossiers are rebuilt only
from the local structured record and link all rendered claims through
`dossier_claims`.

## Scaling assessment

The schema keys entities independently of works and represents appearances as a
many-to-many relation, so cross-game people, factions, and events need not be
duplicated. Source revisions are append-compatible, which supports later
incremental Fallout 76 and television updates without destroying history.
Player-choice and conflicting outcomes can remain separate claims with distinct
sources and canon statuses.

Phase 2 still needs category cataloging, redirect history, revision-change
planning, higher-volume cache management, and a human review interface. Those
are additions to the existing model rather than a schema rewrite.

