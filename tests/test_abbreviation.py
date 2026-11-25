import unittest
from vs import judge
from vs.families import abbreviation


class AbbreviationTest(unittest.TestCase):
    def test_only_final_sign_expands(self):
        key = {"map": {"o": "n", "cth$": "us"}}
        seg = judge.seg_fn("eva-basic")
        cut = judge.key_units({"family": "abbreviation", "key": key}, seg)
        self.assertEqual(abbreviation.decode_word("octh", key, seg), "nus")
        self.assertEqual(abbreviation.decode_word("ctho", key, seg), "n")
        self.assertEqual(cut("cthocth"), ["cth", "o", "cth$"])
