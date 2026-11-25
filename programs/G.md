# G · Meaningless-text procedures

**Goal.** Procedures a 15th-century person could carry out (tables, dice, grilles, copying
nearby words) that produce text without meaning. Score: how many *established* facts on the
record the procedure's text reproduces. Reproducing all of them would itself be a result.

**The scoreboard: the generator test** (step `G-every-fact`). One procedure, one body of
text, sent as attack.json `{"attack": "generator", ...}` with `"cut": "lines"`, scored against
every established fact at once; the record shows k/n reproduced. The pinned self-citation
generator (after Timm & Schinner) reproduces 1 of 7 on the practice pages. The targets that matter most:
line-final m (F-001) and the collapse of edge-glyph dependence at line breaks (P-G-001). A
procedure that names a target pattern in its rules does not count (weak refutation).

**Also counts: production models** (kind `model`, vs/models.py). A model is a mixture of
trusted components (vocab, chain, copy with a window and edits, template with prefix/suffix
sizes, letters, position), fitted on the training pages and scored in held-out bits per word.
Scope it per scribe. This is how the best prior work (Schwartz 2026) compares production
processes; beat its components, find the one that explains a scribe best.

**Also counts.** A red-team fact attack (kind `attack`, `"attack": "fact"`) per fact, with the
generated text as data, at least 7,000 words, no four-word run copied from the manuscript.
New generators as code go in `vs/generators.py` (reviewed PR). Existing: table cipher,
self-citation (after Timm & Schinner 2020), table-and-grille (after Rugg 2004).

**The harder test.** Fit your tables on the public pages only and write text; the scorer cuts
it to the shape of the hidden pages. Text that only works with the whole manuscript in hand
proves less.
