"""Test calibration: the runs that show the test itself works, before anyone relies on it.

    python3 -m vs season --split heldout

Two things only, both about the TEST, not about the manuscript:
  controls  genuine text in each candidate language, enciphered with random keys: the true
            key must pass, and the pinned search must find a passing key (else a grid cell
            in that language can never be ruled out: "no power").
  redteam   decoders built to look fluent (every word -> one Latin word; a hashed real
            word) must fail.
Findings about the manuscript are never produced here: they come only from agents' pull
requests, through vs/score.py, onto the record (registry/items.jsonl).
"""
import json, os, time
from . import path, corpus, judge, controls, search, refcorpus

def _langs():
    from . import refcorpus
    base = ["latin", "italian", "spanish", "french", "catalan", "german", "english", "czech", "hebrew"]
    # constructed languages (conlang_*) are pinned as references for the hypothesis matrix (P-J-004),
    # not as candidate plaintexts: no controls, no grid cells, no first-key steps for them
    return base + [l for l in refcorpus.languages() if l not in base and not l.startswith("conlang_")]


LANGS = _langs()
FAMILIES = ["substitution", "verbose", "nomenclator"]
CONTROL_FOR = {"substitution": "homophonic", "verbose": "verbose", "nomenclator": "nomenclator"}
GRID_FAMILIES = ["substitution", "verbose", "nomenclator", "table-cipher", "abbreviation"]


def _save(split, name, obj):
    d = path("results", split)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + ".json"), "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=str)


def _short(r):
    keep = {k: r[k] for k in ("submission", "family", "target", "verdict", "failed") if k in r}
    keep["passes_without_anchors"] = r["a_compresses"]["pass"] and r["b_reads"]["pass"] and r["kill_tests"]["pass"]
    keep["savings"] = r["a_compresses"]["savings"]
    keep["killed_by"] = [n for n, v in r["kill_tests"]["decoys"].items() if v["killed"]]
    return keep


def _german_verbose_sizes(pages, true_key, log):
    """Report two additional sample sizes on disjoint synthetic training and
    evaluation pages. The grid uses only the standard one-in-seven verdict."""
    rows = []
    for residues in ((3, 4), (3, 4, 5)):
        train, evaluation = [], []
        for page in sorted(pages, key=lambda p: int(p.id[1:])):
            (evaluation if int(page.id[1:]) % 7 in residues else train).append(page)
        key = search.search_cell("german", "verbose", train, tag="control")
        planted = _short(judge.evaluate(true_key, train, evaluation, "control"))
        fitted = _short(judge.evaluate(key, train, evaluation, "control"))
        tokens = sum(len(line.words) for p in evaluation for line in p.lines)
        rows.append({"evaluation_residues_mod_7": list(residues), "tokens": tokens,
                     "true_key": planted, "search_key": fitted})
        log(f"sample size german verbose 2% noise tokens={tokens} "
            f"planted={planted['passes_without_anchors']} search={fitted['passes_without_anchors']}")
    return rows


def run(split, log=print, parts=("controls", "redteam")):
    train, ev = corpus.split_pages(split)
    t0 = time.time()
    if "controls" in parts:
        rows = []
        for lang in LANGS:
            for fam in FAMILIES:
                if fam == "nomenclator" and len(refcorpus.alphabet(lang)) > len(controls.CIPHER_GLYPHS):
                    log(f"control {lang:8s} {fam:12s} unsupported alphabet size")
                    continue
                res = {}
                for noise in (0.0, controls.NOISE):
                    try:
                        ctr, cev, true = controls.make(lang, CONTROL_FOR[fam], noise=noise)
                    except (ValueError, IndexError) as ex:
                        # this cipher family cannot be built over this alphabet: no control, so no power
                        log(f"control {lang:8s} {fam:12s} cannot build a control ({str(ex)[:60]})")
                        res = None
                        break
                    rt = _short(judge.evaluate(true, ctr, cev, "control"))
                    rs = _short(judge.evaluate(search.search_cell(lang, fam, ctr, tag="control"), ctr, cev, "control"))
                    res[noise] = (rt, rs, sum(len(l.words) for p in cev for l in p.lines))
                if res is None:
                    continue
                (rt0, rs0, n0), (rtn, rsn, _) = res[0.0], res[controls.NOISE]
                rows.append({"language": lang, "family": fam, "control": CONTROL_FOR[fam], "control_tokens": n0,
                             "true_key": rt0, "true_key_passes": rt0["passes_without_anchors"],
                             "search_key": rs0, "search_cracks_control_clean": rs0["passes_without_anchors"],
                             "noise": controls.NOISE, "true_key_passes_noisy": rtn["passes_without_anchors"],
                             # power counts only if the search cracks the control with transcription noise
                             "search_cracks_control": rsn["passes_without_anchors"]})
                log(f"control {lang:8s} {fam:12s} clean={rs0['passes_without_anchors']} noisy={rsn['passes_without_anchors']}")
                if (lang, fam) == ("german", "verbose"):
                    rows[-1]["noisy_sample_size_checks"] = _german_verbose_sizes(ctr + cev, true, log)
        _save(split, "controls", rows)
    if "redteam" in parts:
        rows = [_short(judge.evaluate(k, train, ev, split)) for lang in ("latin", "italian") for k in controls.red_team_keys(lang)]
        _save(split, "redteam", rows)
        log(f"red-team decoders: {sum(r['verdict'] == 'FAIL' for r in rows)}/{len(rows)} rejected")
    _save(split, "summary", {"split": split, "environment": judge.environment(), "pages_evaluated": len(ev),
                             "seconds": round(time.time() - t0)})
