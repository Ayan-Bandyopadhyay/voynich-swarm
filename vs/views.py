"""How a key reads the manuscript: transliteration, reading order and the role of spaces.

A key may declare
  "transliteration": "zl" | "it" | "rf" | "gc"      (gc is Claston's v101 alphabet; use segmentation "eva-raw")
  "reading_order":   "normal" | "glyphs_reversed" | "words_reversed"
  "spaces":          "word_breaks" (default) | "ignored"    (each line read as one glyph stream; the
                     key's map may output spaces itself: Schwartz 2026 left this case untested)
                     EXPERIMENTAL: the kill tests handle it; criterion (a) recovers such lines with a
                     line-level, space-aware preimage code (judge.line_preimage_bits), proven on a
                     positive control in tests/test_line_preimage.py.
  "plaintext":       "words" (default) | "respaced"   (the decoded letters run on without the
                     plaintext's spaces and the judge cuts them into words itself: vs/respace.py.
                     Required by the letter-words family, and only that family may use it)
The view is applied to training and evaluation pages alike, before any scoring.
"""
from .ivtff import Page, Line
from . import ivtff

OPTIONS = {"reading_order": ("normal", "glyphs_reversed", "words_reversed"), "spaces": ("word_breaks", "ignored")}


def check(sub):
    for k, allowed in OPTIONS.items():
        if sub.get(k, allowed[0]) not in allowed:
            raise SystemExit(f"{k} must be one of {allowed}")
    respaced = sub.get("plaintext", "words")
    if respaced not in ("words", "respaced"):
        raise SystemExit("plaintext must be one of ('words', 'respaced')")
    if (sub.get("family") == "letter-words") != (respaced == "respaced"):
        raise SystemExit('the letter-words family reads with "plaintext": "respaced", and no other family does')
    if sub.get("family") == "letter-words":
        key = sub.get("key")
        tables = [key.get(k) for k in ("prefix", "suffix")] if isinstance(key, dict) else [None]
        if not all(isinstance(t, dict) and all(isinstance(a, str) and a and isinstance(b, str) for a, b in t.items())
                   for t in tables):
            raise SystemExit('a letter-words key is {"prefix": {glyphs: letters}, "suffix": {glyphs: letters}}')
        if sub.get("spaces", "word_breaks") != "word_breaks" or sub.get("reading_order", "normal") == "glyphs_reversed":
            raise SystemExit("letter-words reads whole words in their written form (spaces word_breaks; glyphs not reversed)")


def apply(pages, sub):
    order = sub.get("reading_order", "normal")
    spaces = sub.get("spaces", "word_breaks")
    if order == "normal" and spaces == "word_breaks":
        return pages
    seg = lambda w: ivtff.segment(w, sub.get("segmentation", "eva-basic"))
    out = []
    for p in pages:
        q = Page(p.id, p.order, dict(p.meta))
        for ln in p.lines:
            ws = list(ln.words)
            if order == "glyphs_reversed":
                ws = ["".join(reversed(seg(w))) for w in ws]
            elif order == "words_reversed":
                ws = ws[::-1]
            if spaces == "ignored" and ws:
                ws = ["".join(ws)]
            q.lines.append(Line(ln.id, ln.page, ln.n, ln.unit, ln.subtype, ws, ln.para_start, ln.para_end))
        out.append(q)
    return out
