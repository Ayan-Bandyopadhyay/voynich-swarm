import os, unittest
from vs import path, corpus, models

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class ConditionedLettersTest(unittest.TestCase):
    def test_components_build_and_help(self):
        tr, ev = corpus.split_pages("practice")
        scope = {"hand": "1"}
        base = {"scope": scope, "components": [{"type": "letters", "order": 3}], "weights": "fit"}
        new = {"scope": scope, "components": [{"type": "letters", "order": 3}, {"type": "position_letters", "order": 3},
                                              {"type": "boundary_letters", "order": 3}], "weights": "fit"}
        a, b = models.evaluate(base, tr, ev), models.evaluate(new, tr, ev)
        self.assertEqual(len(b["weights"]), 3)
        self.assertLess(b["bits_per_word"], a["bits_per_word"])

    def test_contexts_are_distributions(self):
        # each context's glyph model gives total probability at most 1 over a large word set
        tr, _ = corpus.split_pages("practice")
        tr = models.scoped(tr, {"hand": "1"})
        built = models.build({"components": [{"type": "position_letters"}, {"type": "boundary_letters"}]}, tr)
        words = {w for s in models.page_streams(tr) for w, _ in s}
        for c, ctxs in ((built[0], [{"pos": x, "prev": None} for x in ("initial", "mid", "final")]),
                        (built[1], [{"pos": "mid", "prev": x} for x in (None, "daiin", "chol", "qokeedy")])):
            for ctx in ctxs:
                self.assertLessEqual(sum(c.p(w, ctx) for w in words), 1.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
