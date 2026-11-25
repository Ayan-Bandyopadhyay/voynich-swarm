"""Positive control for criterion (a) on keys that ignore the manuscript's spaces (J.md, open).

A simple-substitution control whose plaintext spaces are enciphered as one more glyph, with the
manuscript's spaces put at random glyph boundaries. Read with "spaces": "ignored", the true key
must pass (a), (b) and the kill tests; red-team and wrong keys must fail (a)."""
import random, unittest
from vs import controls, judge, search


def spaces_ignored_control(lang="latin", noise=0.0):
    tr, ev, sub = controls.make_spaces_ignored(lang, noise=noise)
    sg = next(g for g, v in sub["key"]["map"].items() if v == " ")
    return tr, ev, sub, sg


def passes(r):
    return r["a_compresses"]["pass"] and r["b_reads"]["pass"] and r["kill_tests"]["pass"]


class LinePreimage(unittest.TestCase):
    def test_true_key_passes_red_team_fails(self):
        tr, ev, sub, sg = spaces_ignored_control("latin")
        r = judge.evaluate(sub, tr, ev, "control")
        self.assertTrue(passes(r), r["a_compresses"])
        m = sub["key"]["map"]
        gl = [g for g in m if g != sg]
        ls = [m[g] for g in gl]
        random.Random(3).shuffle(ls)
        bad = [dict(k, spaces="ignored") for k in controls.red_team_keys("latin")]
        bad.append(dict(sub, id="wrong-permuted", key={"map": {**dict(zip(gl, ls)), sg: " "}}))
        bad.append(dict(sub, id="space-every-glyph", key={"map": {g: v + " " for g, v in m.items()}}))
        for k in bad:
            r = judge.evaluate(k, tr, ev, "control")
            self.assertFalse(r["a_compresses"]["pass"], k["id"])
            self.assertFalse(passes(r), k["id"])

    def test_search_cracks_spaces_ignored_control(self):
        tr, ev, sub, sg = spaces_ignored_control("latin", noise=controls.NOISE)
        k = search.search_cell("latin", "substitution", tr, tag="control", spaces="ignored")
        self.assertEqual(k["key"]["map"].get(sg), " ")
        self.assertTrue(passes(judge.evaluate(k, tr, ev, "control")))


if __name__ == "__main__":
    unittest.main()
