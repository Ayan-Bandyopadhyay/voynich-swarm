"""Fixed language models: interpolated Kneser-Ney n-grams over any symbols.

The same class models characters of a target language, EVA glyphs of Voynichese, and
words (for the word-order kill test). Everything is deterministic and costs are in bits.
"""
import math
from collections import defaultdict

BOS = "<s>"
WB = "_"   # word boundary symbol in character streams


class KN:
    def __init__(self, sequences, order=5, vocab=None):
        self.n = order
        self.c = [defaultdict(lambda: defaultdict(int)) for _ in range(order + 1)]
        syms = set(vocab or [])
        for seq in sequences:
            s = [BOS] * (order - 1) + list(seq)
            for i in range(order - 1, len(s)):
                syms.add(s[i])
                self.c[order][tuple(s[i - order + 1:i])][s[i]] += 1
        # continuation counts for lower orders
        for k in range(order, 1, -1):
            for ctx, d in self.c[k].items():
                for w in d:
                    self.c[k - 1][ctx[1:]][w] += 1
        self.V = len(syms) + 1
        self.tot = [dict() for _ in range(order + 1)]
        self.typ = [dict() for _ in range(order + 1)]
        self.D = [0.0] * (order + 1)
        for k in range(1, order + 1):
            n1 = n2 = 0
            for ctx, d in self.c[k].items():
                self.tot[k][ctx] = sum(d.values())
                self.typ[k][ctx] = len(d)
                for v in d.values():
                    n1 += v == 1
                    n2 += v == 2
            # clamped so that no symbol ever gets probability zero (tiny corpora)
            self.D[k] = min(max(n1 / (n1 + 2 * n2) if n1 + n2 else 0.5, 0.1), 0.9)
        self._cache = {}

    def prob(self, w, ctx):
        key = (w, ctx)
        p = self._cache.get(key)
        if p is not None:
            return p
        p = 1.0 / self.V
        for k in range(1, self.n + 1):
            h = ctx[len(ctx) - (k - 1):] if k > 1 else ()
            t = self.tot[k].get(h)
            if not t:
                continue
            cnt = self.c[k][h].get(w, 0)
            D = self.D[k]
            p = max(cnt - D, 0) / t + D * self.typ[k][h] / t * p
        if len(self._cache) < 4_000_000:
            self._cache[key] = p
        return p

    def bits(self, seq):
        s = [BOS] * (self.n - 1) + list(seq)
        b = 0.0
        for i in range(self.n - 1, len(s)):
            b -= math.log2(self.prob(s[i], tuple(s[i - self.n + 1:i])))
        return b


def char_stream(words, seg=None):
    """A line of words as one symbol stream with boundaries: _ w1 _ w2 _"""
    out = [WB]
    for w in words:
        out.extend(seg(w) if seg else list(w))
        out.append(WB)
    return out


class WordUnigramEscape:
    """Adaptive word unigram with dev counts as prior; unseen words are spelled by a char model.
    The 'best model of Voynichese alone' takes the cheaper of this and the char KN."""

    def __init__(self, dev_words, char_model, seg=None):
        self.prior = defaultdict(int)
        for w in dev_words:
            self.prior[w] += 1
        self.cm = char_model
        self.seg = seg

    def spell_bits(self, w):
        return self.cm.bits(char_stream([w], self.seg)) if self.cm else 0.0

    def bits_tokens(self, words):
        counts = dict(self.prior)
        N = sum(counts.values())
        T = len(counts)
        b = 0.0
        for w in words:
            c = counts.get(w, 0)
            if c:
                b -= math.log2(c / (N + T))
            else:
                b -= math.log2(T / (N + T))
                b += self.spell_bits(w)
                T += 1
            counts[w] = c + 1
            N += 1
        return b
