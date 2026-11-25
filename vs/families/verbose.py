"""Verbose substitution: the word is cut into the key's units by greedy longest match
(units are EVA strings such as 'aiin', 'ol', 'dy'), and each unit becomes a plaintext
string. Characters not covered by any unit are nulls."""


def decode_word(word, key, seg):
    units = sorted(key["map"], key=len, reverse=True)
    out, i = [], 0
    while i < len(word):
        for u in units:
            if word.startswith(u, i):
                out.append(key["map"][u])
                i += len(u)
                break
        else:
            i += 1
    return "".join(out)
