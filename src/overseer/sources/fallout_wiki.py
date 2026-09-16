"""Independent Fallout Wiki MediaWiki adapter."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from overseer.errors import SourcePolicyError, SourceResponseError
from overseer.http import PoliteHttpClient
from overseer.sources.base import SourcePage


class FalloutWikiAdapter:
    name = "independent-fallout-wiki"
    api_url = "https://fallout.wiki/api.php"
    wiki_base = "https://fallout.wiki/wiki/"
    accepted_license_markers = ("creative commons attribution-sharealike", "cc by-sa")

    def __init__(self, client: PoliteHttpClient) -> None:
        self.client = client
        self.rights_info: dict[str, Any] | None = None

    def _api(self, **params: str) -> dict[str, Any]:
        common = {"action": "query", "format": "json", "formatversion": "2"}
        common.update(params)
        data = self.client.get(self.api_url, common).json()
        if "error" in data:
            raise SourceResponseError(f"MediaWiki API error: {data['error']}")
        return data

    @staticmethod
    def robots_disallows_api(robots_text: str) -> bool:
        """Return whether the wildcard robots group disallows the API path."""
        applies = False
        for raw_line in robots_text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field, value = (part.strip() for part in line.split(":", 1))
            field = field.lower()
            if field == "user-agent":
                applies = value == "*"
            elif applies and field == "disallow" and value.rstrip("/") == "/api.php":
                return True
        return False

    def probe(self) -> dict[str, Any]:
        robots_result = self.client.get(
            "https://fallout.wiki/robots.txt",
            expected_content_types=("text/plain",),
        )
        robots_text = robots_result.body.decode("utf-8", errors="replace")
        robots = {
            "url": robots_result.url,
            "status": robots_result.status,
            "sha256": hashlib.sha256(robots_result.body).hexdigest(),
            "text": robots_text,
            "api_disallowed_for_wildcard": self.robots_disallows_api(robots_text),
        }
        if robots["api_disallowed_for_wildcard"]:
            return {
                "adapter": self.name,
                "retrieved_at": datetime.now(UTC).isoformat(),
                "api_url": self.api_url,
                "policy_status": "blocked",
                "policy_reason": "robots.txt disallows /api.php for User-agent: *",
                "robots": robots,
            }

        site = self._api(meta="siteinfo", siprop="general|rightsinfo|namespaces|statistics")
        query = site.get("query", {})
        rights = query.get("rightsinfo", {})
        license_text = str(rights.get("text", "")).lower()
        if not any(marker in license_text for marker in self.accepted_license_markers):
            raise SourcePolicyError(f"Unclear or unsupported source license: {rights!r}")

        harmless = self._api(
            prop="info|revisions|categories",
            titles="Fallout: New Vegas",
            rvprop="ids|timestamp",
            cllimit="5",
        )
        category = self._api(list="categorymembers", cmtitle="Category:Fallout: New Vegas", cmlimit="5")
        export_info = self._api(meta="siteinfo", siprop="general")
        pages = harmless.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            raise SourceResponseError("Harmless page probe did not return an existing page")
        if "categorymembers" not in category.get("query", {}):
            raise SourceResponseError("Category discovery probe failed")

        self.rights_info = rights
        return {
            "adapter": self.name,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "api_url": self.api_url,
            "policy_status": "allowed",
            "siteinfo": query,
            "harmless_page": harmless,
            "category_discovery": category,
            "robots": robots,
            "export": {
                "special_export_url": "https://fallout.wiki/wiki/Special:Export",
                "api_export_parameter_supported_by_mediawiki": True,
                "bulk_dump_discovered": False,
                "note": "No official bulk dump endpoint established by this bounded probe.",
                "site_general_confirmation": export_info.get("query", {}).get("general", {}),
            },
        }

    def fetch_pages(self, titles: list[str]) -> dict[str, SourcePage]:
        if self.rights_info is None:
            raise SourcePolicyError("Source must pass the capability/license probe before acquisition")
        result: dict[str, SourcePage] = {}
        for offset in range(0, len(titles), 20):
            requested = titles[offset : offset + 20]
            data = self._api(
                prop="info|revisions|categories",
                titles="|".join(requested),
                redirects="1",
                inprop="url",
                rvprop="ids|timestamp|sha1",
                cllimit="max",
            )
            query = data.get("query", {})
            normalized = {item["from"]: item["to"] for item in query.get("normalized", [])}
            redirects = {item["from"]: item["to"] for item in query.get("redirects", [])}
            pages_by_title = {page.get("title"): page for page in query.get("pages", [])}
            for title in requested:
                resolved = redirects.get(normalized.get(title, title), normalized.get(title, title))
                page = pages_by_title.get(resolved)
                if not page or page.get("missing"):
                    continue
                revisions = page.get("revisions", [])
                if not revisions:
                    continue
                revision = revisions[0]
                canonical = str(page["title"])
                result[title] = SourcePage(
                    title=title,
                    canonical_title=canonical,
                    page_id=int(page["pageid"]),
                    revision_id=int(revision["revid"]),
                    revision_timestamp=str(revision["timestamp"]),
                    url=str(page.get("fullurl") or f"{self.wiki_base}{quote(canonical.replace(' ', '_'))}"),
                    categories=tuple(item["title"] for item in page.get("categories", [])),
                    metadata={"page": page, "requested_title": title},
                )
        return result
