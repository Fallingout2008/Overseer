from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from overseer.errors import SourceResponseError
from overseer.http import PoliteHttpClient


class HttpClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.client = PoliteHttpClient(Path(self.temporary.name), "test-agent", retries=0)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_rejects_non_https_urls(self) -> None:
        with self.assertRaises(SourceResponseError):
            self.client.get("http://example.invalid/api")

    def test_cache_key_is_deterministic(self) -> None:
        self.assertEqual(
            self.client._cache_key("https://example.invalid"),
            self.client._cache_key("https://example.invalid"),
        )
        self.assertNotEqual(
            self.client._cache_key("https://example.invalid/a"),
            self.client._cache_key("https://example.invalid/b"),
        )

    def test_corrupt_cache_fails_closed(self) -> None:
        url = "https://example.invalid/api"
        self.client._cache_file(url).write_text("not json", encoding="utf-8")
        with self.assertRaises(SourceResponseError):
            self.client.get(url)


if __name__ == "__main__":
    unittest.main()
