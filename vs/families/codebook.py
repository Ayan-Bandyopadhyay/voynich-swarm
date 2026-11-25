"""Codebook (nomenclator) at word level: a table from whole Voynich words to plaintext.
Words outside the table decode to key['default'] (often ''). The whole table is key,
so it is paid for in full by the description-length test."""


def decode_word(word, key, seg):
    return key["map"].get(word, key.get("default", ""))
