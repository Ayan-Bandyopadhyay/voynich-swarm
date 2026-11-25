"""Conventional word-final abbreviation signs. Each sign expands to a suffix
only at the end of a word. Elsewhere it has no reading.
"""


def units(word, key, seg):
    glyphs = seg(word)
    return [g + "$" if i == len(glyphs) - 1 and g + "$" in key["map"] else g
            for i, g in enumerate(glyphs)]


def decode_word(word, key, seg):
    return "".join(key["map"].get(g, "") for g in units(word, key, seg))
