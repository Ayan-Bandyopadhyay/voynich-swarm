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
