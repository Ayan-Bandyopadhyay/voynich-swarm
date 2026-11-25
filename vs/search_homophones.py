"""Frequency initialization and word-based refinement for homophonic substitution."""
import math
from collections import Counter, defaultdict

from . import ivtff, refcorpus


def refine_homophones(lang, pages, baseline, tri, table, letters, budget):
    from .search import climb

    reference = Counter(word for block in refcorpus.train_text(lang) for word in block.split())
    plaintext_counts = Counter()
    for word, count in reference.items():
        for letter in word:
            plaintext_counts[letter] += count

    words = Counter(tuple(ivtff.segment(word, "eva-basic"))
                    for page in pages for line in page.lines for word in line.words)
    unit_counts = Counter()
    contexts = defaultdict(list)
    for word, count in words.items():
        for unit in word:
            unit_counts[unit] += count
        for unit in set(word):
            contexts[unit].append((word, count))
    units = sorted(unit_counts, key=lambda u: (-unit_counts[u], u))
    if len(units) < 2 or not letters:
        return baseline

    # Try the submodel in which the most frequent letters receive the extra signs.
    ranked_letters = sorted(letters, key=lambda c: (-plaintext_counts[c], c))
    copies = dict.fromkeys(letters, 1)
    for i in range(max(0, len(units) - len(letters))):
        copies[ranked_letters[i % len(letters)]] += 1
    slots = sorted(((plaintext_counts[c] / copies[c], c, j)
                    for c in letters for j in range(copies[c])), reverse=True)
    initial = dict(zip(units, (letter for _, letter, _ in slots)))
    extra = dict(budget, restarts=budget["homophone_ranked_restarts"])
    ranked, _ = climb(tri, table, letters, f"{budget['seed']}/{lang}/substitution/ranked",
                      extra, init=initial, group_swap=budget.get("substitution_group_swap", 0.0))

    def word_score(mapping):
        return sum(count * math.log1p(reference["".join(mapping[u] for u in word)])
                   for word, count in words.items())

    candidates = [baseline, ranked]
    for starting_map in (baseline, ranked):
        mapping = starting_map.copy()
        for _ in range(budget["homophone_word_sweeps"]):
            changed = False
            for u in units:
                weights = Counter()
                for word, count in contexts[u]:
                    pattern = [None if x == u else mapping[x] for x in word]
                    for c in letters:
                        seen = reference["".join(c if x is None else x for x in pattern)]
                        if seen:
                            weights[c] += count * math.log1p(seen)
                if weights:
                    c = max(weights, key=weights.get)
                    if weights[c] > weights[mapping[u]]:
                        mapping[u] = c
                        changed = True
            if not changed:
                break
        candidates.append(mapping)
    return max(candidates, key=word_score)
