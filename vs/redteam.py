"""Program R: the red team. Its only job is to break claims; a successful attack weighs the
same as a result in the ledger (on the path when the target is on the path).

Three kinds of attack, each a mechanical check, so no attack is settled by argument:

  key-attack     Target: a key that passes some of the judge. The attacker names a DECOY
                 (a pinned decoy constructor plus parameters) on which the key's output also
                 passes (b) "reads". Success: the key reads the decoy about as well as the
                 manuscript, so its fluency is not evidence. A successful decoy is proposed
                 for the next season's kill tests (it must not kill any positive control).

  fact-attack    Target: an ESTABLISHED fact that is claimed to show language or meaning.
                 The attacker supplies SYNTHETIC TEXT (data, not code: a list of lines of
                 words, made without the held-out pages) plus a one-paragraph method. The
                 scorer cuts it into the evaluation pages' shapes and reruns the fact.
                 Success: the fact holds on the synthetic text too, so it needs no language.
                 Guard: the text must not copy the manuscript's phrases (no run of 4 consecutive
                 manuscript words). Using the manuscript's own words is allowed, as period
                 table procedures would; the share is reported.

  claim-attack   Target: a published or submitted decipherment claim. The attacker submits
                 the claim as a key (family + key) and the judge rules. A FAIL is a
                 successful attack and goes in the refutation log with the claimant named.

Attack experiments are experiments/<step>/<handle>/ with experiment.json kind
"attack" plus attack.json; see join.txt.
"""
import json, random
from . import corpus, facts, judge, ivtff
from .ivtff import Page, Line

DECOYS = {
    "word_shuffle": "real evaluation pages with words shuffled within each page (params: seed)",
    "glyph_shuffle": "real words with glyphs shuffled within each word (params: seed)",
    "random_glyphs": "random glyphs by training frequency, word lengths kept (params: seed)",
    "reversed_words": "every real word spelled backwards (params: none)",
    "other_language": "a reference language's control text enciphered into EVA (params: language, seed)",
    "cross_section": "pages of one section relabelled as another (params: from, to)",
}


def build_decoy(kind, params, eval_pages, base, seg):
    rng = random.Random(params.get("seed", 1))
    shape = [(p, ln) for p in eval_pages for ln in p.lines if ln.words]
    toks = [w for _p, ln in shape for w in ln.words]
    if kind == "word_shuffle":
        out = []
        for p in eval_pages:
            ws = [w for ln in p.lines for w in ln.words]
            rng.shuffle(ws)
            it = iter(ws)
            out += [[next(it) for _ in ln.words] for ln in p.lines if ln.words]
        return out
    if kind == "glyph_shuffle":
        new = []
        for w in toks:
            g = seg(w)
            rng.shuffle(g)
            new.append("".join(g))
    elif kind == "random_glyphs":
        gl = [g for g in base.glyph_freq if g != "<stop>"]
        gw = [base.glyph_freq[g] for g in gl]
        new = ["".join(rng.choices(gl, gw, k=len(seg(w)))) for w in toks]
    elif kind == "reversed_words":
        new = ["".join(reversed(seg(w))) for w in toks]
    elif kind == "other_language":
        from . import refcorpus
        ow = " ".join(refcorpus.control_text(params["language"])).split()
        glyphs = [g for g, _ in base.glyph_freq.most_common() if g != "<stop>" and not ivtff.uncertain(g)]
        rng.shuffle(glyphs)
        letters = sorted(set("".join(ow)))
        cip = {l: glyphs[i % len(glyphs)] for i, l in enumerate(letters)}
        new = ["".join(cip[c] for c in w) for w in (ow * (1 + len(toks) // max(len(ow), 1)))[: len(toks)]]
    elif kind == "cross_section":
        src = [p for p in corpus.pages() if p.section == params["from"]]
        new = [w for p in src for ln in p.lines for w in ln.words][: len(toks)]
        new += toks[len(new):]
    else:
        raise SystemExit(f"unknown decoy {kind!r}; pinned decoys: {sorted(DECOYS)}")
    it = iter(new)
    return [[next(it) for _ in ln.words] for _p, ln in shape]


def key_attack(target_key, decoy, params, split):
    train, ev = corpus.split_pages(split)
    lang = target_key["target"]["language"]
    seg = judge.seg_fn(target_key.get("segmentation", "eva-basic"))
    base = judge.Baseline(train, seg)
    dec = judge.Decoder(target_key, lang)
    cal = judge.calibration(lang)
    lines = build_decoy(decoy, params, ev, base, seg)
    real = judge.text_metrics(lang, dec.words([w for p in ev for ln in p.lines for w in ln.words]))
    fake = judge.text_metrics(lang, dec.words([w for l in lines for w in l]))
    reads = fake["H"] <= cal["H_max"] and fake["cov"] >= cal["cov_min"]
    close = fake["H"] <= real["H"] + judge.PARAMS["kill_char_gap"] and fake["cov"] >= real["cov"] - judge.PARAMS["kill_cov_gap"]
    return {"attack": "key", "target": target_key.get("id"), "decoy": decoy, "params": params,
            "real": {k: round(v, 4) for k, v in real.items() if k in ("H", "cov")},
            "decoy_output": {k: round(v, 4) for k, v in fake.items() if k in ("H", "cov")},
            "success": bool(reads or close),
            "why": "decoy read about as fluently as the manuscript" if (reads or close) else "the key does not read this decoy"}


def _manuscript_4grams():
    out = set()
    for p in corpus.pages():
        for ln in p.lines:
            w = ln.words
            out.update(tuple(w[i:i + 4]) for i in range(len(w) - 3))
    return out


def fact_attack(fact_id, lines, split, fact_item=None, cut="tokens"):
    """lines: list of lists of words (the attacker's synthetic text). fact_item: the
    registry item for the target fact (its detail holds the metric and params).

    cut: how the synthetic text is laid onto the evaluation pages.
      "tokens" (default): one token stream cut to the pages' line lengths. The attacker's line
               breaks are lost, so no generator can know where a line ends: a positional fact
               (line-initial, line-final) survives every such attack by construction (R-001).
      "lines": each evaluation line takes the next synthetic line whole (its length is the
               attacker's). This lets a procedure that sees the line end, as any scribe or
               table method writing on a page does, be tested against positional facts.
               Page and line metadata (section, language, unit, paragraph marks) stay the
               evaluation pages'."""
    lines = [[str(w) for w in l if str(w)] for l in lines if l]
    toks = [w for l in lines for w in l]
    ms4 = _manuscript_4grams()
    copied = sum(tuple(l[i:i + 4]) in ms4 for l in lines for i in range(len(l) - 3))
    types = {w for p in corpus.pages() for w in p.words()}
    shared = sum(w in types for w in toks) / max(len(toks), 1)
    train, ev = corpus.split_pages(split)
    need = sum(len(ln.words) for p in ev for ln in p.lines)
    guard = []
    if copied:
        guard.append(f"{copied} four-word runs copied from the manuscript")
    marked = sum(1 for w in toks if "?" in w or "*" in w)
    if marked:
        guard.append(f"{marked} tokens carry uncertainty markers (? or *): synthetic text may not use them "
                     "(they are a transcription convention, and metrics skip them; found by the red team, R-003)")
    if cut not in ("tokens", "lines"):
        guard.append(f"cut must be 'tokens' or 'lines', got {cut!r}")
    elif cut == "lines":
        need_lines = sum(1 for p in ev for ln in p.lines if ln.words)
        if len(lines) < need_lines:
            guard.append(f"cut 'lines' needs at least {need_lines} lines to fill the evaluation pages, got {len(lines)}")
    elif len(toks) < need:
        guard.append(f"needs at least {need} tokens to fill the evaluation pages, got {len(toks)}")
    if guard:
        return {"attack": "fact", "target": fact_id, "success": False, "refused": guard}
    it = iter(toks)
    lit = iter(lines)
    fake = []
    for p in ev:
        q = Page(p.id, p.order, dict(p.meta))
        for ln in p.lines:
            if cut == "lines":
                ws = list(next(lit)) if ln.words else []
            else:
                ws = [next(it) for _ in ln.words]
            q.lines.append(Line(ln.id, ln.page, ln.n, ln.unit, ln.subtype, ws, ln.para_start, ln.para_end))
        fake.append(q)
    if fact_item is None:
        from . import registry
        fact_item = registry.get(fact_id)
    if not fact_item or fact_item["type"] != "fact":
        return {"attack": "fact", "target": fact_id, "success": False, "refused": [f"{fact_id} is not a fact on the record"]}
    if "spec" in fact_item["detail"]:
        from . import dsl
        spec = fact_item["detail"]["spec"]
        real, got = dsl.evaluate(spec, ev), dsl.evaluate(spec, fake)
    else:
        m, prm = fact_item["detail"]["metric"], fact_item["detail"]["params"]
        real = facts.METRICS[m](train, ev, **prm)
        got = facts.METRICS[m](train, fake, **prm)
    det = got.get("detail") or {}
    if "rate_in" in det and "n_in" in det and round(det["rate_in"] * det["n_in"]) < 10:
        return {"attack": "fact", "target": fact_id, "success": False,
                "refused": ["positional attack with fewer than 10 hits: too few to reproduce a fact (P-J-001)"]}
    return {"attack": "fact", "target": fact_id, "real": {"pass": real["pass"], "value": real["value"]},
            "synthetic": {"pass": got["pass"], "value": got["value"]}, "shared_type_share": round(shared, 3), "cut": cut,
            "success": bool(real["pass"] and got["pass"]),
            "why": "the fact also holds on text made without language" if (real["pass"] and got["pass"]) else "the synthetic text does not reproduce the fact"}


def run_attack(spec, split):
    kind = spec["attack"]
    if kind == "key":
        tk = spec["target_key"]
        if isinstance(tk, str) and not tk.endswith(".json"):
            from . import registry   # a record id: attack the key exactly as it was submitted
            it = registry.get(tk)
            if not it or "key.json" not in (it.get("submitted") or {}):
                return {"attack": "key", "target": tk, "success": False, "refused": [f"{tk} is not a key on the record"]}
            key = it["submitted"]["key.json"]
        else:
            key = json.load(open(tk)) if isinstance(tk, str) else tk
        return key_attack(key, spec["decoy"], spec.get("params", {}), split)
    if kind == "fact":
        return fact_attack(spec["target_fact"], spec["lines"], split, spec.get("target_fact_item"),
                           cut=spec.get("cut", "tokens"))
    if kind == "claim":
        train, ev = corpus.split_pages(split)
        r = judge.evaluate(spec["key"], train, ev, split)
        return {"attack": "claim", "target": spec["key"].get("id"), "claimant": spec.get("claimant"),
                "verdict": r["verdict"], "failed": r["failed"], "success": r["verdict"] == "FAIL"}
    raise SystemExit("attack must be key, fact or claim")
