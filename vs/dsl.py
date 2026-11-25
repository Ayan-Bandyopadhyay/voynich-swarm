"""Measurement language: a fact claim is a declarative spec interpreted by this trusted code.
No agent code is ever executed by the scorer. A spec is JSON:

  {"scope":     {"hand": "1"|..., "language": "A"|"B", "section": "H"|...},        (optional)
   "select":    {"unit": ["P"], "position": "line_final", "certain": true},       (optional)
   "statistic": {...one of the forms below...},
   "compare":   [ ...one to four tests, all must pass... ]}

Selections may also set language to A or B to compare the two dialects within a shared scope.
positions: any | line_initial | line_final | mid_line | para_initial (first word of a paragraph)
           | para_first_line (any word on a paragraph's first line)
           | not_para_first_line (paragraph text that is not on a first line; never labels or rings)
           | para_first_line_rest / not_para_first_line_rest (the same two, leaving out the first word of
             each line: a first-line pattern that is more than the paragraph's opening word; found by the attack on F-008)
features:  "word" | {"glyph_at": i} (eva-basic glyphs; negative counts from the end)
           | {"prefix": n} | {"suffix": n} (in glyphs, 1..8) | "length" | "glyph" (every glyph of the word)

statistics:
  {"rate": {"feature": F, "in": [values]}}                 share of selected tokens whose feature is in values
  {"ratio": {"feature": F, "in": [values], "of": SELECT, "to": SELECT}}   rate under one selection over another
  {"entropy": F}                                           plug-in entropy of the feature (bits)
  {"cond_entropy": F}                                      H(next word's F | previous word's F), adjacent words in a line
  {"glyph_cond_entropy": k}                                H(glyph | previous k glyphs), k = 1..3, inside lines with word
                                                           boundaries as a symbol (k=1 is Bennett's second-order entropy)
  {"adjacent_mi": F}                                       adjacent mutual information minus the same after shuffling
                                                           each line (so page and section vocabulary cancel)
  {"edge_mi": true}                                        MI between a word's last glyph and the next word's first glyph
  {"edge_mi_break": true}                                  edge MI within lines minus edge MI across line breaks (a line's
                                                           last word with the next line's first word, same page); each
                                                           shuffle-corrected, within-line pairs subsampled to the
                                                           across-line count (10 fixed draws) so both carry equal bias
  {"line_repeat_excess": true}                              share of words repeated on the previous numbered line minus the share
                                                           repeated four lines back, within a page, excluding one-character words
  {"line_near_excess": {"min_length": L}}                  the same comparison for similar words (Timm 2014): share of words of
                                                           length >= L (default 4) with a word at edit distance exactly 1 on the
                                                           previous numbered line, minus the share with one four lines back
  {"repeat_ngram": n}                                      share of word n-grams (n<=6) that occur at least twice
  {"hapax_share": true} | {"zipf_slope": ranks} | {"mean_length": true}
  {"near_copy": {"window": k, "min_length": L}}            share of words of length >= L within edit distance exactly 1
                                                           of one of the previous k (1..50) on the page
  {"page_similarity": {"within": d, "min_words": m}}       median cosine of word-count vectors of two pages at most d pages
                                                           apart in manuscript order (d 1..50), minus the median for pages
                                                           farther apart; pages with fewer than m (default 40) selected words
                                                           are left out. Distance is counted in the manuscript's page order,
                                                           so it stays meaningful on a sample of pages
  {"page_reuse": {"min_length": L}}                        share of words of length >= L already written earlier on the page
  {"context_mi": {"feature": F, "by": B}}                  MI between the feature and where the word stands; B is
                                                           page | section | unit | line_position (initial/mid/final).
                                                           Plug-in MI is biased upward: only meaningful against a null

compare (one to four; all must pass; a spec with none is refused):
  {"op": ">=" | "<=" | ">" | "<", "value": x}              x finite
  {"reference": "below_all" | "above_all" | "inside_range", "margin": m}     m >= 0
       the same statistic on every reference language, on that language's words poured into the exact layout of
       the selected tokens (same pages, lines, gaps and count), so size and shape are matched. Languages with
       fewer words than the selection are left out; at least three must remain. Only for statistics whose
       features carry over to another script (not rate, ratio or context_mi).
  {"null": "shuffle_within_line" | "shuffle_within_page" | "shuffle_within_section" | "shuffle_across_pages"
           | "shuffle_labels" | "shuffle_labels_within_page",
   "perms": N (<= 400), "p": alpha (<= 0.05), "direction": "greater" | "less"}
       the statistic must be extreme against the null (one-sided permutation p-value, ties count against).
       shuffle_labels reassigns which words of a section are the labels (labels trade places with words
       of running text of the same section; all other words stay where they are, so word order elsewhere is
       untouched). shuffle_labels_within_page does the same inside each page (stricter; labels on pages
       without running text cannot move).

Rules that keep a pass from being hollow (each has a test in tests/test_dsl.py):
  - unknown keys anywhere are refused (a misspelt "scope" or "select" used to be silently ignored);
  - at least one comparison; thresholds, margins and alpha must be finite, margins >= 0, alpha <= 0.05, and
    perms large enough to reach alpha;
  - a statistic that is undefined on the selection (fewer than 30 tokens, or fewer than 30 adjacent pairs
    / n-grams / long words for the statistics that count those) is refused, not reported as 0;
  - a value that is not finite (a ratio with an empty denominator) never passes;
  - adjacency means adjacent in the line: words either side of a dropped (uncertain or unselected) word
    are not a pair;
  - a null that cannot move the statistic (all permuted values equal the observed one) is refused.

Bounded cost by construction: n-grams <= 6, windows <= 50, permutations <= 400 per null, comparisons <= 4.
"""
import math, random
from collections import Counter
from functools import lru_cache
from . import ivtff

UNCERTAIN = ivtff.uncertain
MAX_COMPARE, MAX_PERMS, MAX_ALPHA = 4, 400, 0.05
MIN_TOKENS = 30          # selected tokens, and counted units (pairs, n-grams, long words) where a statistic counts them
UNITS = {"P", "L", "C", "R"}
POSITIONS = {"any", "line_initial", "line_final", "mid_line", "para_initial", "para_first_line", "not_para_first_line",
             "para_first_line_rest", "not_para_first_line_rest"}
NAN = float("nan")


@lru_cache(maxsize=200_000)
def SEG(w):
    return tuple(ivtff.segment(w, "eva-basic"))


class SpecError(ValueError):
    pass


def _keys(d, allowed, what, required=()):
    if not isinstance(d, dict):
        raise SpecError(f"{what} must be an object")
    extra = set(d) - set(allowed)
    if extra:
        raise SpecError(f"{what}: unknown key(s) {sorted(extra)}; allowed: {sorted(allowed)}")
    for k in required:
        if k not in d:
            raise SpecError(f"{what} needs {k!r}")


def _num(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise SpecError(f"{what} must be a finite number")
    return float(x)


def _int(x, lo, hi, what):
    if isinstance(x, bool) or not isinstance(x, int) or not lo <= x <= hi:
        raise SpecError(f"{what} must be an integer in {lo}..{hi}")
    return x


# ------------------------------------------------------------- tokens

def tokens(pages, scope=None):
    """One record per word, with its layout context."""
    scope = scope or {}
    out = []
    for pi, p in enumerate(pages):
        if scope.get("hand") and str(p.hand) != str(scope["hand"]):
            continue
        if scope.get("language") and p.language != scope["language"]:
            continue
        if scope.get("section") and p.section != scope["section"]:
            continue
        first_line = True
        for ln in p.lines:
            if not ln.words:
                continue
            pfl = ln.unit == "P" and (ln.para_start or first_line)
            n = len(ln.words)
            for k, w in enumerate(ln.words):
                out.append({"w": w, "page": pi, "section": p.section, "line": (pi, ln.n), "k": k, "n": n,
                            "language": p.language, "unit": ln.unit, "pfl": pfl, "pinit": pfl and k == 0,
                            "order": p.order})
            first_line = ln.para_end if ln.unit == "P" else first_line
    return out


def check_select(sel, what="select"):
    sel = sel or {}
    _keys(sel, {"unit", "position", "certain", "language"}, what)
    if "language" in sel and sel["language"] not in ("A", "B"):
        raise SpecError(f"{what}.language must be A or B")
    u = sel.get("unit") or []
    if not isinstance(u, list) or set(u) - UNITS:
        raise SpecError(f"{what}.unit is a list from {sorted(UNITS)}")
    if sel.get("position", "any") not in POSITIONS:
        raise SpecError(f"unknown position {sel.get('position')!r}")
    if not isinstance(sel.get("certain", True), bool):
        raise SpecError(f"{what}.certain is true or false")
    return sel


def select(toks, sel):
    sel = check_select(sel)
    units = set(sel.get("unit") or [])
    pos = sel.get("position", "any")
    certain = sel.get("certain", True)
    language = sel.get("language")
    keep = []
    for t in toks:
        if language and t["language"] != language:
            continue
        if units and t["unit"] not in units:
            continue
        if certain and UNCERTAIN(t["w"]):
            continue
        ok = {"any": True, "line_initial": t["k"] == 0, "line_final": t["k"] == t["n"] - 1,
              "mid_line": 0 < t["k"] < t["n"] - 1, "para_initial": t["pinit"], "para_first_line": t["pfl"],
              "not_para_first_line": t["unit"] == "P" and not t["pfl"],
              "para_first_line_rest": t["pfl"] and t["k"] > 0,
              "not_para_first_line_rest": t["unit"] == "P" and not t["pfl"] and t["k"] > 0}[pos]
        if ok:
            keep.append(t)
    return keep


def check_feature(f):
    if f in ("word", "length", "glyph"):
        return
    if isinstance(f, dict) and len(f) == 1:
        (k, v), = f.items()
        if k == "glyph_at":
            _int(v, -12, 11, "glyph_at")
            return
        if k in ("prefix", "suffix"):
            _int(v, 1, 8, k)
            return
    raise SpecError(f"unknown feature {f!r}")


def feature(f, w):
    if f == "word":
        return [w]
    if f == "length":
        return [len(SEG(w))]
    if f == "glyph":
        return list(SEG(w))
    if isinstance(f, dict):
        g = SEG(w)
        if "glyph_at" in f:
            i = int(f["glyph_at"])
            return [g[i]] if -len(g) <= i < len(g) else []
        if "prefix" in f:
            return ["".join(g[:int(f["prefix"])])]
        if "suffix" in f:
            return ["".join(g[-int(f["suffix"]):])]
    raise SpecError(f"unknown feature {f!r}")


def lines_of(toks):
    by = {}
    for t in toks:
        by.setdefault(t["line"], []).append(t)
    return [sorted(v, key=lambda t: t["k"]) for _k, v in sorted(by.items())]


def runs_of(toks):
    """Maximal runs of words that are truly adjacent in a line (a dropped word breaks the run)."""
    out = []
    for ln in lines_of(toks):
        run = [ln[0]]
        for t in ln[1:]:
            if t["k"] == run[-1]["k"] + 1:
                run.append(t)
            else:
                out.append(run)
                run = [t]
        out.append(run)
    return out


# ------------------------------------------------------------- statistics

def _entropy(c):
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0


def _mi(pairs):
    pc, a, b = Counter(pairs), Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    n = sum(pc.values())
    return sum(v / n * math.log2(v * n / (a[x] * b[y])) for (x, y), v in pc.items()) if n else 0.0


def _edge_break(toks, draws=10):
    """Edge-glyph MI within lines minus across line breaks, each corrected by its shuffled value."""
    edge = lambda x, y: (SEG(x["w"])[-1], SEG(y["w"])[0])
    within = [edge(x, y) for r in runs_of(toks) for x, y in zip(r, r[1:])]
    lns = lines_of(toks)
    across = [edge(a[-1], b[0]) for a, b in zip(lns, lns[1:])
              if a[-1]["line"][0] == b[0]["line"][0] and a[-1]["k"] == a[-1]["n"] - 1 and b[0]["k"] == 0]
    n = len(across)
    if n < MIN_TOKENS or len(within) < n:
        return NAN

    def corrected(pairs, rng):
        ys = [y for _x, y in pairs]
        rng.shuffle(ys)
        return _mi(pairs) - _mi(list(zip([x for x, _y in pairs], ys)))

    rng = random.Random(1)
    w = sum(corrected(rng.sample(within, n), rng) for _ in range(draws)) / draws
    a = sum(corrected(list(across), rng) for _ in range(draws)) / draws
    return w - a


def _page_similarity(toks, within, min_words):
    """Median cosine of word counts for pages at most `within` apart in manuscript order, minus farther pairs."""
    pages = {}
    for t in toks:
        pages.setdefault(t["order"], Counter())[t["w"]] += 1
    vec = sorted((o, c, math.sqrt(sum(v * v for v in c.values()))) for o, c in pages.items()
                 if sum(c.values()) >= min_words)
    near, far = [], []
    for i, (o1, c1, n1) in enumerate(vec):
        for o2, c2, n2 in vec[i + 1:]:
            cos = sum(v * c2[w] for w, v in c1.items() if w in c2) / (n1 * n2)
            (near if o2 - o1 <= within else far).append(cos)
    if len(near) < MIN_TOKENS or len(far) < MIN_TOKENS:
        return NAN
    med = lambda xs: (lambda s: (s[(len(s) - 1) // 2] + s[len(s) // 2]) / 2)(sorted(xs))
    return med(near) - med(far)


def _edit1(a, b):
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _context(t, by):
    if by == "line_position":
        return "initial" if t["k"] == 0 else "final" if t["k"] == t["n"] - 1 else "mid"
    return t[by]


def check_statistic(st):
    if not isinstance(st, dict) or len(st) != 1:
        raise SpecError("statistic is one {name: args}")
    (name, arg), = st.items()
    if name in ("rate", "ratio"):
        _keys(arg, {"feature", "in"} | ({"of", "to"} if name == "ratio" else set()), name,
              ("feature", "in") + (("of", "to") if name == "ratio" else ()))
        check_feature(arg["feature"])
        if not isinstance(arg["in"], list) or not arg["in"] or not all(isinstance(v, (str, int)) for v in arg["in"]):
            raise SpecError(f"{name}.in is a non-empty list of values")
        if name == "ratio":
            check_select(arg["of"], "ratio.of")
            check_select(arg["to"], "ratio.to")
    elif name in ("entropy", "cond_entropy", "adjacent_mi"):
        check_feature(arg)
    elif name == "glyph_cond_entropy":
        _int(arg, 1, 3, "glyph_cond_entropy order")
    elif name == "repeat_ngram":
        _int(arg, 1, 6, "repeat_ngram n")
    elif name == "zipf_slope":
        _int(arg, 3, 100_000, "zipf_slope ranks")
    elif name in ("edge_mi", "edge_mi_break", "hapax_share", "mean_length", "line_repeat_excess"):
        if arg is not True:
            raise SpecError(f"{name} takes true")
    elif name == "line_near_excess":
        _keys(arg, {"min_length"}, name)
        _int(arg.get("min_length", 4), 1, 40, "line_near_excess min_length")
    elif name == "near_copy":
        _keys(arg, {"window", "min_length"}, name)
        _int(arg.get("window", 10), 1, 50, "near_copy window")
        _int(arg.get("min_length", 6), 1, 40, "near_copy min_length")
    elif name == "page_similarity":
        _keys(arg, {"within", "min_words"}, name, ("within",))
        _int(arg["within"], 1, 50, "page_similarity within")
        _int(arg.get("min_words", 40), 10, 10_000, "page_similarity min_words")
    elif name == "page_reuse":
        _keys(arg, {"min_length"}, name)
        _int(arg.get("min_length", 1), 1, 40, "page_reuse min_length")
    elif name == "context_mi":
        _keys(arg, {"feature", "by"}, name, ("feature", "by"))
        check_feature(arg["feature"])
        if arg["by"] not in ("page", "section", "unit", "line_position"):
            raise SpecError("context_mi.by is page | section | unit | line_position")
    else:
        raise SpecError(f"unknown statistic {name!r}")
    return name


def statistic(st, toks, all_toks):
    """The value, or NaN where the statistic is undefined on this selection (too little to count)."""
    name = check_statistic(st)
    arg = st[name]
    if name == "ratio":
        vals = set(arg["in"])
        num, den = select(all_toks, arg["of"]), select(all_toks, arg["to"])
        if len(num) < MIN_TOKENS or len(den) < MIN_TOKENS:
            return NAN
        r = lambda ts: sum(any(v in vals for v in feature(arg["feature"], t["w"])) for t in ts) / len(ts)
        a, b = r(num), r(den)
        return a / b if b else (float("inf") if a else NAN)
    if len(toks) < MIN_TOKENS:
        return NAN
    if name == "rate":
        vals = set(arg["in"])
        return sum(any(v in vals for v in feature(arg["feature"], t["w"])) for t in toks) / len(toks)
    if name == "entropy":
        return _entropy(Counter(v for t in toks for v in feature(arg, t["w"])))
    if name in ("cond_entropy", "adjacent_mi", "edge_mi"):
        runs = runs_of(toks)
        if sum(len(r) - 1 for r in runs) < MIN_TOKENS:
            return NAN
        if name == "edge_mi":
            return _mi([(SEG(x["w"])[-1], SEG(y["w"])[0]) for r in runs for x, y in zip(r, r[1:])])
        fw = lambda w: tuple(feature(arg, w))
        pairs = [(fw(x["w"]), fw(y["w"])) for r in runs for x, y in zip(r, r[1:])]
        if name == "cond_entropy":
            return _entropy(Counter(pairs)) - _entropy(Counter(p[0] for p in pairs))
        rng = random.Random(1)
        spairs = []
        for r in runs:
            ws = [t["w"] for t in r]
            rng.shuffle(ws)
            spairs += [(fw(x), fw(y)) for x, y in zip(ws, ws[1:])]
        return _mi(pairs) - _mi(spairs)
    if name == "edge_mi_break":
        return _edge_break(toks)
    if name == "glyph_cond_entropy":
        k = int(arg)
        ctx, full = Counter(), Counter()
        for r in runs_of(toks):
            s = ["_"] * k
            for t in r:
                s += list(SEG(t["w"])) + ["_"]
            for i in range(k, len(s)):
                ctx[tuple(s[i - k:i])] += 1
                full[tuple(s[i - k:i + 1])] += 1
        return _entropy(full) - _entropy(ctx)
    if name == "repeat_ngram":
        n = int(arg)
        c = Counter(tuple(t["w"] for t in r[i:i + n]) for r in runs_of(toks) for i in range(len(r) - n + 1))
        tot = sum(c.values())
        return sum(v for v in c.values() if v >= 2) / tot if tot >= MIN_TOKENS else NAN
    if name == "page_similarity":
        return _page_similarity(toks, int(arg["within"]), int(arg.get("min_words", 40)))
    if name in ("line_repeat_excess", "line_near_excess"):
        # Use the same current words for both lags. Require five consecutive
        # selected lines on one page so gaps do not become spurious neighbors.
        words = {}
        for t in toks:
            words.setdefault(t["line"], []).append(t["w"])
        vocabulary = {line: set(ws) for line, ws in words.items()}
        if name == "line_repeat_excess":
            L, on = 2, lambda word, voc: word in voc
        else:
            L, on = int(arg.get("min_length", 4)), lambda word, voc: any(_edit1(word, u) for u in voc)
        hits = eligible = 0
        for (page, line), ws in words.items():
            if not all((page, line - lag) in words for lag in range(1, 5)):
                continue
            near, far = vocabulary[page, line - 1], vocabulary[page, line - 4]
            for word in ws:
                if len(word) >= L:
                    eligible += 1
                    hits += on(word, near) - on(word, far)
        return hits / eligible if eligible >= MIN_TOKENS else NAN
    if name == "hapax_share":
        c = Counter(t["w"] for t in toks)
        return sum(1 for v in c.values() if v == 1) / len(c)
    if name == "zipf_slope":
        fr = [f for _w, f in Counter(t["w"] for t in toks).most_common(int(arg))]
        if len(fr) < 3:
            return NAN
        xs = [math.log10(i + 1) for i in range(len(fr))]
        ys = [math.log10(f) for f in fr]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    if name == "mean_length":
        return sum(len(SEG(t["w"])) for t in toks) / len(toks)
    if name in ("near_copy", "page_reuse"):
        by_page = {}
        for t in toks:
            by_page.setdefault(t["page"], []).append(t["w"])
        hits = n = 0
        if name == "page_reuse":
            L = int(arg.get("min_length", 1))
            for ws in by_page.values():
                seen = set()
                for w in ws:
                    if len(w) >= L:
                        n += 1
                        hits += w in seen
                    seen.add(w)
        else:
            k, L = int(arg.get("window", 10)), int(arg.get("min_length", 6))
            for ws in by_page.values():
                for i, w in enumerate(ws):
                    if len(w) < L:
                        continue
                    n += 1
                    hits += any(_edit1(w, u) for u in ws[max(0, i - k):i])
        return hits / n if n >= MIN_TOKENS else NAN
    if name == "context_mi":
        return _mi([(v, _context(t, arg["by"])) for t in toks for v in feature(arg["feature"], t["w"])])
    raise SpecError(f"unknown statistic {name!r}")


# ------------------------------------------------------------- nulls and references

# statistics whose features mean the same thing in another script, so a reference language can be measured
LAYOUT_FREE = {"entropy", "hapax_share", "zipf_slope", "mean_length", "repeat_ngram", "cond_entropy", "adjacent_mi",
               "edge_mi", "near_copy", "glyph_cond_entropy", "page_reuse", "line_repeat_excess",
               "line_near_excess"}
MIN_REFERENCES = 3

_NULL_KEY = {"shuffle_within_line": lambda t: t["line"], "shuffle_within_page": lambda t: t["page"],
             "shuffle_within_section": lambda t: t["section"], "shuffle_across_pages": lambda t: 0,
             "shuffle_labels": lambda t: t["section"], "shuffle_labels_within_page": lambda t: t["page"]}


def _shuffled(all_toks, how, rng):
    key = _NULL_KEY.get(how)
    if key is None:
        raise SpecError(f"unknown null {how!r}")
    groups = {}
    for i, t in enumerate(all_toks):
        groups.setdefault(key(t), []).append(i)
    words = [t["w"] for t in all_toks]
    for g in groups.values():
        if how.startswith("shuffle_labels"):
            # reassign which words of the stratum are the labels; every other word stays in place
            lab = [i for i in g if all_toks[i]["unit"] == "L"]
            if not lab or len(lab) == len(g):
                continue
            chosen = rng.sample(g, len(lab))
            cs = set(chosen)
            new_labels = [words[i] for i in chosen]
            vacated = [i for i in chosen if all_toks[i]["unit"] != "L"]
            displaced = [words[i] for i in lab if i not in cs]
            rng.shuffle(displaced)
            for i, w in zip(lab, new_labels):
                words[i] = w
            for i, w in zip(vacated, displaced):
                words[i] = w
        else:
            ws = [words[i] for i in g]
            rng.shuffle(ws)
            for i, w in zip(g, ws):
                words[i] = w
    return [dict(t, w=w) for t, w in zip(all_toks, words)]


def _reference_values(st, toks):
    """The statistic on each reference language poured into the layout of the selected tokens."""
    from .facts import ref_langs, ref_words
    vals = {}
    for lang in ref_langs():
        ws = ref_words(lang, len(toks))
        if len(ws) < len(toks):
            continue  # too short to match the size: a smaller sample would bias every plug-in statistic
        ts = [dict(t, w=w) for t, w in zip(toks, ws)]
        vals[lang] = statistic(st, ts, ts)
    if len(vals) < MIN_REFERENCES:
        raise SpecError(f"fewer than {MIN_REFERENCES} reference languages have {len(toks)} words to match this selection")
    return vals


def check(spec):
    """Shape and bounds of a spec; raises SpecError. Nothing here touches the pages."""
    _keys(spec, {"scope", "select", "statistic", "compare"}, "spec", ("statistic", "compare"))
    scope = spec.get("scope") or {}
    _keys(scope, {"hand", "language", "section"}, "scope")
    if not all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in scope.values()):
        raise SpecError("scope values are strings")
    check_select(spec.get("select"))
    name = check_statistic(spec["statistic"])
    cmp_ = spec["compare"]
    if not isinstance(cmp_, list) or not 1 <= len(cmp_) <= MAX_COMPARE:
        raise SpecError(f"compare is a list of 1 to {MAX_COMPARE} tests (a claim with no test is not a claim)")
    for c in cmp_:
        if not isinstance(c, dict) or sum(k in c for k in ("op", "reference", "null")) != 1:
            raise SpecError(f"unknown comparison {c!r}")
        if "op" in c:
            _keys(c, {"op", "value"}, "comparison", ("value",))
            if c["op"] not in (">=", "<=", ">", "<"):
                raise SpecError(f"unknown op {c['op']!r}")
            _num(c["value"], "threshold value")
        elif "reference" in c:
            _keys(c, {"reference", "margin"}, "comparison")
            if c["reference"] not in ("below_all", "above_all", "inside_range"):
                raise SpecError(f"unknown reference test {c['reference']!r}")
            if _num(c.get("margin", 0), "margin") < 0:
                raise SpecError("margin must be >= 0 (a negative margin passes anything)")
            if name not in LAYOUT_FREE:
                raise SpecError(f"reference comparison needs a statistic that carries over to another script ({sorted(LAYOUT_FREE)})")
        else:
            _keys(c, {"null", "perms", "p", "direction"}, "comparison")
            if c["null"] not in _NULL_KEY:
                raise SpecError(f"unknown null {c['null']!r}")
            if c.get("direction", "greater") not in ("greater", "less"):
                raise SpecError("direction is greater or less")
            alpha = _num(c.get("p", 0.01), "p")
            if not 0 < alpha <= MAX_ALPHA:
                raise SpecError(f"p must be in (0, {MAX_ALPHA}]")
            perms = min(_int(c.get("perms", 200), 1, 10 ** 9, "perms"), MAX_PERMS)
            if 1 / (perms + 1) > alpha:
                raise SpecError(f"{perms} permutations cannot reach p <= {alpha}")
    return spec


def canonical(spec):
    """What a spec measures and how it is tested, without the numbers a resubmission could turn:
    thresholds, margins, alpha and the permutation count. Two specs with the same canonical form are
    the same claim for the record (vs/registry.py), however their JSON is ordered or defaulted."""
    check(spec)
    def sel(selection):
        selection = selection or {}
        result = {"unit": sorted(set(selection.get("unit") or [])), "position": selection.get("position", "any"),
                  "certain": selection.get("certain", True)}
        if "language" in selection:
            result["language"] = selection["language"]
        return result

    (name, arg), = spec["statistic"].items()
    if name in ("rate", "ratio"):
        arg = dict(arg, **{"in": sorted(set(arg["in"]), key=str)})
        if name == "ratio":
            arg = dict(arg, of=sel(arg["of"]), to=sel(arg["to"]))
    elif name == "near_copy":
        arg = {"window": arg.get("window", 10), "min_length": arg.get("min_length", 6)}
    elif name == "page_reuse":
        arg = {"min_length": arg.get("min_length", 1)}
    elif name == "line_near_excess":
        arg = {"min_length": arg.get("min_length", 4)}
    tests = set()
    for c in spec["compare"]:
        if "op" in c:
            tests.add("op" + c["op"][0])
        elif "reference" in c:
            tests.add("reference:" + c["reference"])
        else:
            tests.add(f"null:{c['null']}:{c.get('direction', 'greater')}")
    return {"scope": {k: str(v) for k, v in sorted((spec.get("scope") or {}).items()) if v},
            "select": sel(spec.get("select")), "statistic": {name: arg}, "tests": sorted(tests)}


def evaluate(spec, pages):
    """Returns {"value", "pass", "detail"} for a spec on these pages."""
    check(spec)
    all_toks = tokens(pages, spec.get("scope"))
    toks = select(all_toks, spec.get("select"))
    if not toks:
        raise SpecError("the selection is empty")
    st = spec["statistic"]
    v = statistic(st, toks, all_toks)
    if v != v:
        raise SpecError(f"the statistic is undefined on this selection ({len(toks)} tokens): it needs at least "
                        f"{MIN_TOKENS} tokens, and {MIN_TOKENS} pairs / n-grams / long words where it counts those")
    finite = math.isfinite(v)
    detail, ok = {"tokens": len(toks)}, finite
    if not finite:
        detail["not_finite"] = "a value that is not finite never passes"
    for c in spec["compare"]:
        if "op" in c:
            x = float(c["value"])
            r = finite and {">=": v >= x, "<=": v <= x, ">": v > x, "<": v < x}[c["op"]]
            detail[f"{c['op']} {x}"] = r
            ok &= r
        elif "reference" in c:
            refs = _reference_values(st, toks)
            m = float(c.get("margin", 0))
            lo, hi = min(refs.values()), max(refs.values())
            r = all(math.isfinite(x) for x in refs.values()) and \
                {"below_all": v <= lo - m, "above_all": v >= hi + m, "inside_range": lo <= v <= hi}[c["reference"]]
            detail["reference"] = {k: round(x, 5) for k, x in refs.items()}
            ok &= r
        else:
            perms = min(int(c.get("perms", 200)), MAX_PERMS)
            rng = random.Random(408)
            more, moved = 0, False
            greater = c.get("direction", "greater") == "greater"
            for _ in range(perms):
                sh = _shuffled(all_toks, c["null"], rng)
                sv = statistic(st, select(sh, spec.get("select")), sh)
                moved |= sv == sv and abs(sv - v) > 1e-12 if finite else sv != v
                # an undefined permuted value counts against the claim
                more += (sv != sv) or ((sv >= v) if greater else (sv <= v))
            if not moved:
                raise SpecError(f"{c['null']} cannot move this statistic on this selection: it is no test of it")
            p = (more + 1) / (perms + 1)
            r = p <= float(c.get("p", 0.01))
            detail[c["null"]] = {"p": round(p, 4), "perms": perms}
            ok &= r
    return {"value": round(v, 6) if isinstance(v, float) and finite else v, "pass": bool(ok), "detail": detail}
