import os, unittest
from unittest.mock import patch
from vs import path, facts, ivtff, registry

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))

PASSING = {"statistic": {"hapax_share": True}, "compare": [{"op": ">", "value": 0.0}]}
FAILING = {"statistic": {"hapax_share": True}, "compare": [{"op": ">", "value": 1.0}]}
BROKEN = {"statistic": {"not_a_statistic": True}, "compare": [{"op": ">", "value": 0.0}]}


def fixture_pages():
    """More than MIN_TOKENS (30) selected tokens, so the DSL statistics are defined on them."""
    out = []
    for n in range(12):
        ws = ["aa", "bb"] + [f"w{n}{i}" for i in range(4)]
        pg = ivtff.Page(f"p{n:03d}", n, {"I": "B", "L": None, "H": None})
        pg.lines.append(ivtff.Line(f"p{n:03d}.1", f"p{n:03d}", 1, "P", "0", ws, True, True))
        out.append(pg)
    return out, out


def fixture_facts():
    """One fact of each registered shape: the legacy metric, a DSL fact that holds, one that
    fails, one whose spec is invalid, one carrying both schemas, and one carrying neither."""
    return [
        {"id": "F-900", "title": "legacy", "statement": "s",
         "detail": {"metric": "hapax_share", "params": {"lo": 0.0, "hi": 1.0}}},
        {"id": "F-901", "title": "dsl holds", "statement": "s", "detail": {"spec": PASSING}},
        {"id": "F-902", "title": "dsl fails", "statement": "s", "detail": {"spec": FAILING}},
        {"id": "F-903", "title": "dsl refused", "statement": "s", "detail": {"spec": BROKEN}},
        {"id": "F-904", "title": "both schemas", "statement": "s",
         "detail": {"spec": FAILING, "metric": "hapax_share", "params": {"lo": 0.0, "hi": 1.0}}},
        {"id": "F-905", "title": "neither", "statement": "s", "detail": {}},
    ]


class FactsBatteryTest(unittest.TestCase):
    def setUp(self):
        self.tr, self.ev = fixture_pages()
        patcher = patch.object(registry, "read", return_value=fixture_facts())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_dispatchable_fact_is_evaluated(self):
        r = facts.run(self.tr, self.ev)
        self.assertEqual(sorted(r), ["F-900", "F-901", "F-902", "F-903", "F-904"])
        self.assertEqual(facts.undispatchable(), ["F-905"], "a record with no spec and no metric is named, not hidden")

    def test_legacy_metric_still_uses_metrics(self):
        r = facts.run(self.tr, self.ev)["F-900"]
        self.assertTrue(r["pass"])
        self.assertIn("types", r["detail"], "the legacy evaluator's own detail is returned")

    def test_dsl_facts_are_evaluated_including_failing_and_refused(self):
        r = facts.run(self.tr, self.ev)
        self.assertTrue(r["F-901"]["pass"])
        self.assertFalse(r["F-902"]["pass"])
        self.assertNotIn("refused", r["F-902"]["detail"], "a failing DSL fact reads as refuted, not as skipped")
        self.assertFalse(r["F-903"]["pass"])
        self.assertIn("refused", r["F-903"]["detail"])

    def test_spec_wins_when_a_record_carries_both(self):
        r = facts.run(self.tr, self.ev)["F-904"]
        self.assertFalse(r["pass"], "the spec (which fails) is evaluated, not the metric (which would pass)")

    def test_order_and_requested_ids(self):
        self.assertEqual(list(facts.run(self.tr, self.ev)), ["F-900", "F-901", "F-902", "F-903", "F-904"],
                         "the battery keeps registry order")
        self.assertEqual(list(facts.run(self.tr, self.ev, ids=["F-902"])), ["F-902"])

    def test_records_off_the_record_are_left_out(self):
        with patch.object(registry, "read", return_value=fixture_facts()[:1]):
            self.assertEqual(list(facts.run(self.tr, self.ev)), ["F-900"])

    def test_empty_registry_is_a_fresh_board(self):
        with patch.object(registry, "read", return_value=[]):
            self.assertEqual(facts.run(self.tr, self.ev), {})
            self.assertEqual(facts.undispatchable(), [])


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class FactsOnRecordTest(unittest.TestCase):
    def test_the_battery_covers_every_fact_on_record(self):
        self.assertEqual([f["id"] for f in facts.battery()], [i["id"] for i in registry.read("fact")])

    def test_a_registered_spec_fact_runs_on_practice_pages(self):
        from vs import corpus
        tr, ev = corpus.split_pages("practice")
        ids = [f["id"] for f in facts.battery() if "spec" in f]
        self.assertTrue(ids)
        r = facts.run(tr, ev, ids=ids[:1])
        self.assertEqual(list(r), ids[:1])
        self.assertNotIn("refused", r[ids[0]]["detail"], "a fact established on the record is not refused on public pages")
