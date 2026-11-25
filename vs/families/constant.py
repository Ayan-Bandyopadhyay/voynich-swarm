"""Red-team baseline: every word decodes to the same plaintext word. Reads as fluent
nonsense; the judge must reject it."""


def decode_word(word, key, seg):
    return key["word"]
