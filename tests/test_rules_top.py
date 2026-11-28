"""The scripted lead reads the record (synthetic records only, no manuscript data)."""
import unittest
from unittest.mock import patch

from vs import registry, steps


def item(i, type_, verdict, step=None, **kw):
    return {"id": i, "type": type_, "verdict": verdict, "title": kw.pop("title", i),
            "provenance": {"added_by": "someone", "step": step}, **kw}


def step(i, title="", program="X", how="agent"):
    return {"id": i, "title": title, "program": program, "kind": "step", "status": "open", "how": how}


class RulesTopTest(unittest.TestCase):
    def run_rules(self, records, open_steps):
        def read(kind=None):
            return [r for r in records if kind is None or r["type"] == kind]
        why = {}
        with patch.object(registry, "read", side_effect=read):
            return steps.rules_top(open_steps, why), why

    FACTS = [item("F-001", "fact", "ESTABLISHED"), item("F-002", "fact", "ESTABLISHED")]

    def test_generator_step_names_the_best_result_and_its_misses(self):
        gen = item("R-001", "attack", "1/2", detail={"per_fact": {"F-001": True, "F-002": False}})
        top, why = self.run_rules(self.FACTS + [gen, item("R-002", "attack", "SUCCEEDED", target="F-002")],
                                  [step("G-every-fact", how="rule")])
        self.assertEqual(top, ["G-every-fact"])
        self.assertIn("R-001, 1 of 2", why["G-every-fact"])
        self.assertIn("misses F-002", why["G-every-fact"])

    def test_generator_step_drops_once_one_procedure_reproduces_every_fact(self):
        gen = item("R-001", "attack", "2/2", detail={"per_fact": {"F-001": True, "F-002": True}})
        top, _ = self.run_rules(self.FACTS + [gen], [step("G-every-fact", how="rule"), step("P-X-001")])
        self.assertEqual(top, ["P-X-001", "G-every-fact"])

    def test_generator_variants_rank_below_the_shared_test(self):
        top, _ = self.run_rules(self.FACTS, [step("P-G-001", "Generator test, second version"),
                                             step("G-every-fact", how="rule"), step("P-L4-001", program="L4")])
        self.assertEqual(top, ["G-every-fact", "P-L4-001", "P-G-001"])

    def test_unreproduced_fact_comes_first(self):
        top, why = self.run_rules(self.FACTS, [step("G-every-fact", how="rule"), step("R-attack-F-002", how="rule")])
        self.assertEqual(top[0], "R-attack-F-002")
        self.assertIn("no attack", why["R-attack-F-002"])

    def test_picture_steps_wait_while_annotations_do_not_agree(self):
        pics = [item(f"V-{n}", "picture", "DISAGREE") for n in range(10)] + [item("V-99", "picture", "AGREED")]
        top, why = self.run_rules(pics, [step("PIC-f1r"), step("P-X-001")])
        self.assertEqual(top, ["P-X-001", "PIC-f1r"])
        self.assertIn("1 AGREED of 11", why["PIC-f1r"])
        pics += [item(f"V-a{n}", "picture", "AGREED") for n in range(5)]
        top, _ = self.run_rules(pics, [step("PIC-f1r"), step("P-X-001")])
        self.assertEqual(top, ["PIC-f1r", "P-X-001"])

    def test_untouched_steps_first_and_well_worked_steps_drop(self):
        worked = [item(f"S-{n}", "step", "PROPOSED", step="P-X-001") for n in range(3)]
        top, why = self.run_rules(worked + [item("S-9", "step", "PROPOSED", step="P-X-002")],
                                  [step("P-X-001", program="A"), step("P-X-002", program="B"), step("P-X-003", program="C")])
        self.assertEqual(top, ["P-X-003", "P-X-002", "P-X-001"])
        self.assertIn("already 3 submissions", why["P-X-001"])

    def test_word_for_word_letter_cells_are_never_top(self):
        top, _ = self.run_rules([], [step("L3-first-latin-substitution", how="rule"),
                                     step("L3-first-latin-verbose", how="rule")])
        self.assertEqual(top, ["L3-first-latin-verbose"], "only cells that are not letter-for-letter can be a top pick")


if __name__ == "__main__":
    unittest.main()
