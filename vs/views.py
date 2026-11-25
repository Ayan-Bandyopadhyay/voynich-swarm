"""How a key reads the manuscript: transliteration, reading order and the role of spaces.

A key may declare
  "transliteration": "zl" | "it" | "rf" | "gc"      (gc is Claston's v101 alphabet; use segmentation "eva-raw")
  "reading_order":   "normal" | "glyphs_reversed" | "words_reversed"
  "spaces":          "word_breaks" (default) | "ignored"    (each line read as one glyph stream; the
                     key's map may output spaces itself: Schwartz 2026 left this case untested)
                     EXPERIMENTAL: the kill tests handle it, but criterion (a)'s code for recovering
                     the Voynich text is still word-based and over-charges whole-line tokens. A
                     line-level preimage code is an open J step.
The view is applied to training and evaluation pages alike, before any scoring.
"""
from .ivtff import Page, Line
from . import ivtff

OPTIONS = {"reading_order": ("normal", "glyphs_reversed", "words_reversed"), "spaces": ("word_breaks", "ignored")}


def check(sub):
    for k, allowed in OPTIONS.items():
        if sub.get(k, allowed[0]) not in allowed:
            raise SystemExit(f"{k} must be one of {allowed}")


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
