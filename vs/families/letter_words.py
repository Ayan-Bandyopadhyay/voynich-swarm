"""Letters written as whole words (the Naibbe class; Greshko 2025, record K-006).

A Voynich word is a prefix, a suffix, or a prefix followed by a suffix. A prefix stands for one
plaintext letter and a suffix for one plaintext letter, each through its own table, and several
prefixes or suffixes may stand for the same letter (homophones). So a word carries one or two
letters, and the spaces between Voynich words are not the plaintext's word breaks: the letters of
a page run on as one stream ("plaintext": "respaced", vs/respace.py), which the judge cuts into
words of the target language itself.

The key is {"prefix": {glyph string: letter}, "suffix": {glyph string: letter}}. A word is cut at
the longest prefix in the table whose remainder is a suffix in the table (either part may be
empty, not both); a word that cannot be cut this way carries nothing.
https://doi.org/10.1080/01611194.2025.2566408
"""


def split(word, key):
    prefix, suffix = key["prefix"], key["suffix"]
    for i in range(len(word), -1, -1):
        p, s = word[:i], word[i:]
        if (not p or p in prefix) and (not s or s in suffix):
            return p, s
    return None


def units(word, key, seg=None):
    cut = split(word, key)
    if cut is None:
        return [word]
    return [x for x in ("<" + cut[0] if cut[0] else "", ">" + cut[1] if cut[1] else "") if x]


def decode_word(word, key, seg):
    cut = split(word, key)
    if cut is None:
        return ""
    return key["prefix"].get(cut[0], "") + key["suffix"].get(cut[1], "")
