"""Glyph substitution: each glyph (under the declared segmentation) becomes a plaintext
string, possibly empty (a null) or several letters. Covers simple, homophonic
(many glyphs to one letter) and simple verbose ciphers. A glyph missing from the key is
a null."""


def decode_word(word, key, seg):
    m = key["map"]
    return "".join(m.get(g, "") for g in seg(word))
