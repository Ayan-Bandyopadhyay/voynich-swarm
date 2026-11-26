import unittest
from unittest.mock import patch

from vs import ivtff, judge, search


LANGUAGE = "fixture"
ALPHABET = "aemnrt"
ENCODE = str.maketrans(ALPHABET, "oktdly")
PLAIN = "me am eat ate tea team mate tame name mean meant near tear rate tare ram ran amen arena ten net met rent tree meet".split()
ENCIPHERED = [word.translate(ENCODE) for word in PLAIN]


def fit(words, tag):
    page = ivtff.Page("c0", 0, {}, [
        ivtff.Line(f"c0.{i}", "c0", i, "P", "0", words[start:start + 12], False, False)
        for i, start in enumerate(range(0, len(words), 12), 1)
    ])
    budget = {**search.cell_budget(LANGUAGE, "nulls"), "iterations": 220}
    with (patch.object(search.refcorpus, "train_text", return_value=[" ".join(PLAIN * 12)]),
          patch.object(search.refcorpus, "alphabet", return_value=list(ALPHABET))):
        return search.search_cell(LANGUAGE, "nulls", [page], budget=budget, tag=tag)


class NullsSearchTest(unittest.TestCase):
    def test_recovers_repeated_unmarked_words_and_ordinary_substitution(self):
        # Both fillers use only the ordinary cipher alphabet.
        fillers = ["odddd", "tltly"]
        line_group = ENCIPHERED + [fillers[0]] * 4 + [fillers[1]] * 2
        sub = fit(line_group * 7, "word-fixture")

        self.assertEqual(sub["key"]["null_words"], fillers)
        self.assertEqual(sub["key"]["null_glyphs"], [])
        self.assertEqual(judge.Decoder(sub, LANGUAGE).words(line_group), PLAIN)

    def test_recovers_glyph_null_across_refits(self):
        # Each padded spelling appears once, below the frequent-word null threshold.
        padded = [word[:1] + "q" + word[1:] for word in ENCIPHERED[:14]]
        sub = fit(ENCIPHERED * 10 + padded, "glyph-fixture")

        self.assertEqual(sub["key"]["null_words"], [])
        self.assertEqual(sub["key"]["null_glyphs"], ["q"])
        self.assertEqual(judge.Decoder(sub, LANGUAGE).words(ENCIPHERED + padded), PLAIN + PLAIN[:14])
