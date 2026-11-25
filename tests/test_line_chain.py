import os, unittest
from vs import path, corpus, dsl, generators

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class LineChainTest(unittest.TestCase):
    def test_shape_and_edge_dependence(self):
        tr, ev = corpus.split_pages("practice")
        out = generators.GENERATORS["G-line-chain"](tr, ev)
        self.assertEqual([[len(l.words) for l in p.lines] for p in out], [[len(l.words) for l in p.lines] for p in ev])
        self.assertEqual([l.words for p in out for l in p.lines],
                         [l.words for p in generators.g_line_chain(tr, ev) for l in p.lines], "deterministic")
        spec = {"select": {"certain": True, "unit": ["P"]}, "statistic": {"edge_mi": True},
                "compare": [{"op": ">=", "value": 0.15},
                            {"null": "shuffle_within_page", "direction": "greater", "perms": 99, "p": 0.01}]}
        self.assertTrue(dsl.evaluate(spec, out)["pass"])
        self.assertFalse(dsl.evaluate(spec, generators.g_self_citation(tr, ev))["pass"])


if __name__ == "__main__":
    unittest.main()
