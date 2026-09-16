# Phase 1 adversarial review

## Findings addressed

- **Single-game coupling:** entities and works are independent with many-to-many
  appearances; shared records need not be copied.
- **Canon collapse:** claims, relationships, and events retain explicit
  classifications and sources rather than one entity-wide Boolean truth.
- **Update data loss:** revisions are distinct rows and stable source/page keys
  support append-style history.
- **Untraceable claims:** all claims and dossier claim lines link to revisions.
- **Replay/interruption:** uniqueness constraints make imports idempotent;
  transactions roll back record mutations and run rows record failures.
- **Layout fragility:** the sample adapter consumes MediaWiki API metadata, not
  rendered HTML selectors.
- **Unsafe content:** HTTPS/content type/size/status controls are enforced and
  remote material is never executed.
- **License contamination:** code, generated data, attribution, and licensing
  documents are separated; generated archives are ignored by Git.
- **Repository/cache growth:** caches and DBs are ignored and separately sized.
- **Runtime AI dependency:** no AI/LLM code or dependency exists.

## Residual risks / Phase 2 gates

- **Blocking:** `robots.txt` disallows `/api.php` for wildcard agents. The gate
  now evaluates this before API access. No further source acquisition is
  permitted without operator clarification or a separately reviewed, permitted
  official dump/export path. See `SOURCE_POLICY_BLOCKER.md`.
- The live siteinfo rights URL is malformed. Current rights text is clear, but a
  public data release needs another license-policy review.
- No official bulk dump was established. Do not scale via repeated API calls
  until current dump options and operator guidance are checked.
- The Phase 1 facts are curated and page-level revision-backed. More granular
  excerpt/location evidence may be valuable before full-franchise scaling.
- FTS is manually rebuilt at the end of each import; Phase 2 should benchmark
  incremental versus rebuild behavior at realistic catalog size.
- Cache pruning is documented but not exposed as a command, avoiding accidental
  deletion during this conservative first phase.

No material Phase 1 defect requiring a schema rewrite was found.
