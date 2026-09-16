"""Interfaces shared by source adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class SourcePage:
    title: str
    canonical_title: str
    page_id: int
    revision_id: int
    revision_timestamp: str
    url: str
    categories: tuple[str, ...]
    metadata: dict[str, Any]


class SourceAdapter(Protocol):
    name: str

    def probe(self) -> dict[str, Any]: ...

    def fetch_pages(self, titles: list[str]) -> dict[str, SourcePage]: ...

