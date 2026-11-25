"""Reference corpora of candidate plaintext languages: cleaning, normalization, splits.

Each language's pinned texts are cleaned (Gutenberg header and footer removed), normalized
to a small alphabet, and cut into blocks of about 400 characters. Blocks are dealt by index mod 10: 4 goes to the
calibration split (sets the judge's thresholds), 9 to the control split (plaintext for
positive controls), the rest train the language model. The model never sees either.
"""
import json, re, unicodedata
from functools import lru_cache
from . import path

LATIN_LIKE = {"latin", "italian", "german", "french", "spanish", "english", "czech", "catalan"}
HEB_FINALS = str.maketrans({"ך": "כ", "ם": "מ", "ן": "נ", "ף": "פ", "ץ": "צ"})
SPECIAL = {"ß": "ss", "æ": "ae", "œ": "oe", "þ": "th", "ð": "d", "ȝ": "y", "ſ": "s", "ø": "o", "ł": "l"}


KNOWN = {"latin", "italian", "german", "french", "spanish", "english", "czech", "catalan", "hebrew"}


def normalize(text, lang):
    t = text.lower()
    if lang not in KNOWN:
        # any other script (added by an agent): letters only, diacritics removed, one space
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
        t = "".join(c if unicodedata.category(c).startswith("L") else " " for c in t)
        return re.sub(r" +", " ", t).strip()
    if lang == "hebrew":
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
        t = t.translate(HEB_FINALS)
        t = re.sub(r"[^א-ת]+", " ", t)
    else:
        for a, b in SPECIAL.items():
            t = t.replace(a, b)
        t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
        t = re.sub(r"[^a-z]+", " ", t)
        if lang == "latin":
            t = t.replace("j", "i").replace("v", "u")
    return re.sub(r" +", " ", t).strip()


def alphabet(lang):
    if lang not in KNOWN:
        from collections import Counter
        c = Counter(ch for b in blocks(lang) for ch in b if ch != " ")
        tot = sum(c.values()) or 1
        return sorted(ch for ch, n in c.items() if n / tot >= 0.0005)
    return _alphabet_known(lang)


def _alphabet_known(lang):
    if lang == "hebrew":
        return [chr(c) for c in range(0x05D0, 0x05EB) if chr(c) not in "ךםןףץ"]
    a = [chr(c) for c in range(ord("a"), ord("z") + 1)]
    if lang == "latin":
        a = [c for c in a if c not in "jv"]
    return a


def strip_gutenberg(raw):
    s = raw
    m = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*\n", s)
    if m:
        s = s[m.end():]
    m = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", s)
    if m:
        s = s[: m.start()]
    m = re.search(r"End of (the )?Project Gutenberg", s, re.I)
    if m:
        s = s[: m.start()]
    return s


def pins():
    return json.load(open(path("pins", "sources.json")))["reference_corpora"]


def languages():
    return sorted({e["lang"] for e in pins()})


@lru_cache(maxsize=None)
def blocks(lang):
    out = []
    for e in pins():
        if e["lang"] != lang or e.get("skip_reason"):
            continue
        raw = open(path(e["file"]), encoding=e.get("encoding", "utf-8"), errors="replace").read()
        text = normalize(strip_gutenberg(raw), lang)
        words = text.split()
        cur, n = [], 0
        for w in words:
            cur.append(w)
            n += len(w) + 1
            if n >= 400:
                out.append(" ".join(cur))
                cur, n = [], 0
    return out


def train_text(lang):
    return [b for i, b in enumerate(blocks(lang)) if i % 10 not in (4, 9)]


def calib_text(lang):
    return [b for i, b in enumerate(blocks(lang)) if i % 10 == 4]


def control_text(lang):
    return [b for i, b in enumerate(blocks(lang)) if i % 10 == 9]


@lru_cache(maxsize=None)
def blocks_of(corpus_id):
    """Blocks of one pinned text (a genre control)."""
    e = next(x for x in pins() if x["id"] == corpus_id)
    raw = open(path(e["file"]), encoding=e.get("encoding", "utf-8"), errors="replace").read()
    words = normalize(strip_gutenberg(raw), e["lang"]).split()
    out, cur, n = [], [], 0
    for w in words:
        cur.append(w)
        n += len(w) + 1
        if n >= 400:
            out.append(" ".join(cur))
            cur, n = [], 0
    return out
