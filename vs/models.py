"""Production-model language: 'how was this text written?', as a declarative mixture of trusted
components. The scorer fits it on the training pages and scores it word by word on the hidden
pages (held-out bits per word). Lower is better. No agent code runs.

model.json:
  {"title": "...", "statement": "...",
   "scope": {"hand": "1"},                                   (optional: fit and score one scribe/dialect/section)
   "components": [ {"type": "vocab"},                         a memorized vocabulary, order ignored (bag of words)
                   {"type": "chain"},                         each word depends on the one before (habit chain)
                   {"type": "copy", "window": 20},            copy a word seen in the last `window` words of the page,
                                                              possibly with one glyph changed ("edits": 0 | 1)
                   {"type": "template", "prefix": 2, "suffix": 2},   prefix + core + suffix from small inventories
                   {"type": "letters", "order": 3},           glyph by glyph (also spells words never seen before)
                   {"type": "position"} ],                    vocabulary conditioned on line position (initial/final/mid)
   "weights": "fit" | [w1, w2, ...]}                          mixture weights: fitted by EM on part of the training
                                                              pages, or given

Every component is a proper distribution over words, so the mixture is, and the held-out score
is an honest code length. The record keeps, per scope, the reference scores of a bag of words
and of letters alone, so a model's gain over them is visible.
"""
import math, random
from collections import Counter, defaultdict
from . import ivtff, lm

SEG = lambda w: ivtff.segment(w, "eva-basic")
MAX_COMPONENTS = 8


class ModelError(ValueError):
    pass


def scoped(pages, scope):
    scope = scope or {}
    out = []
    for p in pages:
        if scope.get("hand") and str(p.hand) != str(scope["hand"]):
            continue
        if scope.get("language") and p.language != scope["language"]:
            continue
        if scope.get("section") and p.section != scope["section"]:
            continue
        out.append(p)
    return out


def page_streams(pages):
    """Per page: list of (word, position) with position in {initial, final, mid}."""
    out = []
    for p in pages:
        s = []
        for ln in p.lines:
            ws = [w for w in ln.words if not ivtff.uncertain(w)]
            for k, w in enumerate(ws):
                s.append((w, "initial" if k == 0 else "final" if k == len(ws) - 1 else "mid"))
        if s:
            out.append(s)
    return out


class Letters:
    def __init__(self, words, order=3):
        self.m = lm.KN([lm.char_stream([w], SEG) for w in words], max(2, min(int(order), 6)))

    def p(self, w, ctx):
        return 2 ** -self.m.bits(lm.char_stream([w], SEG))


class Vocab:
    def __init__(self, words, letters):
        self.c = Counter(words)
        self.n = sum(self.c.values())
        self.t = len(self.c)
        self.letters = letters

    def p(self, w, ctx):
        c = self.c.get(w, 0)
        # Witten-Bell style escape into letters for unseen words
        return (c + self.t * self.letters.p(w, ctx)) / (self.n + self.t)


class Chain:
    def __init__(self, streams, vocab):
        self.big = defaultdict(Counter)
        for s in streams:
            for (a, _), (b, _) in zip(s, s[1:]):
                self.big[a][b] += 1
        self.vocab = vocab

    def p(self, w, ctx):
        prev = ctx["prev"]
        d = self.big.get(prev)
        if not d:
            return self.vocab.p(w, ctx)
        n, t = sum(d.values()), len(d)
        return (d.get(w, 0) + t * self.vocab.p(w, ctx)) / (n + t)


class Position:
    def __init__(self, streams, vocab):
        self.c = defaultdict(Counter)
        for s in streams:
            for w, pos in s:
                self.c[pos][w] += 1
        self.vocab = vocab

    def p(self, w, ctx):
        d = self.c.get(ctx["pos"], Counter())
        n, t = sum(d.values()), len(d)
        return (d.get(w, 0) + max(t, 1) * self.vocab.p(w, ctx)) / (n + max(t, 1))


def _edit1_variants(w, glyphs):
    g = SEG(w)
    out = set()
    for i in range(len(g)):
        for x in glyphs:
            if x != g[i]:
                out.add("".join(g[:i] + [x] + g[i + 1:]))
    return out


class Copy:
    def __init__(self, window, edits, glyphs, vocab):
        self.window, self.edits, self.glyphs, self.vocab = min(int(window), 50), int(edits), glyphs, vocab

    def p(self, w, ctx):
        recent = ctx["recent"][-self.window:]
        if not recent:
            return self.vocab.p(w, ctx)
        # choose a recent word uniformly; with edits=1, keep it (1/2) or change one glyph uniformly (1/2)
        tot = 0.0
        for r in recent:
            if self.edits == 0:
                tot += (r == w)
            else:
                if r == w:
                    tot += 0.5
                else:
                    gr, gw = SEG(r), SEG(w)
                    if len(gr) == len(gw) and sum(a != b for a, b in zip(gr, gw)) == 1:
                        tot += 0.5 / (len(gr) * max(len(self.glyphs) - 1, 1))
        q = tot / len(recent)
        return 0.9 * q + 0.1 * self.vocab.p(w, ctx) if q else 0.1 * self.vocab.p(w, ctx)


class Template:
    def __init__(self, words, pre, suf, letters):
        self.pre, self.suf = int(pre), int(suf)
        self.cp, self.cc, self.cs = Counter(), defaultdict(Counter), defaultdict(Counter)
        for w in words:
            p, c, s = self.split(w)
            self.cp[p] += 1
            self.cc[p][c] += 1
            self.cs[c][s] += 1
        self.letters = letters

    def split(self, w):
        g = SEG(w)
        if len(g) <= self.pre + self.suf:
            return "".join(g[:self.pre]), "", "".join(g[self.pre:])
        return "".join(g[:self.pre]), "".join(g[self.pre:len(g) - self.suf]), "".join(g[len(g) - self.suf:])

    @staticmethod
    def _wb(counter, key, fallback):
        n, t = sum(counter.values()), len(counter)
        return (counter.get(key, 0) + max(t, 1) * fallback) / (n + max(t, 1))

    def p(self, w, ctx):
        pr, co, su = self.split(w)
        lp = lambda s: (2 ** -self.letters.m.bits(lm.char_stream([s], SEG))) if s else 0.5
        a = self._wb(self.cp, pr, lp(pr))
        b = self._wb(self.cc.get(pr, Counter()), co, lp(co))
        c = self._wb(self.cs.get(co, Counter()), su, lp(su))
        return max(a * b * c, 1e-300)


def build(spec, train_pages):
    comps = spec.get("components") or []
    if not comps or len(comps) > MAX_COMPONENTS:
        raise ModelError(f"1 to {MAX_COMPONENTS} components")
    streams = page_streams(train_pages)
    words = [w for s in streams for w, _ in s]
    if len(words) < 500:
        raise ModelError("too few training words in this scope")
    glyphs = sorted({g for w in set(words) for g in SEG(w)})
    letters = Letters(words, next((c.get("order", 3) for c in comps if c["type"] == "letters"), 3))
    vocab = Vocab(words, letters)
    built = []
    for c in comps:
        t = c.get("type")
        if t == "vocab":
            built.append(vocab)
        elif t == "letters":
            built.append(letters)
        elif t == "chain":
            built.append(Chain(streams, vocab))
        elif t == "position":
            built.append(Position(streams, vocab))
        elif t == "copy":
            built.append(Copy(c.get("window", 20), c.get("edits", 1), glyphs, vocab))
        elif t == "template":
            built.append(Template(words, c.get("prefix", 2), c.get("suffix", 2), letters))
        else:
            raise ModelError(f"unknown component {t!r}")
    return built


def _code_length(built, weights, streams):
    bits, n = 0.0, 0
    for s in streams:
        recent, prev = [], None
        for w, pos in s:
            ctx = {"prev": prev, "pos": pos, "recent": recent}
            p = sum(lam * c.p(w, ctx) for lam, c in zip(weights, built))
            bits -= math.log2(max(p, 1e-300))
            n += 1
            recent.append(w)
            prev = w
    return bits, n


def fit_weights(spec, train_pages):
    """EM for mixture weights on half the training pages, components fitted on the other half."""
    k = len(spec["components"])
    if spec.get("weights") not in (None, "fit"):
        w = [float(x) for x in spec["weights"]]
        if len(w) != k or min(w) < 0 or sum(w) <= 0:
            raise ModelError("weights: one non-negative number per component")
        return [x / sum(w) for x in w]
    pages = list(train_pages)
    random.Random(7).shuffle(pages)
    a, b = pages[: len(pages) // 2], pages[len(pages) // 2:]
    built = build(spec, a)
    streams = page_streams(b)
    lam = [1.0 / k] * k
    for _ in range(15):
        resp = [0.0] * k
        for s in streams:
            recent, prev = [], None
            for w, pos in s:
                ctx = {"prev": prev, "pos": pos, "recent": recent}
                ps = [l * c.p(w, ctx) for l, c in zip(lam, built)]
                tot = sum(ps) or 1e-300
                for j in range(k):
                    resp[j] += ps[j] / tot
                recent.append(w)
                prev = w
        lam = [r / sum(resp) for r in resp]
    return lam


def evaluate(spec, train_pages, eval_pages):
    scope = spec.get("scope")
    tr, ev = scoped(train_pages, scope), scoped(eval_pages, scope)
    if not ev:
        raise ModelError("no evaluation pages in this scope")
    lam = fit_weights(spec, tr)
    built = build(spec, tr)
    bits, n = _code_length(built, lam, page_streams(ev))
    refs = {}
    for name, comps in (("bag_of_words", [{"type": "vocab"}]), ("letters_only", [{"type": "letters", "order": 3}])):
        rb, rn = _code_length(build({"components": comps}, tr), [1.0], page_streams(ev))
        refs[name] = round(rb / max(rn, 1), 4)
    bpw = bits / max(n, 1)
    return {"bits_per_word": round(bpw, 4), "words": n, "weights": [round(x, 4) for x in lam],
            "references": refs, "gain_over_bag": round(refs["bag_of_words"] - bpw, 4)}
