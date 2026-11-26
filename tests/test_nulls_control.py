import unittest
from unittest.mock import patch

from vs import controls, ivtff


def ordered_words(generated):
    training, evaluation, _ = generated
    return [word for page in sorted(training + evaluation, key=lambda page: page.order)
            for line in page.lines for word in line.words]


@patch.object(controls.refcorpus, "control_text", return_value=["abc abbc cbab ab cab " * 120])
@patch.object(controls.refcorpus, "alphabet", return_value=list("abc"))
class NullsControlTest(unittest.TestCase):
    def test_clean_nulls_preserve_ordinary_spelling_and_have_no_clean_collisions(self, _alphabet, _text):
        plain_words = set("abc abbc cbab ab cab".split())
        unpadded = controls.make("fixture", "homophonic", words_per_line=7)
        ordinary = ordered_words(unpadded)
        for rate in (0, 0.10, 0.20, 0.30):
            with self.subTest(rate=rate):
                padded = controls.make("fixture", "nulls", words_per_line=7, null_rate=rate)
                training, evaluation, fixture = padded
                key = fixture["key"]
                words = ordered_words(padded)
                self.assertEqual(fixture["family"], "nulls")
                self.assertEqual(fixture["segmentation"], "eva-basic")
                self.assertEqual(key["map"], unpadded[2]["key"]["map"])
                self.assertEqual(key["null_glyphs"], [])
                stock = set(key["null_words"])
                self.assertEqual(len(stock), 6 if rate else 0)
                self.assertEqual(len(words) - len(ordinary), round(len(ordinary) * rate / (1 - rate)))
                self.assertEqual([word for word in words if word not in stock], ordinary)
                self.assertTrue(all(page.order % 7 != 3 for page in training))
                self.assertTrue(all(page.order % 7 == 3 for page in evaluation))
                self.assertTrue(all(len(line.words) <= 7 for page in training + evaluation for line in page.lines))
                for word in stock:
                    units = ivtff.segment(word)
                    self.assertLessEqual(3, len(units))
                    self.assertLessEqual(len(units), 6)
                    self.assertNotIn("".join(key["map"][unit] for unit in units), plain_words)

    def test_noise_can_hide_clean_nulls_and_does_not_change_zero_padding(self, _alphabet, _text):
        unpadded = controls.make("fixture", "homophonic", noise=controls.NOISE)
        no_nulls = controls.make("fixture", "nulls", noise=controls.NOISE, null_rate=0)
        self.assertEqual(unpadded[:2], no_nulls[:2])

        # With 100% corruption every glyph of a placed null changes. The planted
        # key still contains the original exact shapes, and the word count is intact.
        padded = controls.make("fixture", "nulls", noise=1.0)
        words = ordered_words(padded)
        stock = set(padded[2]["key"]["null_words"])
        self.assertEqual(len(stock), 6)
        self.assertEqual(len(words), 750)
        # Occasionally a corrupted word can coincide with a different stock word.
        self.assertLess(sum(word in stock for word in words), len(words) - 600)

    def test_null_rate_is_a_share_below_one(self, _alphabet, _text):
        for rate in (-0.01, 1):
            with self.subTest(rate=rate), self.assertRaisesRegex(ValueError, "null_rate"):
                controls.make("fixture", "nulls", null_rate=rate)
