"""One experiment per pull request.

A pull request adds exactly one directory, experiments/<step-id>/<handle>/, holding
experiment.json and, for a key, key.json. Nothing else in the repository changes (code
changes, such as a new family or metric, go in their own reviewed pull request first).

experiment.json:
  {"step": "<step id from the desk>", "handle": "<github handle>",
   "kind": "key" | "segmentation",
   "summary": "one plain sentence",
   "lease": "<lease id, optional>"}

  kind "key":           key.json is a submission (family, target, segmentation, key)
  kind "segmentation":  experiment.json also has "units": ["ch", "sh", ...]
  kind "attack":        attack.json is a red-team attack (vs/redteam.py): key, fact or claim

This command is the ADVISORY check anyone can run: it validates the shape and scores the
practice split. The AUTHORITATIVE verdict comes from the scorer, who runs the same pinned
judge on the held-out pages; it never executes code from a pull request, only reads these
two JSON files.
"""
import json, os, re, sys
from . import path, corpus, judge, ivtff, lm

ALLOWED = {"model.json", "source.json", "experiment.json", "key.json", "attack.json", "fact.json", "anchor.json", "step.json", "corpus.json", "picture.json"}
PICTURE_KINDS = {"plant", "plant_part", "root", "leaf", "flower", "star", "sun", "moon", "zodiac_figure", "human_figure", "pool", "pipe", "jar", "container", "rosette", "diagram", "animal", "other"}
KINDS = {"picture": "picture.json", "model": "model.json", "source": "source.json", "corpus": "corpus.json", "key": "key.json", "attack": "attack.json", "fact": "fact.json", "anchor": "anchor.json", "step": "step.json", "segmentation": None}
STEP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,80}$")


def validate(d):
    errs = []
    files = set(os.listdir(d))
    if not {"experiment.json"} <= files:
        errs.append("missing experiment.json")
    if files - ALLOWED:
        errs.append(f"unexpected files: {sorted(files - ALLOWED)}")
    for f in files & ALLOWED:
        if os.path.getsize(os.path.join(d, f)) > 512 * 1024:
            errs.append(f"{f} is larger than 512 KiB")
    if errs:
        return None, errs
    e = json.load(open(os.path.join(d, "experiment.json")))
    parts = os.path.normpath(d).split(os.sep)
    if not STEP.match(str(e.get("step", ""))):
        errs.append("step id missing or malformed")
    if parts[-2:] != [e.get("step"), e.get("handle")]:
        errs.append("directory must be experiments/<step>/<handle>/ matching experiment.json")
    if e.get("kind") not in KINDS:
        errs.append(f"kind must be one of {sorted(KINDS)}")
    elif KINDS[e["kind"]] and KINDS[e["kind"]] not in files:
        errs.append(f"kind '{e['kind']}' needs {KINDS[e['kind']]}")
    if e.get("kind") == "fact":
        f = json.load(open(os.path.join(d, "fact.json")))
        from . import facts as _facts
        for k in ("title", "statement"):
            if k not in f:
                errs.append(f"fact.json needs {k!r}")
        if "spec" in f:
            from . import dsl
            try:
                dsl.evaluate(f["spec"], corpus.split_pages("practice")[1])
            except dsl.SpecError as ex:
                errs.append(f"spec: {ex}")
        elif f.get("metric") not in _facts.METRICS:
            errs.append("fact.json needs a 'spec' (measurement language, see vs/dsl.py) or a built-in 'metric' with 'params'")
    if e.get("kind") == "model":
        from . import models
        m = json.load(open(os.path.join(d, "model.json")))
        for k in ("title", "components"):
            if k not in m:
                errs.append(f"model.json needs {k!r}")
        try:
            models.build(m, models.scoped(corpus.split_pages("practice")[0], m.get("scope")))
        except models.ModelError as ex:
            errs.append(f"model: {ex}")
    if e.get("kind") == "source":
        src = json.load(open(os.path.join(d, "source.json")))
        if src.get("of"):
            if src.get("assessment") not in ("agree", "dissent", "weak"):
                errs.append("a second look needs assessment: agree | dissent (on a source) or weak (on a succeeded attack whose generator writes the target pattern in by hand)")
        else:
            for k in ("title", "authors", "year", "url", "established", "open"):
                if k not in src:
                    errs.append(f"source.json needs {k!r}")
            if not isinstance(src.get("established", []), list) or not isinstance(src.get("open", []), list):
                errs.append("established and open are lists")
            for q in src.get("open", []):
                if not isinstance(q, dict) or not q.get("question") or q.get("front") not in ("L1", "L2", "L3", "L4", "L5", "G", "J", "R", "K"):
                    errs.append("each open item is {\"question\": ..., \"front\": L1|L2|L3|L4|L5|G|J|R|K}")
    if e.get("kind") == "corpus":
        c = json.load(open(os.path.join(d, "corpus.json")))
        for k in ("language", "title", "period", "url", "sha256", "license"):
            if k not in c:
                errs.append(f"corpus.json needs {k!r}")
        if c.get("license") not in ("public-domain", "cc0", "cc-by", "cc-by-sa"):
            errs.append("license must be public-domain, cc0, cc-by or cc-by-sa (no paywalled or unclear sources)")
        if not re.match(r"^[a-z][a-z_-]{1,30}$", str(c.get("language", ""))):
            errs.append("language must be a lowercase name, e.g. occitan, arabic, middle_dutch")
    if e.get("kind") == "picture":
        pic = json.load(open(os.path.join(d, "picture.json")))
        for k in ("folio", "canvas", "objects", "blind"):
            if k not in pic:
                errs.append(f"picture.json needs {k!r}")
        if pic.get("blind") is not True:
            errs.append("picture.json: annotate blind (\"blind\": true): from the scan alone, without reading the transcription's words or anyone else's annotation of this folio")
        objs = pic.get("objects") or []
        if not isinstance(objs, list) or not objs or len(objs) > 200:
            errs.append("objects: a list of 1 to 200 drawn objects")
        for o in objs if isinstance(objs, list) else []:
            if not isinstance(o, dict) or not o.get("id") or o.get("kind") not in PICTURE_KINDS or not isinstance(o.get("features", {}), dict):
                errs.append(f"each object is {{\"id\", \"kind\": one of {sorted(PICTURE_KINDS)}, \"features\": {{...}}, \"label\": ZL locus id or null}}")
                break
    if e.get("kind") == "step":
        st = json.load(open(os.path.join(d, "step.json")))
        for k in ("title", "statement", "program", "check"):
            if k not in st:
                errs.append(f"step.json needs {k!r}")
    return e, errs


def segmentation_score(units, split):
    """Held-out bits per EVA character under the pinned character model, for a segmentation."""
    train, ev = corpus.split_pages(split)
    ivtff.SEGMENTATIONS["_candidate"] = list(units)
    out = {}
    for name in ("eva-raw", "eva-basic", "eva-iin", "_candidate"):
        seg = lambda w, n=name: ivtff.segment(w, n)
        m = lm.KN([lm.char_stream(ln.words, seg) for p in train for ln in p.lines if ln.words], 5)
        bits = sum(m.bits(lm.char_stream(ln.words, seg)) for p in ev for ln in p.lines if ln.words)
        chars = sum(len(w) + 1 for p in ev for ln in p.lines for w in ln.words)
        out[name] = round(bits / chars, 5)
    return out


def main(d, split="practice"):
    e, errs = validate(d)
    if errs:
        print("REFUSED:\n  " + "\n  ".join(errs))
        return 1
    if e["kind"] == "key":
        sub = judge.load_key(os.path.join(d, "key.json"))
        from .models import scoped
        from . import views
        views.check(sub)
        train, ev = corpus.split_pages(split, sub.get("transliteration", "zl"))
        train, ev = views.apply(scoped(train, sub.get("scope")), sub), views.apply(scoped(ev, sub.get("scope")), sub)
        r = judge.evaluate(sub, train, ev, split)
        print(json.dumps({k: r[k] for k in ("verdict", "failed", "pages_evaluated", "pages_passing")}, indent=1))
        print(f"{'ADVISORY ' if split != 'heldout' else ''}VERDICT on {split}: {r['verdict']}")
    elif e["kind"] == "fact":
        from . import facts as _facts
        f = json.load(open(os.path.join(d, "fact.json")))
        train, ev = corpus.split_pages(split)
        if "spec" in f:
            from . import dsl
            r = dsl.evaluate(f["spec"], ev)
        else:
            r = _facts.METRICS[f["metric"]](train, ev, **f["params"])
        print(json.dumps(r, indent=1, default=str))
        print(f"ADVISORY VERDICT on {split}: {'ESTABLISHED' if r['pass'] else 'REFUTED'} (the held-out verdict is the one that counts, scored once)")
    elif e["kind"] == "model":
        from . import models
        m = json.load(open(os.path.join(d, "model.json")))
        train, ev = corpus.split_pages(split)
        print(json.dumps(models.evaluate(m, train, ev), indent=1))
        print(f"ADVISORY score on {split} (held-out bits per word; lower is better)")
    elif e["kind"] == "source":
        print("source: shape OK. The scorer checks the url is openly reachable and not already catalogued; "
              "each open question becomes a step on the desk credited to you.")
    elif e["kind"] == "corpus":
        print("corpus proposal: shape OK. The scorer downloads it, verifies the sha256, checks size and license, "
              "runs the positive controls for the language, and adds it to the pins if it passes.")
    elif e["kind"] in ("anchor", "step"):
        print(f"{e['kind']} proposal: shape OK. Not scored by the test; it goes on the record as a proposal "
              + ("and needs two people to confirm it on the scan." if e["kind"] == "anchor" else "and appears on the desk once merged."))
    elif e["kind"] == "picture":
        pic = json.load(open(os.path.join(d, "picture.json")))
        objs = pic["objects"]
        print(f"picture annotation: shape OK. Folio {pic['folio']}, {len(objs)} objects, "
              f"{sum(1 for o in objs if o.get('label'))} with a label line. Not scored by the test; "
              "a second independent seat's annotation of the same folio makes it AGREED or DISAGREE.")
    elif e["kind"] == "attack":
        from . import redteam
        spec = json.load(open(os.path.join(d, "attack.json")))
        if spec.get("attack") == "key" and isinstance(spec.get("target_key"), str) and spec["target_key"].endswith(".json"):
            tk = os.path.normpath(path(spec["target_key"]))
            if not tk.startswith(path("keys")):
                print("REFUSED: target_key must be a file under keys/")
                return 1
            spec["target_key"] = tk
        r = redteam.run_attack(spec, split)
        print(json.dumps(r, indent=1))
        print(f"{'ADVISORY ' if split != 'heldout' else ''}VERDICT on {split}: attack {'SUCCEEDS' if r['success'] else 'FAILS'}")
    else:
        s = segmentation_score(e["units"], split)
        print(json.dumps(s, indent=1))
        better = s["_candidate"] < s["eva-basic"]
        print(f"{'ADVISORY ' if split != 'heldout' else ''}VERDICT on {split}: {'BETTER than' if better else 'NOT better than'} eva-basic")
    return 0
