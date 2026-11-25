"""G track: historically plausible generators of meaningless (or enciphered) text.

Each generator is fit on the training pages only, then writes pages with exactly the shape
of the evaluation pages (same ids, sections, Currier labels, hands, line lengths, units),
so the L2 fact battery runs on them unchanged. A generator's score is how many facts
ESTABLISHED on the manuscript's held-out pages it also reproduces. Reproducing all of them
would itself be a result: it would show the facts need no language behind them.
"""
import random
from collections import Counter
from . import ivtff, refcorpus
from .ivtff import Page, Line


def _shape_like(eval_pages, word_source):
    out = []
    for p in eval_pages:
        q = Page(p.id, p.order, dict(p.meta))
        for ln in p.lines:
            q.lines.append(Line(ln.id, ln.page, ln.n, ln.unit, ln.subtype, [word_source(p, ln, i) for i in range(len(ln.words))], ln.para_start, ln.para_end))
        out.append(q)
    return out


def train_types(train_pages):
    return Counter(w for p in train_pages for ln in p.lines for w in ln.words if not ivtff.uncertain(w))


def g_table_cipher(train_pages, eval_pages, seed=1):
    """Table cipher (a verbose homophonic cipher with dice and tables, a period-plausible method). Latin plaintext (control
    split) is cut into unigrams and bigrams by coin flip; a card draw (weights 5:2:2:1:1:1)
    picks one of six tables; a unigram becomes a whole Voynich word, a bigram a prefix from
    its first letter plus a suffix from its second. Tables are built from training words."""
    rng = random.Random(seed)
    types = [w for w, _ in train_types(train_pages).most_common(600)]
    letters = refcorpus.alphabet("latin")
    rng.shuffle(types)
    uni = {t: {l: types[(t * len(letters) + i) % len(types)] for i, l in enumerate(letters)} for t in range(6)}
    pre = [w[: max(1, len(w) // 2)] for w in types]
    suf = [w[max(1, len(w) // 2):] or "y" for w in types]
    big = {t: ({l: pre[(t * 31 + i) % len(pre)] for i, l in enumerate(letters)},
               {l: suf[(t * 17 + i) % len(suf)] for i, l in enumerate(letters)}) for t in range(6)}
    plain = [c for c in "".join(refcorpus.control_text("latin")).replace(" ", "") if c in letters]
    pos = [0]

    def nxt(_p, _ln, _i):
        t = rng.choices(range(6), [5, 2, 2, 1, 1, 1])[0]
        i = pos[0] % (len(plain) - 2)
        if rng.random() < 0.5:
            pos[0] += 1
            return uni[t][plain[i]]
        pos[0] += 2
        return big[t][0][plain[i]] + big[t][1][plain[i + 1]]
    return _shape_like(eval_pages, nxt)


def g_self_citation(train_pages, eval_pages, seed=2):
    """Self-citation (after Timm & Schinner 2020): each word copies a word seen recently on the
    same page and changes it slightly (0-2 glyph edits from the training glyph inventory)."""
    rng = random.Random(seed)
    tt = train_types(train_pages)
    seeds = [w for w, _ in tt.most_common(200)]
    glyphs = Counter(g for w, c in tt.items() for g in ivtff.segment(w, "eva-basic") for _ in range(c))
    gl, gw = list(glyphs), list(glyphs.values())
    hist = {}

    def nxt(p, ln, i):
        h = hist.setdefault(p.id, [rng.choice(seeds) for _ in range(5)])
        w = ivtff.segment(rng.choice(h[-40:]), "eva-basic")
        for _ in range(rng.choice([0, 1, 1, 2])):
            op = rng.random()
            j = rng.randrange(len(w)) if w else 0
            if op < 0.5 and w:
                w[j] = rng.choices(gl, gw)[0]
            elif op < 0.75:
                w.insert(j, rng.choices(gl, gw)[0])
            elif len(w) > 2:
                del w[j]
        s = "".join(w) or rng.choice(seeds)
        h.append(s)
        return s
    return _shape_like(eval_pages, nxt)


def g_grille(train_pages, eval_pages, seed=3):
    """Table-and-grille generator (after Rugg 2004): a three-column table of word beginnings,
    middles and ends cut from training words; a grille draw picks one cell from each column."""
    rng = random.Random(seed)
    tt = train_types(train_pages)
    cols = ([], [], [])
    for w, c in tt.most_common(1500):
        g = ivtff.segment(w, "eva-basic")
        if len(g) < 3:
            continue
        a, b = len(g) // 3, 2 * len(g) // 3
        cols[0].append("".join(g[:a]))
        cols[1].append("".join(g[a:b]))
        cols[2].append("".join(g[b:]))

    def nxt(_p, _ln, _i):
        parts = [rng.choice(c) for c in cols]
        if rng.random() < 0.3:
            parts[rng.randrange(2)] = ""
        return "".join(parts) or rng.choice(cols[2])
    return _shape_like(eval_pages, nxt)


GENERATORS = {
    "G-table-cipher": g_table_cipher,
    "G-self-citation": g_self_citation,
    "G-grille": g_grille,
}
