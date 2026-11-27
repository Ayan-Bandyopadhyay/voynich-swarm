"""Download every pinned input and refuse any whose sha256 does not match."""
import hashlib
import http.client
import json
import os
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request

from . import path


RETRY_HTTP_STATUS = {408, 429, 500, 502, 503, 504}


def sha256(fn):
    h = hashlib.sha256()
    with open(fn, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def entries():
    pins = json.load(open(path("pins", "sources.json")))
    return pins["sources"] + pins["reference_corpora"]


def _download_pin(entry, fn, verbose):
    request = urllib.request.Request(entry["url"], headers={"User-Agent": "voynichswarm-fetch/1"})
    for delay in (1, 4, None):
        temporary = None
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with tempfile.NamedTemporaryFile(dir=os.path.dirname(fn), suffix=".part", delete=False) as out:
                    temporary = out.name
                    out.write(response.read())
            digest = sha256(temporary)
            if digest == entry["sha256"]:
                os.replace(temporary, fn)
                temporary = None
            return digest
        except (
            urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead,
            ssl.SSLEOFError, ssl.SSLZeroReturnError,
        ) as error:
            if delay is None or (isinstance(error, urllib.error.HTTPError) and error.code not in RETRY_HTTP_STATUS):
                raise
            if isinstance(error, urllib.error.HTTPError):
                error.close()
            if verbose:
                print(f"retry {entry['id']} in {delay}s: {error}", file=sys.stderr, flush=True)
        finally:
            if temporary is not None:
                os.unlink(temporary)
        time.sleep(delay)


def fetch(verbose=True):
    bad = 0
    for e in entries():
        fn = path(e["file"])
        got = sha256(fn) if os.path.exists(fn) else None
        if got != e["sha256"]:
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            got = _download_pin(e, fn, verbose)
        ok = got == e["sha256"]
        bad += not ok
        if verbose:
            print(("ok  " if ok else "BAD ") + e["id"], got[:16], e["file"])
    if bad:
        sys.exit(f"{bad} input(s) failed checksum: refusing to continue")


def verify():
    for e in entries():
        fn = path(e["file"])
        if not os.path.exists(fn) or sha256(fn) != e["sha256"]:
            raise SystemExit(f"pinned input {e['id']} missing or altered: run `python3 -m vs fetch`")
