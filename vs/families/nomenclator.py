"""Marked word-code nomenclator. A key maps marked whole words to plaintext
words and unmarked EVA glyphs to plaintext letters. The reserved introducer
and the entire joint mapping are charged as key material.
"""


def units(word, key, seg):
    return [word] if word.startswith(key["marker"]) else seg(word)


def decode_word(word, key, seg):
    return "".join(key["map"].get(u, "") for u in units(word, key, seg))
