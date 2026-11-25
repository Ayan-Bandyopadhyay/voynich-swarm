"""Commit-reveal held-out split.

Before any work, a 256-bit seed is drawn at random. Within each section ($I in the ZL
page headers), pages are ranked by sha256(seed + ':' + page id) and the first
round_half_up(0.15 * n) are held out. Only the commitment is published:

    commitment = sha256("voynichsolved/heldout/S1\\n" + seed + "\\n" + ",".join(sorted(heldout)))

At the reveal the seed is published; anyone can recompute the list with
`python3 -m vs split --verify <seed>` and check it against the commitment. Held-out
pages are used only to score frozen submissions. The seed lives in secrets/heldout_seed.json,
which is never committed.
"""
import hashlib, json, math, os, secrets as _secrets
from . import path, SEASON, ivtff
from .fetch import sha256 as file_sha256

FRACTION = 0.15
COMMIT_FILE = path("heldout", "COMMITMENT.json")
SEED_FILE = path("secrets", "heldout_seed.json")


def k_for(n):
    return max(1, math.floor(FRACTION * n + 0.5))


def select(seed, pages):
    by_sec = {}
    for p in pages:
        by_sec.setdefault(p.section, []).append(p.id)
    held = []
    for sec in sorted(by_sec):
        ids = by_sec[sec]
        ranked = sorted(ids, key=lambda pid: hashlib.sha256(f"{seed}:{pid}".encode()).hexdigest())
        held += ranked[: k_for(len(ids))]
    return sorted(held)


def commitment(seed, held):
    tag = "voynichsolved" if SEASON == "S1" else "voynichswarm"
    msg = f"{tag}/heldout/{SEASON}\n{seed}\n" + ",".join(sorted(held))
    return hashlib.sha256(msg.encode()).hexdigest()


def create():
    if os.path.exists(SEED_FILE) or os.path.exists(COMMIT_FILE):
        raise SystemExit("a held-out split already exists for this season; it is never redrawn")
    pages = ivtff.parse()
    seed = _secrets.token_hex(32)
    held = select(seed, pages)
    by_sec = {}
    for p in pages:
        by_sec.setdefault(p.section, []).append(p.id)
    os.makedirs(os.path.dirname(SEED_FILE), exist_ok=True)
    with open(SEED_FILE, "w") as f:
        json.dump({"season": SEASON, "seed": seed}, f)
    os.chmod(SEED_FILE, 0o600)
    pub = {
        "season": SEASON,
        "commitment_sha256": commitment(seed, held),
        "scheme": "sha256(\"voynichswarm/heldout/<season>\\n\" + seed + \"\\n\" + comma-joined sorted held-out page ids)",
        "selection": "within each $I section, pages ranked by sha256(seed:page), first round_half_up(0.15*n) held out",
        "transliteration_sha256": file_sha256(path("data", "raw", "ZL3b-n.txt")),
        "pages_total": len(pages),
        "heldout_per_section": {s: k_for(len(v)) for s, v in sorted(by_sec.items())},
        "heldout_total": len(held),
        "reveal": "at the end of the season, or earlier only if the judge's rules change",
    }
    with open(COMMIT_FILE, "w") as f:
        json.dump(pub, f, indent=2)
    return pub


def load_seed():
    if not os.path.exists(SEED_FILE):
        return None
    return json.load(open(SEED_FILE))["seed"]


def heldout_pages():
    """The held-out page ids, available only where the seed is (the scorer)."""
    seed = load_seed()
    if seed is None:
        return None
    held = select(seed, ivtff.parse())
    pub = json.load(open(COMMIT_FILE))
    if commitment(seed, held) != pub["commitment_sha256"]:
        raise SystemExit("seed does not match the published commitment")
    return set(held)


def verify(seed):
    held = select(seed, ivtff.parse())
    pub = json.load(open(COMMIT_FILE))
    ok = commitment(seed, held) == pub["commitment_sha256"]
    return ok, held
