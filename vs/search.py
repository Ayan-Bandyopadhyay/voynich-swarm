"""L3 key search at a fixed, published budget.

A cell of the hypothesis grid (language x cipher family) is searched by hill climbing with
restarts. The objective is the training pages' glyph-trigram log-likelihood under the
target language's trigram model (decoded letters, word boundaries kept). The best key is
then handed to the judge like any other submission.

A cell is RULED OUT only if (1) the best key at budget fails the judge on the evaluation
pages and (2) the same search at the same budget finds a passing key on a positive control
in that language (see controls.py). Without (2) the cell stays OPEN: the search, not the
hypothesis, failed.
"""
import math, random
from collections import Counter
from . import ivtff, lm, refcorpus

BUDGET = {"restarts": 4, "iterations": 6000, "seed": 1404, "bpe_merges": 30,
          "verbose_segmentations": ["bpe-greedy", "fixed-2"]}


def trigram_table(lang):
    tr = refcorpus.train_text(lang)
    m = lm.KN([lm.char_stream(b.split()) for b in tr], 3, vocab=refcorpus.alphabet(lang) + [lm.WB])
    sy = refcorpus.alphabet(lang) + [lm.WB]
    return {(a, b, c): math.log2(m.prob(c, (lm.BOS, a) if a == "^" else (a, b))) for a in sy for b in sy for c in sy}, sy


def unit_trigrams(train_pages, segf):
    c = Counter()
    for p in train_pages:
        for ln in p.lines:
            s = [lm.WB]
            for w in ln.words:
                s += segf(w) + [lm.WB]
            for x, y, z in zip(s, s[1:], s[2:]):
                c[x, y, z] += 1
    return c


def bpe_units(train_pages, merges):
    words = Counter(w for p in train_pages for ln in p.lines for w in ln.words if not ivtff.uncertain(w))
    segs = {w: ivtff.segment(w, "eva-basic") for w in words}
    units = set(g for s in segs.values() for g in s)
    for _ in range(merges):
        pairs = Counter()
        for w, s in segs.items():
            for a, b in zip(s, s[1:]):
                pairs[a, b] += words[w]
        if not pairs:
            break
        (a, b), _n = max(pairs.items(), key=lambda kv: (kv[1], kv[0]))
        units.add(a + b)
        for w, s in segs.items():
            out, i = [], 0
            while i < len(s):
                if i + 1 < len(s) and s[i] == a and s[i + 1] == b:
                    out.append(a + b)
                    i += 2
                else:
                    out.append(s[i])
                    i += 1
            segs[w] = out
    return sorted(units, key=lambda u: (-len(u), u))


def greedy(word, units):
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


def fixed_width(word, n):
    """Cut a word into n-glyph chunks from its start (the last chunk may be shorter)."""
    return [word[i:i + n] for i in range(0, len(word), n)]


def climb(tri, table, letters, seed, budget=BUDGET, init=None, pin=None, accept=None):
    """Hill climbing over unit->letter maps. Returns (best map, best score).
    pin: unit->letter set at the start of every restart (still free to move).
    accept: a restart's map may become the best only if accept(map) is true (if no restart's
    map is accepted, the best overall is returned)."""
    units = sorted({u for t in tri for u in t if u != lm.WB})
    by = {u: [] for u in units}
    items = list(tri.items())
    for i, ((x, y, z), _c) in enumerate(items):
        for u in {x, y, z} - {lm.WB}:
            by[u].append(i)
    rng = random.Random(seed)
    best_m, best_s, best_ok = None, -float("inf"), False
    freq = Counter()
    for (x, y, z), c in items:
        freq[z] += c
    for r in range(budget["restarts"]):
        if r == 0 and init:
            m = dict(init)
        elif r == 0:
            ranked = sorted(units, key=lambda u: -freq[u])
            lf = [l for l in letters]
            m = {u: lf[i % len(lf)] for i, u in enumerate(ranked)}
        else:
            m = {u: rng.choice(letters) for u in units}
        if pin and not (r == 0 and init):
            m.update({u: l for u, l in pin.items() if u in m})
        m[lm.WB] = lm.WB

        def tscore(i):
            (x, y, z), c = items[i]
            return c * table[m[x], m[y], m[z]]

        s = sum(tscore(i) for i in range(len(items)))
        for _ in range(budget["iterations"]):
            if rng.random() < 0.5:
                u = rng.choice(units)
                old = m[u]
                new = rng.choice(letters)
                if new == old:
                    continue
                idx = by[u]
                before = sum(tscore(i) for i in idx)
                m[u] = new
                d = sum(tscore(i) for i in idx) - before
                if d > 0:
                    s += d
                else:
                    m[u] = old
            else:
                u, v = rng.sample(units, 2)
                if m[u] == m[v]:
                    continue
                idx = sorted(set(by[u]) | set(by[v]))
                before = sum(tscore(i) for i in idx)
                m[u], m[v] = m[v], m[u]
                d = sum(tscore(i) for i in idx) - before
                if d > 0:
                    s += d
                else:
                    m[u], m[v] = m[v], m[u]
        mm = {u: l for u, l in m.items() if u != lm.WB}
        ok = accept(mm) if accept else True
        if (ok, s) > (best_ok, best_s):
            best_ok, best_s, best_m = ok, s, mm
    return best_m, best_s


def search_cell(lang, family, train_pages, budget=BUDGET, tag="cell", spaces="word_breaks"):
    """spaces="ignored": train_pages are already viewed one glyph stream per line
    (views.apply), so the key must emit the word breaks itself. The word break becomes one more
    target letter (written " " in the key); every restart starts with the most frequent unit
    on it, and only keys that emit a break can win: on spaceless lines the trigram objective
    otherwise prefers a key with no break at all (one giant word per line), which can never
    read; a key must spend >= 5% of glyph tokens on breaks. Restart 0 starts from frequency rank
    against the language's letter frequencies. Measured on spaces-ignored simple-substitution controls: 0/4 -> 4/4."""
    table, sy = trigram_table(lang)
    letters = [l for l in sy if l != lm.WB]
    if spaces == "ignored":
        if family != "substitution":
            raise ValueError("spaces=ignored search is implemented for substitution only")
        segf = lambda w: ivtff.segment(w, "eva-basic")
        tri = unit_trigrams(train_pages, segf)
        f = Counter()
        for (_x, _y, z), c in tri.items():
            f[z] += c
        ranked = sorted((u for u in f if u != lm.WB), key=lambda u: (-f[u], u))
        lf = Counter(ch for b in refcorpus.train_text(lang) for ch in b if ch in letters)
        lr = sorted(letters, key=lambda l: (-lf[l], l))
        init = {ranked[0]: lm.WB, **{u: lr[i % len(lr)] for i, u in enumerate(ranked[1:])}}
        tot = sum(f[u] for u in ranked)
        # a key must spend >= 5% of glyph tokens on word breaks (natural text: ~15%)
        accept = lambda mm: sum(f[u] for u, l in mm.items() if l == lm.WB) >= 0.05 * tot
        m, s = climb(tri, table, letters + [lm.WB], f"{budget['seed']}/{lang}/{family}/{tag}/spaces-ignored", budget,
                     init=init, pin={ranked[0]: lm.WB}, accept=accept)
        return {"id": f"grid-{lang}-{family}-{tag}-spaces-ignored", "family": family, "segmentation": "eva-basic",
                "target": {"language": lang, "period": "grid search"}, "spaces": "ignored",
                "key": {"map": {u: (" " if l == lm.WB else l) for u, l in m.items()}},
                "search": {"budget": budget, "objective_bits": round(-s, 1)}}
    if family == "substitution":
        segf = lambda w: ivtff.segment(w, "eva-basic")
        tri = unit_trigrams(train_pages, segf)
        m, s = climb(tri, table, letters, f"{budget['seed']}/{lang}/{family}/{tag}", budget)
        key = {"map": m}
    elif family == "verbose":
        # Several segmentation hypotheses are searched at the same per-hypothesis budget; the
        # one whose best key has the lower mean objective per unit trigram is kept. BPE with
        # greedy longest match misaligns fixed-width verbose units (it merges across unit
        # boundaries), so a fixed-width hypothesis is searched alongside it.
        best = None
        for segname in budget.get("verbose_segmentations", ["bpe-greedy"]):
            if segname == "bpe-greedy":
                units = bpe_units(train_pages, budget["bpe_merges"])
                allu = units + sorted({c for p in train_pages for ln in p.lines for w in ln.words for c in w} - set(units))
                allu = sorted(set(allu), key=lambda u: (-len(u), u))
                segf = lambda w, allu=allu: greedy(w, allu)
            elif segname.startswith("fixed-"):
                segf = lambda w, n=int(segname.split("-")[1]): fixed_width(w, n)
            else:
                raise ValueError(segname)
            tri = unit_trigrams(train_pages, segf)
            suffix = "" if segname == "bpe-greedy" else "/" + segname
            m, s = climb(tri, table, letters, f"{budget['seed']}/{lang}/{family}/{tag}{suffix}", budget)
            per = s / max(1, sum(tri.values()))
            if best is None or per > best[0]:
                best = (per, m, s, segname)
        _per, m, s, chosen = best
        key = {"map": m}
    else:
        raise ValueError(family)
    info = {"budget": budget, "objective_bits": round(-s, 1)}
    if family == "verbose":
        info["segmentation_chosen"] = chosen
    return {"id": f"grid-{lang}-{family}-{tag}", "family": family, "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"}, "key": key,
            "search": info}
