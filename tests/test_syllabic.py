import unittest
from vs import judge
from vs.families import syllabic


class SyllabicTest(unittest.TestCase):
    def test_homophones_unknown_and_trailing_marker(self):
        key = {"marker": "q", "map": {"qa": "ma", "qd": "ma", "ch": "n"}}
        seg = judge.seg_fn("eva-basic")
        cut = judge.key_units({"family": "syllabic", "key": key}, seg)
        for word, expected in (("qaqdch", "maman"), ("qch", ""), ("chq", "n")):
            self.assertEqual("".join(cut(word)), word)
            self.assertEqual(syllabic.decode_word(word, key, seg), expected)
