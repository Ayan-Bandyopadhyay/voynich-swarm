"""Word-preserving substitution with declared glyph and whole-word nulls."""

NULL_WORD_PREFIX = "null-word:"


def units(word, key, seg):
    """Keep enough information to recover the ciphertext, including its nulls."""
    if word in key.get("null_words", ()):
        return [NULL_WORD_PREFIX + word]
    return list(seg(word))


def decode_word(word, key, seg):
    if word in key.get("null_words", ()):
        return ""
    mapping = key["map"]
    null_glyphs = key.get("null_glyphs", ())
    return "".join(mapping.get(glyph, "") for glyph in seg(word) if glyph not in null_glyphs)
