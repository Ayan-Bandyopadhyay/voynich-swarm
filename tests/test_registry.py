"""Duplicate detection for anchor proposals and second looks (no manuscript data)."""
import copy
import os
import tempfile
import unittest
from unittest.mock import patch

from vs import registry


class AnchorDuplicateTest(unittest.TestCase):
    def look(self, target="N-002", assessment="agree", author="Pavlenko77"):
        return {
            "id": "N-009", "type": "anchor", "page": None,
            "title": "Second look", "verdict": "DRAFT",
            "detail": {"of": target, "assessment": assessment},
            "provenance": {"added_by": author},
        }

    def test_different_targets_are_not_duplicates(self):
        with patch.object(registry, "read", return_value=[self.look()]):
            self.assertIsNone(registry.duplicate_of(self.look("N-005")))

    def test_resubmission_is_duplicate_despite_changed_prose(self):
        retry = self.look()
        retry.update(id="N-010", title="A revised title", statement="More detail")
        with patch.object(registry, "read", return_value=[self.look()]):
            self.assertEqual(registry.duplicate_of(retry), "N-009")

    def test_different_assessments_are_distinct(self):
        self.assertNotEqual(registry.fingerprint(self.look()),
                            registry.fingerprint(self.look(assessment="dissent")))

    def test_independent_reviewers_are_distinct(self):
        self.assertNotEqual(registry.fingerprint(self.look()),
                            registry.fingerprint(self.look(author="another-reviewer")))

    def test_legacy_title_matches_structured_second_look(self):
        legacy = self.look()
        legacy["detail"] = {}
        legacy["title"] = "Second look at N-002: AGREE"
        self.assertEqual(registry.fingerprint(legacy),
                         registry.fingerprint(self.look()))

    def test_proposal_fingerprint_is_unchanged(self):
        proposal = self.look()
        proposal.update(page="f70v2", detail={"voynich": "otolal"})
        self.assertEqual(registry.fingerprint(proposal),
                         ("anchor", "f70v2", '"otolal"', "Pavlenko77"))
        self.assertNotEqual(registry.fingerprint(proposal),
                            registry.fingerprint(self.look()))

    def test_record_accepts_new_target_but_rejects_retry(self):
        with tempfile.TemporaryDirectory() as root, \
                patch.object(registry, "FN", os.path.join(root, "items.jsonl")), \
                patch.object(registry, "WITHDRAWN", os.path.join(root, "withdrawn.jsonl")):
            registry.add(self.look())
            second = self.look("N-005")
            second["id"] = "N-010"
            registry.add(second)
            retry = copy.deepcopy(second)
            retry["id"] = "N-011"
            with self.assertRaisesRegex(SystemExit, "DUPLICATE.*N-010"):
                registry.add(retry)
            self.assertEqual(len(registry.read("anchor")), 2)
