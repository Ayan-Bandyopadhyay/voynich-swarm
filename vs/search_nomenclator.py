"""Key search for the nomenclator family."""
import math
from collections import Counter
from . import ivtff, lm, refcorpus
from .search import climb, unit_trigrams

SETTINGS = {"word_code_limit": 24, "candidate_words": 48, "assignment_sweeps": 4}


def search_nomenclator(lang, pages, budget, tag, table, letters, whole_words=False):
    """Find a repeated introducer, fit the unmarked alphabet, then assign frequent
    whole codes by their neighboring words in the reference language."""
    words = Counter(w for p in pages for line in p.lines for w in line.words)
    markers = Counter()
    for word, n in words.items():
        if len(word) == 4 and word[0] == word[1]:
            markers[word[:2]] += n
    marker = max(sorted(markers), key=markers.get) if markers else "hh"
    if whole_words:
        marker = ""
    cut = lambda w: [] if w.startswith(marker) else ivtff.segment(w, "eva-basic")
    tri = unit_trigrams(pages, cut)
    if len({u for t in tri for u in t if u != lm.WB}) >= 2:
        mapping, _ = climb(tri, table, letters, f"{budget['seed']}/{lang}/nomenclator/{tag}", budget,
                           group_swap=budget.get("substitution_group_swap", 0))
    else:
        mapping = {}
    codes = [w for w, _ in words.most_common() if w.startswith(marker)][:budget["word_code_limit"]]
    blocks = [block.split() for block in refcorpus.train_text(lang)]
    freq = Counter(w for block in blocks for w in block if whole_words or len(w) >= 2)
    candidates = [w for w, _ in freq.most_common(budget["candidate_words"])]
    assigned = dict(zip(codes, candidates))
    if assigned:
        ref = lm.KN(blocks, 2)
        context = {u: Counter() for u in assigned}
        spelled = {w: "".join(mapping.get(g, "") for g in cut(w)) for w in words}
        for page in pages:
            for line in page.lines:
                for left, right in zip(line.words, line.words[1:]):
                    if left in assigned:
                        context[left][(True, right)] += 1
                    if right in assigned:
                        context[right][(False, left)] += 1
        for _ in range(budget["assignment_sweeps"]):
            changed = False
            for code in codes:
                def score(word):
                    total = 0
                    for (before, other), n in context[code].items():
                        neighbor = assigned.get(other, spelled[other])
                        if before:
                            prob = ref.prob(neighbor, (word,))
                        else:
                            prob = ref.prob(word, (neighbor,))
                        total += n * math.log2(prob)
                    return total
                word = max(candidates, key=score)
                if word != assigned[code]:
                    assigned[code] = word
                    changed = True
            if not changed:
                break
    return {"marker": marker, "map": {**mapping, **assigned}}
