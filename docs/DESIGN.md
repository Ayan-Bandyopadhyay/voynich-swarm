# How the judge works, and what it cannot do

## Order of operations (see `git log`)

1. Inputs pinned by sha256 (`pins/sources.json`).
2. Held-out split drawn from a fresh 256-bit seed; only the commitment committed. No
   analysis had been run on any split at that point.
3. L2 fact battery (F01-F16) pre-registered with thresholds, then F17 added after looking only
   at the public practice split.
4. The judge was developed and calibrated only on synthetic positive controls (genuine
   text enciphered with random keys) and the practice split, then frozen (commit "Judge S1
   frozen").
5. Only then was anything scored on held-out pages.

## The judge (vs/judge.py)

A submission is a merged family program plus a key, with a target language, period and
segmentation. Families decode one Voynich word at a time (so the word-order decoy cannot
be detected by the decoder).

**(a) Compresses.** Total description length of the evaluation pages' exact Voynich text:
program code (compressed, no docstrings) + key (compressed canonical JSON) + plaintext
under the cheaper of a character KN-5 model and a word-unigram-with-escape model, both
trained on the target corpus plus the key's own reading of the training pages + bits to
recover each Voynich word from its plaintext (adaptive choice among training words with
the same reading, or an exact unit-by-unit preimage code). Baseline: the cheaper of a
character KN-5 model and a word-unigram-with-escape model of Voynichese, trained on the
training pages. Pass: positive savings at the lower 95% bound of a page bootstrap.

*Why no fixed margin.* For a simple substitution the Voynich-only model is the same model
as the plaintext's, trained on less text; a correct key's edge is only what the language
corpus adds (2-7% on our controls). A 5% margin rejected true keys. Homophonic and verbose
true keys save 10-15%.

**(b) Reads.** Per section, mean over 300-token chunks of output: bits/char under the fixed
target model at most the 95th percentile of genuine calibration text, lexicon coverage at
least the 5th percentile, type/token ratio inside the 5th-95th band.

**(3) Kill tests.** D1 word order shuffled within pages: word-bigram cost must rise by at
least half of what shuffling genuine text costs. D2 glyphs shuffled within words, D3
random glyphs by frequency, D4 an unrelated language enciphered into EVA: killed if the
decoy's output is within 0.5 bits/char and 0.2 coverage of the real output.

**(c) Pictures.** At least 3 confirmed anchors, at least half matched (normalized edit
similarity >= 0.6 to a name in the target language), permutation p <= 0.01. No anchor is
confirmed yet, so no key can pass the full judge: this is deliberate.

## Known limits (stated before anyone asks)

- **The whole text is public.** The held-out split stops us choosing a flattering split and
  stops tuning to the scoring pages; it does not hide the text. Overfitting the whole text
  is what the description-length test is for.
- **Power is uneven.** Czech (19th-century text) and Hebrew corpora are too small for the
  positive controls to pass, so those cells cannot be ruled out. The verbose-family search
  does not crack its own control, so every verbose cell is open. These are listed as J steps.
- **"Ruled out" is at a budget.** It means the pinned hill-climb, at its pinned budget, found
  no passing key, while the same search cracks a control of that language. It is not a proof
  that no key exists.
- **Reference corpora are only partly period-appropriate**, and some include modern editorial
  matter. Each pin carries its period.
- **Mostly word-level families.** Ciphers that cross word boundaries (transposition, spaces as
  nulls) need line-level families: planned, not built. One family does not keep words as words:
  `letter-words` (letters written as whole words, the Naibbe class), read as a letter stream the
  judge cuts into words itself (vs/respace.py), every band taken from genuine text put through
  the same treatment.
- **The fact battery's operationalizations can be weak.** F04/F05 (precedence grammar) and
  F16 (JSD of small samples) are refuted partly because the tests are blunt. They stay
  refuted as stated; sharper versions are new claims with new ids.
- **Audits reconstruct prose.** Cheshire's alphabet is published as figures plus prose; we
  judged every EVA key consistent with the prose and published our reading for correction.
  Gibbs and the 2026 "AI decoded 30%" story published no key. Paywalled sources are not
  used; our table-cipher generator uses our own tables.
- **Anchors are drafts.** Month readings come from transcription comments and common
  scholarship; only one has a candidate Voynich pairing, and it is our assumption.

## Proposed for season S2 (not in force; S1 stays frozen)

Drawn from prior work reviewed on 2026-11-24 (pequalnp.com; Schwartz 2026 preprint,
bootloops.ai/voynich.pdf; the Mollick/Claude "Voynich Text Examination"; Rozanova &
Temerev, arXiv:2608.17096; Gaskell & Bowern 2022). Each is a judge change, so it starts a new
season with a new held-out commitment.

1. **Matched-freedom control** (Schwartz §4.7). Run the same key search, same budget, on
   meaningless text from self-citation, table-cipher and human-gibberish (Gaskell & Bowern)
   generators shaped like the held-out pages. A key passes (a) only if its savings beat the
   best of those by a margin. Catches the "decipherment illusion" our random-text decoy
   undershoots.
2. **Plaintext shape.** The output's letter distribution (top-3 letter share), type/token
   ratio and hapax share must lie inside the target language's calibration range. Catches
   degenerate 8-letter "languages".
3. **Language exclusivity.** The same key read as the best rival language must score
   clearly worse; a reading that is equally good Hebrew and Arabic is no reading.
4. **Phrase repetition.** F18 shows the manuscript almost never repeats a four-word phrase.
   A word-level decipherment carries that over into its plaintext, so (b) should require the
   plaintext's repeated-4-gram rate to be in the target language's range. Expect this to rule
   out every word-level family at once; it is the strongest single constraint known.
5. **Transliteration robustness.** Pass on ZL and on RF/GC, and under both glyph
   segmentations, and report Currier A and B separately (both must pass).
6. **Submission budget** per handle per season on held-out scoring, and rotating holdouts.
7. **Anchors pre-registered with confidence levels**; the month names are a later hand and
   their language is disputed, so criterion (c) will have little power on them alone.
8. **Hold strong claims** (pequalnp): any PASS on the full judge is held, not shown as a
   result, until a named person releases it.
