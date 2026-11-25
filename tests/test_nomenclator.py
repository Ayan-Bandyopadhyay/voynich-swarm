import unittest
from vs import judge
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
