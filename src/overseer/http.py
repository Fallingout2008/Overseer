"""Polite, bounded, cached HTTP client using only the standard library."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from overseer.errors import SourceResponseError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HttpResult:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    from_cache: bool

    def json(self) -> dict[str, Any]:
        try:
            value = json.loads(self.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SourceResponseError(f"Invalid JSON from {self.url}") from exc
        if not isinstance(value, dict):
            raise SourceResponseError(f"Expected JSON object from {self.url}")
        return value


class PoliteHttpClient:
    """GET-only client with cache, rate limiting, retries, and response bounds."""

    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        *,
        timeout: float = 20.0,
        min_interval: float = 1.0,
        max_bytes: int = 5_000_000,
        retries: int = 3,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("A descriptive User-Agent is required")
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self.max_bytes = max_bytes
        self.retries = retries
        self._last_request = 0.0
        self._consecutive_service_failures = 0

    @staticmethod
    def _cache_key(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _cache_file(self, url: str) -> Path:
        return self.cache_dir / f"{self._cache_key(url)}.json"

    def _read_cache(self, url: str) -> HttpResult | None:
        path = self._cache_file(url)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return HttpResult(
                url=url,
                status=int(payload["status"]),
                headers=dict(payload["headers"]),
                body=bytes.fromhex(payload["body_hex"]),
                from_cache=True,
            )
        except FileNotFoundError:
            return None
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SourceResponseError(f"Corrupt cache entry: {path}") from exc

    def _write_cache(self, result: HttpResult) -> None:
        path = self._cache_file(result.url)
        payload = {
            "url": result.url,
            "status": result.status,
            "headers": result.headers,
            "body_hex": result.body.hex(),
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _headers(message: Message) -> dict[str, str]:
        return {key.lower(): value for key, value in message.items()}

    def get(
        self,
        base_url: str,
        params: dict[str, str] | None = None,
        *,
        use_cache: bool = True,
        expected_content_types: tuple[str, ...] = ("application/json",),
    ) -> HttpResult:
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise SourceResponseError("Only explicit HTTPS source URLs are allowed")
        url = base_url if not params else f"{base_url}?{urlencode(sorted(params.items()))}"
        if use_cache and (cached := self._read_cache(url)) is not None:
            return cached

        for attempt in range(self.retries + 1):
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            request = Request(url, headers={"User-Agent": self.user_agent, "Accept": ", ".join(expected_content_types)})
            try:
                self._last_request = time.monotonic()
                with urlopen(request, timeout=self.timeout) as response:
                    headers = self._headers(response.headers)
                    content_type = headers.get("content-type", "").lower()
                    if expected_content_types and not any(item in content_type for item in expected_content_types):
                        raise SourceResponseError(f"Unexpected content type {content_type!r} from {url}")
                    declared = headers.get("content-length")
                    if declared and int(declared) > self.max_bytes:
                        raise SourceResponseError(f"Response exceeds {self.max_bytes} byte limit")
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise SourceResponseError(f"Response exceeds {self.max_bytes} byte limit")
                    result = HttpResult(url, response.status, headers, body, False)
                    self._consecutive_service_failures = 0
                    if use_cache:
                        self._write_cache(result)
                    return result
            except HTTPError as exc:
                if exc.code not in {403, 429, 503}:
                    raise SourceResponseError(f"HTTP {exc.code} from {url}") from exc
                self._consecutive_service_failures += 1
                if self._consecutive_service_failures >= 3:
                    raise SourceResponseError(f"Stopped after repeated HTTP {exc.code} responses") from exc
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            except URLError as exc:
                delay = 2**attempt
                if attempt >= self.retries:
                    raise SourceResponseError(f"Network failure for {url}: {exc.reason}") from exc
            if attempt >= self.retries:
                break
            time.sleep(delay + random.uniform(0.0, 0.25))
        raise SourceResponseError(f"Request failed after retries: {url}")

