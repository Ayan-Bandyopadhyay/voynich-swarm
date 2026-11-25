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
import itertools, math, random
from collections import Counter, defaultdict
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
    if family == "nomenclator" and lang in ("english", "latin", "spanish"):
        from .search_nomenclator import SETTINGS
        return {**BUDGET, **SETTINGS, "homophone_ranked_restarts": 1, "homophone_word_sweeps": 5,
                "nomenclator_unique_word_sweeps": 6}
    if (lang, family) == ("nahuatl", "substitution"):
        return {**BUDGET, "homophone_ranked_restarts": 1, "homophone_word_sweeps": 5}
    if family == "verbose" and lang in ("french", "german"):
        return {**BUDGET, "verbose_lexicon_sweeps": 6, "verbose_max_assignment": 6, "verbose_singleton_limit": 16}
    if (lang, family) == ("italian", "verbose"):
        return {**BUDGET, "verbose_lexicon_sweeps": 6, "verbose_singleton_limit": 8}
    if (lang, family) == ("spanish", "verbose"):
        return {**BUDGET, "verbose_lexicon_sweeps": 6}
    if family in ("nomenclator", "codebook"):
        from .search_nomenclator import SETTINGS
        return dict(SETTINGS) if family == "codebook" else {**BUDGET, **SETTINGS}
    return BUDGET


def refine_pairs(pages, reference, letters, initial, sweeps):
    """Refine a fixed-width draft by coordinate ascent on reference word counts.

    Even-length words supply aligned pairs. An odd-length word has at least one
    incomplete pair and can put every subsequent pair out of alignment.
    """
    words = Counter(w for p in pages for line in p.lines for w in line.words if len(w) % 2 == 0)
    counts = Counter()
    for word, n in words.items():
        for unit in fixed_width(word, 2):
            counts[unit] += n
    active = {u for u, n in counts.items() if n >= 3}
    mapping = {u: v for u, v in initial.items() if u in active}
    contexts = defaultdict(list)
    for word, n in words.items():
        units = tuple(fixed_width(word, 2))
        if all(u in active for u in units):
            for u in set(units):
                contexts[u].append((units, n))
    for _ in range(sweeps):
        changed = False
        for u in sorted(active, key=lambda u: (-counts[u], u)):
            def score(letter):
                return sum(n * math.log1p(reference["".join(
                    letter if x == u else mapping.get(x, "?") for x in units)])
                           for units, n in contexts[u])
            value, letter = max((score(c), c) for c in letters)
            if value and letter != mapping.get(u):
                mapping[u] = letter
                changed = True
        if not changed:
            break
    return mapping


def assign_missing_letters(pages, mapping, reference, table, letters, limit):
    """Try the injective submodel when one pair per target letter is supported.
    Hold the common representative of each letter. Rank permutations of the
    remaining letters using word counts and character trigrams."""
    if len(mapping) != len(letters):
        return mapping
    missing = sorted(set(letters) - set(mapping.values()))
    if not 0 < len(missing) <= limit:
        return mapping
    words = Counter(w for p in pages for ln in p.lines for w in ln.words)
    counts = Counter()
    for word, n in words.items():
        if len(word) % 2 == 0:
            for u in fixed_width(word, 2):
                counts[u] += n
    groups = defaultdict(list)
    for u, letter in mapping.items():
        groups[letter].append(u)
    unresolved = sorted(u for group in groups.values()
                        for u in sorted(group, key=lambda u: (-counts[u], u))[1:])
    contexts = Counter()
    inventory = sorted(mapping)
    changing = set(unresolved)
    for word, n in words.items():
        sequence = tuple(g for g in greedy(word, inventory) if g in mapping)
        if changing.intersection(sequence):
            contexts[sequence] += n

    def objective(order):
        trial = {**mapping, **dict(zip(unresolved, order))}
        score = 0.0
        for sequence, n in contexts.items():
            word = "".join(trial[u] for u in sequence)
            padded = [lm.WB, lm.WB, *word, lm.WB]
            bits = sum(table[t] for t in zip(padded, padded[1:], padded[2:]))
            score += n * (bits + 2 * math.log2(1 + reference[word]))
        return score

    best = max(itertools.permutations(missing), key=objective)
    return {**mapping, **dict(zip(unresolved, best))}


def fit_singletons(pages, mapping, reference, table, letters, limit):
    """Retain the most frequent stray glyphs as noisy one-letter units. A
    single-glyph transcription replacement still occupies a plaintext letter.
    Fit its emission in context using reference words and boundary trigrams."""
    words = Counter(w for p in pages for ln in p.lines for w in ln.words)
    pairs = sorted(mapping, key=lambda u: (-len(u), u))
    contexts = defaultdict(list)
    counts = Counter()
    for w, n in words.items():
        sequence = greedy(w, pairs)
        for u in set(sequence) - mapping.keys():
            if len(u) == 1:
                contexts[u].append((sequence, n))
                counts[u] += n
    for u in sorted(counts, key=lambda u: (-counts[u], u))[:limit]:
        def score(letter):
            total = 0.0
            for sequence, n in contexts[u]:
                word = "".join(letter if g == u else mapping.get(g, "") for g in sequence)
                padded = [lm.WB, lm.WB, *word, lm.WB]
                char_score = sum(table[t] for t in zip(padded, padded[1:], padded[2:]))
                total += n * (char_score + 2 * math.log2(1 + reference[word]))
            return total
        mapping[u] = max(letters, key=score)


def search_cell(lang, family, train_pages, budget=None, tag="cell"):
    if budget is None:
        budget = cell_budget(lang, family)
    table, sy = trigram_table(lang)
    letters = [l for l in sy if l != lm.WB]
    if family in ("nomenclator", "codebook"):
        from .search_nomenclator import search_nomenclator, SETTINGS
        budget = {**SETTINGS, **budget}
        key = search_nomenclator(lang, train_pages, budget, tag, table, letters, whole_words=family == "codebook")
        if family == "codebook":
            del key["marker"]
        return {"id": f"grid-{lang}-{family}-{tag}", "family": family, "segmentation": "eva-basic",
                "target": {"language": lang, "period": "grid search"}, "key": key,
                "search": {"budget": dict(budget)}}
    if family == "substitution":
        segf = lambda w: ivtff.segment(w, "eva-basic")
        tri = unit_trigrams(train_pages, segf)
        m, s = climb(tri, table, letters, f"{budget['seed']}/{lang}/{family}/{tag}", budget,
                     group_swap=budget.get("substitution_group_swap", 0.0))
        if budget.get("homophone_ranked_restarts", 0) and budget.get("homophone_word_sweeps", 0):
            from .search_homophones import refine_homophones
            m = refine_homophones(lang, train_pages, m, tri, table, letters, budget)
            scored = {**m, lm.WB: lm.WB}
            s = sum(n * table[scored[a], scored[b], scored[c]] for (a, b, c), n in tri.items())
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
        if chosen == "fixed-2" and budget.get("verbose_lexicon_sweeps"):
            reference = Counter(w for block in refcorpus.train_text(lang) for w in block.split())
            m = refine_pairs(train_pages, reference, letters, m, budget["verbose_lexicon_sweeps"])
            if budget.get("verbose_max_assignment"):
                m = assign_missing_letters(train_pages, m, reference, table, letters, budget["verbose_max_assignment"])
            if budget.get("verbose_singleton_limit"):
                fit_singletons(train_pages, m, reference, table, letters, budget["verbose_singleton_limit"])
        key = {"map": m}
    else:
        raise ValueError(family)
    info = {"budget": budget, "objective_bits": round(-s, 1)}
    if family == "verbose":
        info["segmentation_chosen"] = chosen
        if chosen == "fixed-2" and budget.get("verbose_lexicon_sweeps"):
            info["initial_objective_bits"] = info.pop("objective_bits")
    return {"id": f"grid-{lang}-{family}-{tag}", "family": family, "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"}, "key": key,
            "search": info}
