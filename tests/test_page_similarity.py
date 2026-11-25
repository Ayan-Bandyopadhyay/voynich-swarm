"""page_similarity (vs/dsl.py): pages close in manuscript order share more words than pages far apart."""
import unittest
from vs import corpus, dsl, generators as G

SPEC = {"select": {"certain": True}, "statistic": {"page_similarity": {"within": 10}},
        "compare": [{"op": ">=", "value": 0.04}, {"null": "shuffle_across_pages", "direction": "greater", "perms": 99, "p": 0.01}]}


class PageSimilarity(unittest.TestCase):
    def test_manuscript_has_neighbourhoods_generators_do_not(self):
        train, ev = corpus.split_pages("practice")
        self.assertTrue(dsl.evaluate(SPEC, train)["pass"])
        self.assertTrue(dsl.evaluate(SPEC, ev)["pass"])
        for gen in (G.g_self_citation, G.g_table_cipher):
            self.assertFalse(dsl.evaluate(SPEC, gen(train, ev))["pass"], gen.__name__)

    def test_too_few_page_pairs_is_undefined(self):
        _train, ev = corpus.split_pages("practice")
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate({**SPEC, "statistic": {"page_similarity": {"within": 1}}}, ev)

    def test_spec_checks(self):
        for bad in (True, {}, {"within": 0}, {"within": 51}, {"within": 5, "min_words": 5}, {"within": 5, "window": 3}):
            with self.assertRaises(dsl.SpecError):
                dsl.check_statistic({"page_similarity": bad})


if __name__ == "__main__":
    unittest.main()
