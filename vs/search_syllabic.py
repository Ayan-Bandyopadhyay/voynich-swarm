"""Key search for the syllabic family."""
import math
from collections import Counter
from . import ivtff, lm, refcorpus
from .search import climb, unit_trigrams

SETTINGS = {"syllable_candidates": 64, "sign_limit": 24, "lexical_sweeps": 5}


def search_syllabic(lang, pages, budget, tag, table, letters):
    """Identify alphabet and word-internal CV signs from unlabelled training
    words. Candidate syllables come only from the target reference training text."""
    from .families import syllabic
    marker = "q"
    key = {"marker": marker, "map": {}}
    def cut(w):
        return syllabic.units(w, key, lambda x: ivtff.segment(x, "eva-basic"))
    words = Counter(w for p in pages for line in p.lines for w in line.words)
    units = {w: tuple(cut(w)) for w in words}
    tri = unit_trigrams(pages, lambda w: [lm.WB if g.startswith(marker) else g for g in units[w]])
    mapping = {}
    if len({g for t in tri for g in t if g != lm.WB}) >= 2:
        mapping, _ = climb(tri, table, letters, f"{budget['seed']}/{lang}/syllabic/{tag}", budget,
                           group_swap=budget.get("substitution_group_swap", 0))
    ref = Counter(w for block in refcorpus.train_text(lang) for w in block.split())
    syllables = Counter()
    for w, n in ref.items():
        for a, b in zip(w, w[1:]):
            if a not in "aeiou" and b in "aeiou":
                syllables[a + b] += n
    candidates = [s for s, _ in syllables.most_common(budget["syllable_candidates"])]
    sign_frequency = Counter()
    for w, n in words.items():
        for g in units[w]:
            if len(g) > 1 and g.startswith(marker):
                sign_frequency[g] += n
    signs = [g for g, n in sign_frequency.most_common(budget["sign_limit"]) if n >= 3] if candidates else []
    for i, g in enumerate(signs):
        mapping[g] = candidates[i % len(candidates)]
    contexts = {g: [] for g in mapping}
    for w, n in words.items():
        for g in set(units[w]) & mapping.keys():
            contexts[g].append((units[w], n))
    for _ in range(budget["lexical_sweeps"]):
        changed = False
        for g in signs + [u for u in mapping if u not in signs]:
            def score(value):
                total = 0.0
                for sequence, n in contexts[g]:
                    word = "".join(value if u == g else mapping.get(u, "") for u in sequence)
                    chars = [lm.WB, lm.WB, *word, lm.WB]
                    total += n * (sum(table[t] for t in zip(chars, chars[1:], chars[2:]))
                                  + 2 * math.log2(1 + ref[word]))
                return total
            choices = candidates if g in signs else letters
            best = max(choices, key=score)
            if best != mapping[g] and score(best) > score(mapping[g]):
                mapping[g] = best
                changed = True
        if not changed:
            break
    key["map"] = mapping
    return {"id": f"grid-{lang}-syllabic-{tag}", "family": "syllabic", "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"}, "key": key,
            "search": {"budget": dict(budget)}}
