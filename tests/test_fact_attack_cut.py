"""Fact attacks with cut "lines" keep the attacker's line ends (vs/redteam.py).

A layout-aware table procedure (independent words by frequency from public Currier B text;
the last word of each line from the line-final vocabulary; no language) reproduces a
line-final positional fact only when its line breaks reach the scorer."""
import random, unittest
from collections import Counter
from vs import corpus, redteam, ivtff

F001 = {"id": "F-001", "type": "fact", "detail": {"spec": {
    "compare": [{"op": ">=", "value": 10}, {"direction": "greater", "null": "shuffle_within_line", "p": 0.01, "perms": 199}],
    "scope": {"language": "B"}, "select": {"certain": True, "position": "line_final", "unit": ["P"]},
    "statistic": {"ratio": {"feature": {"glyph_at": -1}, "in": ["m"],
                            "of": {"certain": True, "position": "line_final", "unit": ["P"]},
                            "to": {"certain": True, "position": "mid_line", "unit": ["P"]}}}}}}


def table_lines(n=1500, seed=408):
    train, _ev = corpus.split_pages("practice")
    B = [ln for p in train if p.language == "B" for ln in p.lines if ln.unit.startswith("P") and ln.words]
    ok = lambda w: not ivtff.uncertain(w) and "?" not in w and "*" not in w
    lens = Counter(len(ln.words) for ln in B)
    mid = Counter(w for ln in B for w in ln.words[:-1] if ok(w))
    fin = Counter(ln.words[-1] for ln in B if ok(ln.words[-1]))
    rng = random.Random(seed)
    draw = lambda c: rng.choices(list(c), weights=list(c.values()))[0]
    out = []
    for _ in range(n):
        k = rng.choices(list(lens), weights=list(lens.values()))[0]
        out.append([draw(mid) for _ in range(k - 1)] + [draw(fin)])
    return out


class FactAttackCut(unittest.TestCase):
    def test_line_cut_keeps_line_ends(self):
        lines = table_lines()
        tok = redteam.fact_attack("F-001", lines, "practice", F001)
        lin = redteam.fact_attack("F-001", lines, "practice", F001, cut="lines")
        self.assertFalse(tok["success"], tok)
        self.assertTrue(lin["success"], lin)

    def test_line_cut_guards(self):
        r = redteam.fact_attack("F-001", table_lines(n=10), "practice", F001, cut="lines")
        self.assertIn("refused", r)
        r = redteam.fact_attack("F-001", table_lines(n=10), "practice", F001, cut="pages")
        self.assertIn("refused", r)


if __name__ == "__main__":
    unittest.main()
