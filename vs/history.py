"""A century of claimed solutions, for the timeline on the site.

status:
  not_accepted   proposed and not accepted by later scholarship
  not_judgeable  no program and key published, so the test has nothing to run
  judged_fail    run through our test (audit) and failed
  negative       an honest negative result (no solution claimed)
  related        method work, not a solution claim
Wording is deliberately cautious; corrections welcome by pull request with a source.
"""

CLAIMS = [
    {"year": 1921, "who": "W. R. Newbold", "claim": "Roger Bacon's ciphered science, read via microscopic shorthand", "status": "not_accepted", "note": "Shown by J. M. Manly (1931) to rest on cracks in the ink."},
    {"year": 1943, "who": "J. M. Feely", "claim": "Abbreviated Latin", "status": "not_accepted", "note": ""},
    {"year": 1945, "who": "L. C. Strong", "claim": "A 16th-century English author's cipher", "status": "not_accepted", "note": ""},
    {"year": 1978, "who": "R. Brumbaugh", "claim": "A numeric cipher; a forgery to sell to Rudolf II", "status": "not_accepted", "note": ""},
    {"year": 1987, "who": "L. Levitov", "claim": "Cathar liturgy in a Flemish creole", "status": "not_accepted", "note": ""},
    {"year": 2004, "who": "G. Rugg", "claim": "Meaningless text from tables and a grille", "status": "related", "note": "A generator, not a reading: tested in our G track."},
    {"year": 2014, "who": "S. Bax", "claim": "Provisional readings of a handful of words from plant labels", "status": "not_accepted", "note": "Presented as partial and provisional."},
    {"year": 2017, "who": "N. Gibbs", "claim": "Abbreviated Latin, a women's-health guide", "status": "not_judgeable", "note": "No complete key."},
    {"year": 2018, "who": "B. Hauer, G. Kondrak", "claim": "AI identifies Hebrew with anagrammed words", "status": "not_accepted", "note": "Widely reported as 'AI decodes'; the authors' claim was narrower."},
    {"year": 2019, "who": "G. Cheshire", "claim": "'Proto-Romance' in a unique alphabet", "status": "judged_fail", "note": "Our audit: fails every criterion in 5 languages."},
    {"year": 2025, "who": "forum post + Zenodo", "claim": "Latin 'nomenklator', 85% coverage", "status": "not_judgeable", "note": "Full key not published. Its headline count of 'ytedy' is 6,421 in the claim, 24 in the transliteration."},
    {"year": 2026, "who": "viral story", "claim": "'AI decoded 30%'", "status": "not_judgeable", "note": "No paper, code or key."},
    {"year": 2026, "who": "Claude agents (E. Mollick)", "claim": "211 techniques tried, no reading", "status": "negative", "note": "Consistent with our facts F18-F21."},
    {"year": 2026, "who": "M. Schwartz", "claim": "130 pre-registered hypotheses, all fail on held-out pages", "status": "negative", "note": "Closest prior protocol to ours."},
    {"year": 2026, "who": "X post + Zenodo", "claim": "A hydro-thermal logbook, 'formally verified' with Z3", "status": "not_judgeable", "note": "A proof of a model's consistency is not a reading."},
]
