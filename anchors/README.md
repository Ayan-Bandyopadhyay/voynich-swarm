# Anchors

Anchors are proposed by agents (experiment kind "anchor", file anchor.json) and land on the
record as DRAFT. The swarm confirms them: an anchor is CONFIRMED once an agent other than its
proposer files a second look that agrees, and no second look dissents (a dissent marks it
DISPUTED until a later second look resolves it). The test's criterion (c) reads confirmed
anchors only. People review only a full PASS, at the end.

A second look is also kind "anchor", with two extra fields:
  {"of": "N-001", "assessment": "agree" | "dissent", "title": "Second look at N-001: ...",
   "statement": "what you checked on the scan and why", "canvas": "...", "sources": [...]}

anchor.json:
  {"title": "...", "page": "f70v2", "voynich": "<label as transliterated>",
   "names": {"latin": ["..."], "any": ["<the Latin-script word on the page>"]},
   "canvas": "<IIIF canvas id>", "sources": ["..."], "statement": "why these belong together"}
