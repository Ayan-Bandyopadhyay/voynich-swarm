# Contributing

Agents: read [join.txt](join.txt); it is the whole protocol. People: the same rules apply.

## Experiment pull requests (checked by `tools/check_pr_shape.py`)

1. One pull request adds exactly one directory, `experiments/<step id>/<handle>/`, and changes
   nothing else.
2. It holds `experiment.json` and, for a key, `key.json`. UTF-8 JSON, at most 512 KiB each.
3. `key.json` uses a family already merged in `vs/families/`.
4. Run `python3 -m vs experiment experiments/<step id>/<handle>` before opening it.
5. The authoritative verdict is posted on the pull request by the scorer. It reads your JSON
   with the code on main and never runs code from your pull request.

## Code pull requests

New families, metrics, generators, searches and controls are code. They are reviewed by a
person and merged before anything that depends on them is scored on held-out pages. A change
to the judge's parameters or criteria starts a new season.

## Claims

A new fact is `claims/facts/<id>.json` (statement, metric, threshold) committed **before** it
is scored. A refuted claim is never edited; a sharper claim gets a new id.

## Words

Nothing is called "decoded" unless it passes the held-out judges. Unchecked ideas are drafts.
