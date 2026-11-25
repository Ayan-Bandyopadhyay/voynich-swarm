"""The public ledger: who did which step, and what the judge said.

ledger/ledger.jsonl holds one record per judged contribution:
  {"t": iso date, "handle": github handle or "fleet:<seat>", "step": id, "program": id,
   "kind": established | refuted | ruled_out | key_judged | anchor_confirmed | audit | control |
           attack_succeeded | attack_failed,
   "on_path": bool, "ref": results file or pull request}

Credit: a record on the path weighs 3, off the path 1. A contributor's share is the weight
of their records over the weight of all outside contributors' records. Refutations and
ruled-out cells weigh the same as results. The fleet's own seats are listed but take no
share. The formula is frozen for the season; no one sets a share by hand.
"""
import json, os, datetime
from collections import defaultdict
from . import path

FN = path("ledger", "ledger.jsonl")
WEIGHT = {True: 3, False: 1}


def read():
    """Ledger records, credited to the GitHub owner; the agent seat is kept as a detail."""
    if not os.path.exists(FN):
        return []
    from .identity import owner, agent
    out = []
    for l in open(FN):
        if l.strip():
            r = json.loads(l)
            if "seat" not in r:
                r = dict(r, seat=r["handle"], handle=owner(r["handle"]), agent=agent(r["handle"]))
            out.append(r)
    return out


def write(records):
    os.makedirs(os.path.dirname(FN), exist_ok=True)
    with open(FN, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def from_results(split, seat="fleet:claude"):
    """Ledger records for the fleet's own season run (it takes no share)."""
    recs = []
    today = datetime.date.today().isoformat()

    def load(n):
        fn = path("results", split, n + ".json")
        return json.load(open(fn)) if os.path.exists(fn) else None
    for f in load("facts") or []:
        recs.append({"t": today, "handle": seat, "step": f["id"], "program": "L2", "kind": f["status"].lower(), "on_path": False, "ref": f"results/{split}/facts.json"})
    for c in load("grid") or []:
        if c["status"] == "RULED OUT":
            recs.append({"t": today, "handle": seat, "step": f"L3-{c['language']}-{c['family']}", "program": "L3", "kind": "ruled_out", "on_path": True, "ref": f"results/{split}/grid.json"})
    a = load("audits")
    for r in (a or {}).get("judged", []):
        recs.append({"t": today, "handle": seat, "step": r["submission"], "program": "audit", "kind": "audit", "on_path": False, "ref": f"results/{split}/audits.json"})
    return recs


def is_fleet(handle):
    """Only the project's own automation (not people's agents) is a fleet seat."""
    return handle.startswith("fleet:")


def append(rec):
    recs = [json.loads(l) for l in open(FN) if l.strip()] if os.path.exists(FN) else []
    key = (rec["handle"], rec["step"], rec.get("ref"))
    if any((r["handle"], r["step"], r.get("ref")) == key for r in recs):
        return False
    rec.setdefault("t", datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    recs.append(rec)
    write(recs)
    return True


def board(records, since=None):
    if since:
        records = [r for r in records if r.get("t", "") >= since]
    out = defaultdict(lambda: {"weight": 0, "records": 0, "on_path": 0, "refutations": 0, "agents": set()})
    for r in records:
        b = out[r["handle"]]
        if r.get("agent"):
            b["agents"].add(r["agent"])
        b["weight"] += WEIGHT[bool(r.get("on_path"))]
        b["records"] += 1
        b["on_path"] += bool(r.get("on_path"))
        b["refutations"] += r["kind"] in ("refuted", "ruled_out", "attack_succeeded")
    outside = sum(v["weight"] for h, v in out.items() if not is_fleet(h))
    rows = []
    for h, v in out.items():
        fleet = is_fleet(h)
        rows.append(dict(v, agents=sorted(v["agents"]), handle=h, fleet=fleet, share=None if fleet or not outside else v["weight"] / outside))
    return sorted(rows, key=lambda r: (r["fleet"], -r["weight"], r["handle"]))
