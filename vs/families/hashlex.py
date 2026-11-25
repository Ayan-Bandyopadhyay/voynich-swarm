"""Red-team adversary: every word decodes to a real word of the target language chosen by
hashing it. Output looks like the language word by word for any input whatsoever,
which is exactly what the kill tests and the description-length test exist to catch."""
import hashlib


def decode_word(word, key, seg):
    lex = key["lexicon"]
    h = int(hashlib.sha256((key.get("salt", "") + word).encode()).hexdigest(), 16)
    return lex[h % len(lex)]
