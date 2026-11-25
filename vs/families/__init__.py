"""Decoder families. A decipherment is (family program, key). Each family exposes
decode_word(word: str, key: dict, seg: callable) -> str, a deterministic function of ONE
Voynich word. The word-level interface is deliberate: a decoder cannot tell whether a
word came from a real page or from a word-shuffled decoy, so the word-order kill test
cannot be dodged. Line-level families are planned for a later season.

A new family is added by pull request and must be reviewed and merged before any key that
uses it is scored on the held-out pages.
"""
import importlib, os

FAMILIES = ["substitution", "verbose", "codebook", "abbreviation", "constant", "hashlex"]


def load(name):
    if name not in FAMILIES:
        raise SystemExit(f"unknown family {name!r}: families must be merged before use")
    return importlib.import_module(f"vs.families.{name}")


def source_file(name):
    return os.path.join(os.path.dirname(__file__), f"{name}.py")
