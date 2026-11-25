"""Search a periodic tabula recta with a known alphabet order."""
import math
from collections import Counter
from . import ivtff, lm, refcorpus
from .controls import CIPHER_GLYPHS
from .search import trigram_table

BUDGET = {"max_period": 4, "sweeps": 4}


def search(lang, pages, budget, tag):
    """Fit each cyclic column by unigram likelihood, then refine full cycles
    against the reference trigram model. Every tested period restarts per word."""
    if not all(isinstance(budget.get(k), int) and budget[k] > 0 for k in BUDGET):
        raise ValueError("table-cipher searches need positive max_period and sweeps")
    letters = refcorpus.alphabet(lang)
    if len(letters) > len(CIPHER_GLYPHS):
        raise ValueError("target alphabet exceeds the table glyph inventory")
    glyphs = sorted(CIPHER_GLYPHS[:len(letters)])
    index = {g: i for i, g in enumerate(glyphs)}
    size = len(letters)
    ref = Counter(c for block in refcorpus.train_text(lang) for c in block)
    table, _ = trigram_table(lang)
    words = Counter(w for p in pages for ln in p.lines for w in ln.words)
    best_score, best_key = -float("inf"), None
    for period in range(1, budget["max_period"] + 1):
        counts = [Counter() for _ in range(period)]
        triples = Counter()
        for word, n in words.items():
            units = [(i % period, index[g]) for i, g in enumerate(ivtff.segment(word, "eva-basic")) if g in index]
            for col, g in units:
                counts[col][g] += n
            padded = [None, None, *units, None]
            for a, b, c in zip(padded, padded[1:], padded[2:]):
                triples[a, b, c] += n
        shifts = [max(range(size), key=lambda k: sum(n * math.log2(1 + ref[letters[(g - k) % size]])
                                                      for g, n in count.items())) for count in counts]

        def objective(items):
            value = 0.0
            for triple, n in items:
                a, b, c = (lm.WB if unit is None else letters[(unit[1] - shifts[unit[0]]) % size]
                           for unit in triple)
                value += n * table[a, b, c]
            return value

        for _ in range(budget["sweeps"]):
            changed = False
            for col in range(period):
                items = [(t, n) for t, n in triples.items() if any(u and u[0] == col for u in t)]
                old = shifts[col]
                scores = []
                for k in range(size):
                    shifts[col] = k
                    scores.append(objective(items))
                shifts[col] = max(range(size), key=scores.__getitem__)
                changed |= shifts[col] != old
            if not changed:
                break
        score = objective(triples.items()) - period * math.log2(size)
        if score > best_score:
            best_score = score
            best_key = {"map": dict(zip(glyphs, letters)), "shifts": shifts}
    return {"id": f"grid-{lang}-table-cipher-{tag}", "family": "table-cipher", "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"}, "key": best_key,
            "search": {"budget": dict(budget)}}
