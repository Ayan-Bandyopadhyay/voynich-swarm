"""Parse an IVTFF transliteration (ZL by default) into pages, lines and words.

Conventions (documented so that every choice is a pinned, named option):
  [a:b]     alternative readings: the first is taken (ZL lists its preferred reading first)
  {..}      ligature braces: removed, the glyphs inside are kept; a ' inside is dropped
  @nnn;     a rare glyph: becomes '*' (a word holding it is 'uncertain')
  ?         an unreadable glyph: kept as '?' (the word is 'uncertain')
  .         a word space
  ,         an uncertain space: a word space when uncertain_space='split' (default), else joined
  <->, <~>  a break around a drawing: a word space
  <%> <$>   paragraph start / end
  <!..>     comments: removed
  #=IVTFF v101  glyph case is significant; other alphabets retain existing lowercase handling
"""
import re
from dataclasses import dataclass, field
from . import path

SECTIONS = {
    "H": "herbal", "A": "astronomical", "Z": "zodiac", "B": "biological",
    "C": "cosmological", "P": "pharmaceutical", "S": "recipes", "T": "text-only",
}

PAGE_RE = re.compile(r"^<(f\d+[rv]\d*)>\s*<!(.*)>")
LINE_RE = re.compile(r"^<(f\d+[rv]\d*)\.(\d+),([@+*=&~\-])(\w)(\w*)>\s*(.*)$")


@dataclass
class Line:
    id: str
    page: str
    n: int
    unit: str          # P paragraph, L label, C circle, R radial
    subtype: str
    words: list        # EVA strings
    para_start: bool
    para_end: bool


@dataclass
class Page:
    id: str
    order: int
    meta: dict
    lines: list = field(default_factory=list)

    @property
    def section(self):
        return self.meta.get("I")

    @property
    def language(self):
        return self.meta.get("L")

    @property
    def hand(self):
        return self.meta.get("H")

    def words(self, units=None):
        out = []
        for ln in self.lines:
            if units is None or ln.unit in units:
                out.extend(ln.words)
        return out


def clean_text(s, uncertain_space="split", *, preserve_case=False):
    para_start = "<%>" in s
    para_end = "<$>" in s
    s = re.sub(r"<![^>]*>", "", s)
    s = s.replace("<%>", "").replace("<$>", "")
    s = re.sub(r"<[-~]>", ".", s)
    s = re.sub(r"<@[^>]*>", "", s)
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"\[([^:\]]*)(:[^\]]*)?\]", r"\1", s)
    s = re.sub(r"@\d+;", "*", s)
    s = s.replace("{", "").replace("}", "").replace("'", "")
    if not preserve_case:
        s = s.lower()
    s = s.replace(",", "." if uncertain_space == "split" else "")
    words = [w for w in re.split(r"[.\s]+", s) if w]
    return words, para_start, para_end


def parse(fn=None, uncertain_space="split"):
    fn = fn or path("data", "raw", "ZL3b-n.txt")
    pages, order = {}, 0
    preserve_case = False
    for line_number, raw in enumerate(open(fn, encoding="utf-8", errors="strict")):
        raw = raw.rstrip("\n")
        if line_number == 0:
            preserve_case = raw.startswith("#=IVTFF v101 ")
        if raw.startswith("#") or not raw.strip():
            continue
        m = PAGE_RE.match(raw)
        if m:
            meta = dict(re.findall(r"\$(\w)=(\w+)", m.group(2)))
            pages[m.group(1)] = Page(m.group(1), order, meta)
            order += 1
            continue
        m = LINE_RE.match(raw)
        if not m:
            continue
        pid, n, _pos, unit, sub, text = m.groups()
        words, ps, pe = clean_text(text, uncertain_space, preserve_case=preserve_case)
        pages[pid].lines.append(Line(f"{pid}.{n}", pid, int(n), unit, sub, words, ps, pe))
    return [pages[k] for k in sorted(pages, key=lambda k: pages[k].order)]


def uncertain(word):
    return "?" in word or "*" in word


# ---- glyph segmentation (an L1 question, so every choice is named and pinned) ----

SEGMENTATIONS = {
    # single EVA characters
    "eva-raw": [],
    # benches and pedestalled gallows as single glyphs: the common default
    "eva-basic": ["cth", "ckh", "cph", "cfh", "ch", "sh"],
    # also treat the i-runs and their finals as units
    "eva-iin": ["cth", "ckh", "cph", "cfh", "ch", "sh", "iiin", "iin", "in", "iiir", "iir", "ir", "ee"],
}


def segment(word, scheme="eva-basic"):
    units = sorted(SEGMENTATIONS[scheme], key=len, reverse=True)
    out, i = [], 0
    while i < len(word):
        for u in units:
            if word.startswith(u, i):
                out.append(u)
                i += len(u)
                break
        else:
            out.append(word[i])
            i += 1
    return out
