"""The judge. Nothing else marks a decipherment as a result.

A submission is a key file (keys/*.json): a merged family program, a key, a declared target
language and period, and a glyph segmentation. Given training pages T and evaluation pages E
(the held-out pages, for the authoritative verdict), the judge decides four things:

 (a) COMPRESSES. Description length of E's text under the decipherment,
         L(program) + L(key) + L_target(plaintext) + L(Voynich words | plaintext),
     must be clearly below the best model of Voynichese alone (trained on T): the savings,
     with program and key paid in full, must be positive at the page bootstrap's lower 95%
     bound. A large key pays for itself bit by bit, so a key that 'explains' anything scores
     nothing. (Why no fixed margin: for a simple cipher the Voynich-only model is the same
     model as the plaintext's, trained on less text, so a correct key's edge is only what
     the language corpus adds. The controls in vs/controls.py measure that edge.)
 (b) READS. In every section with enough output, the plaintext's per-character cost under
     the fixed target model, its lexicon coverage and its type/token ratio fall inside the
     range of genuine target-language text of the same size (calibration split, which the
     model never saw).
 (3) SURVIVES THE RED TEAM. The method fails if it reads word-shuffled Voynichese with
     about the same word order fluency, or glyph-shuffled words, text sampled from a
     Voynich-only model, or an unrelated text enciphered into EVA, about as fluently.
 (c) FITS THE PICTURES. Confirmed anchors (zodiac month labels, plant identifications)
     must decode to matching names, beyond what shuffling the decodings gives.

All parameters are pinned below for season S1. A change to any of them is a new season.
"""
import hashlib, json, lzma, math, os, platform, random, re, subprocess, sys
from collections import Counter, defaultdict
from functools import lru_cache
from . import path, SEASON, ivtff, lm, refcorpus, families

PARAMS = {
    "char_order": 5,
    "word_order": 2,
    "mdl_min_savings": 0.0,
    "bootstrap": 1000,
    "seed": 408,
    "chunk_tokens": 300,
    "fluency_q": 0.95,
    "coverage_q": 0.05,
    "ttr_band": [0.05, 0.95],
    "lexicon_min_count": 2,
    "kill_char_gap": 0.5,
    "kill_cov_gap": 0.2,
    "kill_order_frac": 0.5,
    "anchor_similarity": 0.6,
    "anchor_min_confirmed": 3,
    "anchor_min_frac": 0.5,
    "anchor_perm_p": 0.01,
    "anchor_perms": 2000,
    # criterion (d), added 24 Nov 2026 after prior work (Schwartz 2026; Voynich Text Examination 2026)
    "shape_band": [0.02, 0.98],
    "calib_noise": 0.02,
    "exclusive_margin": 0.15,
    "freedom_margin": 0.02,
}

RAW_LZMA = [{"id": lzma.FILTER_LZMA2, "preset": 9 | lzma.PRESET_EXTREME}]


def program_bits(fn):
    """A family program is charged for its code, not its documentation."""
    import ast
    tree = ast.parse(open(fn).read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return compressed_bits(ast.unparse(tree).encode())


def compressed_bits(data: bytes):
    return 8 * len(lzma.compress(data, format=lzma.FORMAT_RAW, filters=RAW_LZMA))


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def seg_fn(name):
    return lambda w: ivtff.segment(w, name)


# ------------------------------------------------------------- fixed target models

@lru_cache(maxsize=None)
def target_models(lang):
    tr = refcorpus.train_text(lang)
    cm = lm.KN([lm.char_stream(b.split()) for b in tr], PARAMS["char_order"],
               vocab=refcorpus.alphabet(lang) + [lm.WB])
    wm = lm.KN([b.split() for b in tr], PARAMS["word_order"])
    cnt = Counter(w for b in tr for w in b.split())
    lex = frozenset(w for w, c in cnt.items() if c >= PARAMS["lexicon_min_count"])
    return cm, wm, lex


def text_metrics(lang, words):
    cm, wm, lex = target_models(lang)
    if not words:
        return {"H": float("inf"), "cov": 0.0, "ttr": 0.0, "wb": float("inf"), "n": 0}
    stream = lm.char_stream(words)
    return {"H": cm.bits(stream) / len(stream), "cov": sum(w in lex for w in words) / len(words),
            "ttr": len(set(words)) / len(words), "wb": wm.bits(words) / len(words), "n": len(words)}


def chunks(words, n):
    return [words[i:i + n] for i in range(0, len(words) - n + 1, n)]


def quantile(xs, q):
    xs = sorted(xs)
    i = q * (len(xs) - 1)
    lo, hi = math.floor(i), math.ceil(i)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)


def noisy(words, lang, rate, seed):
    """Genuine text with transcription-like noise: each letter replaced at the given rate."""
    if not rate:
        return words
    rng = random.Random(seed)
    alpha = refcorpus.alphabet(lang)
    return ["".join(rng.choice(alpha) if rng.random() < rate else ch for ch in w) for w in words]


@lru_cache(maxsize=None)
def calibration(lang):
    """Bands for criterion (b), from genuine target-language text the models never saw. Bands
    take the union of clean text and text with transcription noise (PARAMS["calib_noise"]), so a
    correct reading of an imperfect transliteration is not rejected."""
    n = PARAMS["chunk_tokens"]
    clean = " ".join(refcorpus.calib_text(lang)).split()
    ms = [text_metrics(lang, c) for c in chunks(clean, n)]
    ms += [text_metrics(lang, c) for c in chunks(noisy(clean, lang, PARAMS["calib_noise"], 11), n)]
    words = clean
    rng = random.Random(PARAMS["seed"])
    gaps = []
    for c in chunks(words, n)[:60]:
        s = c[:]
        rng.shuffle(s)
        gaps.append(text_metrics(lang, s)["wb"] - text_metrics(lang, c)["wb"])
    lo, hi = PARAMS["ttr_band"]
    return {
        "chunks": len(ms),
        "H_max": quantile([m["H"] for m in ms], PARAMS["fluency_q"]),
        "cov_min": quantile([m["cov"] for m in ms], PARAMS["coverage_q"]),
        "ttr_lo": quantile([m["ttr"] for m in ms], lo),
        "ttr_hi": quantile([m["ttr"] for m in ms], hi),
        "H_median": quantile([m["H"] for m in ms], 0.5),
        "order_gap": sum(gaps) / len(gaps) if gaps else 0.0,
    }


# ------------------------------------------------------------- Voynich-only baseline

class Baseline:
    def __init__(self, train_pages, seg):
        tr_lines = [ln.words for p in train_pages for ln in p.lines if ln.words]
        self.seg = seg
        self.char = lm.KN([lm.char_stream(l, seg) for l in tr_lines], PARAMS["char_order"])
        self.dev_words = [w for l in tr_lines for w in l]
        self.train_counts = Counter(self.dev_words)
        self.glyph_freq = Counter(g for w in self.dev_words for g in seg(w))
        self.glyph_freq["<stop>"] = len(self.dev_words)

    def spell_bits(self, w):
        return self.char.bits(lm.char_stream([w], self.seg))

    def page_costs(self, eval_pages):
        b1 = {p.id: sum(self.char.bits(lm.char_stream(ln.words, self.seg)) for ln in p.lines if ln.words)
              for p in eval_pages}
        uni = lm.WordUnigramEscape(self.dev_words, self.char, self.seg)
        counts, N, T = dict(uni.prior), sum(uni.prior.values()), len(uni.prior)
        b2 = {}
        for p in eval_pages:
            b = 0.0
            for ln in p.lines:
                for w in ln.words:
                    c = counts.get(w, 0)
                    if c:
                        b -= math.log2(c / (N + T))
                    else:
                        b -= math.log2(T / (N + T))
                        b += self.spell_bits(w)
                        T += 1
                    counts[w] = c + 1
                    N += 1
            b2[p.id] = b
        best = "char_kn5" if sum(b1.values()) <= sum(b2.values()) else "word_unigram_escape"
        return (b1 if best == "char_kn5" else b2), {"char_kn5": sum(b1.values()), "word_unigram_escape": sum(b2.values()), "chosen": best}


# ------------------------------------------------------------- decoding

class Decoder:
    def __init__(self, sub, lang):
        self.sub = sub
        self.fam = families.load(sub["family"])
        self.seg = seg_fn(sub.get("segmentation", "eva-basic"))
        self.lang = lang
        self.key = sub["key"]
        self._c = {}

    def raw(self, w):
        r = self._c.get(w)
        if r is None:
            out = self.fam.decode_word(w, self.key, self.seg)
            r = refcorpus.normalize(out, self.lang)
            self._c[w] = r
        return r

    def words(self, ws):
        out = []
        for w in ws:
            out.extend(self.raw(w).split())
        return out


def key_units(sub, seg):
    """How a key cuts a Voynich word into the units its map reads: glyphs for
    substitution, greedy longest-match units (unmatched characters are nulls) for verbose."""
    if sub["family"] == "table-cipher":
        from .families import table_cipher
        return lambda w: table_cipher.units(w, sub["key"], seg)
    if sub["family"] == "substitution":
        return seg
    if sub["family"] == "verbose":
        units = sorted(sub["key"]["map"], key=len, reverse=True)

        def cut(word):
            out, i = [], 0
            while i < len(word):
                for u in units:
                    if word.startswith(u, i):
                        out.append(u)
                        i += len(u)
                        break
                else:
                    out.append(word[i])
                    i += 1
            return out
        return cut
    return None


def preimage_bits(units, plain, m, ufreq):
    """Bits to recover the Voynich word from its plaintext under a unit map: unit by unit,
    choose among the units whose output fits the plaintext still to be spelled (nulls always
    fit), weighted by training unit frequency; then a stop. A deterministic prefix code, so
    it is an honest upper bound. Returns None if the word cannot be coded this way."""
    target = plain.replace(" ", "")
    pool = [h for h in ufreq if h != "<stop>"]
    pos, bits = 0, 0.0
    for g in units + ["<stop>"]:
        rest = target[pos:]
        cands = [h for h in pool if rest.startswith(m.get(h, ""))]
        if not rest:
            cands.append("<stop>")
        if g not in cands:
            return None
        bits -= math.log2(ufreq[g] / sum(ufreq[h] for h in cands))
        if g != "<stop>":
            pos += len(m.get(g, ""))
    return bits


def unit_output_keep_spaces(v, lang):
    """A unit's plaintext output, normalized like the decoder's output but keeping the spaces it
    emits (normalize() strips a lone ' ' to '')."""
    n = refcorpus.normalize(v, lang)
    if not n:
        return " " if v and not v.isalpha() else ""
    return (" " if not v[:1].isalpha() else "") + n + (" " if not v[-1:].isalpha() else "")


def line_preimage_bits(units, plain, m, ufreq):
    """preimage_bits for keys that read a whole line as one glyph stream ("spaces": "ignored").

    The decoded plaintext of such a line carries its word breaks, so a unit that emits a space
    is only a candidate where the plaintext has one. One flag bit per line picks the mode:
    strict (the units' outputs concatenate to the plaintext exactly, so a space unit fits only
    at a space the plaintext still has), else collapsing (the receiver replays the decoder's
    normalization: runs of spaces collapse and line ends are stripped, so space units also fit
    after a space). Each step chooses among the fitting units (nulls always fit), weighted by
    training unit frequency, then a stop once the stream equals the plaintext. A deterministic
    prefix code, so an honest upper bound. Returns None if the line cannot be coded this way."""
    pool = [h for h in ufreq if h != "<stop>"]

    def code(strict):
        raw, bits = "", 0.0
        if strict:
            fits = lambda t: plain.startswith(t)
            done = lambda t: t == plain
        else:
            def fits(t):
                t = re.sub(" +", " ", t).lstrip()
                return plain.startswith(t) or (t.endswith(" ") and (plain + " ").startswith(t))
            done = lambda t: re.sub(" +", " ", t).strip() == plain
        for g in units + ["<stop>"]:
            cands = [h for h in pool if fits(raw + m.get(h, ""))]
            if done(raw):
                cands.append("<stop>")
            if g not in cands:
                return None
            bits -= math.log2(ufreq[g] / sum(ufreq[h] for h in cands))
            if g != "<stop>":
                raw += m.get(g, "")
        return bits

    b = code(True)
    if b is None:
        b = code(False)
    return None if b is None else b + 1.0


def description_length(dec, base, train_pages, eval_pages, lang):
    """Bits to transmit the evaluation pages' Voynich text through the decipherment.

    Plaintext is coded by the cheaper of two models (one flag bit), both trained on the
    target corpus PLUS the decipherment's own reading of the training pages, which mirrors
    the baseline's right to learn from the training pages: a character KN model, and a word
    unigram with escapes into it. The Voynich words are then recovered from the plaintext by
    the cheaper of two codes (one flag bit): adaptive choice among the training words with
    the same reading, or, for substitution keys, an exact glyph-by-glyph preimage code (line-level,
    space-aware, for keys that ignore the manuscript's spaces)."""
    fam = dec.sub["family"]
    prog_bits = program_bits(families.source_file(fam))
    key_bits = compressed_bits(canonical(dec.key))
    tr_plain = [dec.words(ln.words) for p in train_pages for ln in p.lines if ln.words]
    corpus = [b.split() for b in refcorpus.train_text(lang)]
    cm = lm.KN([lm.char_stream(x) for x in corpus + tr_plain], PARAMS["char_order"],
               vocab=refcorpus.alphabet(lang) + [lm.WB])
    plain_by_page = {pg.id: [dec.words(ln.words) for ln in pg.lines if ln.words] for pg in eval_pages}

    # plaintext stream, model 1: character KN
    p_char = {pid: sum(cm.bits(lm.char_stream(l)) for l in ls) for pid, ls in plain_by_page.items()}
    # plaintext stream, model 2: word unigram (prior: decoded training words) + escape
    prior = Counter(w for l in tr_plain for w in l)
    counts, N, T = dict(prior), sum(prior.values()), len(prior)
    p_uni = {}
    for pid, ls in plain_by_page.items():
        b = 0.0
        for l in ls:
            b += 1.0  # line length is implicit in the char model; the unigram pays ~1 bit/line for it
            for w in l:
                c = counts.get(w, 0)
                if c:
                    b -= math.log2(c / (N + T))
                else:
                    b -= math.log2(T / (N + T)) if N else 0.0
                    b += cm.bits(lm.char_stream([w]))
                    T += 1
                counts[w] = c + 1
                N += 1
        p_uni[pid] = b
    plain_cost = p_char if sum(p_char.values()) <= sum(p_uni.values()) else p_uni
    plain_model = "char_kn5" if plain_cost is p_char else "word_unigram_escape"

    # recovering the Voynich words: an exact unit preimage code where the family has one
    cut = key_units(dec.sub, dec.seg)
    if cut is not None:
        lines_mode = dec.sub.get("spaces") == "ignored"
        if lines_mode:
            umap = {g: unit_output_keep_spaces(v, lang) for g, v in dec.key["map"].items()}
        else:
            umap = {g: refcorpus.normalize(v, lang).replace(" ", "") for g, v in dec.key["map"].items()}
        ufreq = Counter(g for w in base.dev_words for g in cut(w))
        ufreq["<stop>"] = len(base.dev_words)
    # code 1: adaptive choice among same-reading training words
    pre = defaultdict(dict)
    for u, c in base.train_counts.items():
        pre[dec.raw(u)][u] = c
    state = {p: [dict(d), sum(d.values()), len(d)] for p, d in pre.items()}
    ch_adapt, ch_pre = {}, {}
    for pg in eval_pages:
        b1 = b2 = 0.0
        for ln in pg.lines:
            for w in ln.words:
                p = dec.raw(w)
                pb = None
                if cut is not None:
                    us = cut(w)
                    if all(u in ufreq for u in us):
                        pb = (line_preimage_bits if lines_mode else preimage_bits)(us, p, umap, ufreq)
                b2 += pb if pb is not None else base.spell_bits(w) + 1.0
                st = state.setdefault(p, [{}, 0, 0])
                counts_p, Np, Tp = st
                c = counts_p.get(w, 0)
                if c:
                    b1 -= math.log2(c / (Np + Tp))
                else:
                    if Np:
                        b1 -= math.log2(Tp / (Np + Tp))
                    b1 += pb if pb is not None else base.spell_bits(w)
                    st[2] = Tp + 1
                counts_p[w] = c + 1
                st[1] = Np + 1
        ch_adapt[pg.id], ch_pre[pg.id] = b1, b2
    choice = ch_adapt if cut is None or sum(ch_adapt.values()) <= sum(ch_pre.values()) else ch_pre
    choice_model = "adaptive_choice" if choice is ch_adapt else "unit_preimage"
    page_bits = {pid: plain_cost[pid] + choice[pid] for pid in plain_by_page}
    info = {"plaintext_model": plain_model, "plaintext_bits": round(sum(plain_cost.values()), 1),
            "choice_code": choice_model, "choice_bits": round(sum(choice.values()), 1)}
    return prog_bits + 2, key_bits, page_bits, plain_by_page, info


# ------------------------------------------------------------- decoys for the red team

def decoys(eval_pages, base, lang, seg):
    rng = random.Random(PARAMS["seed"])
    shape = [[len(ln.words) for ln in p.lines if ln.words] for p in eval_pages]
    tokens = [w for p in eval_pages for ln in p.lines for w in ln.words]

    def reshape(ws):
        it = iter(ws)
        return [[next(it) for _ in range(n)] for sh in shape for n in sh]

    # D1: word order shuffled within each page. When lines are read as one stream (spaces
    # ignored), shuffle 6-glyph chunks within each line instead.
    d1 = []
    stream_mode = all(len(ln.words) <= 1 for p in eval_pages for ln in p.lines if ln.words)
    for p in eval_pages:
        if stream_mode:
            for ln in p.lines:
                if ln.words:
                    g = seg(ln.words[0])
                    ch = [g[i:i + 6] for i in range(0, len(g), 6)]
                    rng.shuffle(ch)
                    d1.append(["".join(x for c in ch for x in c)])
            continue
        ws = [w for ln in p.lines for w in ln.words]
        rng.shuffle(ws)
        it = iter(ws)
        d1 += [[next(it) for _ in ln.words] for ln in p.lines if ln.words]
    # D2: glyphs shuffled within each word
    d2 = []
    for w in tokens:
        g = seg(w)
        rng.shuffle(g)
        d2.append("".join(g))
    # D3: random text: glyphs drawn by their training frequency, word lengths kept
    gl = [g for g in base.glyph_freq if g != "<stop>"]
    gw = [base.glyph_freq[g] for g in gl]
    d3 = ["".join(rng.choices(gl, gw, k=len(seg(w)))) for w in tokens]
    # D4: an unrelated text enciphered into EVA glyphs with a random substitution
    other = "english" if lang != "english" else "german"
    ow = " ".join(refcorpus.control_text(other)).split()
    glyphs = [g for g, _ in base.glyph_freq.most_common() if g not in ("<stop>",) and not ivtff.uncertain(g)]
    letters = sorted(set("".join(ow)))
    rng.shuffle(glyphs)
    cip = {l: glyphs[i % len(glyphs)] for i, l in enumerate(letters)}
    d4 = ["".join(cip[c] for c in w) for w in (ow * (1 + len(tokens) // max(len(ow), 1)))[: len(tokens)]]
    return {"D1_word_order_shuffled": d1, "D2_glyphs_shuffled": reshape(d2),
            "D3_random_glyphs": reshape(d3), "D4_unrelated_text_enciphered": reshape(d4)}


# ------------------------------------------------------------- anchors

def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a, b):
    a, b = a.replace(" ", ""), b.replace(" ", "")
    if not a or not b:
        return 0.0
    return 1 - lev(a, b) / max(len(a), len(b))


def _look(a):
    """(target id, assessment) of a second look: structured fields, or 'Second look at N-001: DISSENT' titles."""
    import re as _re
    d = a.get("detail") or {}
    if d.get("of"):
        return d["of"], str(d.get("assessment", "")).lower()
    m = _re.match(r"\s*second look at ([A-Z]-\d+)\s*:\s*(agree|dissent)", a.get("title", ""), _re.I)
    return (m.group(1), m.group(2).lower()) if m else (None, None)


def anchor_status(item, anchors):
    """Anchors are confirmed by the swarm, not by people: an anchor proposal counts once an agent
    other than its proposer files an 'agree' second look on it and nobody has an unanswered
    'dissent'. People review only a full PASS, at the end."""
    looks = [a for a in anchors if _look(a)[0] == item["id"]]
    seat = lambda a: a["provenance"].get("seat", a["provenance"].get("added_by"))
    agrees = {seat(a) for a in looks if _look(a)[1] == "agree" and seat(a) != seat(item)}
    dissents = [a for a in looks if _look(a)[1] == "dissent"]
    if dissents:
        return "disputed"
    return "confirmed" if agrees else "draft"


def load_anchors():
    """Anchor proposals on the record (second looks excluded), with their swarm status."""
    from . import registry
    items = registry.read("anchor")
    out = []
    for i in items:
        if _look(i)[0]:
            continue
        d = dict(i["detail"])
        d["id"] = i["id"]
        d["status"] = anchor_status(i, items)
        out.append(d)
    return out


def judge_anchors(dec, lang):
    conf = [a for a in load_anchors() if a.get("status") == "confirmed"]
    out = {"confirmed": len(conf), "pass": False}
    if len(conf) < PARAMS["anchor_min_confirmed"]:
        out["reason"] = f"only {len(conf)} confirmed anchors (need {PARAMS['anchor_min_confirmed']}): criterion (c) cannot pass yet"
        return out

    def names(a):
        return [refcorpus.normalize(n, lang) for n in a["names"].get(lang, []) + a["names"].get("any", [])]

    decs = [" ".join(dec.words(a["voynich"].split())) for a in conf]

    def matched(ds):
        return sum(any(similarity(d, n) >= PARAMS["anchor_similarity"] for n in names(a)) for d, a in zip(ds, conf))

    k = matched(decs)
    rng = random.Random(PARAMS["seed"])
    ge = 0
    for _ in range(PARAMS["anchor_perms"]):
        s = decs[:]
        rng.shuffle(s)
        ge += matched(s) >= k
    p = (ge + 1) / (PARAMS["anchor_perms"] + 1)
    out.update({"matched": k, "p_value": round(p, 5), "decoded": dict(zip([a["id"] for a in conf], decs)),
                "pass": k >= PARAMS["anchor_min_confirmed"] and k / len(conf) >= PARAMS["anchor_min_frac"] and p <= PARAMS["anchor_perm_p"]})
    return out


# ------------------------------------------------------------- the verdict

def environment():
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path(), capture_output=True, text=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "vs", "claims", "anchors", "pins"], cwd=path(), capture_output=True, text=True).stdout.strip())
    except Exception:
        commit, dirty = None, None
    return {"season": SEASON, "python": platform.python_version(), "code_commit": commit, "tree_dirty": dirty,
            "params_sha256": hashlib.sha256(canonical(PARAMS)).hexdigest()}


def evaluate(sub, train_pages, eval_pages, split_name):
    lang = sub["target"]["language"]
    if lang not in refcorpus.languages():
        return {"verdict": "NOT JUDGEABLE", "reason": f"no pinned corpus for {lang!r}"}
    seg = seg_fn(sub.get("segmentation", "eva-basic"))
    base = Baseline(train_pages, seg)
    dec = Decoder(sub, lang)
    cal = calibration(lang)
    rng = random.Random(PARAMS["seed"])

    # (a) compression
    base_pages, base_info = base.page_costs(eval_pages)
    prog_bits, key_bits, cand_pages, plain, dl_info = description_length(dec, base, train_pages, eval_pages, lang)
    diffs = [base_pages[p.id] - cand_pages[p.id] for p in eval_pages]
    fixed = prog_bits + key_bits
    total_base = sum(base_pages.values())
    savings = (sum(diffs) - fixed) / total_base
    boot = []
    for _ in range(PARAMS["bootstrap"]):
        s = [diffs[rng.randrange(len(diffs))] for _ in diffs]
        boot.append(sum(s) - fixed)
    lo95 = quantile(boot, 0.025)
    a = {"pass": savings > PARAMS["mdl_min_savings"] and lo95 > 0, "savings": round(savings, 5),
         "baseline_bits": round(total_base, 1), "candidate_bits": round(sum(cand_pages.values()) + fixed, 1),
         "program_bits": prog_bits, "key_bits": key_bits, "bootstrap_lo95_bits": round(lo95, 1), "baseline": base_info, "candidate": dl_info}

    # (b) reading, per section
    pmap = {p.id: p for p in eval_pages}
    by_sec = defaultdict(list)
    for pid, lines in plain.items():
        for l in lines:
            by_sec[pmap[pid].section].extend(l)
    secs, judged = {}, 0
    n = PARAMS["chunk_tokens"]
    for s, ws in sorted(by_sec.items()):
        cs = chunks(ws, n)
        if not cs:
            secs[s] = {"tokens": len(ws), "judged": False}
            continue
        judged += 1
        ms = [text_metrics(lang, c) for c in cs]
        H = sum(m["H"] for m in ms) / len(ms)
        cov = sum(m["cov"] for m in ms) / len(ms)
        ttr = sum(m["ttr"] for m in ms) / len(ms)
        ok = H <= cal["H_max"] and cov >= cal["cov_min"] and cal["ttr_lo"] <= ttr <= cal["ttr_hi"]
        secs[s] = {"tokens": len(ws), "judged": True, "H": round(H, 4), "coverage": round(cov, 4), "ttr": round(ttr, 4), "pass": ok}
    allw = [w for s in by_sec.values() for w in s]
    b = {"pass": judged > 0 and all(v["pass"] for v in secs.values() if v.get("judged")),
         "sections": secs, "calibration": {k: round(v, 4) for k, v in cal.items()}, "output_tokens": len(allw),
         "voynich_tokens": sum(len(ln.words) for p in eval_pages for ln in p.lines)}

    # (3) kill tests
    real_lines = [l for pid in plain for l in plain[pid]]
    real = text_metrics(lang, [w for l in real_lines for w in l])
    kills = {}
    for name, lines in decoys(eval_pages, base, lang, seg).items():
        ws = dec.words([w for l in lines for w in l])
        m = text_metrics(lang, ws)
        if name.startswith("D1"):
            gap = m["wb"] - real["wb"]
            killed = gap < PARAMS["kill_order_frac"] * cal["order_gap"]
            kills[name] = {"word_bits_gap": round(gap, 4), "needed": round(PARAMS["kill_order_frac"] * cal["order_gap"], 4), "killed": killed}
        else:
            killed = m["H"] <= real["H"] + PARAMS["kill_char_gap"] and m["cov"] >= real["cov"] - PARAMS["kill_cov_gap"]
            kills[name] = {"H": round(m["H"], 4), "coverage": round(m["cov"], 4), "killed": killed}
    k = {"pass": not any(v["killed"] for v in kills.values()),
         "real": {"H": round(real["H"], 4), "coverage": round(real["cov"], 4), "word_bits": round(real["wb"], 4)}, "decoys": kills}

    # (c) anchors
    c = judge_anchors(dec, lang)

    # (d) not an illusion
    d = not_an_illusion(sub, dec, lang, allw, train_pages, eval_pages, a["savings"])

    passed = a["pass"] and b["pass"] and k["pass"] and c["pass"] and d["pass"]
    pages_pass = []
    if passed:
        for p in eval_pages:
            ws = [w for l in plain[p.id] for w in l]
            if ws and text_metrics(lang, ws)["H"] <= cal["H_max"] and base_pages[p.id] > cand_pages[p.id]:
                pages_pass.append(p.id)
    failed = [n for n, r in (("a_compresses", a), ("b_reads", b), ("kill_tests", k), ("c_pictures", c), ("d_not_illusion", d)) if not r["pass"]]
    # a decoded held-out line could reveal which pages are held out: withheld until the reveal
    sample = " ".join(w for l in real_lines[:3] for w in l)[:300] if split_name != "heldout" else "(withheld on held-out pages until the reveal)"
    return {
        "submission": sub.get("id"), "family": sub["family"], "target": sub["target"], "split": split_name,
        "verdict": "PASS" if passed else "FAIL", "failed": failed,
        "pages_evaluated": len(eval_pages), "pages_passing": len(pages_pass) if passed else 0,
        "a_compresses": a, "b_reads": b, "kill_tests": k, "c_pictures": c, "d_not_illusion": d,
        "plaintext_sample": sample, "params": PARAMS, "environment": environment(),
    }


def _rep4(words):
    from collections import Counter as _C
    c = _C(tuple(words[i:i + 4]) for i in range(len(words) - 3))
    t = sum(c.values())
    return sum(v for v in c.values() if v >= 2) / t if t else 0.0


@lru_cache(maxsize=None)
def _shape_calib(lang, n):
    words = " ".join(refcorpus.calib_text(lang)).split()
    words = words + noisy(words, lang, PARAMS["calib_noise"], 12)
    rows = []
    for i in range(0, max(len(words) - n, 1), max(n, 1)):
        w = words[i:i + n]
        if len(w) < n:
            break
        letters = Counter(ch for x in w for ch in x)
        tot = sum(letters.values()) or 1
        top3 = sum(v for _k, v in letters.most_common(3)) / tot
        cw = Counter(w)
        rows.append((top3, sum(1 for v in cw.values() if v == 1) / max(len(cw), 1), _rep4(w)))
    return rows


def not_an_illusion(sub, dec, lang, words, train_pages, eval_pages, savings):
    """Criterion (d), from prior work on the 'decipherment illusion' (Schwartz 2026) and on phrase
    repetition (Voynich Text Examination 2026). A flexible key can make anything look like a language;
    these checks ask whether the output is shaped like the language, repeats like it, belongs to it
    rather than to a rival, and beats what the same freedom achieves on meaningless text."""
    out = {}
    n = max(len(words), 1)
    cal = _shape_calib(lang, min(n, 3000)) or [(0, 0, 0)]
    lo, hi = PARAMS["shape_band"]
    letters = Counter(ch for x in words for ch in x)
    tot = sum(letters.values()) or 1
    top3 = sum(v for _k, v in letters.most_common(3)) / tot
    cw = Counter(words)
    hap = sum(1 for v in cw.values() if v == 1) / max(len(cw), 1)
    q = lambda xs, p: quantile(xs, p) if xs else 0
    t_lo, t_hi = q([r[0] for r in cal], lo), q([r[0] for r in cal], hi)
    h_lo, h_hi = q([r[1] for r in cal], lo), q([r[1] for r in cal], hi)
    out["shape"] = {"top3_letter_share": round(top3, 4), "band": [round(t_lo, 4), round(t_hi, 4)],
                    "hapax_share": round(hap, 4), "hapax_band": [round(h_lo, 4), round(h_hi, 4)],
                    "pass": t_lo <= top3 <= t_hi and h_lo <= hap <= h_hi}
    rep = _rep4(words)
    floor = q([r[2] for r in cal], lo)  # the low end of genuine text of the same length
    out["phrase_repetition"] = {"rate": round(rep, 5), "language_low_end": round(floor, 5),
                                "language_mean": round(sum(r[2] for r in cal) / len(cal), 5),
                                "pass": rep >= floor - 4.0 / n}  # allow for a repeated phrase or two missed by chance (one repeat = 2 occurrences)
    # exclusivity: the output must read better as the declared language than as any rival
    stream = lm.char_stream(words[:3000])
    own = target_models(lang)[0].bits(stream) / max(len(stream), 1)
    rivals = {}
    for r in refcorpus.languages():
        if r == lang:
            continue
        try:
            src = " ".join(words[:3000])
            rw = refcorpus.normalize(src, r).split()
            if sum(map(len, rw)) < 0.8 * sum(map(len, words[:3000])):
                continue  # a rival in another script cannot read this output at all
            rs = lm.char_stream(rw)
            rivals[r] = target_models(r)[0].bits(rs) / max(len(rs), 1)
        except Exception:
            continue
    best = min(rivals.values()) if rivals else float("inf")
    out["exclusive"] = {"own_bits_per_char": round(own, 4), "best_rival": min(rivals, key=rivals.get) if rivals else None,
                        "rival_bits_per_char": round(best, 4), "pass": own <= best - PARAMS["exclusive_margin"]}
    # matched freedom: the same family, searched at the same budget, on meaningless text shaped like the pages
    fam = sub["family"]
    if fam in ("substitution", "verbose", "table-cipher") and sub.get("search", {}).get("budget"):
        from . import search, generators
        try:
            gtr = generators.g_table_cipher(train_pages, train_pages)
            gev = generators.g_table_cipher(train_pages, eval_pages, seed=2)
            fk = search.search_cell(lang, fam, gtr, budget=sub["search"]["budget"], tag="freedom")
            fr = evaluate_core(fk, gtr, gev, lang)
            out["matched_freedom"] = {"meaningless_savings": round(fr, 5), "savings": round(savings, 5),
                                      "pass": savings >= fr + PARAMS["freedom_margin"]}
        except Exception as ex:
            out["matched_freedom"] = {"pass": False, "error": str(ex)[:200]}
    else:
        out["matched_freedom"] = {"pass": True, "note": "no declared search budget: not applicable (keys from unknown searches are judged on (a)-(c) and the other checks)"}
    out["pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict))
    return out


def evaluate_core(sub, train_pages, eval_pages, lang):
    """Compression savings only (criterion a), for the matched-freedom control."""
    seg = seg_fn(sub.get("segmentation", "eva-basic"))
    base = Baseline(train_pages, seg)
    dec = Decoder(sub, lang)
    bp, _ = base.page_costs(eval_pages)
    pb, kb, cp, _plain, _info = description_length(dec, base, train_pages, eval_pages, lang)
    return (sum(bp.values()) - sum(cp.values()) - pb - kb) / max(sum(bp.values()), 1)


def load_key(fn):
    sub = json.load(open(fn))
    for f in ("id", "family", "target", "key"):
        if f not in sub:
            raise SystemExit(f"key file missing {f!r}")
    return sub
