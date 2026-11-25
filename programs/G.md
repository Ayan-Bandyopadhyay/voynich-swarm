# G · Meaningless-text procedures

**Goal.** Procedures a 15th-century person could carry out (tables, dice, grilles, copying
nearby words) that produce text without meaning. Score: how many *established* facts on the
record the procedure's text reproduces. Reproducing all of them would itself be a result.

**What counts, first: production models** (kind `model`, vs/models.py). A model is a mixture of
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
