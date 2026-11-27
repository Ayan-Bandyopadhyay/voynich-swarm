"""Fit substitutions with a small inventory of repeated whole-word or glyph fillers."""

from collections import Counter

from . import ivtff, lm, refcorpus
from .search import climb
from .search_homophones import refine_homophones


SETTINGS = {
    "null_word_limit": 8,
    "null_word_max_share": 0.35,
    "null_word_min_share": 0.006,
    "null_word_frequency_ratio": 4,
    "null_initial_type_cap": 0.005,
    "null_glyph_limit": 2,
    "null_glyph_min_types": 12,
    "null_glyph_min_gain": 0.30,
    "null_refits": 2,
    "homophone_ranked_restarts": 1,
    "homophone_word_sweeps": 5,
}


def fit_mapping(lang, pages, counts, units, table, letters, seed, budget, mapping=None):
    trigrams = Counter()
    used = sorted({unit for word in counts for unit in units[word]})
    if not used or not letters:
        return {}
    for word, count in counts.items():
        glyphs = [lm.WB, lm.WB, *units[word], lm.WB]
        for trigram in zip(glyphs, glyphs[1:], glyphs[2:]):
            trigrams[trigram] += count
    if len(letters) == 1:
        return dict.fromkeys(used, letters[0])
    if len(used) == 1:
        def score(letter):
            return sum(count * table[tuple(lm.WB if unit == lm.WB else letter for unit in trigram)]
                       for trigram, count in trigrams.items())
        return {used[0]: max(letters, key=score)}
    initial = None
    if mapping:
        initial = {unit: mapping.get(unit, letters[0]) for unit in used}
    fitted, _ = climb(trigrams, table, letters, seed, budget, init=initial,
                      group_swap=budget.get("substitution_group_swap", 0.0))
    if initial is not None and budget["homophone_ranked_restarts"] and budget["homophone_word_sweeps"]:
        # Without a lexical check, the trigram objective can prefer collapsing
        # distinct glyphs onto one common letter even after fillers are removed.
        fitted = refine_homophones(lang, pages, fitted, trigrams, table, letters, budget,
                                   cut=lambda word: units.get(word, ()))
    return fitted


def word_nulls(counts, decoded, reference, budget):
    if not budget["null_word_limit"]:
        return ()
    total = counts.total()
    reference_total = reference.total()
    low = budget["null_word_min_share"] * total
    maximum = budget["null_word_max_share"] * total
    candidates = []
    for word, count in counts.items():
        expected = total * reference[decoded[word]] / max(reference_total, 1)
        surplus = count - budget["null_word_frequency_ratio"] * expected
        if low <= count <= maximum and surplus >= low:
            candidates.append((surplus, word))

    chosen = []
    dropped = 0
    for _, word in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if dropped + counts[word] <= maximum:
            chosen.append(word)
            dropped += counts[word]
            if len(chosen) >= budget["null_word_limit"]:
                break
    return tuple(sorted(chosen))


def glyph_nulls(units, mapping, reference, budget, previous=()):
    by_unit = {}
    for word, glyphs in units.items():
        for unit in set(glyphs):
            by_unit.setdefault(unit, []).append(word)

    def spell(word, removed):
        return "".join(mapping.get(unit, "") for unit in units[word] if unit not in removed)

    removed = set(previous)
    for _ in range(budget["null_glyph_limit"] - len(removed)):
        gain = []
        for unit in sorted(by_unit.keys() - removed):
            words = by_unit[unit]
            if len(words) < budget["null_glyph_min_types"]:
                continue
            next_removed = removed | {unit}
            # A single frequent spelling cannot account for the glyph's gain.
            extra = sum((spell(word, next_removed) in reference) - (spell(word, removed) in reference)
                        for word in words)
            gain.append((extra / len(words), unit))
        if not gain:
            break
        best, unit = max(gain)
        if best < budget["null_glyph_min_gain"]:
            break
        removed.add(unit)
    return tuple(sorted(removed))


def search(lang, pages, budget, tag, table, letters):
    counts = Counter(word for page in pages for line in page.lines for word in line.words)
    units = {word: ivtff.segment(word, "eva-basic") for word in counts}
    reference = Counter(word for paragraph in refcorpus.train_text(lang) for word in paragraph.split())
    seed = f"{budget['seed']}/{lang}/nulls/{tag}"

    # Before the first fit, limit any one frequent raw word's leverage on the
    # alphabet. Filler types can be among the most frequent words in the stream.
    cap = max(1, round(budget["null_initial_type_cap"] * counts.total()))
    capped = {word: min(count, cap) for word, count in counts.items()}
    mapping = fit_mapping(lang, pages, capped, units, table, letters, seed + "/initial", budget)

    null_words, null_glyphs = (), ()
    for i in range(budget["null_refits"]):
        decoded = {word: "".join(mapping.get(unit, "") for unit in glyphs if unit not in null_glyphs)
                   for word, glyphs in units.items()}
        words = word_nulls(counts, decoded, reference, budget)
        retained = {word: units[word] for word in units if word not in words}
        # Infer glyph nulls after an ordinary-word refit, where reference-word
        # matches are less likely to depend on a collapsed substitution.
        glyphs = glyph_nulls(retained, mapping, reference, budget, null_glyphs) if i else ()
        if (words, glyphs) == (null_words, null_glyphs) and i > 0:
            break
        null_words, null_glyphs = words, glyphs
        filtered = {word: [unit for unit in sequence if unit not in glyphs] for word, sequence in retained.items()}
        kept_counts = {word: counts[word] for word in filtered}
        mapping = fit_mapping(lang, pages, kept_counts, filtered, table, letters, f"{seed}/refit/{i}",
                              budget, mapping)

    return {"id": f"grid-{lang}-nulls-{tag}", "family": "nulls", "segmentation": "eva-basic",
            "target": {"language": lang, "period": "grid search"},
            "key": {"map": mapping, "null_words": list(null_words), "null_glyphs": list(null_glyphs)},
            "search": {"budget": dict(budget)}}
