"""Enforce one experiment per pull request: exactly one new directory experiments/<step>/<handle>/
holding experiment.json (and key.json), and nothing else changed.

  python3 tools/check_pr_shape.py <base> [--head <ref>] [--list] [--extract DIR]
"""
import os, re, subprocess, sys

DIR = re.compile(r"^experiments/([A-Za-z0-9][A-Za-z0-9_.-]{1,80})/([A-Za-z0-9][A-Za-z0-9-]{0,38})/(experiment|key|attack|fact|anchor|step|corpus|source|model|picture)\.json$")


def changed(base, head):
    out = subprocess.run(["git", "diff", "--name-status", f"{base}...{head}"], capture_output=True, text=True, check=True).stdout
    return [l.split("\t") for l in out.splitlines() if l.strip()]


def main():
    a = sys.argv[1:]
    base = a[0]
    head = a[a.index("--head") + 1] if "--head" in a else "HEAD"
    rows = changed(base, head)
    errs, dirs = [], set()
    for row in rows:
        status, name = row[0], row[-1]
        m = DIR.match(name)
        if not m or status[0] not in ("A", "M"):
            errs.append(f"not allowed in an experiment PR: {status} {name}")
        else:
            dirs.add(os.path.dirname(name))
    if len(dirs) != 1:
        errs.append(f"exactly one experiment directory per PR (found {len(dirs)})")
    if errs:
        print("REFUSED:\n  " + "\n  ".join(errs))
        sys.exit(1)
    d = dirs.pop()
    if "--list" in a:
        print(d)
    if "--extract" in a:
        out = os.path.join(a[a.index("--extract") + 1], d)
        os.makedirs(out, exist_ok=True)
        for fn in ("experiment.json", "key.json", "attack.json", "fact.json", "anchor.json", "step.json", "corpus.json", "source.json", "model.json", "picture.json"):
            r = subprocess.run(["git", "show", f"{head}:{d}/{fn}"], capture_output=True)
            if r.returncode == 0:
                open(os.path.join(out, fn), "wb").write(r.stdout)
    if not ("--list" in a or "--extract" in a):
        print(f"ok: one experiment, {d}")


if __name__ == "__main__":
    main()
