# Sources, provenance, and imports

## Phase 1 policy gate

Before importing named sample records, the adapter obtains MediaWiki siteinfo,
rights information, namespace/statistics data, one harmless page and revision,
a five-item category sample, and `robots.txt`. A successful response is saved
verbatim as a timestamped JSON probe report under `data/manifests/` (ignored by
Git because it is generated state).

On 2026-09-16 the live API reported `Creative Commons
Attribution-ShareAlike License 4.0`. This supersedes the build plan's historical
Wikidata observation of 3.0 for current acquisition. The API's rights URL was
malformed, so redistribution remains a review item even though the returned
license text is clear. The final `robots.txt` review found an explicit
`User-agent: *` disallow for `/api.php`. Acquisition was stopped, and the
adapter now checks this rule before any API operation and fails closed. No
Fandom endpoint is implemented. The exact resolution requirements are recorded
in [SOURCE_POLICY_BLOCKER.md](SOURCE_POLICY_BLOCKER.md).

The pre-block bounded probe established that MediaWiki `Special:Export`/API export
functionality exists conceptually, but did not establish a supported official
bulk-dump endpoint. Phase 2 must investigate current official dump availability
and community policy before any bulk import; it must prefer a permitted dump if
one exists.

## Record provenance

Every imported entity links to a `source_revision` containing source adapter,
page ID, canonical title and URL, revision ID and timestamp, retrieval time,
metadata hash, exact raw metadata, and the license response. Every claim,
relationship, and timeline event also links to the revision used for it.

The Phase 1 manifest contains concise editorial summaries and facts rather than
article prose. Unsupported or ambiguous future transformations must be retained
as source material and placed in `review_flags`, not silently asserted.

## Updating and cache handling

`./overseer update --check` repeats only the capability/policy probe. It
currently reports the policy block. Phase 1
does not automatically mutate records during update checks. Re-running
`import-sample` is safe and idempotent; a changed source revision creates a new
revision record. The HTTP cache is disposable and excluded from version
control. It can be removed manually while OVERSEER is not running; deleting it
does not affect offline archive use.
