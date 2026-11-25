"""Positive and negative controls for the judge.

A judge that rejects everything proves nothing. So for each target language we build a
synthetic 'manuscript': genuine text from that language's control split (never seen by the
language model, nor used for thresholds), enciphered into EVA glyphs with a random key, laid
out in pages and lines. The judge must PASS the true key on it (criteria a, b and the kill
tests; c needs anchors a synthetic text does not have) and FAIL the red-team decoders.
The same controls measure whether a search budget can find a key at all (L3).
"""
import random
from . import refcorpus, ivtff
from .ivtff import Page, Line

# glyphs whose concatenation re-segments unambiguously under eva-basic (no bare c or h)
CIPHER_GLYPHS = ["o", "e", "y", "a", "d", "i", "k", "l", "r", "s", "t", "n", "q", "p", "m", "f", "g",
                 "x", "v", "j", "u", "z", "b", "w", "ch", "sh", "cth", "ckh", "cph", "cfh"]


ABBREVIATION_SIGNS = ("cth", "ckh", "cph", "cfh")

NOISE = 0.02  # transcription noise used for power (after Schwartz 2026: power at 2% noise)


def make(lang, kind="simple", seed=0, words_per_line=8, lines_per_page=10, homophones=2, noise=0.0, corpus_id=None):
    """A synthetic enciphered manuscript. noise: share of glyphs replaced by a random other glyph
    (transcription error). corpus_id: draw plaintext from one pinned text (a genre) instead of
    the language's whole control split."""
    rng = random.Random(f"control/{lang}/{kind}/{seed}/{noise}/{corpus_id}")
    if corpus_id:
        from . import refcorpus as _rc
        blocks = [b for i, b in enumerate(_rc.blocks_of(corpus_id)) if i % 10 == 9] or _rc.blocks_of(corpus_id)
        words = " ".join(blocks).split()
    else:
        words = " ".join(refcorpus.control_text(lang)).split()
    letters = refcorpus.alphabet(lang)
    glyphs = CIPHER_GLYPHS[:]
    if kind == "abbreviation":
        glyphs = [g for g in glyphs if g not in ABBREVIATION_SIGNS]
    if kind == "abbreviation" and len(letters) > len(glyphs):
        raise ValueError(f"target alphabet exceeds the abbreviation glyph inventory")
    if kind == "syllabic":
        glyphs.remove("q")
        if len(letters) > len(glyphs):
            raise ValueError("target alphabet exceeds the syllabic spelling inventory")
    if kind == "nomenclator" and len(letters) > len(glyphs):
        raise ValueError(f"target alphabet exceeds the nomenclator glyph inventory")
    if kind == "table-cipher" and len(letters) > len(glyphs):
        raise ValueError(f"target alphabet exceeds the table-cipher glyph inventory")
    rng.shuffle(glyphs)
    if kind == "table-cipher":
        # A periodic tabula recta uses the public alphabet order and secret column shifts.
        glyphs = sorted(CIPHER_GLYPHS[:len(letters)])
        shifts = [rng.randrange(len(letters)) for _ in range(3)]
        enc = {c: [g] for c, g in zip(letters, glyphs)}
    elif kind == "simple":
        enc = {l: [glyphs[i]] for i, l in enumerate(letters)}
    elif kind == "codebook":
        enc = {}
    elif kind in ("homophonic", "nomenclator", "abbreviation", "syllabic"):
        # the most frequent letters get `homophones` glyphs, the rest one; needs few letters
        freq = sorted(letters, key=lambda l: -sum(w.count(l) for w in words[:5000]))
        enc, i = {}, 0
        for l in freq:
            k = homophones if i + homophones <= len(glyphs) - (len(freq) - len(enc) - 1) else 1
            enc[l] = glyphs[i:i + k]
            i += k
    elif kind == "verbose":
        # each letter becomes a two-character EVA unit, as in verbose ciphers
        chars = list("oeyadiklrstnqpmfg")
        pairs = [a + b for a in chars for b in chars]
        rng.shuffle(pairs)
        enc = {l: [pairs[i]] for i, l in enumerate(letters)}
    else:
        raise ValueError(kind)
    dec = {g: l for l, gs in enc.items() for g in gs}

    noise_pool = sorted({g for gs in enc.values() for g in gs} | set(CIPHER_GLYPHS[:10]))

    abbreviated = {}
    if kind == "abbreviation":
        from collections import Counter
        endings = Counter(w[-n:] for block in refcorpus.train_text(lang) for w in block.split()
                          for n in (2, 3) if len(w) > n)
        signs = list(ABBREVIATION_SIGNS)
        rng.shuffle(signs)
        abbreviated = dict(zip((s for s, _ in endings.most_common(len(signs))), signs))
        noise_pool = sorted(set(noise_pool) | set(signs))
    sign_map = {}
    if kind == "syllabic":
        from collections import Counter
        frequencies = Counter(a + b for block in refcorpus.train_text(lang) for w in block.split()
                              for a, b in zip(w, w[1:]) if a not in "aeiou" and b in "aeiou")
        if not frequencies:
            raise ValueError(f"no supported written CV syllables in {lang}")
        labels = [g for g in glyphs if len(g) == 1]
        rng.shuffle(labels)
        for i, (syllable, _) in enumerate(frequencies.most_common(10)):
            sign_map[syllable] = labels[2*i:2*i+2]

    marker = ""
    word_codes = {}
    if kind == "nomenclator":
        # Spell ordinary words with the alphabet. Use a separate marked group
        # for each of 24 frequent words, assigned without exposing the key to search.
        from collections import Counter
        candidates = Counter(w for block in refcorpus.train_text(lang) for w in block.split() if len(w) >= 2)
        marker = rng.choice("ch") * 2
        alphabet = "oeyadiklrstnqpmfg"
        codes = [marker + a + b for a in alphabet for b in alphabet]
        rng.shuffle(codes)
        word_codes = dict(zip((w for w, _ in candidates.most_common(24)), codes))

    if kind == "codebook":
        from itertools import product
        alphabet = "oeyadiklrstnqpmfg"
        vocabulary = sorted(set(words))
        width = 1
        while len(alphabet) ** width < len(vocabulary):
            width += 1
        codes = ["".join(chars) for chars in product(alphabet, repeat=width)]
        rng.shuffle(codes)
        word_codes = dict(zip(vocabulary, codes))

    def cipher(w):
        if w in word_codes:
            return "".join(rng.choice([x for x in CIPHER_GLYPHS if x != c]) if rng.random() < noise else c
                           for c in word_codes[w])
        suffix = next((s for s in sorted(abbreviated, key=len, reverse=True)
                       if len(w) > len(s) and w.endswith(s)), None) if kind == "abbreviation" else None
        if suffix:
            w = w[:-len(suffix)]
        if kind == "table-cipher":
            units = [glyphs[(letters.index(c) + shifts[i % len(shifts)]) % len(letters)]
                     for i, c in enumerate(w) if c in enc]
        elif kind == "syllabic":
            units = []
            i = 0
            while i < len(w):
                pair = w[i:i + 2]
                if pair in sign_map:
                    units.extend(["q", rng.choice(sign_map[pair])])
                    i += 2
                else:
                    if w[i] in enc:
                        units.append(rng.choice(enc[w[i]]))
                    i += 1
        else:
            units = [rng.choice(enc[c]) for c in w if c in enc]
        if suffix:
            units.append(abbreviated[suffix])
        if noise:
            units = [rng.choice([x for x in noise_pool if x != u]) if rng.random() < noise else u for u in units]
        return "".join(units)

    pages, i, n = [], 0, 0
    while i < len(words):
        pid = f"c{n:03d}"
        pg = Page(pid, n, {"I": "H", "L": None, "H": None})
        for k in range(lines_per_page):
            ws = [cipher(w) for w in words[i:i + words_per_line]]
            i += words_per_line
            ws = [w for w in ws if w]
            if ws:
                pg.lines.append(Line(f"{pid}.{k + 1}", pid, k + 1, "P", "0", ws, k == 0, k == lines_per_page - 1))
            if i >= len(words):
                break
        pages.append(pg)
        n += 1
    ev = [p for p in pages if int(p.id[1:]) % 7 == 3]
    tr = [p for p in pages if int(p.id[1:]) % 7 != 3]
    true_key = {"id": f"control-{lang}-{kind}", "family": "verbose" if kind == "verbose" else "substitution", "segmentation": "eva-basic",
                "target": {"language": lang, "period": "control"}, "key": {"map": dec}}
    if kind in ("codebook", "nomenclator"):
        true_key["family"] = kind
        if kind == "nomenclator":
            true_key["key"]["marker"] = marker
        true_key["key"]["map"].update({code: word for word, code in word_codes.items()})
    if kind == "table-cipher":
        true_key.update(family=kind, key={"map": dict(zip(glyphs, letters)), "shifts": shifts})
    if kind == "abbreviation":
        true_key["family"] = kind
        true_key["key"]["map"].update({g + "$": s for s, g in abbreviated.items()})
    if kind == "syllabic":
        true_key["family"] = kind
        true_key["key"]["marker"] = "q"
        true_key["key"]["map"].update({"q" + label: syllable for syllable, labels in sign_map.items() for label in labels})
    return tr, ev, true_key


def red_team_keys(lang, n_lex=2000):
    from .judge import target_models
    _cm, _wm, lex = target_models(lang)
    cnt = {}
    for b in refcorpus.train_text(lang):
        for w in b.split():
            cnt[w] = cnt.get(w, 0) + 1
    top = sorted(cnt, key=lambda w: (-cnt[w], w))
    return [
        {"id": f"redteam-constant-{lang}", "family": "constant", "target": {"language": lang, "period": "red team"},
         "key": {"word": top[0]}},
        {"id": f"redteam-hashlex-{lang}", "family": "hashlex", "target": {"language": lang, "period": "red team"},
         "key": {"lexicon": top[:n_lex], "salt": "s1"}},
    ]
