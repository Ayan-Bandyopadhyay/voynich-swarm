"""Measurement language: a fact claim is a declarative spec interpreted by this trusted code.
No agent code is ever executed by the scorer. A spec is JSON:

  {"scope":     {"hand": "1"|..., "language": "A"|"B", "section": "H"|...},        (optional)
   "select":    {"unit": ["P"], "position": "line_final", "certain": true},       (optional)
   "statistic": {...one of the forms below...},
   "compare":   [ ...one or more tests, all must pass... ]}

positions: any | line_initial | line_final | mid_line | para_initial (first word of a paragraph)
           | para_first_line (any word on a paragraph's first line) | not_para_first_line
features:  "word" | {"glyph_at": i} (eva-basic glyphs; negative counts from the end)
           | {"prefix": n} | {"suffix": n} (in glyphs) | "length" | "glyph" (every glyph of the word)

statistics:
  {"rate": {"feature": F, "in": [values]}}                 share of selected tokens whose feature is in values
  {"ratio": {"feature": F, "in": [values], "of": SELECT, "to": SELECT}}   rate under one selection over another
  {"entropy": F}                                           plug-in entropy of the feature (bits)
  {"cond_entropy": F}                                      H(next | previous) within lines
  {"adjacent_mi": F}                                       adjacent mutual information minus the line-shuffled value
  {"edge_mi": true}                                        MI between a word's last glyph and the next word's first glyph
  {"repeat_ngram": n}                                      share of word n-grams (n<=6) that occur at least twice
  {"hapax_share": true} | {"zipf_slope": ranks} | {"mean_length": true}
  {"near_copy": {"window": k, "min_length": L}}            share of words of length >= L within edit distance 1 of one of the previous k

compare (all must pass):
  {"op": ">=" | "<=" | ">" | "<", "value": x}
  {"reference": "below_all" | "above_all" | "inside_range", "margin": m}
       the same statistic on every reference language at matched size (flat lines of 8 words: only for statistics that do not use layout)
  {"null": "shuffle_within_line" | "shuffle_within_page" | "shuffle_within_section" | "shuffle_across_pages" | "shuffle_labels",
   "perms": N (<= 400), "p": alpha, "direction": "greater" | "less"}
       the statistic must be extreme against the null (one-sided permutation p-value)

Bounded cost by construction: n-grams <= 6, windows <= 50, permutations <= 400.
"""
import math, random
from collections import Counter
from . import ivtff

UNCERTAIN = ivtff.uncertain
SEG = lambda w: ivtff.segment(w, "eva-basic")


class SpecError(ValueError):
    pass


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
                            "unit": ln.unit, "pfl": pfl, "pinit": pfl and k == 0})
            first_line = ln.para_end if ln.unit == "P" else first_line
    return out


def select(toks, sel):
    sel = sel or {}
    units = set(sel.get("unit") or [])
    pos = sel.get("position", "any")
    certain = sel.get("certain", True)
    keep = []
    for t in toks:
        if units and t["unit"] not in units:
            continue
        if certain and UNCERTAIN(t["w"]):
            continue
        ok = {"any": True, "line_initial": t["k"] == 0, "line_final": t["k"] == t["n"] - 1,
              "mid_line": 0 < t["k"] < t["n"] - 1, "para_initial": t["pinit"], "para_first_line": t["pfl"],
              "not_para_first_line": not t["pfl"]}.get(pos)
        if ok is None:
            raise SpecError(f"unknown position {pos!r}")
        if ok:
            keep.append(t)
    return keep


def feature(f, w):
    if f == "word":
        return [w]
    if f == "length":
        return [len(SEG(w))]
    if f == "glyph":
        return SEG(w)
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


# ------------------------------------------------------------- statistics

def _entropy(c):
    n = sum(c.values())
    return -sum(v / n * math.log2(v / n) for v in c.values()) if n else 0.0


def _mi(pairs):
    pc, a, b = Counter(pairs), Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    n = sum(pc.values())
    return sum(v / n * math.log2(v * n / (a[x] * b[y])) for (x, y), v in pc.items()) if n else 0.0


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


def statistic(st, toks, all_toks):
    if not isinstance(st, dict) or len(st) != 1:
        raise SpecError("statistic is one {name: args}")
    (name, arg), = st.items()
    if name == "rate":
        vals = set(arg["in"])
        hits = sum(any(v in vals for v in feature(arg["feature"], t["w"])) for t in toks)
        return hits / len(toks) if toks else 0.0
    if name == "ratio":
        vals = set(arg["in"])
        num, den = select(all_toks, arg["of"]), select(all_toks, arg["to"])
        r = lambda ts: sum(any(v in vals for v in feature(arg["feature"], t["w"])) for t in ts) / len(ts) if ts else 0.0
        a, b = r(num), r(den)
        return a / b if b else (float("inf") if a else 0.0)
    if name == "entropy":
        return _entropy(Counter(v for t in toks for v in feature(arg, t["w"])))
    if name == "cond_entropy":
        pairs = [(tuple(feature(arg, x["w"])), tuple(feature(arg, y["w"])))
                 for ln in lines_of(toks) for x, y in zip(ln, ln[1:])]
        return _entropy(Counter(pairs)) - _entropy(Counter(p[0] for p in pairs))
    if name == "adjacent_mi":
        ls = lines_of(toks)
        pairs = [(tuple(feature(arg, x["w"])), tuple(feature(arg, y["w"]))) for ln in ls for x, y in zip(ln, ln[1:])]
        rng = random.Random(1)
        flat = [t for ln in ls for t in ln]
        sh = flat[:]
        rng.shuffle(sh)
        it = iter(sh)
        sl = [[next(it) for _ in ln] for ln in ls]
        spairs = [(tuple(feature(arg, x["w"])), tuple(feature(arg, y["w"]))) for ln in sl for x, y in zip(ln, ln[1:])]
        return _mi(pairs) - _mi(spairs)
    if name == "edge_mi":
        pairs = [(SEG(x["w"])[-1], SEG(y["w"])[0]) for ln in lines_of(toks) for x, y in zip(ln, ln[1:]) if x["w"] and y["w"]]
        return _mi(pairs)
    if name == "repeat_ngram":
        n = int(arg)
        if not 1 <= n <= 6:
            raise SpecError("repeat_ngram n must be 1..6")
        c = Counter(tuple(t["w"] for t in ln[i:i + n]) for ln in lines_of(toks) for i in range(len(ln) - n + 1))
        tot = sum(c.values())
        return sum(v for v in c.values() if v >= 2) / tot if tot else 0.0
    if name == "hapax_share":
        c = Counter(t["w"] for t in toks)
        return sum(1 for v in c.values() if v == 1) / len(c) if c else 0.0
    if name == "zipf_slope":
        fr = [f for _w, f in Counter(t["w"] for t in toks).most_common(int(arg))]
        if len(fr) < 3:
            return 0.0
        xs = [math.log10(i + 1) for i in range(len(fr))]
        ys = [math.log10(f) for f in fr]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    if name == "mean_length":
        return sum(len(SEG(t["w"])) for t in toks) / len(toks) if toks else 0.0
    if name == "near_copy":
        k, L = min(int(arg.get("window", 10)), 50), int(arg.get("min_length", 6))
        by_page = {}
        for t in toks:
            by_page.setdefault(t["page"], []).append(t["w"])
        hits = n = 0
        for ws in by_page.values():
            for i, w in enumerate(ws):
                if len(w) < L:
                    continue
                n += 1
                hits += any(_edit1(w, u) for u in ws[max(0, i - k):i])
        return hits / n if n else 0.0
    raise SpecError(f"unknown statistic {name!r}")


# ------------------------------------------------------------- nulls and references

LAYOUT_FREE = {"entropy", "hapax_share", "zipf_slope", "mean_length", "repeat_ngram", "cond_entropy", "adjacent_mi", "edge_mi", "near_copy"}


def _shuffled(all_toks, how, rng):
    groups = {}
    key = {"shuffle_within_line": lambda t: t["line"], "shuffle_within_page": lambda t: t["page"],
           "shuffle_within_section": lambda t: t["section"], "shuffle_across_pages": lambda t: 0,
           "shuffle_labels": lambda t: ("L", 0) if t["unit"] == "L" else ("x", id(t))}.get(how)
    if key is None:
        raise SpecError(f"unknown null {how!r}")
    if how == "shuffle_labels":
        # swap label words with running-text words of the same pages: labels lose their special status
        pool = [t for t in all_toks if t["unit"] in ("L", "P")]
        words = [t["w"] for t in pool]
        rng.shuffle(words)
        it = iter(words)
        out = [dict(t, w=next(it)) if t["unit"] in ("L", "P") else t for t in all_toks]
        return out
    for t in all_toks:
        groups.setdefault(key(t), []).append(t)
    out = []
    for g in groups.values():
        words = [t["w"] for t in g]
        rng.shuffle(words)
        out += [dict(t, w=w) for t, w in zip(g, words)]
    return out


def _reference_values(st, n_tokens):
    from .facts import ref_langs, ref_sample
    from .ivtff import Page, Line
    vals = {}
    for lang in ref_langs():
        lines = ref_sample(lang, n_tokens)
        p = Page("ref", 0, {"I": None, "L": None, "H": None})
        p.lines = [Line(f"ref.{i}", "ref", i, "P", "0", l, i == 0, False) for i, l in enumerate(lines)]
        ts = tokens([p])
        vals[lang] = statistic(st, ts, ts)
    return vals


def evaluate(spec, pages):
    """Returns {"value", "pass", "detail"} for a spec on these pages."""
    if not isinstance(spec, dict) or "statistic" not in spec:
        raise SpecError("spec needs a statistic")
    all_toks = tokens(pages, spec.get("scope"))
    toks = select(all_toks, spec.get("select"))
    if not toks:
        raise SpecError("the selection is empty")
    st = spec["statistic"]
    v = statistic(st, toks, all_toks)
    detail, ok = {"tokens": len(toks)}, True
    for c in spec.get("compare") or []:
        if "op" in c:
            x = float(c["value"])
            r = {">=": v >= x, "<=": v <= x, ">": v > x, "<": v < x}.get(c["op"])
            if r is None:
                raise SpecError(f"unknown op {c['op']!r}")
            detail[f"{c['op']} {x}"] = r
            ok &= r
        elif "reference" in c:
            name = next(iter(st))
            if name not in LAYOUT_FREE:
                raise SpecError(f"reference comparison needs a statistic that does not use layout ({sorted(LAYOUT_FREE)})")
            refs = _reference_values(st, len(toks))
            m = float(c.get("margin", 0))
            r = {"below_all": v <= min(refs.values()) - m, "above_all": v >= max(refs.values()) + m,
                 "inside_range": min(refs.values()) <= v <= max(refs.values())}.get(c["reference"])
            if r is None:
                raise SpecError(f"unknown reference test {c['reference']!r}")
            detail["reference"] = {k: round(x, 5) for k, x in refs.items()}
            ok &= r
        elif "null" in c:
            perms = min(int(c.get("perms", 200)), 400)
            rng = random.Random(408)
            more = 0
            for _ in range(perms):
                sh = _shuffled(all_toks, c["null"], rng)
                sv = statistic(st, select(sh, spec.get("select")), sh)
                more += (sv >= v) if c.get("direction", "greater") == "greater" else (sv <= v)
            p = (more + 1) / (perms + 1)
            r = p <= float(c.get("p", 0.01))
            detail[c["null"]] = {"p": round(p, 4), "perms": perms}
            ok &= r
        else:
            raise SpecError(f"unknown comparison {c!r}")
    return {"value": round(v, 6) if isinstance(v, float) and math.isfinite(v) else v, "pass": bool(ok), "detail": detail}
