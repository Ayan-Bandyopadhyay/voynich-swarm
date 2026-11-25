"""Scorer: judge one experiment on the held-out pages and put it on the record.

    python3 -m vs score experiments/<step>/<handle> --pr <pull request url>

Only the scorer can run this (it needs the season seed). It reads the experiment's JSON with
the code already merged; it never runs code from the pull request. The verdict is printed
(for the PR comment), added to the registry (the record) and the ledger (the leaderboard).
Nothing reaches the record any other way.
"""
import json, os
from . import corpus, judge, ledger, registry, path
from .experiment import validate, segmentation_score


def _steps():
    fn = path("steps", "steps.json")
    return {s["id"]: s for s in json.load(open(fn))["steps"]} if os.path.exists(fn) else {}


# Corpora may come from any public website. The license must be declared open (checked by the
# validator, open to dissent on the record) and the file must be served publicly over http(s).
# The scorer holds the season seed, so the download is fenced: http(s) only, public addresses
# only (no loopback, private, link-local or cloud-metadata hosts, re-checked on every redirect),
# no credentials in the url, a size cap, and the bytes are only ever treated as text.
MAX_BYTES = 12 * 1024 * 1024
MIN_CHARS = 150_000


def _public_url(url):
    """Refuse anything but a plain http(s) url on a public internet address."""
    import ipaddress, socket, urllib.parse
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password:
        raise ValueError("corpus url must be a plain public http(s) url")
    port = u.port or (443 if u.scheme == "https" else 80)
    for info in socket.getaddrinfo(u.hostname, port, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise ValueError(f"corpus url resolves to a non-public address ({ip})")


def _public_fetch(url, limit):
    import urllib.request

    class Checked(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _public_url(newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    _public_url(url)
    opener = urllib.request.build_opener(Checked)
    req = urllib.request.Request(url, headers={"User-Agent": "voynichswarm-scorer/1"})
    with opener.open(req, timeout=120) as r:
        return r.read(limit)


def _score_corpus(c, e):
    """Download, verify, check, calibrate. Returns (item, ledger kind) or (None, refusal)."""
    import hashlib, urllib.request, urllib.parse
    from . import refcorpus, controls, judge, search
    try:
        raw = _public_fetch(c["url"], MAX_BYTES + 1)
    except ValueError as ex:
        return None, {"verdict": "REFUSED", "errors": [str(ex)]}
    except Exception as ex:
        return None, {"verdict": "REFUSED", "errors": [f"could not download the url ({str(ex)[:120]})"]}
    if len(raw) > MAX_BYTES:
        return None, {"verdict": "REFUSED", "errors": ["file larger than 12 MB"]}
    if hashlib.sha256(raw).hexdigest() != c["sha256"]:
        return None, {"verdict": "REFUSED", "errors": ["sha256 does not match the file at the url"]}
    pins_fn = path("pins", "sources.json")
    pins = json.load(open(pins_fn))
    if any(r["sha256"] == c["sha256"] for r in pins["reference_corpora"]):
        return None, {"verdict": "REFUSED", "errors": ["this file is already pinned"]}
    lang = c["language"]
    pid = f"{lang}_{c['sha256'][:8]}"
    fn = f"data/raw/agent_{pid}.txt"
    open(path(fn), "wb").write(raw)
    entry = {"id": pid, "lang": lang, "period": c["period"], "title": c["title"], "url": c["url"], "file": fn,
             "bytes": len(raw), "sha256": c["sha256"], "license": c["license"], "encoding": c.get("encoding", "utf-8"),
             "added_by": e["handle"]}
    pins["reference_corpora"].append(entry)
    json.dump(pins, open(pins_fn, "w"), indent=2, ensure_ascii=False)
    refcorpus.blocks.cache_clear()
    chars = sum(len(b) for b in refcorpus.blocks(lang))
    if chars < MIN_CHARS:
        pins["reference_corpora"].pop()
        json.dump(pins, open(pins_fn, "w"), indent=2, ensure_ascii=False)
        return None, {"verdict": "REFUSED", "errors": [f"only {chars} characters of {lang} after cleaning (need {MIN_CHARS})"]}
    # calibration: does the test have power in this language?
    power = {}
    for fam, kind in (("substitution", "homophonic"), ("verbose", "verbose")):
        try:
            tr, ev, true = controls.make(lang, kind)
            rt = judge.evaluate(true, tr, ev, "control")
            rs = judge.evaluate(search.search_cell(lang, fam, tr, tag="control"), tr, ev, "control")
            ok = lambda r: r["a_compresses"]["pass"] and r["b_reads"]["pass"] and r["kill_tests"]["pass"]
            power[fam] = {"true_key_passes": ok(rt), "search_cracks_control": ok(rs)}
        except Exception as ex:
            power[fam] = {"error": str(ex)[:200]}
    cfn = path("results", "heldout", "controls.json")
    rows = [r for r in json.load(open(cfn)) if r["language"] != lang]
    for fam, pw in power.items():
        if "error" not in pw:
            rows.append({"language": lang, "family": fam, "control": "homophonic" if fam == "substitution" else "verbose",
                         "true_key_passes": pw["true_key_passes"], "search_cracks_control": pw["search_cracks_control"], "added_with": pid})
    json.dump(rows, open(cfn, "w"), indent=1)
    item = {"id": registry.next_id("C"), "type": "corpus", "title": f"{lang.title()}: {c['title']}"[:160],
            "statement": f"{c['title']} ({c['period']}), {chars:,} characters after cleaning, {c['license']}.",
            "verdict": "ADDED", "value": chars, "detail": {"pin": entry, "power": power}, "program": "J", "language": lang}
    return item, "corpus_added"


def score(d, pr=None):
    e, errs = validate(d)
    if errs:
        return {"verdict": "REFUSED", "errors": errs}
    step = _steps().get(e["step"], {})
    _sp = e["step"].split("-")
    program = step.get("program") or (_sp[1] if _sp[0] == "M" and len(_sp) > 1 else _sp[0])
    on_path = bool(step.get("on_path"))
    files = sorted(os.path.join(d, f) for f in os.listdir(d))
    from .identity import owner as _owner, agent as _agent
    prov = {"added_by": e["handle"], "how": "agent", "pr": pr, "files": files, "step": e["step"]}
    who = "@" + _owner(e["handle"]) + (f" ({_agent(e['handle'], e.get('agent'))})" if _agent(e["handle"], e.get("agent")) else "")
    load = lambda n: json.load(open(os.path.join(d, n)))
    train, ev = corpus.split_pages("heldout")
    item = None
    if e["kind"] == "fact":
        from . import facts
        f = load("fact.json")
        robust = {}
        if "spec" in f:
            from . import dsl
            try:
                r = dsl.evaluate(f["spec"], ev)
            except dsl.SpecError as ex:   # e.g. the scope or selection is too small on the hidden pages
                return {"verdict": "REFUSED", "errors": [f"spec: {ex}"]}
            det = dict(r["detail"], spec=f["spec"])
            # robustness: the claim must also hold on an independent transliteration (Takahashi)
            for t in ("it", "rf"):
                try:
                    robust[t] = dsl.evaluate(f["spec"], corpus.split_pages("heldout", t)[1])["pass"]
                except Exception as ex:
                    robust[t] = f"error: {str(ex)[:80]}"
            det["transliterations"] = dict(robust, zl=r["pass"])
        else:
            r = facts.METRICS[f["metric"]](train, ev, **f["params"])
            det = dict(r["detail"], metric=f["metric"], params=f["params"])
        verdict = "ESTABLISHED" if r["pass"] else "REFUTED"
        if verdict == "ESTABLISHED" and robust and robust.get("it") is not True:
            verdict = "FRAGILE"  # holds on ZL but not on Takahashi's independent transliteration
        item = {"id": registry.next_id("F"), "type": "fact", "title": f["title"], "statement": f["statement"],
                "verdict": verdict, "value": r["value"], "detail": det,
                "program": "L2", "source": f.get("source", "")}
        kind = verdict.lower()
    elif e["kind"] == "key":
        sub = judge.load_key(os.path.join(d, "key.json"))
        from .models import scoped
        from . import views
        views.check(sub)
        t = sub.get("transliteration", "zl")
        if t not in corpus.TRANSLITERATIONS:
            return {"verdict": "REFUSED", "errors": [f"transliteration must be one of {sorted(corpus.TRANSLITERATIONS)}"]}
        ktr, kev = corpus.split_pages("heldout", t) if t != "zl" else (train, ev)
        str_, sev = views.apply(scoped(ktr, sub.get("scope")), sub), views.apply(scoped(kev, sub.get("scope")), sub)
        if not sev:
            return {"verdict": "REFUSED", "errors": ["no hidden pages in this scope"]}
        r = judge.evaluate(sub, str_, sev, "heldout")
        lang, fam = sub["target"]["language"], sub["family"]
        nowa = r.get("a_compresses", {}).get("pass") and r.get("b_reads", {}).get("pass") and r.get("kill_tests", {}).get("pass")
        verdict = "PASS" if r["verdict"] == "PASS" else ("OPEN" if nowa else "FAIL")
        item = {"id": registry.next_id(f"K-{lang}-{fam}"), "type": "grid", "title": f"{lang.title()} × {fam}: a key by {who}",
                "statement": e.get("summary", ""), "verdict": verdict, "value": r.get("a_compresses", {}).get("savings"),
                "detail": {k: r.get(k) for k in ("failed", "a_compresses", "b_reads", "kill_tests", "c_pictures", "pages_passing")},
                "program": "L3", "language": lang, "family": fam, "budget": sub.get("search", {}).get("budget")}
        if r["verdict"] == "PASS":
            item["held"] = "A full pass is held until a named person releases it."
        kind = "key_passed" if r["verdict"] == "PASS" else "key_judged"
    elif e["kind"] == "attack":
        from . import redteam
        spec = load("attack.json")
        # one attack per fact per contributor per day: each verdict carries a bit about the hidden layout
        import datetime as _dt
        from .identity import owner as _ow
        day = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
        if spec.get("attack") == "fact" and any(
                i["type"] == "attack" and i.get("target") == spec.get("target_fact")
                and i["provenance"]["added_by"] == _ow(e["handle"]) and str(i["provenance"].get("at", "")).startswith(day)
                for i in registry.read()):
            return {"verdict": "REFUSED", "errors": ["one attack per fact per contributor per day (the hidden layout must not be probed)"]}
        if spec.get("attack") == "generator" and any(
                i["type"] == "attack" and i.get("target") == "*"
                and i["provenance"]["added_by"] == _ow(e["handle"]) and str(i["provenance"].get("at", "")).startswith(day)
                for i in registry.read()):
            return {"verdict": "REFUSED", "errors": ["one generator test per contributor per day (each verdict carries a bit per fact about the hidden pages)"]}
        if spec.get("attack") == "key" and isinstance(spec.get("target_key"), str):
            spec["target_key"] = path(os.path.normpath(spec["target_key"]))
        if spec.get("attack") == "fact":
            spec["target_fact_item"] = registry.get(spec["target_fact"])
        r = redteam.run_attack(spec, "heldout")
        verdict = "SUCCEEDED" if r["success"] else "FAILED"
        if spec["attack"] == "generator" and not r.get("refused"):
            verdict = f"{r['reproduced']}/{r['of']}"
            if spec.get("hypothesis") in ("invented_language", "meaningless"):
                r["hypothesis"] = spec["hypothesis"]
        typ = "audit" if spec["attack"] == "claim" else "attack"
        item = {"id": registry.next_id("A" if typ == "audit" else "R"), "type": typ,
                "title": (spec.get("claimant") or ((f"Invented-language test: {spec.get('title') or 'a constructed language'}, against every established fact" if spec.get("hypothesis") == "invented_language" else f"Generator test: {spec.get('title') or 'a procedure'}, against every established fact") if spec["attack"] == "generator" else f"{spec['attack']} attack on {r.get('target')}"))[:160],
                "statement": spec.get("method") or e.get("summary", ""), "verdict": verdict if typ == "attack" else ("FAIL" if r["success"] else "PASS"),
                "value": None, "detail": {k: v for k, v in r.items() if k != "lines"}, "program": "R", "target": r.get("target")}
        kind = "attack_succeeded" if r["success"] else "attack_failed"
        on_path = on_path or r["success"]
    elif e["kind"] == "segmentation":
        r = segmentation_score(e["units"], "heldout")
        better = r["_candidate"] < r["eva-basic"]
        item = {"id": registry.next_id("S"), "type": "segmentation", "title": f"Segmentation by {who}",
                "statement": e.get("summary", ""), "verdict": "ESTABLISHED" if better else "REFUTED", "value": r["_candidate"],
                "detail": dict(r, units=e["units"]), "program": "L1"}
        kind = "segmentation_better" if better else "segmentation_not_better"
    elif e["kind"] == "model":
        from . import models
        m = load("model.json")
        try:
            r = models.evaluate(m, train, ev)
        except models.ModelError as ex:
            return {"verdict": "REFUSED", "errors": [str(ex)]}
        sc = m.get("scope") or {}
        item = {"id": registry.next_id("M"), "type": "model", "title": m["title"][:160], "statement": m.get("statement", ""),
                "verdict": "SCORED", "value": r["bits_per_word"], "detail": dict(r, spec=m), "program": "G",
                "scope": " ".join(f"{k}={v}" for k, v in sorted(sc.items())) or "whole manuscript"}
        kind = "model_scored"
    elif e["kind"] == "source":
        src = load("source.json")
        if src.get("of"):
            tgt = registry.get(src["of"])
            if src.get("assessment") == "weak":
                # a weak refutation: the attack's generator writes the target pattern in by hand
                from .identity import owner as _ow2
                if not tgt or tgt["type"] != "attack" or tgt["verdict"] != "SUCCEEDED":
                    return {"verdict": "REFUSED", "errors": [f"{src['of']} is not a succeeded attack on the record"]}
                if tgt["provenance"]["added_by"] == _ow2(e["handle"]):
                    return {"verdict": "REFUSED", "errors": ["a second look must come from someone other than the attacker"]}
            elif not tgt or tgt["type"] != "source":
                return {"verdict": "REFUSED", "errors": [f"{src['of']} is not a source on the record"]}
            item = {"id": registry.next_id("Q"), "type": "source", "title": f"Second look at {src['of']}: {src['assessment'].upper()}",
                    "statement": src.get("statement", ""), "verdict": src["assessment"].upper(), "value": None,
                    "detail": src, "program": "K"}
            kind = "source_reviewed"
        else:
            import urllib.request
            try:
                req = urllib.request.Request(src["url"], headers={"User-Agent": "voynichswarm-scorer/1"}, method="GET")
                code = urllib.request.urlopen(req, timeout=40).status
            except Exception as ex:
                return {"verdict": "REFUSED", "errors": [f"url not openly reachable ({str(ex)[:80]}); paywalled or dead links are not catalogued"]}
            if any(i["type"] == "source" and (i["detail"].get("url") == src["url"] or (src.get("doi") and i["detail"].get("doi") == src.get("doi")))
                   for i in registry.read()):
                return {"verdict": "REFUSED", "errors": ["already catalogued"]}
            item = {"id": registry.next_id("K"), "type": "source", "title": f"{src['authors']} ({src['year']}): {src['title']}"[:200],
                    "statement": src.get("summary", ""), "verdict": "CATALOGUED", "value": len(src.get("open", [])),
                    "detail": src, "program": "K"}
            kind = "source_catalogued"
    elif e["kind"] == "corpus":
        item, kind = _score_corpus(load("corpus.json"), e)
        if item is None:
            return kind  # refusal
    elif e["kind"] == "anchor":
        a = load("anchor.json")
        item = {"id": registry.next_id("N"), "type": "anchor", "title": a.get("title", f"Anchor on {a.get('page')}"),
                "statement": a.get("statement", ""), "verdict": "DRAFT", "value": None, "detail": a, "program": "L4", "page": a.get("page")}
        kind = "anchor_proposed"
    elif e["kind"] == "step":
        st = load("step.json")
        item = {"id": registry.next_id(f"P-{st['program']}"), "type": "step", "title": st["title"], "statement": st["statement"],
                "verdict": "PROPOSED", "value": None, "detail": st, "program": st["program"],
                "check": st["check"], "on_path": bool(st.get("on_path")), "hard": bool(st.get("hard"))}
        kind = "step_proposed"
    item["provenance"] = prov
    # snapshot of exactly what was submitted (the folder may be reused by later submissions)
    item["submitted"] = {os.path.basename(f): json.load(open(f)) for f in files if f.endswith(".json")}
    if item["type"] == "attack":
        # hidden-page values would leak layout information; keep the outcome and the reason only
        item["detail"] = {k: v for k, v in item["detail"].items() if k in ("attack", "target", "success", "why", "refused", "decoy", "shared_type_share", "cut", "reproduced", "of", "per_fact", "hypothesis")}
    try:
        registry.add(item)
    except SystemExit as ex:
        return {"verdict": "REFUSED", "errors": [str(ex)]}
    rec = {"handle": e["handle"], "step": e["step"], "program": item["program"], "kind": kind, "on_path": on_path,
           "ref": pr or d, "item": item["id"], "summary": e.get("summary", "")[:200]}
    ledger.append(rec)
    from . import steps as _steps_mod
    _steps_mod.build()  # new items open new steps (rules) and agent-proposed steps reach the desk
    public = {"item": item["id"], "verdict": item["verdict"], "ledger": rec}
    if item["type"] in ("fact", "grid", "segmentation"):
        public["value"] = item.get("value")
    return public  # attack internals (held-out values) are not echoed into PR comments
