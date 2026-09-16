# Unresolved source-policy and data-license blocker

**Status:** Phase 2 is paused at this gate. No additional lore acquisition or
later phase is authorized while it remains unresolved.

## Exact blocker

As observed on 2026-09-16, the Independent Fallout Wiki's live `robots.txt`
contains this wildcard rule:

```text
User-agent: *
Disallow: /api.php
```

OVERSEER's intended source adapter uses `https://fallout.wiki/api.php`.
Therefore, under the project's conservative acquisition rules, automated use of
that Action API is currently **disallowed or materially unclear**. A successful
HTTP/API response is evidence of technical availability, not permission. The
adapter now evaluates this rule before any API request and fails closed.

This block can be resolved only by one of the following:

1. Written or published clarification from an authorized Independent Fallout
   Wiki operator that OVERSEER's described, rate-limited Action API use is
   permitted despite the wildcard robots rule; or
2. Identification and review of an official dump/export mechanism whose access
   policy explicitly permits the intended acquisition and redistribution model.

Until then, do not run a new lore import, expand the existing sample, or begin
Phase 2. Do not substitute Fandom scraping.

## Separate data-license verification

Before the block was discovered, MediaWiki `siteinfo` returned the rights text
`Creative Commons Attribution-ShareAlike License 4.0`, but returned this malformed
rights URL:

```text
https://fallout.wiki/wiki/Https://fallout.uesp.net/wiki/FalloutWiki:General_Disclaimer
```

The text is a strong license signal, but the malformed link prevents the stored
metadata from serving as a clean authoritative license reference. Before any
source-derived lore database is distributed, verify the current authoritative
license page and record its exact attribution and share-alike obligations.

## What is not blocked

The original OVERSEER application code and original project documentation are
licensed under MIT. That decision does not apply to imported lore, source text,
source metadata, generated lore databases, or third-party contributions. The
existing `DATA-LICENSE.md` and `ATTRIBUTION.md` separation remains controlling.

Local development against synthetic fixtures, schema work, tests, and offline
inspection of the retained Phase 1 evidence database are not source acquisition.
Phase 2 nevertheless remains prohibited until explicit user authorization after
the source issue is resolved.
