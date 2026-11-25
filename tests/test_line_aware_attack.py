import os, random, unittest
from vs import path, corpus, redteam

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))

# F-001 as registered (line-final m in Currier B), so the test does not depend on the record
F001 = {"type": "fact", "detail": {"spec": {
    "scope": {"language": "B"},
    "select": {"unit": ["P"], "position": "line_final", "certain": True},
    "statistic": {"ratio": {"feature": {"glyph_at": -1}, "in": ["m"],
                            "of": {"unit": ["P"], "position": "line_final", "certain": True},
                            "to": {"unit": ["P"], "position": "mid_line", "certain": True}}},
    "compare": [{"op": ">=", "value": 10},
                {"null": "shuffle_within_line", "direction": "greater", "perms": 199, "p": 0.01}]}}}


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class LineAwareAttackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tr, _ = corpus.split_pages("practice")
        ws = [w for p in tr if p.language == "B" for ln in p.lines for w in ln.words if "?" not in w and "*" not in w]
        cls.m, cls.o = [w for w in ws if w.endswith("m")], [w for w in ws if not w.endswith("m")]
        r = random.Random(3)
        body = [r.choice(cls.o) for _ in range(9000)]
        cls.lines = [body[i:i + 10] for i in range(0, 9000, 10)]
        cls.finals = [r.choice(cls.m) if r.random() < 0.15 else r.choice(cls.o) for _ in range(9000)]

    def test_blind_stream_cannot_reproduce_a_line_final_fact(self):
        r = redteam.fact_attack("F-001", self.lines, "practice", F001)
        self.assertFalse(r["success"])
        self.assertFalse(r["line_aware"])

    def test_line_aware_stream_reproduces_it(self):
        r = redteam.fact_attack("F-001", self.lines, "practice", F001, self.finals)
        self.assertTrue(r["line_aware"])
        self.assertTrue(r["success"], r)

    def test_guards(self):
        r = redteam.fact_attack("F-001", self.lines, "practice", F001, self.finals[:5])
        self.assertIn("refused", r)
        r = redteam.fact_attack("F-001", self.lines, "practice", F001, ["da?m"] + self.finals)
        self.assertIn("refused", r)


if __name__ == "__main__":
    unittest.main()
