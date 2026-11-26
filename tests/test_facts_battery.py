"""The advisory battery must not silently skip registered DSL facts."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vs import corpus, dsl, facts, fetch, registry
from vs import __main__ as cli
from vs.ivtff import Line, Page


def item(name, detail):
    return {"id": name, "type": "fact", "title": name, "statement": "fixture", "detail": detail}


def mean_length(threshold):
    return {"statistic": {"mean_length": True}, "compare": [{"op": ">=", "value": threshold}]}


class FactBatteryTest(unittest.TestCase):
    def setUp(self):
        page = Page("fixture", 0, {"I": "H", "L": "A", "H": "1"})
        for i in range(40):
            page.lines.append(Line(f"fixture.{i}", "fixture", i, "P", "0", ["ol", "daiin"], i == 0, False))
        self.pages = [page]
        self.legacy = item("legacy", {"metric": "hapax_share", "params": {"lo": 0, "hi": 0}})
        self.passing = item("passing", {"spec": mean_length(3)})
        self.failing = item("failing", {"spec": mean_length(4)})

    def run_rows(self, rows, ids=None):
        with patch.object(registry, "read", return_value=rows) as read:
            result = facts.run([], self.pages, ids)
        read.assert_called_once_with("fact")
        return result

    def test_legacy_result_is_unchanged(self):
        expected = facts.METRICS["hapax_share"]([], self.pages, lo=0, hi=0)
        self.assertEqual(self.run_rows([self.legacy]), {"legacy": expected})

    def test_dsl_pass_and_failure_are_both_evaluated(self):
        result = self.run_rows([self.passing, self.failing])
        for row in (self.passing, self.failing):
            self.assertEqual(result[row["id"]], dsl.evaluate(row["detail"]["spec"], self.pages))
        self.assertTrue(result["passing"]["pass"])
        self.assertFalse(result["failing"]["pass"])

    def test_mixed_records_preserve_order_and_coverage(self):
        self.assertEqual(list(self.run_rows([self.legacy, self.passing, self.failing])),
                         ["legacy", "passing", "failing"])

    def test_requested_ids_select_both_schemas(self):
        result = self.run_rows([self.legacy, self.passing, self.failing], ["failing", "legacy"])
        self.assertEqual(list(result), ["legacy", "failing"])

    def test_empty_id_list_keeps_existing_all_records_behavior(self):
        self.assertEqual(list(self.run_rows([self.legacy, self.passing], [])), ["legacy", "passing"])

    def test_spec_takes_precedence_over_metric(self):
        row = item("both", {"spec": mean_length(4), "metric": "not_a_metric", "params": {}})
        self.assertFalse(self.run_rows([row])["both"]["pass"])

    def test_invalid_selected_spec_raises(self):
        row = item("broken", {"spec": {"statistic": {"mean_length": True}, "compare": []}})
        with self.assertRaises(dsl.SpecError):
            self.run_rows([row])

    def test_filtered_out_spec_is_not_evaluated(self):
        broken = item("broken", {"spec": {}})
        self.assertEqual(list(self.run_rows([broken, self.passing], ["passing"])), ["passing"])

    def test_unsupported_record_cannot_look_like_an_empty_battery(self):
        with self.assertRaisesRegex(ValueError, "Registered fact broken"):
            self.run_rows([item("broken", {})])

    def test_empty_registry_returns_empty_mapping(self):
        self.assertEqual(self.run_rows([]), {})

    def test_registry_withdrawal_overlay_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            records = Path(tmp) / "items.jsonl"
            withdrawn = Path(tmp) / "withdrawn.jsonl"
            records.write_text("\n".join(json.dumps(row) for row in (self.passing, self.failing)) + "\n",
                               encoding="utf-8")
            withdrawn.write_text(json.dumps({"id": "failing", "reason": "fixture withdrawal"}) + "\n",
                                 encoding="utf-8")
            with patch.object(registry, "FN", str(records)), patch.object(registry, "WITHDRAWN", str(withdrawn)):
                self.assertEqual(list(facts.run([], self.pages)), ["passing"])

    def cli_output(self, rows):
        output = io.StringIO()
        with patch.object(registry, "read", return_value=rows), patch.object(fetch, "verify"), \
             patch.object(corpus, "split_pages", return_value=([], self.pages)) as split, \
             contextlib.redirect_stdout(output):
            cli.main(["facts"])
        split.assert_called_once_with("practice")
        return output.getvalue()

    def test_cli_reports_each_result_including_dsl_failure(self):
        lines = self.cli_output([self.legacy, self.passing, self.failing]).splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("legacy ESTABLISHED"))
        self.assertTrue(lines[1].startswith("passing ESTABLISHED"))
        self.assertTrue(lines[2].startswith("failing REFUTED"))

    def test_empty_cli_has_an_explicit_diagnostic(self):
        self.assertEqual(self.cli_output([]), "No registered facts.\n")


if __name__ == "__main__":
    unittest.main()
