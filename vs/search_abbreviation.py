"""Key search for the abbreviation family."""
import math
from collections import Counter
from . import ivtff, lm, refcorpus
from .search import climb, unit_trigrams

SETTINGS = {"suffix_candidates": 48, "lexical_sweeps": 4}


def search_abbreviations(lang, pages, budget, tag, table, letters):
    """Fit alphabet glyphs first, then score suffix expansions in whole-word
    contexts. The four possible abbreviation signs are part of the family."""
    from .controls import ABBREVIATION_SIGNS
    cut = lambda w: [g for g in ivtff.segment(w, "eva-basic") if g not in ABBREVIATION_SIGNS]
    tri = unit_trigrams(pages, cut)
    mapping = {}
    if len({u for t in tri for u in t if u != lm.WB}) >= 2:
        mapping, _ = climb(tri, table, letters, f"{budget['seed']}/{lang}/abbreviation/{tag}", budget,
                           group_swap=budget.get("substitution_group_swap", 0))
    ref = Counter(w for b in refcorpus.train_text(lang) for w in b.split())
    suffixes = Counter()
    for word, n in ref.items():
        for width in (2, 3):
            if len(word) > width:
                suffixes[word[-width:]] += n
    candidates = [s for s, _ in suffixes.most_common(budget["suffix_candidates"])]
    words = Counter(w for p in pages for ln in p.lines for w in ln.words)
    observed = {sign: Counter() for sign in ABBREVIATION_SIGNS}
    for word, n in words.items():
        glyphs = ivtff.segment(word, "eva-basic")
        if glyphs and glyphs[-1] in observed:
            stem = "".join(mapping.get(g, "") for g in glyphs[:-1])
            observed[glyphs[-1]][stem] += n
    for sign, stems in observed.items():
        if stems and candidates:
            mapping[sign + "$"] = max(candidates, key=lambda suffix: sum(
                n * math.log1p(ref[stem + suffix]) for stem, n in stems.items()))
    contexts = {u: [] for u in mapping}
    for word, n in words.items():
        units = ivtff.segment(word, "eva-basic")
        if units and units[-1] + "$" in mapping:
            units[-1] += "$"
        for u in set(units) & mapping.keys():
            contexts[u].append((units, n))
    for _ in range(budget["lexical_sweeps"]):
        changed = False
        for unit in mapping:
            choices = candidates if unit.endswith("$") else letters
            def score(value):
                return sum(n * math.log1p(ref["".join(value if g == unit else mapping.get(g, "")
                                                      for g in units)]) for units, n in contexts[unit])
            old = mapping[unit]
            value = max(choices, key=score)
            if score(value) > score(old):
                mapping[unit] = value
                changed = True
        if not changed:
            break
    return {"id": f"grid-{lang}-abbreviation-{tag}", "family": "abbreviation", "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"}, "key": {"map": mapping},
            "search": {"budget": dict(budget)}}
