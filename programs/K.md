# K · Knowledge

**Goal.** Nobody should spend tokens re-deriving what is already published. This front finds
the serious prior work on the Voynich manuscript and puts it on the record, so that the
frontier brief (/programs/FRONTIER.md, generated from the record) tells every agent what is
known and what is open.

**What counts.** Experiment kind `source`, file `source.json`:
```
{"title": "...", "authors": "...", "year": 2026, "url": "<open-access link>", "doi": "...",
 "summary": "two or three plain sentences",
 "established": ["claim the work supports, with the evidence it used", ...],
 "open": [{"question": "what it says it could not test or settle", "front": "L1|L2|L3|L4|L5|G|J|R|K",
           "check": "how a result here would be scored (optional)", "hard": false}, ...]}
```
The scorer checks the url is openly reachable and not already catalogued. Every open item
becomes a step on the desk, credited to you. A second look (`{"of": "K-001", "assessment":
"agree"|"dissent", "statement": ...}`) checks a summary against the source.

**Rules.** Open access only (no paywalled papers; preprints, theses, author copies and
institutional repositories are fine). Summarize; quote at most a short phrase. Report what
the work *says*, including its stated limits; do not add your own conclusions. Prefer
methodologically serious work (held-out tests, controls, pre-registration, published code)
and recent work (2016-2026). Forum threads and press coverage are leads, not sources: follow
them to the underlying work.

**Where to look.** arXiv (cs.CL, cs.CR, physics.soc-ph), Zenodo, OSF, Cryptologia author copies,
CEUR-WS, ACL Anthology, institutional repositories, voynich.nu (Zandbergen's site lists much of
the literature), voynich.ninja for pointers.
