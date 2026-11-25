"""Constructed languages are references, not grid cells (P-J-004): the grid must not open steps for them."""
import unittest
from vs import season, refcorpus
from vs.facts import ref_langs


class ConlangNotInGrid(unittest.TestCase):
    def test_grid_languages_exclude_conlangs(self):
        self.assertFalse([l for l in season.LANGS if l.startswith("conlang_")])

    def test_no_first_key_step_for_a_conlang(self):
        from vs import steps
        self.assertFalse([x["id"] for x in steps.derived_steps() if x["id"].startswith("L3-first-conlang_")])

    def test_conlangs_stay_references(self):
        pinned = [l for l in refcorpus.languages() if l.startswith("conlang_")]
        self.assertTrue(set(pinned) <= set(refcorpus.languages()))
        for l in pinned:
            if l in ref_langs():
                self.assertIn(l, ref_langs())


if __name__ == "__main__":
    unittest.main()
