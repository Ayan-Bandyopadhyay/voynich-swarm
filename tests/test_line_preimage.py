"""Positive control for criterion (a) on keys that ignore the manuscript's spaces (J.md, open).

A simple-substitution control whose plaintext spaces are enciphered as one more glyph, with the
manuscript's spaces put at random glyph boundaries. Read with "spaces": "ignored", the true key
must pass (a), (b) and the kill tests; red-team and wrong keys must fail (a)."""
import random, unittest
from vs import controls, judge, views
from vs.ivtff import Page, Line


def spaces_ignored_control(lang="latin", noise=0.0):
    tr, ev, true = controls.make(lang, "simple", noise=noise)
    m = dict(true["key"]["map"])
    sg = [g for g in controls.CIPHER_GLYPHS if g not in m and len(g) == 1][0]
    m[sg] = " "
    rng = random.Random(7)

    def respace(pages):
        out = []
        for p in pages:
            q = Page(p.id, p.order, dict(p.meta))
            for ln in p.lines:
                ws, cur = [], ""
                for ch in sg.join(ln.words):
                    cur += ch
                    if rng.random() < 0.2:
                        ws.append(cur)
                        cur = ""
                if cur:
                    ws.append(cur)
                q.lines.append(Line(ln.id, ln.page, ln.n, ln.unit, ln.subtype, ws, ln.para_start, ln.para_end))
            out.append(q)
        return out

    sub = dict(true, key={"map": m}, spaces="ignored", id=f"control-{lang}-spaces-ignored")
    return views.apply(respace(tr), sub), views.apply(respace(ev), sub), sub, sg


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


if __name__ == "__main__":
    unittest.main()
