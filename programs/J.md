# J · The test's power

**Goal.** A grid cell can only be ruled out if the key search provably works in that language
and family. Right now the pinned search cracks simple/homophonic substitution controls in
most languages but not verbose ciphers or small corpora (see /how: "Does the test work?",
data in results/heldout/controls.json).

**What counts.** A code PR to `vs/search.py` (reviewed) that cracks more positive controls at
the same or a published new budget, with `python3 -m vs season --parts controls` output.
Also: pinning better period corpora (`pins/sources.json`, data PR) for Czech, Hebrew, Occitan.

**Add languages (experiment kind `corpus`).** corpus.json:
`{"language": "occitan", "title", "period", "url", "sha256", "license": "public-domain|cc0|cc-by|cc-by-sa", "encoding"}`.
Hosts accepted: Project Gutenberg (and its mirrors), Wikisource, archive.org, The Latin Library,
raw.githubusercontent.com, ebible.org, Menota, the Text Creation Partnership, the MHG corpus.
Prior art: the 2026 "Voynich Text Examination" used 40 texts in 31 languages from exactly these
sources (Bible translations from ebible.org for breadth; medieval transcriptions from Menota,
TCP and the MHG reference corpus for period fit). Period-true transcriptions beat modern
editions: prefer them. The scorer downloads, verifies the sha256, needs 150,000+ characters
after cleaning, runs the positive controls in that language, and adds it to the grid with its
measured power. Paywalled or unclearly licensed texts are refused. Prefer texts close to
1400-1450 and to the manuscript's likely milieu (herbal, medical, astronomical).

**Do not** tune on the manuscript. Controls only.

**Open (from the maintainer):** criterion (a) needs a line-level preimage code so keys that read
whole lines with spaces ignored (`"spaces": "ignored"`, vs/views.py) are charged fairly. Today a
true key on a spaces-ignored control fails (a) only because of this. A code PR to vs/judge.py
with a positive control proving it (true key passes, red-team keys fail) is the check.

**Open (from the maintainer, priority):** (1) German substitution: the search lost power on the
noisy German control; step J-power-german-substitution. (2) Verbose ciphers have demonstrated
power only in Latin and English: extend to Italian, Spanish and French before any verbose key
there counts. (3) Syllabic / Naibbe-style ciphers (Greshko 2025, on the record): a cipher family
(code PR to vs/families/) with a positive control the search cracks at 2% noise. Until a family
has power in a language, keys there are INCONCLUSIVE by rule, so this unlocks those cells.
