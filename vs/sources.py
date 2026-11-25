"""Bibliography: where each part of the test and each fact comes from.

Each entry: key, citation, url (if any), and what we use it for. The site's /sources page and
the inline citations on /how are generated from this list.
"""

REFERENCES = [
    # --- the method
    {"key": "shannon1949", "cite": "C. E. Shannon (1949). Communication Theory of Secrecy Systems. Bell System Technical Journal 28(4): 656-715.",
     "url": "https://doi.org/10.1002/j.1538-7305.1949.tb00928.x", "use": "Unicity distance: with enough key freedom, a cipher can be 'solved' into anything. Why key length must be paid for."},
    {"key": "rissanen1978", "cite": "J. Rissanen (1978). Modeling by shortest data description. Automatica 14(5): 465-471.",
     "url": "https://doi.org/10.1016/0005-1098(78)90005-5", "use": "Minimum description length: criterion (a), program + key + plaintext must beat the best model of the text alone."},
    {"key": "grunwald2007", "cite": "P. Grünwald (2007). The Minimum Description Length Principle. MIT Press.",
     "url": "https://mitpress.mit.edu/9780262072816/", "use": "Two-part codes and why a model's own size counts."},
    {"key": "kneserney1995", "cite": "R. Kneser, H. Ney (1995). Improved backing-off for M-gram language modeling. ICASSP 1995.",
     "url": "https://doi.org/10.1109/ICASSP.1995.479394", "use": "The smoothed n-gram language models used for fluency and compression."},
    {"key": "chengoodman1999", "cite": "S. F. Chen, J. Goodman (1999). An empirical study of smoothing techniques for language modeling. Computer Speech & Language 13(4): 359-394.",
     "url": "https://doi.org/10.1006/csla.1999.0128", "use": "Interpolated Kneser-Ney, as implemented in vs/lm.py."},
    {"key": "nosek2018", "cite": "B. A. Nosek et al. (2018). The preregistration revolution. PNAS 115(11): 2600-2606.",
     "url": "https://doi.org/10.1073/pnas.1708274114", "use": "Claims and thresholds are committed before they are scored."},
    {"key": "knight2011", "cite": "K. Knight, B. Megyesi, C. Schaefer (2011). The Copiale Cipher. Proc. 4th Workshop on Building and Using Comparable Corpora (ACL).",
     "url": "https://aclanthology.org/W11-1202/", "use": "Precedent that statistical, language-model-driven search can crack a real historical cipher: our positive controls test the same ability."},
    {"key": "raviknight2011", "cite": "S. Ravi, K. Knight (2011). Bayesian inference for Zodiac and other homophonic ciphers. ACL 2011.",
     "url": "https://aclanthology.org/P11-1025/", "use": "Homophonic-cipher search; our homophonic positive controls."},
    {"key": "hauer2016", "cite": "B. Hauer, G. Kondrak (2016). Decoding anagrammed texts written in an unknown language and script. TACL 4: 75-86.",
     "url": "https://aclanthology.org/Q16-1006/", "use": "A published AI approach to the Voynich text (language identification, anagrammed Hebrew); an example of why output must be checked against decoys."},
    {"key": "schwartz2026", "cite": "M. Schwartz (2026). How the Voynich Manuscript was written. Preprint (preliminary).",
     "url": "https://bootloops.ai/voynich.pdf", "use": "Closest prior protocol: pre-registered hypotheses, held-out pages, planted answers; documents the 'decipherment illusion'."},
    # --- the manuscript and its statistics
    {"key": "zandbergen", "cite": "R. Zandbergen. The Voynich MS (voynich.nu), transliteration files incl. ZL 3b (2025) and the IVTFF format.",
     "url": "https://www.voynich.nu/transcr.html", "use": "The pinned transliteration."},
    {"key": "beinecke", "cite": "Beinecke Rare Book & Manuscript Library, Yale University. MS 408 ('Cipher manuscript'), digital facsimile.",
     "url": "https://collections.library.yale.edu/catalog/2002046", "use": "The scans (public domain); anchors cite its IIIF canvases."},
    {"key": "currier1976", "cite": "P. Currier (1976). Papers on the Voynich Manuscript (seminar papers; reproduced by D. D'Imperio and on voynich.nu).",
     "url": None, "use": "Languages A and B, line and paragraph effects (F06-F09, F16)."},
    {"key": "bennett1976", "cite": "W. R. Bennett (1976). Scientific and Engineering Problem-Solving with the Computer. Prentice-Hall.",
     "url": None, "use": "Low conditional character entropy of Voynichese (F03)."},
    {"key": "rugg2004", "cite": "G. Rugg (2004). An elegant hoax? A possible solution to the Voynich manuscript. Cryptologia 28(1): 31-46.",
     "url": "https://doi.org/10.1080/0161-110491892755", "use": "Table-and-grille generator (G track)."},
    {"key": "montemurro2013", "cite": "M. A. Montemurro, D. H. Zanette (2013). Keywords and co-occurrence patterns in the Voynich Manuscript: an information-theoretic analysis. PLoS ONE 8(6): e66344.",
     "url": "https://doi.org/10.1371/journal.pone.0066344", "use": "Section-specific vocabulary (F10, F21)."},
    {"key": "timm2020", "cite": "T. Timm, A. Schinner (2020). A possible generating algorithm of the Voynich manuscript. Cryptologia 44(1): 1-19.",
     "url": "https://doi.org/10.1080/01611194.2019.1596999", "use": "Self-citation generator; near-repeats (F13, F14, F22)."},
    {"key": "davis2020", "cite": "L. F. Davis (2020). How many glyphs and how many scribes? Digital paleography and the Voynich Manuscript. Manuscript Studies 5(1): 164-180.",
     "url": "https://doi.org/10.1353/mns.2020.0011", "use": "Five scribal hands (F11)."},
    {"key": "gaskell2022", "cite": "D. E. Gaskell, C. L. Bowern (2022). Gibberish after all? Voynichese is statistically similar to human-produced samples of meaningless text. CEUR-WS 3313.",
     "url": "https://ceur-ws.org/Vol-3313/paper4.pdf", "use": "Human-made meaningless text as a control (proposed for S2)."},
    {"key": "layfield2026", "cite": "C. Layfield, L. F. Davis (2026). Singulion structure and the Voynich Manuscript. Digital Medievalist.",
     "url": None, "use": "Codicology; a candidate L1 step."},
    {"key": "claudeexam2026", "cite": "Voynich Text Examination (2026), written by Claude agents at the prompt of E. Mollick.",
     "url": "https://voynich-text-examination.netlify.app/", "use": "Phrase repetition and related measurements (F18-F21)."},
]

# Which references back which part of the test, for inline citations.
TEST_CITES = {
    "a": ["rissanen1978", "grunwald2007", "shannon1949", "kneserney1995"],
    "b": ["chengoodman1999", "knight2011"],
    "kill": ["schwartz2026", "hauer2016", "gaskell2022"],
    "c": ["beinecke"],
    "heldout": ["nosek2018", "schwartz2026"],
    "controls": ["knight2011", "raviknight2011", "schwartz2026"],
}


def by_key():
    return {r["key"]: r for r in REFERENCES}
