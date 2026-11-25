"""Fact attacks may send first_lines: lines written as the first line of a paragraph (vs/redteam.py).

A table procedure with two word lists (words seen on paragraph first lines; words seen on other
lines; independent draws, no language) reproduces a paragraph-first-line fact only when the
scorer puts its first lines where paragraphs open."""
import random, unittest
from collections import Counter
from vs import corpus, redteam, ivtff

F008 = {"id": "F-008", "type": "fact", "detail": {"spec": {
    "compare": [{"op": ">=", "value": 3}, {"direction": "greater", "null": "shuffle_within_page", "p": 0.01, "perms": 199}],
    "select": {"certain": True, "position": "para_first_line", "unit": ["P"]},
    "statistic": {"ratio": {"feature": {"glyph_at": 0}, "in": ["p", "f"],
                            "of": {"certain": True, "position": "para_first_line", "unit": ["P"]},
                            "to": {"certain": True, "position": "not_para_first_line", "unit": ["P"]}}}}}}


def two_lists(n=1500, seed=408):
    train, _ev = corpus.split_pages("practice")
    top, rest = Counter(), Counter()
    for p in train:
        first = True
        for ln in p.lines:
            if not ln.words or ln.unit != "P":
                continue
            (top if (ln.para_start or first) else rest).update(w for w in ln.words if not ivtff.uncertain(w))
            first = ln.para_end
    rng = random.Random(seed)
    draw = lambda c, k: rng.choices(list(c), weights=list(c.values()), k=k)
    return [draw(rest, 9) for _ in range(n)], [draw(top, 9) for _ in range(n)]


class FirstLines(unittest.TestCase):
    def test_paragraph_fact_needs_first_lines(self):
        lines, first = two_lists()
        self.assertTrue(redteam.fact_attack("F-008", lines, "practice", F008, cut="lines", first_lines=first)["success"])
        self.assertFalse(redteam.fact_attack("F-008", lines, "practice", F008, cut="lines")["success"])

    def test_guards(self):
        lines, first = two_lists()
        self.assertIn("refused", redteam.fact_attack("F-008", lines, "practice", F008, cut="tokens", first_lines=first))
        self.assertIn("refused", redteam.fact_attack("F-008", lines, "practice", F008, cut="lines", first_lines=first[:5]))
        self.assertIn("refused", redteam.fact_attack("F-008", lines, "practice", F008, cut="lines", first_lines=[["a?b"] * 9] * 1500))


if __name__ == "__main__":
    unittest.main()
