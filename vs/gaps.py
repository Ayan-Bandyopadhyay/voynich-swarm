"""Public calibration of short occurrence gaps within matched paragraph runs."""

from math import sqrt
from random import Random
from statistics import mean

from . import corpus


EVA = frozenset("acdefghiklmnopqrsty")
SHORT_LAGS = tuple(range(1, 6))
MIN_PAIRS = 25


def eligible_line_ids(pages):
    """Keep nonempty paragraph lines written entirely in the declared EVA alphabet."""
    return {line.id for page in pages for line in page.lines
            if line.unit == "P" and line.words and all(EVA.issuperset(word) for word in line.words)}


def paragraph_runs(pages, retained):
    """Build word runs in reading order. Omitting a paragraph line breaks a run."""
    runs = []
    for page in pages:
        run = []
        for line in page.lines:
            if line.unit != "P":
                continue
            keep = line.id in retained
            if (line.para_start or not keep) and run:
                runs.append(run)
                run = []
            if keep:
                run.extend(line.words)
            if line.para_end and run:
                runs.append(run)
                run = []
        if run:
            runs.append(run)
    return runs


def hit_positions(words, symbol):
    """Use raw EVA characters and one space between words, including across retained lines."""
    return [i for i, char in enumerate(" ".join(words)) if char == symbol]


def gap_curve(hit_groups, lags):
    """Return {lag: (correlation, pair count)} with endpoints centered within each run."""
    centered = []
    for hits in hit_groups:
        gaps = [end - start for start, end in zip(hits, hits[1:])]
        if len(gaps) > 2:
            center = mean(gaps)
            centered.append([gap - center for gap in gaps])

    curve = {}
    for lag in lags:
        pairs = 0
        xx = yy = xy = 0.0
        for gaps in centered:
            if len(gaps) <= lag + 1:
                continue
            left, right = gaps[:-lag], gaps[lag:]
            pairs += len(left)
            xx += sum(x * x for x in left)
            yy += sum(y * y for y in right)
            xy += sum(x * y for x, y in zip(left, right))
        curve[lag] = (xy / sqrt(xx * yy) if pairs >= MIN_PAIRS and xx and yy else None, pairs)
    return curve


def word_order_test(runs, symbol, permutations=399):
    """Permute intact words separately within each original run, and keep the run order."""
    rng = Random(408)
    observed = gap_curve((hit_positions(run, symbol) for run in runs), SHORT_LAGS)
    null = []
    for _ in range(permutations):
        shuffled = []
        for run in runs:
            words = list(run)
            rng.shuffle(words)
            shuffled.append(hit_positions(words, symbol))
        null.append(gap_curve(shuffled, SHORT_LAGS))

    # Average only lags defined on both the observed text and every permutation.
    lags = [lag for lag in SHORT_LAGS if all(curve[lag][0] is not None for curve in [observed, *null])]
    result = {"pairs_by_lag": {lag: pairs for lag, (_, pairs) in observed.items()}, "lags": lags,
              "permutations": permutations, "observed": None, "null_mean": None, "p": None}
    if lags:
        value = mean(observed[lag][0] for lag in lags)
        draws = [mean(curve[lag][0] for lag in lags) for curve in null]
        p = (1 + sum(draw >= value - 1e-12 for draw in draws)) / (len(draws) + 1)
        result.update(observed=value, null_mean=mean(draws), p=p)
    return result


def practice():
    """Assess EVA o on the same eligible public lines in ZL and Takahashi."""
    pages = {edition: corpus.split_pages("practice", edition)[1] for edition in ("zl", "it")}
    retained = eligible_line_ids(pages["zl"]) & eligible_line_ids(pages["it"])
    results = {}
    for edition, folios in pages.items():
        runs = paragraph_runs(folios, retained)
        results[edition] = {"pages": sum(any(line.id in retained for line in page.lines) for page in folios),
                            "runs": len(runs), **word_order_test(runs, "o")}
    return {"split": "practice", "symbol": "o", "matched_lines": len(retained), "results": results}
