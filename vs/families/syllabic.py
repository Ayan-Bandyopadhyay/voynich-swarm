"""Word-preserving syllabic homophones. A marker and its following glyph
form one sign. A sign represents a CV syllable and ordinary glyphs spell
the remaining letters. Multiple signs may represent the same syllable.

This bounded model tests alternating single-letter and multi-letter plaintext
units with homophones. Greshko's Naibbe (2025, record K-006) additionally
uses card-weighted tables and respaces the original plaintext.
https://doi.org/10.1080/01611194.2025.2566408
"""


def units(word, key, seg):
    glyphs = iter(seg(word))
    marker = key["marker"]
    return [g + next(glyphs, "") if g == marker else g for g in glyphs]


def decode_word(word, key, seg):
    return "".join(key["map"].get(u, "") for u in units(word, key, seg))
