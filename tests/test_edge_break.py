"""edge_mi_break (vs/dsl.py): edge-glyph dependence within lines minus across line breaks."""
import unittest
from vs import corpus, dsl, generators as G

SPEC = {"select": {"unit": ["P"], "certain": True}, "statistic": {"edge_mi_break": True},
        "compare": [{"op": ">=", "value": 0.1}, {"null": "shuffle_within_page", "direction": "greater", "perms": 99, "p": 0.01}]}


class EdgeBreak(unittest.TestCase):
    def test_manuscript_has_a_break_generators_do_not(self):
        train, ev = corpus.split_pages("practice")
        self.assertTrue(dsl.evaluate(SPEC, train)["pass"])
        for gen in (G.g_self_citation, G.g_table_cipher):
            self.assertFalse(dsl.evaluate(SPEC, gen(train, ev))["pass"], gen.__name__)

    def test_spec_checks(self):
        with self.assertRaises(dsl.SpecError):
            dsl.check_statistic({"edge_mi_break": 1})


if __name__ == "__main__":
    unittest.main()
