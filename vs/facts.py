"""L2 metrics: the library of measurements an agent can register a fact claim against.
Registering a fact (experiment kind "fact") names one of these metrics with params and a
threshold; a new metric is code, reviewed and merged first.

Every metric takes (train_pages, eval_pages) and returns a dict with 'value', 'pass' and
'detail'. Pages may be the manuscript's or a generator's imitation of them (G track), which
is why nothing here reads the transliteration directly.
"""
import json, math, random
from collections import Counter, defaultdict
from . import path, ivtff, refcorpus

GALLOWS = set("ptkf")


def _words(pgs, units=None):
    return [w for p in pgs for ln in p.lines if units is None or ln.unit in units
            for w in ln.words if not ivtff.uncertain(w)]


def _lines(pgs, units=("P",)):
    return [[w for w in ln.words if not ivtff.uncertain(w)] for p in pgs for ln in p.lines
            if ln.unit in units and ln.words]


def _z(a, n1, b, n2):
    if n1 == 0 or n2 == 0:
        return 0.0
    p1, p2 = a / n1, b / n2
    p = (a + b) / (n1 + n2)
    se = math.sqrt(max(0.0, p * (1 - p) * (1 / n1 + 1 / n2))) or 1e-12
    return (p1 - p2) / se


def _ratio_test(a, n1, b, n2, ratio, zmin):
    r1, r2 = a / max(n1, 1), b / max(n2, 1)
    rat = r1 / r2 if r2 else float("inf")
    z = _z(a, n1, b, n2)
    return {"value": round(rat, 4), "pass": rat >= ratio and z >= zmin,
            "detail": {"rate_in": round(r1, 5), "n_in": n1, "rate_out": round(r2, 5), "n_out": n2, "z": round(z, 2)}}


def ref_sample(lang, n_tokens, line_len=8):
    words = " ".join(refcorpus.calib_text(lang)).split()[:n_tokens]
    return [words[i:i + line_len] for i in range(0, len(words), line_len)]


def ref_words(lang, n_tokens):
    """The first n_tokens words of a reference language's calibration text (fewer if it is shorter)."""
    return " ".join(refcorpus.calib_text(lang)).split()[:n_tokens]


def ref_langs():
    # languages with enough calibration text to match the held-out size
    return [l for l in refcorpus.languages() if len(" ".join(refcorpus.calib_text(l)).split()) >= 4000]


def skew(xs):
    n = len(xs)
    m = sum(xs) / n
    s2 = sum((x - m) ** 2 for x in xs) / n
    s3 = sum((x - m) ** 3 for x in xs) / n
    return s3 / s2 ** 1.5 if s2 else 0.0


def h2(lines):
    pair, ctx = Counter(), Counter()
    for ln in lines:
        s = "_" + "_".join(ln) + "_"
        for a, b in zip(s, s[1:]):
            pair[a, b] += 1
            ctx[a] += 1
    n = sum(pair.values())
    return -sum(c / n * math.log2(c / ctx[a]) for (a, _b), c in pair.items())


def entropy(counter):
    n = sum(counter.values())
    return -sum(c / n * math.log2(c / n) for c in counter.values())


def edit1(a, b):
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


class SlotGrammar:
    """Precedence grammar: glyph x must precede y when, across training word types,
    x comes before y in at least 95% of the words holding both (and at least 20 times)."""

    def __init__(self, types, seg):
        before = Counter()
        for w in types:
            g = seg(w)
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    if g[i] != g[j]:
                        before[g[i], g[j]] += 1
        self.must = set()
        for (x, y), c in before.items():
            rev = before.get((y, x), 0)
            if c >= 20 and rev / (c + rev) <= 0.05:
                self.must.add((x, y))
        self.seg = seg

    def accepts(self, w):
        g = self.seg(w)
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if (g[j], g[i]) in self.must:
                    return False
        return True

    def cover(self, tokens):
        return sum(self.accepts(w) for w in tokens) / max(len(tokens), 1)


def eva_seg(w):
    return ivtff.segment(w, "eva-basic")


def _shuffled(tokens, seed=1):
    rng = random.Random(seed)
    out = []
    for w in tokens:
        g = eva_seg(w)
        rng.shuffle(g)
        out.append("".join(g))
    return out


def profile(pgs_or_page):
    c = Counter()
    for ln in pgs_or_page.lines:
        s = ["_"]
        for w in ln.words:
            s += eva_seg(w) + ["_"]
        for a, b in zip(s, s[1:]):
            c[a, b] += 1
    n = math.sqrt(sum(v * v for v in c.values())) or 1
    return {k: v / n for k, v in c.items()}


def classify(train, evalp, label, min_acc, over_majority=None):
    cents = defaultdict(lambda: defaultdict(float))
    for p in train:
        lab = p.meta.get(label)
        if lab:
            for k, v in profile(p).items():
                cents[lab][k] += v
    for lab, d in cents.items():
        n = math.sqrt(sum(v * v for v in d.values()))
        for k in d:
            d[k] /= n
    hits = total = 0
    maj = Counter()
    for p in evalp:
        lab = p.meta.get(label)
        if not lab or not p.words():
            continue
        prof = profile(p)
        best = max(sorted(cents), key=lambda L: sum(v * cents[L].get(k, 0) for k, v in prof.items()))
        hits += best == lab
        total += 1
        maj[lab] += 1
    acc = hits / max(total, 1)
    need = min_acc
    majority = max(maj.values()) / total if total else 0
    if over_majority is not None:
        need = max(min_acc, majority + over_majority)
    return {"value": round(acc, 4), "pass": total > 0 and acc >= need,
            "detail": {"pages": total, "threshold": round(need, 4), "majority_rate": round(majority, 4)}}


def jsd(c1, c2):
    n1, n2 = sum(c1.values()), sum(c2.values())
    keys = set(c1) | set(c2)
    out = 0.0
    for k in keys:
        p, q = c1.get(k, 0) / n1, c2.get(k, 0) / n2
        m = (p + q) / 2
        if p:
            out += 0.5 * p * math.log2(p / m)
        if q:
            out += 0.5 * q * math.log2(q / m)
    return out


# ---------------------------------------------------------------- metrics

def m_len_skew(train, evalp, **_):
    toks = _words(evalp)
    v = abs(skew([len(w) for w in toks]))
    refs = {l: abs(skew([len(w) for ln in ref_sample(l, len(toks)) for w in ln])) for l in ref_langs()}
    return {"value": round(v, 4), "pass": v < min(refs.values()), "detail": {"reference_abs_skew": {k: round(x, 4) for k, x in refs.items()}}}


def m_zipf_slope(train, evalp, ranks, lo, hi):
    c = Counter(_words(evalp))
    fr = [f for _, f in c.most_common(ranks)]
    xs = [math.log10(i + 1) for i in range(len(fr))]
    ys = [math.log10(f) for f in fr]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return {"value": round(slope, 4), "pass": lo <= slope <= hi, "detail": {"types": len(c), "tokens": sum(c.values())}}


def m_h2_gap(train, evalp, gap):
    lines = _lines(evalp, units=("P", "L", "C", "R"))
    v = h2(lines)
    n = sum(len(l) for l in lines)
    refs = {l: h2(ref_sample(l, n)) for l in ref_langs()}
    return {"value": round(v, 4), "pass": v <= min(refs.values()) - gap, "detail": {"reference_h2": {k: round(x, 4) for k, x in refs.items()}}}


def m_slot_cover(train, evalp, min_cover, max_shuffled):
    g = SlotGrammar(set(_words(train)), eva_seg)
    toks = _words(evalp)
    cov, sh = g.cover(toks), g.cover(_shuffled(toks))
    return {"value": round(cov, 4), "pass": cov >= min_cover and sh <= max_shuffled,
            "detail": {"shuffled_cover": round(sh, 4), "rules": len(g.must), "tokens": len(toks)}}


def m_slot_vs_ref(train, evalp, gap):
    g = SlotGrammar(set(_words(train)), eva_seg)
    toks = _words(evalp)
    cov = g.cover(toks)
    refs = {}
    for l in ref_langs():
        tr = " ".join(refcorpus.train_text(l)).split()[: len(_words(train))]
        ev = [w for ln in ref_sample(l, len(toks)) for w in ln]
        refs[l] = SlotGrammar(set(tr), list).cover(ev)
    return {"value": round(cov - max(refs.values()), 4), "pass": cov - max(refs.values()) >= gap,
            "detail": {"voynich_cover": round(cov, 4), "reference_cover": {k: round(x, 4) for k, x in refs.items()}}}


def _para_lines(evalp):
    """Paragraph text lines in order, each with (is_first_line_of_paragraph, words)."""
    out = []
    for p in evalp:
        prev_end = True
        for ln in p.lines:
            if ln.unit != "P" or not ln.words:
                continue
            first = ln.para_start or prev_end
            out.append((first, ln.words))
            prev_end = ln.para_end
    return out


def m_para_gallows(train, evalp, ratio, z):
    a = n1 = b = n2 = 0
    for first, ws in _para_lines(evalp):
        w = ws[0]
        if ivtff.uncertain(w):
            continue
        hit = w[0] in GALLOWS
        if first:
            a += hit; n1 += 1
        else:
            b += hit; n2 += 1
    return _ratio_test(a, n1, b, n2, ratio, z)


def m_line_final_m(train, evalp, ratio, z):
    a = n1 = b = n2 = 0
    for _first, ws in _para_lines(evalp):
        ws = [w for w in ws if not ivtff.uncertain(w)]
        for i, w in enumerate(ws):
            hit = w.endswith("m")
            if i == len(ws) - 1:
                a += hit; n1 += 1
            else:
                b += hit; n2 += 1
    return _ratio_test(a, n1, b, n2, ratio, z)


def m_pf_first_line(train, evalp, ratio, z):
    a = n1 = b = n2 = 0
    for first, ws in _para_lines(evalp):
        for w in ws:
            if ivtff.uncertain(w):
                continue
            g = eva_seg(w)
            hits = sum(x in ("p", "f") for x in g)
            if first:
                a += hits; n1 += len(g)
            else:
                b += hits; n2 += len(g)
    return _ratio_test(a, n1, b, n2, ratio, z)


def m_classify(train, evalp, **kw):
    return classify(train, evalp, **kw)


def m_label_o(train, evalp, ratio, z):
    lab, par = _words(evalp, units=("L",)), _words(evalp, units=("P",))
    return _ratio_test(sum(w.startswith("o") for w in lab), len(lab), sum(w.startswith("o") for w in par), len(par), ratio, z)


def _adjacent_rate(lines, pred):
    hits = n = 0
    for ln in lines:
        for a, b in zip(ln, ln[1:]):
            hits += pred(a, b)
            n += 1
    return hits / max(n, 1), n


def _rep(train, evalp, ratio, pred):
    lines = _lines(evalp)
    v, n = _adjacent_rate(lines, pred)
    ntok = sum(len(l) for l in lines)
    refs = {l: _adjacent_rate(ref_sample(l, ntok), pred)[0] for l in ref_langs()}
    mx = max(refs.values())
    return {"value": round(v / mx, 4) if mx else float("inf"), "pass": v >= ratio * mx,
            "detail": {"rate": round(v, 5), "pairs": n, "reference_rate": {k: round(x, 5) for k, x in refs.items()}}}


def m_rep_exact(train, evalp, ratio):
    return _rep(train, evalp, ratio, lambda a, b: a == b)


def m_rep_near(train, evalp, ratio):
    return _rep(train, evalp, ratio, edit1)


def m_word_entropy(train, evalp, **_):
    toks = _words(evalp)
    v = entropy(Counter(toks))
    refs = {l: entropy(Counter(w for ln in ref_sample(l, len(toks)) for w in ln)) for l in ref_langs()}
    return {"value": round(v, 4), "pass": min(refs.values()) <= v <= max(refs.values()),
            "detail": {"reference_entropy": {k: round(x, 4) for k, x in refs.items()}}}


def m_ab_vocab(train, evalp, ratio):
    A = [p for p in evalp if p.language == "A"]
    B = [p for p in evalp if p.language == "B"]
    if len(A) < 2 or not B:
        return {"value": None, "pass": False, "detail": {"error": "too few A or B pages"}}
    cA, cB = Counter(_words(A)), Counter(_words(B))
    h1, h2_ = Counter(_words(A[0::2])), Counter(_words(A[1::2]))
    d, base = jsd(cA, cB), jsd(h1, h2_)
    return {"value": round(d / base, 4) if base else None, "pass": base > 0 and d >= ratio * base,
            "detail": {"jsd_ab": round(d, 4), "jsd_a_halves": round(base, 4), "pages_a": len(A), "pages_b": len(B)}}


METRICS = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}


def battery():
    """Registered DSL or legacy metric specs, in registry order."""
    from . import registry
    rows = []
    for item in registry.read("fact"):
        detail = item["detail"]
        row = {k: item[k] for k in ("id", "title", "statement")}
        if "spec" in detail:
            row["spec"] = detail["spec"]
        elif "metric" in detail:
            row.update(metric=detail["metric"], params=detail["params"])
        else:
            raise ValueError(f"Registered fact {item['id']} has neither a DSL spec nor a legacy metric")
        rows.append(row)
    return rows


def run(train, evalp, ids=None):
    out = {}
    for f in battery():
        if ids and f["id"] not in ids:
            continue
        if "spec" in f:
            from . import dsl
            out[f["id"]] = dsl.evaluate(f["spec"], evalp)
        else:
            out[f["id"]] = METRICS[f["metric"]](train, evalp, **f["params"])
    return out


def order_consistency(types, seg):
    before = Counter()
    for w in types:
        g = seg(w)
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                if g[i] != g[j]:
                    before[g[i], g[j]] += 1
    num = den = 0
    for (x, y), c in before.items():
        if x < y:
            r = before.get((y, x), 0)
            num += max(c, r)
            den += c + r
    return num / den if den else 0.0


def m_order_consistency(train, evalp, gap):
    toks = _words(evalp)
    v = order_consistency(set(toks), eva_seg)
    refs = {l: order_consistency(set(w for ln in ref_sample(l, len(toks)) for w in ln), list) for l in ref_langs()}
    return {"value": round(v - max(refs.values()), 4), "pass": v - max(refs.values()) >= gap,
            "detail": {"voynich": round(v, 4), "reference": {k: round(x, 4) for k, x in refs.items()}}}


METRICS = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}


# ---------------------------------------------------------------- S1b metrics

def _ngram_repeat_rate(lines, n=4):
    c = Counter(tuple(l[i:i + n]) for l in lines for i in range(len(l) - n + 1))
    tot = sum(c.values())
    return sum(v for v in c.values() if v >= 2) / tot if tot else 0.0


def m_repeat_4gram(train, evalp, ratio):
    lines = _lines(evalp)
    v = _ngram_repeat_rate(lines)
    ntok = sum(len(l) for l in lines)
    refs = {l: _ngram_repeat_rate(ref_sample(l, ntok)) for l in ref_langs()}
    mn = min(refs.values())
    return {"value": round(v, 5), "pass": v <= ratio * mn, "detail": {"reference_rate": {k: round(x, 5) for k, x in refs.items()}}}


def m_hapax_share(train, evalp, lo, hi):
    c = Counter(_words(evalp))
    v = sum(1 for x in c.values() if x == 1) / max(len(c), 1)
    return {"value": round(v, 4), "pass": lo <= v <= hi, "detail": {"types": len(c)}}


def _mi(lines):
    pairs, left, right = Counter(), Counter(), Counter()
    for l in lines:
        for a, b in zip(l, l[1:]):
            pairs[a, b] += 1
            left[a] += 1
            right[b] += 1
    n = sum(pairs.values())
    return sum(c / n * math.log2(c * n / (left[a] * right[b])) for (a, b), c in pairs.items()) if n else 0.0


def _mi_excess(lines, seed=5):
    rng = random.Random(seed)
    toks = [w for l in lines for w in l]
    rng.shuffle(toks)
    it = iter(toks)
    sh = [[next(it) for _ in l] for l in lines]
    return _mi(lines) - _mi(sh)


def m_word_pair_mi(train, evalp, gap):
    lines = _lines(evalp)
    v = _mi_excess(lines)
    ntok = sum(len(l) for l in lines)
    refs = {l: _mi_excess(ref_sample(l, ntok)) for l in ref_langs()}
    return {"value": round(v, 4), "pass": v <= min(refs.values()) - gap, "detail": {"reference_excess_mi": {k: round(x, 4) for k, x in refs.items()}}}


def _seen_before_rate(pages_tokens):
    hits = n = 0
    for toks in pages_tokens:
        seen = set()
        for w in toks:
            hits += w in seen
            n += 1
            seen.add(w)
    return hits / max(n, 1)


def m_page_burst(train, evalp, ratio):
    pt = [_words([p]) for p in evalp]
    v = _seen_before_rate(pt)
    rng = random.Random(7)
    allt = [w for t in pt for w in t]
    base = []
    for _ in range(20):
        rng.shuffle(allt)
        it = iter(allt)
        base.append(_seen_before_rate([[next(it) for _ in t] for t in pt]))
    b = sum(base) / len(base)
    return {"value": round(v / b, 4) if b else None, "pass": b > 0 and v >= ratio * b, "detail": {"rate": round(v, 4), "random_pages_rate": round(b, 4)}}


def _copy_rate(lines_by_page, minlen=6, window=10):
    hits = n = 0
    for toks in lines_by_page:
        for i, w in enumerate(toks):
            if len(w) < minlen:
                continue
            n += 1
            hits += any(edit1(w, u) for u in toks[max(0, i - window):i])
    return hits / max(n, 1)


def m_copy_tweak(train, evalp, min_rate, ratio):
    pt = [_words([p], units=("P",)) for p in evalp]
    v = _copy_rate(pt)
    ntok = sum(len(t) for t in pt)
    refs = {}
    for l in ref_langs():
        ws = [w for ln in ref_sample(l, ntok) for w in ln]
        refs[l] = _copy_rate([ws[i:i + 250] for i in range(0, len(ws), 250)])
    return {"value": round(v, 4), "pass": v >= min_rate and v >= ratio * max(refs.values()),
            "detail": {"reference_rate": {k: round(x, 4) for k, x in refs.items()}}}


METRICS = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}
