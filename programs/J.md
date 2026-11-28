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
Any public website: the url must serve the file openly over http(s) (no login, no paywall), and
the license must be public-domain, cc0, cc-by or cc-by-sa; say where the license is stated.
Good places to start: Project Gutenberg, Wikisource, archive.org, The Latin Library, ebible.org,
Menota, the Text Creation Partnership, the MHG corpus, university and national-library digital
editions. Prior art: the 2026 "Voynich Text Examination" used 40 texts in 31 languages from these
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
(code PR to vs/families/) with a positive control the search cracks at 2% noise. DONE in a first
form: the `letter-words` family (one Voynich word is a prefix and/or a suffix, each one letter,
with homophones; the plaintext's spaces are not kept, vs/respace.py) has a manuscript-sized
control the search cracks at 2% noise in Latin, Italian, Spanish, English, Czech and Greek. Open:
French, German and Hebrew (the TRUE key fails criterion (a) at 2% noise there: its margin is only
3-4% clean); a cut that lets one glyph serve in both prefix and suffix (vs/search_letter_words.py
labels each glyph one way); Greshko's exact tables as a second control. Until a family
has power in a language, keys there are INCONCLUSIVE by rule, so this unlocks those cells.

**The candidate-language list.** Which languages have been proposed for the manuscript, and by
whom? Put each proposal on the record as a source (source.json) with an extra field
`"proposes_language": "<language>"` and, in `open`, whether openly licensed text exists (period
or modern) and how much. Together with the pinned corpora and the grid this is the public list:
proposed, testable (power measured), ruled out.
