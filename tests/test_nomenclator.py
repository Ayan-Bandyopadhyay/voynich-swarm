import unittest
from collections import Counter

from vs import judge, lm
from vs.search_nomenclator import assign_distinct_codes
from vs.families import codebook, nomenclator


class NomenclatorTest(unittest.TestCase):
    def test_marked_words_and_spelling_use_the_same_scored_units(self):
        key = {"marker": "hh", "map": {"hhda": "terra", "ch": "a", "d": "b"}}
        seg = judge.seg_fn("eva-basic")
        cut = judge.key_units({"family": "nomenclator", "key": key}, seg)
        for word, expected in (("hhda", "terra"), ("hhde", ""), ("chd", "ab")):
            self.assertEqual("".join(cut(word)), word)
            self.assertEqual(nomenclator.decode_word(word, key, seg), expected)

    def test_whole_word_codebook_default(self):
        key = {"map": {"dd": "in"}, "default": "et"}
        self.assertEqual(codebook.decode_word("dd", key, list), "in")
        self.assertEqual(codebook.decode_word("ddd", key, list), "et")

    def test_frequency_evidence_can_swap_two_occupied_words(self):
        model = lm.KN([["red", "blue"]], 2)
        result = assign_distinct_codes(
            ["hhda", "hhde"], ["blue", "red"], {"hhda": {}, "hhde": {}}, {},
            model, Counter(hhda=90, hhde=10), Counter(red=900, blue=100), 2,
        )
        self.assertEqual(result, {"hhda": "red", "hhde": "blue"})
