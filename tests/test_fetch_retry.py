import hashlib
import io
import ssl
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError, URLError

from vs import fetch


class FetchRetryTests(unittest.TestCase):
    def setUp(self):
        scratch = self.enterContext(tempfile.TemporaryDirectory())
        self.target = Path(scratch) / "data" / "pin.txt"
        self.content = b"verified input\n"
        self.url = "https://example.invalid/pin.txt"
        self.enterContext(patch.object(fetch, "entries", return_value=[{
            "id": "test-pin",
            "file": "data/pin.txt",
            "url": self.url,
            "sha256": hashlib.sha256(self.content).hexdigest(),
        }]))
        self.enterContext(patch.object(fetch, "path", return_value=str(self.target)))

    def test_recovers_from_connection_and_read_failures(self):
        incomplete_response = io.BytesIO(b"partial")
        incomplete_response.read = Mock(side_effect=IncompleteRead(b"partial", 10))
        attempts = [URLError("connection reset"), incomplete_response, io.BytesIO(self.content)]

        with (
            patch("urllib.request.urlopen", side_effect=attempts) as urlopen,
            patch("vs.fetch.time.sleep") as sleep,
        ):
            fetch.fetch(verbose=False)
            self.assertEqual(self.target.read_bytes(), self.content)
            self.assertEqual(list(self.target.parent.iterdir()), [self.target])
            self.assertEqual(urlopen.call_count, 3)
            self.assertEqual(sleep.call_args_list, [call(1), call(4)])

            fetch.fetch(verbose=False)
            self.assertEqual(urlopen.call_count, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_retries_gateway_timeout_and_tls_eof(self):
        gateway_timeout = HTTPError(self.url, 504, "Gateway Timeout", None, io.BytesIO())
        interrupted_response = io.BytesIO()
        interrupted_response.read = Mock(side_effect=ssl.SSLEOFError("unexpected EOF"))
        attempts = [gateway_timeout, interrupted_response, io.BytesIO(self.content)]

        with (
            patch("urllib.request.urlopen", side_effect=attempts) as urlopen,
            patch("vs.fetch.time.sleep") as sleep,
        ):
            fetch.fetch(verbose=False)

        self.assertEqual(self.target.read_bytes(), self.content)
        self.assertEqual(urlopen.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1), call(4)])

    def test_permanent_http_error_is_not_retried(self):
        missing = HTTPError(self.url, 404, "Not Found", None, None)
        with (
            patch("urllib.request.urlopen", side_effect=missing) as urlopen,
            patch("vs.fetch.time.sleep") as sleep,
        ):
            with self.assertRaises(HTTPError) as failed:
                fetch.fetch(verbose=False)

        self.assertEqual(failed.exception.code, 404)
        urlopen.assert_called_once()
        sleep.assert_not_called()
        self.assertEqual(list(self.target.parent.glob("*")), [])

    def test_bad_checksum_preserves_original_file(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b"previous invalid input")
        with (
            patch("urllib.request.urlopen", return_value=io.BytesIO(b"different download")) as urlopen,
            patch("vs.fetch.time.sleep") as sleep,
        ):
            with self.assertRaisesRegex(SystemExit, "checksum"):
                fetch.fetch(verbose=False)

        self.assertEqual(self.target.read_bytes(), b"previous invalid input")
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])
        urlopen.assert_called_once()
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
