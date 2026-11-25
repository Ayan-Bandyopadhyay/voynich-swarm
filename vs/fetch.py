"""Download every pinned input and refuse any whose sha256 does not match."""
import hashlib, json, os, sys, urllib.request
from . import path


def sha256(fn):
    h = hashlib.sha256()
    with open(fn, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def entries():
    pins = json.load(open(path("pins", "sources.json")))
    return pins["sources"] + pins["reference_corpora"]


def fetch(verbose=True):
    bad = 0
    for e in entries():
        fn = path(e["file"])
        if not (os.path.exists(fn) and sha256(fn) == e["sha256"]):
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            req = urllib.request.Request(e["url"], headers={"User-Agent": "voynichswarm-fetch/1"})
            with urllib.request.urlopen(req, timeout=120) as r, open(fn + ".part", "wb") as out:
                out.write(r.read())
            os.replace(fn + ".part", fn)
        got = sha256(fn)
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
