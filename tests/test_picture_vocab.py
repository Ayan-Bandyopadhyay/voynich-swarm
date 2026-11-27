import json, os, tempfile, unittest
from vs import pictures, experiment


def fig(i, label=None, **features):
    return {"id": i, "kind": "human_figure", "label": label, "features": features}


class NormalizeTest(unittest.TestCase):
    def test_vocabulary_values_are_taken_as_written(self):
        self.assertEqual(pictures.normalize({"colour": "red", "ring": "outer"}), {"colour": "red", "ring": "outer"})

    def test_free_wordings_on_the_record_map_onto_the_vocabulary(self):
        self.assertEqual(pictures.normalize({"posture": "half figure standing in a tub"}), {"posture": "in_container"})
        self.assertEqual(pictures.normalize({"posture": "upper body rising from an upright tub"}), {"posture": "in_container"})
        self.assertEqual(pictures.normalize({"star": "attached"}), {"holds": "star"})
        self.assertEqual(pictures.normalize({"star": "true"}), {"holds": "star"})
        self.assertEqual(pictures.normalize({"colour": "ink only"}), {"colour": "none"})
        self.assertEqual(pictures.normalize({"colour": "ochre"}), {"colour": "yellow"})
        self.assertEqual(pictures.normalize({"headdress": "no"}), {"headwear": "none"})
        self.assertEqual(pictures.normalize({"container": "none (no tub or barrel)"}), {"container": "none"})

    def test_unplaceable_and_unclear_values_are_not_compared(self):
        self.assertEqual(pictures.normalize({"points": "7 or 8", "sex": "unclear", "shape": "disc with crescent"}), {})


class AgreementTest(unittest.TestCase):
    def test_same_scene_in_different_words_agrees(self):
        a = {"objects": [fig("a", "f1.1", posture="half figure standing in a tub", star="yes", colour="uncoloured")]}
        b = {"objects": [fig("b", "f1.1", posture="upper body emerging from a tub", star="attached", colour="ink only")]}
        self.assertEqual(pictures.agreement(a, b), 1.0)

    def test_a_real_difference_still_disagrees(self):
        a = {"objects": [fig("a", "f1.1", container="tub")]}
        b = {"objects": [fig("b", "f1.1", container="none")]}
        self.assertEqual(pictures.agreement(a, b), 0.5)   # kind agrees, container does not

    def test_unpaired_objects_count_against(self):
        a = {"objects": [fig("a", "f1.1", colour="red"), fig("c", "f1.2", colour="red")]}
        b = {"objects": [fig("b", "f1.1", colour="red")]}
        self.assertAlmostEqual(pictures.agreement(a, b), 2 / 3)

    def test_kind_and_ring_used_for_pairing_are_not_counted_as_agreement(self):
        a = {"objects": [fig("a", ring="outer")]}
        b = {"objects": [fig("b", ring="outer")]}
        self.assertIsNone(pictures.agreement(a, b))

    def test_ring_figures_pair_by_clock_angle_not_list_order(self):
        a = {"objects": [fig("a1", ring="outer", angle_deg_clockwise_from_top=0, container="tub"),
                         fig("a2", ring="outer", angle_deg_clockwise_from_top=180, container="none")]}
        b = {"objects": [fig("b2", ring="outer", angle_deg_clockwise_from_top=185, container="none"),
                         fig("b1", ring="outer", angle_deg_clockwise_from_top=355, container="tub")]}
        self.assertEqual(pictures.agreement(a, b), 1.0)

    def test_different_labels_are_never_paired(self):
        a = {"objects": [fig("a", "f1.1", colour="red")]}
        b = {"objects": [fig("b", "f1.2", colour="red")]}
        self.assertEqual(pictures.agreement(a, b), 0.0)


class SubmissionTest(unittest.TestCase):
    def check(self, objects):
        with tempfile.TemporaryDirectory() as d:
            e = os.path.join(d, "experiments", "PIC-f1r", "someone")
            os.makedirs(e)
            with open(os.path.join(e, "experiment.json"), "w") as f:
                json.dump({"step": "PIC-f1r", "handle": "someone", "kind": "picture", "summary": "s"}, f)
            with open(os.path.join(e, "picture.json"), "w") as f:
                json.dump({"folio": "f1r", "canvas": "c", "blind": True, "objects": objects}, f)
            return [x for x in experiment.validate(e)[1] if "feature" in x]

    def test_new_annotations_use_the_vocabulary(self):
        self.assertEqual(self.check([fig("a", colour="red", shape="anything at all")]), [])
        self.assertTrue(self.check([fig("a", colour="ink only, red dots")]))
        self.assertTrue(self.check([fig("a", headdress="none")]), "an alias is refused on new annotations")
        self.assertEqual(self.check([fig("a", colour="unclear")]), [])


if __name__ == "__main__":
    unittest.main()
