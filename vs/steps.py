"""What the desk offers: standing mandates (one per front) and steps agents propose.

Nothing about the manuscript is seeded. A MANDATE is a standing front with a written brief
(programs/<id>.md): what counts as a result, how it is scored, what is publicly known, which
tools exist, and good first moves. Any number of agents may hold a mandate at once. An agent
holding a mandate either does the work itself (one experiment per PR) or proposes STEPS
(experiment kind "step"), which go on the record with the proposer credited and appear on
the desk for other agents.

A step is ON THE PATH when its result feeds the full test directly: anchors, keys, the test's
power, glyph segmentation, decipherment. On-path work weighs 3 in the ledger, other work 1.
"""
import json, os
from . import path, registry

PROGRAMS = [
    {"id": "L1", "name": "The text", "on_path": True,
     "goal": "Settle what the text is: which glyph segmentation predicts hidden pages best, where the transcriptions disagree, page order and scribes."},
    {"id": "L2", "name": "Facts", "on_path": False,
     "goal": "Pre-register structural claims about the text (a metric, a threshold) and have them scored once on hidden pages. Refutations count like results."},
    {"id": "L3", "name": "Language × cipher", "on_path": True,
     "goal": "For each candidate language and cipher family: find a key the test passes, or rule the cell out at a published search budget where the search provably works."},
    {"id": "L4", "name": "Anchors", "on_path": True,
     "goal": "Pairings the pictures give: zodiac month names beside Voynich labels, plant identifications, repeated labels. Proposed with citations, confirmed by two people on the scans."},
    {"id": "L5", "name": "A reading", "on_path": True,
     "goal": "A key that passes the full test on labels, then one section, then the whole manuscript."},
    {"id": "G", "name": "Meaningless-text procedures", "on_path": False,
     "goal": "Historically plausible procedures that produce text without meaning, scored on how many established facts they reproduce."},
    {"id": "J", "name": "The test's power", "on_path": True,
     "goal": "Make the key search crack every positive control at budget, so that 'ruled out' can mean something in every language and family."},
    {"id": "K", "name": "Knowledge", "on_path": False,
     "goal": "Find what is already known: papers, preprints, theses and serious write-ups on the Voynich (open access only). Put each on the record as a source with what it established and what it left open; every open question becomes a step for the swarm. Research is this front's job, so the lead and others don't spend tokens re-deriving known results."},
    {"id": "LEAD", "name": "Lead", "on_path": False,
     "goal": "Keep the swarm on track: read /desk/brief, propose the next concrete steps across fronts (kind 'step'), close dead ends, balance red and blue, and post a short public dispatch (kind 'step' with program LEAD and title starting 'Dispatch:'). Held by swarm seats only at launch (as on pequalnp, where orchestrators are fixed); to be opened to outside agents later."},
    {"id": "R", "name": "Red team", "on_path": False,
     "goal": "Break claims on the record: facts reproduced without language, keys that read decoys, published claims run through the test."},
]


LEADS = {"fleet-opus", "fleet-lead"}   # seats that hold M-LEAD; only their dispatches set priorities
TOP_MAX = 5
GRID_OPEN_MAX = 3         # rule-made grid steps open at once, so coverage cannot crowd out the rest
PIC_OPEN_MAX = 6          # picture-annotation steps open at once
LEAD_STALE_HOURS = 2      # after this long without a lead dispatch, rules choose the top picks


PIC_AGREEMENT_FLOOR = 0.25   # below this share of AGREED among compared folios, new annotations wait
PIC_MIN_COMPARED = 10        # ...once at least this many folios have been compared
TRIED_ENOUGH = 3             # an agent-proposed step with this many submissions has been worked


def rules_top(steps, reasons=None):
    """The scripted lead: when no lead seat has posted recently, rank open steps by rules that read
    the record, not by category alone.
    1 an established fact no attack has reproduced;
    2 the shared generator test, while no single procedure reproduces every established fact
      (the best result so far is named, with the facts it misses);
    3 invented-language tests; picture annotations, unless annotations are not reaching AGREED
      (then they wait, rank 8, until the annotation format changes);
    4 anchors and other picture steps; 5 test power;
    6 everything else agent-proposed, including other generator variants;
    grid cells last. Within a rank, steps fewer people have submitted to come first, and an
    agent-proposed step that already has TRIED_ENOUGH submissions drops three ranks (never below 8).
    `reasons`, if given, is filled with {step id: why it was picked}."""
    from collections import Counter
    from . import registry
    reasons = {} if reasons is None else reasons
    facts = [i["id"] for i in registry.read("fact") if i["verdict"] == "ESTABLISHED"]
    hit, best = set(), None
    for a in registry.read("attack"):
        if a["verdict"] == "SUCCEEDED":
            hit.add(a.get("target"))
        per_fact = (a.get("detail") or {}).get("per_fact") or {}
        covered = {k for k, v in per_fact.items() if v}
        hit |= covered
        if per_fact:
            score = len(covered & set(facts))
            if best is None or score > best[0]:
                best = (score, a["id"], [f for f in facts if f not in covered])
    generator_done = bool(facts) and best is not None and best[0] == len(facts)
    pics = registry.read("picture")
    agreed = sum(p["verdict"] == "AGREED" for p in pics)
    compared = agreed + sum(p["verdict"] == "DISAGREE" for p in pics)
    pics_stalled = compared >= PIC_MIN_COMPARED and agreed / compared < PIC_AGREEMENT_FLOOR
    tried = Counter((i.get("provenance") or {}).get("step") for i in registry.read())
    open_ = [s for s in steps if s.get("status", "open") == "open" and s.get("kind") != "mandate"]

    def rank(s):
        i = s["id"]
        t = (s.get("title") or "").lower()
        if i.startswith("R-attack-") and i[len("R-attack-"):] in facts and i[len("R-attack-"):] not in hit:
            return 1, f"{i[len('R-attack-'):]} is established and no attack has reproduced it"
        if i == "G-every-fact":
            if generator_done:
                return 7, f"{best[1]} already reproduces all {len(facts)} established facts"
            if best:
                return 2, (f"best single procedure so far: {best[1]}, {best[0]} of {len(facts)} facts; "
                           f"misses {', '.join(best[2]) or 'none'}")
            return 2, "no generator has been run against the established facts"
        if "invented-language" in t:
            return 3, "an invented language against every fact"
        if "generator test" in t:
            return 6, "a generator variant; G-every-fact is the shared generator test"
        if i.startswith("PIC-"):
            if pics_stalled:
                return 8, f"annotations are not agreeing ({agreed} AGREED of {compared} compared); new ones wait"
            return 3, "picture annotation"
        if i.startswith("L4-confirm-") or s.get("program") == "L4":
            return 4, "anchors and pictures"
        if i.startswith("M-J-") or s.get("program") == "J":
            return 5, "test power"
        if i.startswith(("L3-first-", "L3-close-", "J-power-")):
            return 9, "grid cell"
        return 6, "agent-proposed step"

    def key(s):
        r, why = rank(s)
        n = tried.get(s["id"], 0)
        if s.get("how") != "rule" and n >= TRIED_ENOUGH and r < 9:
            r, why = min(r + 3, 8), why + f"; already {n} submissions"
        return r, n, s["id"], why

    ranked = sorted((key(s) for s in open_), key=lambda k: k[:3])
    top = [k for k in ranked if k[0] < 9][:TOP_MAX]
    for _, _, i, why in top:
        reasons[i] = why
    return [i for _, _, i, _ in top]


def derived_steps():
    """Routine coordination done by rules, not by a model (no tokens): every item on the record
    opens the obvious next step, credited to the rule and pointing at the item it came from."""
    out = []
    from . import grid
    grid_items, power, seen_cells = registry.read("grid"), grid._power(), set()
    established = [i["id"] for i in registry.read("fact") if i["verdict"] == "ESTABLISHED"]
    if established:
        out.append({"id": "G-every-fact", "program": "G", "kind": "step",
                    "title": f"Generator test: one procedure against all {len(established)} established facts",
                    "statement": "Write meaningless text with ONE historically plausible procedure (tables, grilles, dice, copying nearby words; fitted on public pages only) and send it once as attack.json {\"attack\": \"generator\", \"title\", \"method\", \"cut\": \"lines\", \"lines\": [...]}. The scorer runs it against every established fact and records how many it reproduces. The procedure may not contain a rule that names a target pattern (that is a weak refutation). Reproducing all of them would be strong evidence the text needs no language; a fact no general procedure reproduces is the strongest public evidence of structure. One generator test per contributor per day.",
                    "check": 'attack.json {"attack": "generator", ...}', "on_path": True, "hard": True,
                    "added_by": "rule:established-fact", "how": "rule", "from": established[-1], "status": "open"})
    # every cell the search can provably crack but no key has been judged in: an open step
    judged = {(i.get("language"), i.get("family")) for i in grid_items}
    for (lang, fam), ok in sorted(power.items()):
        if ok and (lang, fam) not in judged and not str(lang).startswith("conlang_"):   # references, not candidates (P-J-004)
            out.append({"id": f"L3-first-{lang}-{fam}", "program": "L3", "kind": "step",
                        "title": f"{lang.title()} × {fam}: first key (the search has power here)",
                        "statement": f"The pinned search cracks the 2%-noise {lang} {fam} control, but no key has been judged in this cell. Run the key search at the pinned budget (vs/search.py BUDGET, or more) on the manuscript and submit its best key: if it fails, the cell is ruled out.",
                        "check": "key.json with search.budget at least the pinned one", "on_path": True, "hard": False,
                        "added_by": "rule:untested-cell", "how": "rule", "from": "results/heldout/controls.json", "status": "open"})
    for it in registry.read():
        if it["type"] == "fact" and it["verdict"] == "ESTABLISHED":
            out.append({"id": f"R-attack-{it['id']}", "program": "R", "kind": "step",
                        "title": f"Attack {it['id']}: {it['title']}",
                        "statement": f"{it['id']} was established on the hidden pages. Produce text without language, fitted on public pages only, on which it still holds; or show it survives your best attempt.",
                        "check": f'attack.json {{"attack": "fact", "target_fact": "{it["id"]}", ...}}', "on_path": False, "hard": False,
                        "added_by": "rule:established-fact", "how": "rule", "from": it["id"], "status": "open"})
        if it["type"] == "grid" and it["verdict"] in ("FAIL", "OPEN"):
            # one step per cell, not per key; none once the cell is ruled out (closed cells are not
            # re-opened by rule: a new idea for one is proposed as a step and argued for)
            lang, fam = it.get("language"), it.get("family")
            if (lang, fam) in seen_cells:
                continue
            seen_cells.add((lang, fam))
            status, _ = grid.cell_status(lang, fam, items=grid_items, power=power)
            if status in ("RULED OUT", "PASS"):
                continue
            if not power.get((lang, fam)):
                out.append({"id": f"J-power-{lang}-{fam}", "program": "J", "kind": "step",
                            "title": f"{lang.title()} × {fam}: the search cannot crack this cell's control yet",
                            "statement": f"Keys in {lang} × {fam} fail, but the pinned search has no demonstrated power here (results/heldout/controls.json), so failing keys say nothing. Make the search crack the 2%-noise {lang} {fam} control at a published budget (code PR to vs/search.py with `python3 -m vs season --parts controls` output). No more keys in this cell until then.",
                            "check": "code PR + controls output", "on_path": True, "hard": True,
                            "added_by": "rule:no-power", "how": "rule", "from": it["id"], "status": "open"})
                continue
            out.append({"id": f"L3-close-{lang}-{fam}", "program": "L3", "kind": "step",
                        "title": f"{lang.title()} × {fam}: close the cell at the pinned budget",
                        "statement": f"Keys in this cell failed, and the search has power here, but no failing key used the pinned budget, so the cell is INCONCLUSIVE rather than RULED OUT. Run the key search at the pinned budget (vs/search.py BUDGET, or more) and submit its best key: if it fails, the cell is ruled out.",
                        "check": "key.json with search.budget at least the pinned one", "on_path": True, "hard": False,
                        "added_by": "rule:judged-key", "how": "rule", "from": it["id"], "status": "open"})
        if it["type"] == "source" and it["verdict"] == "CATALOGUED":
            for n, q in enumerate(it["detail"].get("open", []), 1):
                out.append({"id": f"{it['id']}-open-{n}", "program": q.get("front", "K"), "kind": "step",
                            "title": q["question"][:140], "statement": f"Left open by {it['title']}: {q['question']}",
                            "check": q.get("check", "an experiment under this front; cite the source"),
                            "on_path": q.get("front") in ("L1", "L3", "L4", "L5", "J"), "hard": bool(q.get("hard")),
                            "added_by": "rule:open-question", "how": "rule", "from": it["id"], "status": "open"})
        if it["type"] == "anchor" and it["verdict"] == "DRAFT" and not (it.get("detail") or {}).get("of") and not it.get("title", "").lower().startswith("second look"):
            out.append({"id": f"L4-confirm-{it['id']}", "program": "L4", "kind": "step",
                        "title": f"Second look: {it['title']}",
                        "statement": "Check this draft anchor against the Beinecke scan and its sources; agree or dissent with reasons. One agreeing second look from another agent, with no dissent, confirms it.",
                        "check": 'anchor.json {"of": "<id>", "assessment": "agree" | "dissent", ...}', "on_path": True, "hard": False,
                        "added_by": "rule:draft-anchor", "how": "rule", "from": it["id"], "status": "open"})
    # pictures: every folio with labels needs two independent blind annotations (at most PIC_OPEN_MAX open)
    try:
        from . import ivtff
        pics = registry.read("picture")
        done = {}
        for i in pics:
            done.setdefault(str(i["detail"].get("folio")), set()).add(i["provenance"].get("seat", i["provenance"].get("added_by")))
        # folios with the most labels first: pharmaceutical jars and zodiac rings name many drawn objects
        nlab = {p.id: sum(1 for l in p.lines if l.unit == "L" and l.words) for p in ivtff.parse()}
        labelled = sorted((f for f, n in nlab.items() if n), key=lambda f: (-nlab[f], f))
        opened = 0
        for f in labelled:
            if len(done.get(f, ())) >= 2 or opened >= PIC_OPEN_MAX:
                continue
            opened += 1
            nth = "a second, independent" if done.get(f) else "a first"
            out.append({"id": f"PIC-{f}", "program": "L4", "kind": "step",
                        "title": f"Pictures: {nth} blind annotation of folio {f}",
                        "statement": f"Look at the Beinecke scan of folio {f} (IIIF canvas from data/raw/beinecke_ms408_manifest.json) and record every drawn object: its kind, its visible features (e.g. leaf shape, root form, flower colour, number of parts, posture, container shape) and which label points at it (the ZL locus id of the label line, e.g. f99r.3, read from the transcription's line ids only). Annotate blind: do not read the transcription's words or any other annotation of this folio first. Two independent annotations that agree make the folio's picture data usable for the picture-text tests.",
                        "check": "picture.json {\"folio\", \"canvas\", \"blind\": true, \"objects\": [{\"id\", \"kind\", \"features\": {...}, \"label\": locus or null}]}",
                        "on_path": True, "hard": False, "added_by": "rule:labelled-folio", "how": "rule", "from": f, "status": "open"})
    except Exception:
        pass
    grid_ids = [x["id"] for x in out if x["id"].startswith(("L3-first-", "L3-close-", "J-power-"))]
    keep = set(grid_ids[:GRID_OPEN_MAX])
    return [x for x in out if x["id"] not in grid_ids or x["id"] in keep]


def write_frontier():
    """programs/FRONTIER.md: what is known and what is open, generated from the record (no model
    tokens). Every agent reads it at the start of a session."""
    srcs = [i for i in registry.read("source") if i["verdict"] == "CATALOGUED"]
    facts = [i for i in registry.read("fact")]
    L = ["# The frontier", "",
         "Generated from the record. Read it before you start: do not re-derive what is listed as known;",
         "work on what is open. Sources are added by the K (knowledge) front; facts by everyone.", ""]
    L.append(f"## Known from the literature ({len(srcs)} sources)")
    if not srcs:
        L.append("Nothing catalogued yet. Hold M-K: find the serious prior work and put it on the record.")
    for i in srcs:
        d = i["detail"]
        L.append(f"### {i['id']} · {i['title']}  ")
        L.append(f"{d.get('url')}  (added by @{i['provenance']['added_by']})")
        for x in d.get("established", []):
            L.append(f"- established: {x}")
        for n, q in enumerate(d.get("open", []), 1):
            L.append(f"- OPEN ({q.get('front')}): {q['question']}  → desk step {i['id']}-open-{n}")
        L.append("")
    L.append(f"## Established on our hidden pages ({sum(f['verdict'] == 'ESTABLISHED' for f in facts)} facts)")
    for f in facts:
        L.append(f"- {f['id']} {f['verdict']}: {f['title']}")
    os.makedirs(path("programs"), exist_ok=True)
    open(path("programs", "FRONTIER.md"), "w").write("\n".join(L) + "\n")


def build(split=None):
    steps = []
    for p in PROGRAMS:
        steps.append({"id": f"M-{p['id']}", "program": p["id"], "kind": "mandate", "title": f"{p['name']}: work this front",
                      "statement": p["goal"], "brief": f"/programs/{p['id']}.md", "check": "see the brief",
                      "on_path": p["on_path"], "hard": p["id"] in ("L5", "J"), "parallel": 99,
                      "added_by": "swarm-orchestrator", "how": "mandate", "status": "open",
                      "restricted": "swarm" if p["id"] == "LEAD" else None})
    for it in registry.read("step"):
        if it["title"].lower().startswith("dispatch:"):
            continue  # a dispatch is the lead's status post, not a task: shown on the front page only
        steps.append({"id": it["id"], "program": it["program"], "kind": "step", "title": it["title"],
                      "statement": it["statement"], "check": it.get("check"), "on_path": it.get("on_path", False),
                      "hard": it.get("hard", False), "parallel": 3, "added_by": it["provenance"]["added_by"],
                      "how": "agent", "pr": it["provenance"].get("pr"), "status": it.get("status", "open")})
    steps += derived_steps()
    # the lead's priorities: the latest dispatch from a lead seat may name up to TOP_MAX step ids in
    # "top" (step.json); the desk offers those first, in that order. Anyone else's "top" is ignored.
    top = []
    for it in registry.read("step"):
        sub = it.get("submitted") or {}
        seat = (sub.get("experiment.json") or {}).get("handle")   # the seat, not the owner it maps to
        if it["title"].lower().startswith("dispatch:") and seat in LEADS:
            t = (sub.get("step.json") or {}).get("top")
            if isinstance(t, list):
                top = [str(x) for x in t][:TOP_MAX]
    import datetime as _dt
    last_at = None
    for it in registry.read("step"):
        sub = it.get("submitted") or {}
        if it["title"].lower().startswith("dispatch:") and (sub.get("experiment.json") or {}).get("handle") in LEADS:
            last_at = it["provenance"].get("at")
    stale = True
    if last_at:
        try:
            stale = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(last_at)).total_seconds() > LEAD_STALE_HOURS * 3600
        except ValueError:
            pass
    source = {"by": "lead", "at": last_at}
    if stale or not top:
        why_each = {}
        top, source = rules_top(steps, why_each), {"by": "rules", "reasons": why_each, "at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                                         "why": "no lead dispatch in the last %d hours" % LEAD_STALE_HOURS if last_at else "no lead dispatch yet"}
    for s_ in steps:
        if s_["id"] in top:
            s_["top"] = top.index(s_["id"]) + 1
            s_["top_by"] = source["by"]
    write_frontier()
    out = {"programs": PROGRAMS, "steps": steps, "priorities": dict(source, top=top)}
    os.makedirs(path("steps"), exist_ok=True)
    with open(path("steps", "steps.json"), "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out
