import unittest
from unittest.mock import patch
from vs import registry, redteam, steps


def fact(i, best=None):
    d = {"spec": {}}
    if best is not None:
        d["best_generator"] = {"attack": "R-002", "reproduced": best}
    return {"id": i, "type": "fact", "verdict": "ESTABLISHED", "detail": d}


def gen(i, per, hypothesis=None, lines=True):
    d = {"attack": "generator", "target": "*", "per_fact": per}
    if hypothesis:
        d["hypothesis"] = hypothesis
    return {"id": i, "type": "attack", "verdict": "x", "target": "*", "detail": d,
            "submitted": {"attack.json": {"lines": [["a"]] if lines else []}}, "provenance": {}}


RECORD = [fact("F-001"), fact("F-002"), fact("F-003", best=True), fact("F-004", best=False),
          gen("R-001", {"F-001": True}), gen("R-002", {"F-001": True, "F-002": True}),
          gen("R-003", {"F-001": True, "F-002": True, "F-004": True}, hypothesis="invented_language")]


def read(type=None):
    return [i for i in RECORD if type is None or i["type"] == type]


class BestGeneratorTest(unittest.TestCase):
    def setUp(self):
        p = patch.object(registry, "read", side_effect=read)
        p.start()
        self.addCleanup(p.stop)

    def test_the_best_meaningless_generator_is_picked(self):
        self.assertEqual(redteam.best_generator()["id"], "R-002", "invented-language tests are not generators")

    def test_a_fact_the_best_generator_reproduces_is_not_a_top_attack_target(self):
        open_steps = [{"id": f"R-attack-{f}", "status": "open", "kind": "step"} for f in ("F-003", "F-004")]
        why = {}
        top = steps.rules_top(open_steps, why)
        self.assertEqual(top[0], "R-attack-F-004", "F-004 survives the best generator: it stays the top pick")
        self.assertIn("R-002", why["R-attack-F-003"])
        self.assertGreater(top.index("R-attack-F-003"), top.index("R-attack-F-004"))


if __name__ == "__main__":
    unittest.main()


class ScriptedLeadTest(unittest.TestCase):
    """Rules added with the 2026-11-27 audit: saturation, enciphered language, spread over fronts."""
    def run_rules(self, record, open_steps):
        with patch.object(registry, "read", side_effect=lambda type=None: [i for i in record if type is None or i["type"] == type]):
            why = {}
            return steps.rules_top(open_steps, why), why

    def saturated_record(self, extra=()):
        facts = [fact(f"F-{n:03d}") for n in range(1, 13)]
        return facts + [gen("R-001", {f["id"]: f["id"] != "F-012" for f in facts})] + list(extra)

    def step(self, i, program, title="t", how="agent"):
        return {"id": i, "program": program, "title": title, "status": "open", "kind": "step", "how": how}

    def test_saturated_facts_demote_text_statistics_and_the_generator_test(self):
        top, why = self.run_rules(self.saturated_record(),
                                  [self.step("P-L2-001", "L2"), self.step("G-every-fact", "G", how="rule"),
                                   self.step("G-enciphered-language", "G", how="rule"), self.step("P-L4-001", "L4")])
        self.assertEqual(top[:2], ["G-enciphered-language", "P-L4-001"])
        self.assertEqual(top[-1], "P-L2-001")
        self.assertIn("saturated", why["P-L2-001"])
        self.assertIn("saturated", why["G-every-fact"])

    def test_an_enciphered_language_test_is_not_a_refutation_and_not_the_best_generator(self):
        enc = gen("R-009", {f"F-{n:03d}": True for n in range(1, 13)}, hypothesis="enciphered_language")
        top, why = self.run_rules(self.saturated_record([enc]), [self.step("R-attack-F-012", "R", how="rule")])
        self.assertIn("no attack has reproduced", why["R-attack-F-012"])
        with patch.object(registry, "read", side_effect=lambda type=None: [i for i in self.saturated_record([enc]) if type is None or i["type"] == type]):
            self.assertEqual(redteam.best_generator()["id"], "R-001")

    def test_top_picks_are_spread_over_the_fronts(self):
        top, _ = self.run_rules(self.saturated_record(), [self.step(f"P-L4-{n:03d}", "L4") for n in range(1, 6)]
                                + [self.step("L3-first-latin-table-cipher", "L3", how="rule"),
                                   self.step("L3-first-latin-substitution", "L3", how="rule")])
        self.assertEqual(sum(t.startswith("P-L4-") for t in top), steps.TOP_PER_PROGRAM)
        self.assertIn("L3-first-latin-table-cipher", top)
        self.assertNotIn("L3-first-latin-substitution", top, "word-for-word letter cells stay last")
