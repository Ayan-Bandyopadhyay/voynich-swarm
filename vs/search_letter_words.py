"""Key search for the letter-words family (letters written as whole words, vs/families/letter_words.py).

Two steps, both on the training pages only.

1. The cut. Every glyph is called a front glyph or a back glyph, and a word is read as front
   glyphs followed by back glyphs: its prefix and its suffix. The labelling kept is the one under
   which the words need the fewest distinct prefixes and suffixes (words that do not fit count
   against it). Calling every glyph a front glyph makes each word its own prefix, which is the
   most expensive labelling there is, so the count cannot be gamed that way.
   Limit, stated: a glyph that the scribe used in both places cannot be labelled both ways here.

2. The letters. Prefixes and suffixes, in page order, form one stream of signs with no word
   breaks: a homophonic substitution of the target language written without spaces. Simulated
   annealing assigns a letter to each sign, scored by the language's letter trigrams (spaces
   removed) times each sign's share among its letter's signs (see anneal). Signs rarer than SETTINGS["lw_min_unit_share"] are left out and read as nothing.
"""
import math, random
from collections import Counter
from . import ivtff, lm, refcorpus

SETTINGS = {"lw_restarts": 6, "lw_moves": 20000, "lw_min_unit_share": 0.0005, "lw_t0": [1.0, 6.0, 60.0], "lw_cooling": 30.0}


def spaceless_trigrams(lang):
    """log2 P(c | a, b) for the language written without spaces, as nested lists over its alphabet."""
    letters = refcorpus.alphabet(lang)
    m = lm.KN([list(b.replace(" ", "")) for b in refcorpus.train_text(lang)], 3, vocab=letters)
    return letters, [[[math.log2(m.prob(c, (a, b))) for c in letters] for b in letters] for a in letters]


def learn_cut(pages, seg=None):
    """Label each glyph front (0) or back (1). Returns (labels, cost) for the cheapest labelling
    found by flipping one glyph at a time from a positional start."""
    seg = seg or (lambda w: ivtff.segment(w, "eva-basic"))
    types = Counter(w for p in pages for ln in p.lines for w in ln.words if w and not ivtff.uncertain(w))
    segs = {w: seg(w) for w in types}
    place, seen = Counter(), Counter()
    for w, gs in segs.items():
        for i, g in enumerate(gs):
            place[g] += types[w] * (i + 0.5) / len(gs)
            seen[g] += types[w]
    glyphs = sorted(seen)
    labels = {g: int(place[g] / seen[g] >= 0.5) for g in glyphs}

    def cost(lab):
        pre, suf, misfit = set(), set(), 0
        for w, gs in segs.items():
            ls = [lab[g] for g in gs]
            if ls != sorted(ls):
                misfit += 1
                continue
            k = ls.count(0)
            if k:
                pre.add("".join(gs[:k]))
            if k < len(gs):
                suf.add("".join(gs[k:]))
        return len(pre) + len(suf) + 2 * misfit

    best = cost(labels)
    improved = True
    while improved:
        improved = False
        for g in glyphs:
            labels[g] ^= 1
            c = cost(labels)
            if c < best:
                best, improved = c, True
            else:
                labels[g] ^= 1
    return labels, best


def cut_word(word, labels, seg=None):
    """(prefix, suffix) of a word under a labelling, or None if it does not read front-then-back."""
    gs = (seg or (lambda w: ivtff.segment(w, "eva-basic")))(word)
    ls = [labels.get(g) for g in gs]
    if None in ls or ls != sorted(ls):
        return None
    k = ls.count(0)
    return "".join(gs[:k]), "".join(gs[k:])


def anneal(streams, letters, table, seed, moves, restarts, t0s, cooling):
    """Assign a letter to each sign so that the streams read as the language. streams: lists of
    sign names. Returns ({sign: letter}, score in bits).

    The score is the full likelihood of the signs, not of the letters alone: the letters under the
    language's trigrams, times each sign's share among the signs of its letter. Without the second
    term the best "reading" folds every sign onto a few common letters (a text of five letters is
    very predictable): on the Latin control that collapse scored within 4% of the true key on
    trigrams alone and every run ended in it. With it, a letter pays for every homophone it owns.

    One run finds the planted key about half the time (French control: starting temperatures 1 and
    60 found it, 6 and 20 did not), and a run that finds it scores far above one that does not
    (714,800 against 783,000 bits). So the restarts cycle through the starting temperatures t0s,
    each cooled by the factor `cooling`, and the best-scoring run is kept."""
    signs = sorted({u for s in streams for u in s})
    if not signs:
        return {}, 0.0
    ix = {u: i for i, u in enumerate(signs)}
    tri = Counter()
    for s in streams:
        ids = [ix[u] for u in s]
        for t in zip(ids, ids[1:], ids[2:]):
            tri[t] += 1
    items = list(tri.items())
    by = [[] for _ in signs]
    for k, ((x, y, z), _c) in enumerate(items):
        for u in {x, y, z}:
            by[u].append(k)
    counts = Counter(u for s in streams for u in s)
    freq = [counts[u] for u in signs]
    n_letters = len(letters)
    xlogx = lambda n: n * math.log2(n) if n > 0 else 0.0
    rng = random.Random(seed)
    best_m, best_s = None, -float("inf")
    for r in range(restarts):
        m = [rng.randrange(n_letters) for _ in signs]
        t0 = t0s[r % len(t0s)]
        t1 = t0 / cooling
        load = [0] * n_letters          # sign tokens on each letter
        for u, l in enumerate(m):
            load[l] += freq[u]

        def part(idx):
            return sum(c * table[m[x]][m[y]][m[z]] for (x, y, z), c in (items[k] for k in idx))

        def move(u, new):
            """Score change of giving sign u the letter new (applied; undo by moving back)."""
            old = m[u]
            before = part(by[u]) - xlogx(load[old]) - xlogx(load[new])
            m[u] = new
            load[old] -= freq[u]
            load[new] += freq[u]
            return part(by[u]) - xlogx(load[old]) - xlogx(load[new]) - before

        s = part(range(len(items))) - sum(xlogx(n) for n in load)
        scale = max(1.0, len(items) / 2000)   # the moves that matter change the score by hundreds of bits
        for step in range(moves):
            t = scale * t0 * (t1 / t0) ** (step / max(moves - 1, 1))
            u = rng.randrange(len(signs))
            old = m[u]
            if rng.random() < 0.7:
                new = rng.randrange(n_letters)
                if new == old:
                    continue
                d = move(u, new)
                if d >= 0 or rng.random() < math.exp(d / t):
                    s += d
                else:
                    move(u, old)
            else:
                v = rng.randrange(len(signs))
                lv = m[v]
                if lv == old:
                    continue
                d = move(u, lv) + move(v, old)
                if d >= 0 or rng.random() < math.exp(d / t):
                    s += d
                else:
                    move(v, lv)
                    move(u, old)
        # finish greedily: every sign takes its best letter given the rest, until nothing changes
        changed = True
        while changed:
            changed = False
            for u in sorted(range(len(signs)), key=lambda i: -freq[i]):
                old, gain, top = m[u], 0.0, m[u]
                for l in range(n_letters):
                    if l == old:
                        continue
                    d = move(u, l)
                    move(u, old)
                    if d > gain + 1e-9:
                        gain, top = d, l
                if top != old:
                    s += move(u, top)
                    changed = True
        if s > best_s:
            best_s, best_m = s, {u: letters[m[ix[u]]] for u in signs}
    return best_m, best_s


def search_letter_words(lang, pages, budget, tag):
    labels, cut_cost = learn_cut(pages)
    cuts = {}
    streams, count = [], Counter()
    for p in pages:
        s = []
        for ln in p.lines:
            for w in ln.words:
                if w not in cuts:
                    cuts[w] = None if not w or ivtff.uncertain(w) else cut_word(w, labels)
                c = cuts[w]
                if c:
                    s.extend(x for x in ("<" + c[0] if c[0] else "", ">" + c[1] if c[1] else "") if x)
        streams.append(s)
        count.update(s)
    total = sum(count.values()) or 1
    keep = {u for u, n in count.items() if n >= budget["lw_min_unit_share"] * total}
    streams = [[u for u in s if u in keep] for s in streams]
    letters, table = spaceless_trigrams(lang)
    mapping, score = anneal(streams, letters, table, f"{budget['seed']}/{lang}/letter-words/{tag}",
                            budget["lw_moves"], budget["lw_restarts"], budget["lw_t0"], budget["lw_cooling"])
    key = {"prefix": {u[1:]: l for u, l in mapping.items() if u[0] == "<"},
           "suffix": {u[1:]: l for u, l in mapping.items() if u[0] == ">"}}
    return {"id": f"grid-{lang}-letter-words-{tag}", "family": "letter-words", "segmentation": "eva-basic",
            "plaintext": "respaced", "target": {"language": lang, "period": "grid search"}, "key": key,
            "search": {"budget": dict(budget), "objective_bits": round(-score, 1), "cut_cost": cut_cost,
                       "front_glyphs": sorted(g for g, v in labels.items() if v == 0),
                       "back_glyphs": sorted(g for g, v in labels.items() if v == 1),
                       "signs": len(mapping)}}
