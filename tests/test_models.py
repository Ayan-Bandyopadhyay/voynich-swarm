"""Red-team tests for the production-model language (vs/models.py)."""
import math, random, unittest
from vs import models
from vs.ivtff import Page, Line

WORDS = ["daiin", "chol", "shedy", "qokeedy", "ol", "or", "aiin", "chedy", "okal", "dar", "qokain", "chey"]


def pages(n, lines, seed, section="H"):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        p = Page(f"f{seed}_{i}r", i, {"I": section, "L": "A", "H": "1"})
        p.lines = [Line(f"{p.id}.{j}", p.id, j, "P", "0", [rng.choice(WORDS) for _ in range(8)], j == 0, False) for j in range(lines)]
        out.append(p)
    return out


class ModelRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tr, cls.ev = pages(8, 20, 1), pages(2, 20, 2)

    def refused(self, spec, ev=None):
        with self.assertRaises(models.ModelError):
            models.evaluate(spec, self.tr, ev or self.ev)

    def test_a_plain_model_scores(self):
        r = models.evaluate({"title": "t", "components": [{"type": "vocab"}, {"type": "copy", "window": 50, "edits": 0}]}, self.tr, self.ev)
        self.assertTrue(math.isfinite(r["bits_per_word"]))
        self.assertAlmostEqual(sum(r["weights"]), 1.0, places=3)

    def test_nan_weights_are_refused(self):
        """Before: weights [NaN, 1] passed the check (NaN < 0 is false) and the record got bits_per_word NaN."""
        comps = [{"type": "vocab"}, {"type": "letters"}]
        self.refused({"components": comps, "weights": [float("nan"), 1]})
        self.refused({"components": comps, "weights": [float("inf"), 1]})
        self.refused({"components": comps, "weights": "tuned"})
        self.refused({"components": comps, "weights": [1]})

    def test_copy_window_is_bounded(self):
        """Before: window 0 meant recent[-0:], the whole page so far (the documented bound is 50), and a
        negative window meant everything but the first words."""
        self.refused({"components": [{"type": "copy", "window": 0}]})
        self.refused({"components": [{"type": "copy", "window": -5}]})
        self.refused({"components": [{"type": "copy", "window": 51}]})
        self.refused({"components": [{"type": "copy", "edits": 2}]})

    def test_unknown_keys_are_refused(self):
        """Before: {"scope": {"scribe": "1"}} was ignored and the model was scored on the whole manuscript;
        a component without a type crashed the scorer with KeyError instead of a refusal."""
        self.refused({"scope": {"scribe": "1"}, "components": [{"type": "vocab"}]})
        self.refused({"components": [{"type": "copy", "windw": 5}]})
        self.refused({"components": [{}]})
        self.refused({"components": ["vocab"]})
        self.refused({"components": [{"type": "letters", "order": 2}, {"type": "letters", "order": 5}]})

    def test_tiny_evaluation_scope_is_refused(self):
        """Before: a scope leaving a few dozen evaluation words was scored (bits per word of noise)."""
        self.refused({"components": [{"type": "vocab"}]}, pages(1, 5, 3))

    def test_copy_is_a_proper_distribution(self):
        """The copy component's own mass (before its vocabulary share) never exceeds 0.9, with or without edits."""
        class Zero:
            def p(self, w, ctx):
                return 0.0
        glyphs = sorted({g for w in WORDS for g in models.SEG(w)})
        recent = ["daiin", "chol", "daiin", "shedy", "ol"]
        cands = set(recent)
        for r in recent:
            cands |= models._edit1_variants(r, glyphs)
        for edits in (0, 1):
            c = models.Copy(5, edits, glyphs, Zero())
            mass = sum(c.p(w, {"recent": recent}) for w in cands)
            self.assertLessEqual(mass, 0.9 + 1e-9)
            self.assertGreater(mass, 0.85)


if __name__ == "__main__":
    unittest.main()
