"""Audits of past claims, run through the same judge before we claim anything ourselves.

Each audit records what the claimant actually published, what we could turn into a
deterministic program plus key, and the judge's verdict. Where a claimant published no
key, the audit says so: under our rules that is not a result, whatever the press said.
Where the published key is a prose description, we build every key consistent with the
description and judge the best one in each candidate language, which is generous to the
claimant.
"""
import itertools, math
from collections import Counter
from . import ivtff, lm, refcorpus
from .search import trigram_table

# Cheshire 2019 (Romance Studies 37:30-67, accepted author manuscript, Bristol Research
# Portal): his alphabet is described in prose with figures. Fixed readings are those the
# prose makes unambiguous in EVA terms; the choices list every EVA reading we could not
# pin down from the text alone. Each is our reading of his words, published for correction.
CHESHIRE_FIXED = {
    "o": "o",       # Fig. 16: "the letter 'o' which is a familiar Latin symbol"
    "a": "a",       # Figs. 1-2: 'trapped a' / 'free a'
    "e": "e",       # Figs. 7-9: variants of 'e'
    "i": "i",       # Fig. 10: 'i', "akin to the short e"
    "n": "n",       # Fig. 15: 'n', from the Arabic nuun
    "r": "r",       # Fig. 21: 'r', like a capital R
}
CHESHIRE_CHOICES = {
    # Figs. 11-12: l and m are two-legged with one / two loops -> the EVA gallows k and t
    "kt": [{"k": "l", "t": "m"}, {"k": "m", "t": "l"}],
    # Figs. 17-18: p and qu are one-legged with two / one loops -> the EVA gallows p and f
    "pf": [{"p": "p", "f": "qu"}, {"p": "qu", "f": "p"}],
    # Figs. 13-14, 19-20: gallows with the 'long e' -> ele, eme, epe, eque (follows kt/pf)
    # Figs. 7-9: the 'long e' is the bench
    "ch": [{"ch": "e", "sh": "e"}, {"ch": "ee", "sh": "e"}],
    # Fig. 6: d, a Greek delta
    "d": [{"d": "d"}, {"d": "a"}],
    # Figs. 22-23: 'sitting s' at word ends (or z, by pronunciation)
    "y": [{"y": "s"}, {"y": "z"}, {"y": "a"}, {"y": "u"}],
    # Figs. 22, 24: 'standing s' and t, told apart by the foot
    "s": [{"s": "s"}, {"s": "t"}],
    "l": [{"l": "t"}, {"l": "s"}, {"l": "l"}],
    # Figs. 27-28: u and v
    "q": [{"q": "v"}, {"q": "u"}, {"q": ""}],
    "m": [{"m": "s"}, {"m": "z"}, {"m": "m"}],
}


def cheshire_map(choice):
    m = dict(CHESHIRE_FIXED)
    for part in choice:
        m.update(part)
    for g, c in (("ckh", "k"), ("cth", "t"), ("cph", "p"), ("cfh", "f")):
        m[g] = "e" + m[c] + "e"
    return m


def score_map(m, types, table, sy, lang):
    s = 0.0
    for w, c in types:
        d = refcorpus.normalize("".join(m.get(g, "") for g in ivtff.segment(w, "eva-basic")), lang)
        seq = [lm.WB] + [ch for ch in d if ch in sy] + [lm.WB]
        for x, y, z in zip(seq, seq[1:], seq[2:]):
            s += c * table[x, y, z]
    return s


def cheshire_best(lang, train_pages, passes=3):
    """Coordinate ascent over Cheshire's open choices, maximizing the target-language trigram
    fit of the training pages. Returns the best key file."""
    table, sy = trigram_table(lang)
    types = Counter(w for p in train_pages for ln in p.lines for w in ln.words if not ivtff.uncertain(w)).most_common(3000)
    names = list(CHESHIRE_CHOICES)
    cur = {n: 0 for n in names}
    best = score_map(cheshire_map([CHESHIRE_CHOICES[n][cur[n]] for n in names]), types, table, sy, lang)
    for _ in range(passes):
        for n in names:
            for i in range(len(CHESHIRE_CHOICES[n])):
                trial = dict(cur, **{n: i})
                s = score_map(cheshire_map([CHESHIRE_CHOICES[k][trial[k]] for k in names]), types, table, sy, lang)
                if s > best:
                    best, cur = s, trial
    m = cheshire_map([CHESHIRE_CHOICES[n][cur[n]] for n in names])
    return {"id": f"audit-cheshire2019-{lang}", "family": "substitution", "segmentation": "eva-basic",
            "target": {"language": lang, "period": "claimed 'proto-Romance', 15th c."},
            "claimant": "G. Cheshire (2019), Romance Studies 37:30-67",
            "provenance": "our reading of the prose alphabet in the accepted author manuscript; the best of "
                          f"{math.prod(len(v) for v in CHESHIRE_CHOICES.values())} readings consistent with it, chosen on training pages",
            "choices": cur, "key": {"map": m}}


NOT_JUDGEABLE = [
    {"id": "audit-gibbs2017", "claim": "N. Gibbs, 'Voynich manuscript: the solution', Times Literary Supplement, 5 Sep 2017",
     "summary": "Abbreviated medieval Latin; a women's-health guide.",
     "published_key": "No complete glyph-to-expansion table; two lines offered as a reading.",
     "status": "NOT JUDGEABLE AS SUBMITTED",
     "what_we_did": "Nothing to run: no deterministic program and key. The abbreviation-expansion family is an open cell (L3) that anyone may submit to.",
     "sources": ["https://www.the-tls.co.uk/articles/public/voynich-manuscript-solution/ (not fetched: blocked to our fetcher)", "Wikipedia summary of contemporary criticism"]},
    {"id": "audit-ai30pct2026", "claim": "Viral 2026 story that an AI 'decoded 30%' of the manuscript",
     "summary": "No paper, code, key or plaintext was released with the story.",
     "published_key": "None.", "status": "NOT JUDGEABLE AS SUBMITTED",
     "what_we_did": "Nothing to run. If the authors publish a program and key, the judge will run it the day it arrives.",
     "sources": []},
    {"id": "audit-hydrothermal2026", "claim": "Post on X, 22 Nov 2026, with a Zenodo record: the manuscript is a 'coupled hydro-thermal manual and logbook' (brewery, hypocaustum, baths), its repetitions are 'operational ticks', 'formally verified' with the Z3 SMT solver",
     "summary": "A structural reinterpretation: words are mapped to states of a discrete state space and a solver shows the state machine converges.",
     "published_key": "No glyph-to-plaintext key and no plaintext. The Z3 proof shows the author's own state machine is consistent; it says nothing about whether the manuscript encodes it.",
     "status": "NOT JUDGEABLE AS SUBMITTED",
     "what_we_did": "Nothing to run. A formal proof of a model's internal consistency is not evidence that the text is that model: any text can be mapped onto a convergent state machine. Under our rules a reading needs a program and key that pass the held-out judges.",
     "sources": ["https://x.com/rajo_PL/status/2124592987468415067"]},
    {"id": "audit-claude-examination2026", "claim": "'Voynich Text Examination' (Sep 2026): Claude agents, prompted by E. Mollick, tried 211 techniques against the manuscript and reported no decipherment",
     "summary": "Not a decipherment claim: an honest negative result. 23 measurements against 243 samples of real writing in 31 languages; seven explanations scored; best guess a dice-and-tables procedure, not confirmed.",
     "published_key": "No key (none claimed). Measurements and verdicts published as a site.",
     "status": "NEGATIVE RESULT, CONSISTENT WITH OURS",
     "what_we_did": "Pre-registered its strongest finding as F18 (the manuscript almost never repeats a four-word phrase; every real text does) plus F19-F21, and scored them on our held-out pages: established. Its 'harder test' (fit tables on half, write the other half) is how our G track already scores generators.",
     "sources": ["https://x.com/emollick/status/2100767116819325141", "https://voynich-text-examination.netlify.app/"]},
    {"id": "audit-nomenklator2025", "claim": "voynich.ninja thread and Zenodo record (Dec 2025): a Latin 'nomenklator' key with 85% coverage and 99.8% confidence; e.g. ytedy = DEINDE, said to occur 6,421 times",
     "summary": "A word-level codebook into Latin.",
     "published_key": "Partial; the linked code repository is reported to return 404.",
     "status": "FACTUAL CLAIM REFUTED",
     "what_we_did": "Checked the headline statistic against the pinned ZL 3b transliteration: 'ytedy' occurs 24 times in 38,486 words (the commonest word, daiin, occurs 846 times), not 6,421. Under our rules the judge computes every statistic itself from pinned inputs and ignores submitted numbers. If the full key is published, the codebook family will judge it.",
     "sources": ["https://www.voynich.ninja/printthread.php?tid=5118", "https://zenodo.org/records/17794596"]},
    {"id": "related-schwartz2026", "claim": "M. Schwartz, 'How the Voynich Manuscript was written' (preprint, Oct 2026)",
     "summary": "The closest prior work to this project: pre-registered hypotheses scored on held-out pages, every solver first required to recover planted answers. 130 hypotheses in 18 languages fail. Documents a 'decipherment illusion': unconstrained optimizers gain bits that vanish once output must look like the language.",
     "published_key": "Not a decipherment claim.",
     "status": "RELATED WORK, CONSISTENT WITH OURS",
     "what_we_did": "Adopted for season S2: a matched-freedom control and a plaintext-shape check (see docs/DESIGN.md). Our positive controls are the same idea as its planted answers. Preprint marked preliminary; we cite it, we have not reproduced it.",
     "sources": ["https://bootloops.ai/voynich.pdf"]},
]
