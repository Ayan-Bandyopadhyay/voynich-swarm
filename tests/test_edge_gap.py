import os, unittest
from vs import path, corpus, dsl

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class EdgeGapTest(unittest.TestCase):
    def test_edge_gap(self):
        _, ev = corpus.split_pages("practice")
        spec = {"select": {"unit": ["P"], "certain": True}, "statistic": {"edge_gap": True},
                "compare": [{"op": ">=", "value": 0.08},
                            {"null": "shuffle_within_page", "direction": "greater", "perms": 99, "p": 0.01}]}
        r = dsl.evaluate(spec, ev)
        self.assertTrue(r["pass"], r)
        self.assertEqual(r["value"], dsl.evaluate(spec, ev)["value"], "deterministic")

    def test_too_few_breaks_is_zero(self):
        _, ev = corpus.split_pages("practice")
        r = dsl.evaluate({"select": {"unit": ["P"]}, "statistic": {"edge_gap": True}}, [p for p in ev if any(l.unit == "P" for l in p.lines)][:1])
        self.assertEqual(r["value"], 0.0)


if __name__ == "__main__":
    unittest.main()
