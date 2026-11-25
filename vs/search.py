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
          "verbose_segmentations": ["bpe-greedy", "fixed-2"], "verbose_min_unit_share": 0.0005,
          "substitution_group_swap": 0.2}


def prune_rare(tri, share):
    """Drop unit trigrams that contain a unit rarer than `share` of all unit tokens.

    Under transcription noise a verbose segmentation spawns many junk units (a single-glyph
    error shifts every later cut in the word): on the 2% noise Latin control, fixed-2 yields
    ~205 units for 24 true ones, the junk covering ~2% of tokens. The climb then spends its
    budget on junk and stalls far below the true key's objective. Rare units are left out of
    the key and decode as nulls, as uncovered glyphs already do (families/verbose.py).

    Measured limit (2% noise controls): where the pruned search still fails (Italian, French)
    it is not under-budgeted: 8 restarts x 12000 iterations returns the same key as 4 x 6000,
    and that key scores BETTER on this objective than the true key (Italian -216385 vs
    -218645 bits; French -172808 vs -174427). Its errors are the rare letters (j k w x y z)
    folded into common ones. Closing that gap needs a different objective (e.g. word-level,
    or an injectivity prior on the unit map), not more search."""
    if not share:
        return tri
    f = Counter()
    for (_x, _y, z), c in tri.items():
        f[z] += c
    tot = sum(v for u, v in f.items() if u != lm.WB)
    keep = {u for u, v in f.items() if u == lm.WB or v >= share * tot}
    return Counter({t: c for t, c in tri.items() if set(t) <= keep})


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


def climb(tri, table, letters, seed, budget=BUDGET, init=None, group_swap=0.0):
    """Hill climbing over unit->letter maps. Returns (best map, best score).

    group_swap: share of moves that exchange two letters' whole homophone groups (every unit
    on letter a moves to b and every unit on b to a). Single-unit moves cannot leave a basin
    where two frequent letters are interchanged across several homophones at once: on the
    German homophonic control (ch/sch) the search ended at -114447 bits against -103058 for
    the true key, at any budget tried. With 0 the random stream is exactly as before."""
    units = sorted({u for t in tri for u in t if u != lm.WB})
    by = {u: [] for u in units}
    items = list(tri.items())
    for i, ((x, y, z), _c) in enumerate(items):
        for u in {x, y, z} - {lm.WB}:
            by[u].append(i)
    rng = random.Random(seed)
    best_m, best_s = None, -float("inf")
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
        m[lm.WB] = lm.WB

        def tscore(i):
            (x, y, z), c = items[i]
            return c * table[m[x], m[y], m[z]]

        s = sum(tscore(i) for i in range(len(items)))
        for _ in range(budget["iterations"]):
            if group_swap and rng.random() < group_swap:
                la, lb = rng.sample(letters, 2)
                ga = [u for u in units if m[u] == la]
                gb = [u for u in units if m[u] == lb]
                if not ga and not gb:
                    continue
                idx = sorted({i for u in ga + gb for i in by[u]})
                before = sum(tscore(i) for i in idx)
                for u in ga:
                    m[u] = lb
                for u in gb:
                    m[u] = la
                d = sum(tscore(i) for i in idx) - before
                if d > 0:
                    s += d
                else:
                    for u in ga:
                        m[u] = la
                    for u in gb:
                        m[u] = lb
            elif rng.random() < 0.5:
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
        if s > best_s:
            best_s, best_m = s, {u: l for u, l in m.items() if u != lm.WB}
    return best_m, best_s


def cell_budget(lang, family):
    if family in ("abbreviation",):
        from .search_abbreviation import SETTINGS
        return {**BUDGET, **SETTINGS}
    return BUDGET


def search_cell(lang, family, train_pages, budget=None, tag="cell"):
    if budget is None:
        budget = cell_budget(lang, family)
    table, sy = trigram_table(lang)
    letters = [l for l in sy if l != lm.WB]
    if family == "abbreviation":
        from .search_abbreviation import search_abbreviations, SETTINGS
        budget = {**SETTINGS, **budget}
        return search_abbreviations(lang, train_pages, budget, tag, table, letters)
    if family == "substitution":
        segf = lambda w: ivtff.segment(w, "eva-basic")
        tri = unit_trigrams(train_pages, segf)
        m, s = climb(tri, table, letters, f"{budget['seed']}/{lang}/{family}/{tag}", budget,
                     group_swap=budget.get("substitution_group_swap", 0.0))
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
            tri = prune_rare(unit_trigrams(train_pages, segf), budget.get("verbose_min_unit_share", 0))
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
