"""Periodic tabula recta. Column shifts repeat from the beginning of each
word. Undoing each shift permutes the ciphertext glyph inventory, so the
original glyph sequence is recovered by applying the opposite shift.
"""


def units(word, key, seg):
    row = sorted(key["map"])
    shifts = key["shifts"]
    return [row[(row.index(g) - shifts[i % len(shifts)]) % len(row)] if g in key["map"] else g
            for i, g in enumerate(seg(word))]


def decode_word(word, key, seg):
    return "".join(key["map"].get(g, "") for g in units(word, key, seg))
