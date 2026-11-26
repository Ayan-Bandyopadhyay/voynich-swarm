import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from vs import experiment


class PictureExperimentTest(unittest.TestCase):
    def test_valid_picture_has_an_advisory_result(self):
        manifest = {"step": "PIC-f1r", "handle": "observer", "kind": "picture"}
        picture = {
            "folio": "f1r",
            "canvas": "https://example.invalid/canvas/f1r",
            "blind": True,
            "objects": [{"id": "plant-1", "kind": "plant", "features": {}, "label": None}],
        }
        with TemporaryDirectory() as root:
            directory = Path(root) / "experiments" / "PIC-f1r" / "observer"
            directory.mkdir(parents=True)
            for name, data in (("experiment.json", manifest), ("picture.json", picture)):
                (directory / name).write_text(json.dumps(data), encoding="utf-8")

            output = StringIO()
            with redirect_stdout(output):
                status = experiment.main(directory, split="practice")

        self.assertEqual(status, 0)
        self.assertIn("picture: shape OK.", output.getvalue())
