import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vs import controls, judge, refcorpus, score, search, season


class CorpusNoiseTest(unittest.TestCase):
    def test_clean_success_cannot_open_the_new_cell(self):
        raw = b"example"
        submission = {"url": "https://example.org/words.txt", "title": "Fixture", "period": "test",
                      "license": "cc0", "language": "fixture", "sha256": hashlib.sha256(raw).hexdigest()}

        def make(lang, kind, noise):
            return [], [], noise

        def evaluate(key, train, evaluation, split):
            ok = key == 0
            return {"a_compresses": {"pass": ok, "savings": 0.1}, "b_reads": {"pass": True},
                    "kill_tests": {"pass": True, "decoys": {}}}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("pins", "results/heldout", "data/raw"):
                (root / folder).mkdir(parents=True)
            (root / "pins/sources.json").write_text('{"reference_corpora":[]}')
            results = root / "results/heldout/controls.json"
            results.write_text('[{"language":"existing","family":"verbose","search_cracks_control":true}]')
            with (patch.object(season, "FAMILIES", ["substitution", "verbose", "nomenclator"]),
                  patch.object(score, "path", root.joinpath),
                  patch.object(score, "_public_fetch", return_value=raw),
                  patch.object(score.registry, "next_id", return_value="C-001"),
                  patch.object(refcorpus, "blocks", return_value=["x" * score.MIN_CHARS]),
                  patch.object(controls, "make", side_effect=make) as generated,
                  patch.object(search, "search_cell", side_effect=[0, 1] * 3),
                  patch.object(judge, "evaluate", side_effect=evaluate)):
                item, kind = score._score_corpus(submission, {"handle": "fleet-astra"})
            self.assertEqual(kind, "corpus_added")
            self.assertEqual([call.kwargs["noise"] for call in generated.call_args_list],
                             [0.0, controls.NOISE] * 3)
            old, *rows = json.loads(results.read_text())
            self.assertEqual(old["language"], "existing")
            self.assertEqual([r["family"] for r in rows], ["substitution", "verbose", "nomenclator"])
            for row in rows:
                self.assertTrue(row["search_cracks_control_clean"])
                self.assertFalse(row["search_cracks_control"])
                self.assertEqual(row["noise"], controls.NOISE)
                self.assertFalse(item["detail"]["power"][row["family"]]["search_cracks_control"])
