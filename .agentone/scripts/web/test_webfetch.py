import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import webfetch
from webfetch import webFetch


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self) -> None:
        return None


def _fetch(html: str, **kwargs):
    with patch.object(webfetch.httpx, "get", return_value=_FakeResponse(html)):
        return webFetch(None, "https://example.com/docs/page", **kwargs)


class TestWebFetch(unittest.TestCase):
    """Tests for the webFetch tool."""

    def test_webfetch_no_url(self) -> None:
        """webFetch with an empty URL returns an error."""
        success, result = webFetch(None, '')
        self.assertFalse(success)
        self.assertIn('not provided', result['message'])

    def test_webfetch_basic(self) -> None:
        """webFetch fetches a URL and returns content."""
        success, result = webFetch(None, 'https://httpbin.org/html', format='text')
        self.assertTrue(success)
        self.assertIn('url', result)
        self.assertIn('content', result)

    def test_markdown_strips_scripts_styles_and_inline_images(self) -> None:
        """Page chrome and base64 images never reach the returned markdown."""
        html = (
            "<html><head><script>var tracking = 1;</script>"
            "<style>.x{color:red}</style></head><body><h1>Real docs</h1>"
            "<template id=\"mint-config\">{\"docsConfig\": {\"name\": \"bloat\"}}</template>"
            "<img alt=\"Chart\" src=\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAA+gAAAPo\">"
            "<p>Useful text.</p></body></html>"
        )
        success, result = _fetch(html)
        self.assertTrue(success)
        content = result['content']
        self.assertIn('Real docs', content)
        self.assertIn('Useful text', content)
        self.assertNotIn('docsConfig', content)
        self.assertNotIn('tracking', content)
        self.assertNotIn('data:image', content)
        self.assertIn('[Chart omitted]', content)
        self.assertFalse(result['truncated'])

    def test_large_page_is_truncated_and_cached(self) -> None:
        """A page over the limit is cached in the session folder, with a hint."""
        html = "<p>" + "x" * 50_000 + "</p>"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(webfetch, "_session_cache_dir", return_value=Path(tmp)):
                success, result = _fetch(html)
            self.assertTrue(success)
            self.assertTrue(result['truncated'])
            self.assertEqual(len(result['content']), webfetch.MAX_CONTENT_CHARS)
            self.assertEqual(result['original_chars'], len(result['content']) + 50_000 - webfetch.MAX_CONTENT_CHARS)
            cached = Path(result['full_content_path'])
            self.assertTrue(cached.exists())
            self.assertIn("x" * 50_000, cached.read_text(encoding="utf-8"))
            self.assertIn(str(cached), result['hint'])
            self.assertEqual(cached.parent.name, "webfetch")

    def test_session_cache_dir_from_env(self) -> None:
        """Script-mode callers can point at their session dir via env var."""
        with patch.dict(os.environ, {"AGENTONE_SESSION_DIR": "/tmp/session-1"}):
            self.assertEqual(
                webfetch._session_cache_dir(None), Path("/tmp/session-1/cache")
            )

    def test_large_page_without_session_still_truncates(self) -> None:
        """Outside an agent session there is no cache path, but no crash."""
        html = "<p>" + "y" * 50_000 + "</p>"
        with patch.object(webfetch, "_session_cache_dir", return_value=None):
            success, result = _fetch(html)
        self.assertTrue(success)
        self.assertTrue(result['truncated'])
        self.assertNotIn('full_content_path', result)
        self.assertIn('no session cache', result['hint'])


if __name__ == '__main__':
    unittest.main()
