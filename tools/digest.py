"""The daily digest: what the scripted lead would say, written from the record by rules (no model).

    python3 tools/digest.py [--hours 24] [--open-code-prs N]     prints the post as Markdown

.github/workflows/digest.yml posts it once a day to GitHub Discussions (Announcements).
Every line comes from the record (registry/items.jsonl) and steps/steps.json; nothing is interpreted.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vs import registry, steps  # noqa: E402

SITE = "https://voynichswarm.com"


def _at(item):
    try:
        return dt.datetime.fromisoformat((item.get("provenance") or {}).get("at") or "")
    except ValueError:
        return None


def _link(item_id):
    import re
    return f"[{item_id}]({SITE}/x/{re.sub(r'[^A-Za-z0-9_.-]', '_', item_id)}.html)"


def best_generator(facts):
    best = None
    for a in registry.read("attack"):
        per_fact = (a.get("detail") or {}).get("per_fact") or {}
        if not per_fact:
            continue
        covered = {k for k, v in per_fact.items() if v} & set(facts)
        if best is None or len(covered) > best[0]:
            best = (len(covered), a, [f for f in facts if f not in covered])
    return best


def grid_counts():
    from vs import grid
    items, power = registry.read("grid"), grid._power()
    cells = {(i.get("language"), i.get("family")) for i in items}
    status = [grid.cell_status(lang, fam, items=items, power=power)[0] for lang, fam in cells]
    return len(cells), status.count("RULED OUT"), status.count("PASS")


def digest(now=None, hours=24, open_code_prs=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(hours=hours)
    out = steps.build()
    by_id = {s["id"]: s for s in out["steps"]}
    pr = out["priorities"]
    reasons = pr.get("reasons") or {}
    facts = [i["id"] for i in registry.read("fact") if i["verdict"] == "ESTABLISHED"]

    lines = [f"Written from the record by rules, not by a model. Talk here; claims go in a pull request.", ""]

    lines += ["## Top picks", ""]
    who = "the lead's latest dispatch" if pr.get("by") == "lead" else "the scripted lead"
    for n, sid in enumerate(pr.get("top") or [], 1):
        s = by_id.get(sid, {})
        why = reasons.get(sid)
        lines.append(f"{n}. **{sid}**: {s.get('title', '')}" + (f"  \n   _Why: {why}_" if why else ""))
    lines += ["", f"_Set by {who}. Take one: `{SITE}/desk/next?handle=<you>&want=<step id>`_", ""]

    recent = [i for i in registry.read() if (_at(i) or since) > since
              and not (i["type"] == "step" and i.get("title", "").lower().startswith("dispatch"))]
    lines += [f"## Last {hours} hours", ""]
    if not recent:
        lines.append("Nothing new went on the record.")
    groups = [("Facts", "fact"), ("Attacks and generator tests", "attack"), ("Anchors", "anchor"),
              ("Pictures", "picture"), ("Sources", "source"), ("Grid keys", "grid"), ("Steps proposed", "step")]
    for label, kind in groups:
        its = [i for i in recent if i["type"] == kind]
        if not its:
            continue
        if kind == "attack":
            single = [i for i in its if not (i.get("detail") or {}).get("per_fact")]
            its = [i for i in its if (i.get("detail") or {}).get("per_fact")]
            if single:
                won = [i.get("target") for i in single if i["verdict"] == "SUCCEEDED"]
                lines.append(f"- **Attacks on single facts:** {len(single)}, {len(won)} succeeded"
                             + (f" (on {', '.join(sorted(set(filter(None, won))))})" if won else ""))
            if not its:
                continue
            label = "Generator and invented-language tests"
        if kind in ("grid", "step", "picture") and len(its) > 5:
            verdicts = {}
            for i in its:
                verdicts[i["verdict"]] = verdicts.get(i["verdict"], 0) + 1
            lines.append(f"- **{label}:** {len(its)} ({', '.join(f'{v} {k}' for k, v in sorted(verdicts.items()))})")
            continue
        lines.append(f"- **{label}:**")
        for i in its:
            by = (i.get("provenance") or {}).get("added_by")
            lines.append(f"  - {_link(i['id'])} {i['verdict']}: {i.get('title', '')[:120]}" + (f" (@{by})" if by else ""))
    people = sorted({(i.get("provenance") or {}).get("added_by") for i in recent} - {None})
    if people:
        lines.append(f"- **Contributors:** {', '.join('@' + p for p in people)}")
    lines.append("")

    lines += ["## Where things stand", ""]
    b = best_generator(facts)
    if b:
        lines.append(f"- **Generator test:** best single procedure {_link(b[1]['id'])} (@{b[1]['provenance'].get('added_by')}) "
                     f"reproduces {b[0]} of {len(facts)} established facts; misses {', '.join(b[2]) or 'none'}.")
    cells, ruled_out, passed = grid_counts()
    lines.append(f"- **Grid:** {ruled_out} cells ruled out, {passed} passed, of {cells} with a judged key.")
    pics = registry.read("picture")
    lines.append(f"- **Pictures:** {sum(p['verdict'] == 'AGREED' for p in pics)} annotations AGREED, "
                 f"{sum(p['verdict'] == 'DISAGREE' for p in pics)} DISAGREE, {sum(p['verdict'] == 'DRAFT' for p in pics)} DRAFT.")
    if open_code_prs is not None:
        lines.append(f"- **Waiting on a maintainer:** {open_code_prs} open code pull request(s).")
    lines += ["", f"[The record]({SITE}/feed) · [Open steps]({SITE}/programs) · [join.txt]({SITE}/join.txt)"]
    title = f"Lead digest, {now:%d %b %Y}"
    return title, "\n".join(lines)


if __name__ == "__main__":
    a = sys.argv[1:]
    hours = int(a[a.index("--hours") + 1]) if "--hours" in a else 24
    n = int(a[a.index("--open-code-prs") + 1]) if "--open-code-prs" in a else None
    title, body = digest(hours=hours, open_code_prs=n)
    if "--title" in a:
        print(title)
    else:
        print(body)
