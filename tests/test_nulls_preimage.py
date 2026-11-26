import math
import unittest
from unittest.mock import call, patch

from vs import ivtff, judge


def page(page_id, *lines):
    return ivtff.Page(page_id, 0, {}, [
        ivtff.Line(f"{page_id}.{n}", page_id, n, "P", "0", words, False, False)
        for n, words in enumerate(lines, 1)
    ])


class NullsPreimageTest(unittest.TestCase):
    def test_description_length_charges_each_page_for_dropped_word_positions(self):
        key = {"map": {"o": "a", "d": ""}, "null_words": ["ok"], "null_glyphs": ["d"]}
        sub = {"family": "nulls", "key": key, "target": {"language": "latin"}}
        dec = judge.Decoder(sub, "latin")
        train = [page("train", ["o", "ok", "do"], ["d"], [])]
        evaluation = [page("first", ["ok", "o", "ok"], ["d"], []),
                      page("second", ["do", "d"], [])]
        base = judge.Baseline(train, dec.seg)

        with (patch.object(judge.refcorpus, "train_text", return_value=["a"]),
              patch.object(judge.lm.KN, "bits", return_value=0.0),
              patch.object(judge, "preimage_bits", return_value=0.0) as preimage):
            _, _, bits, decoded, detail = judge.description_length(dec, base, train, evaluation, "latin")

        q = 2.5 / 7  # Two drops, two survivors, two nonempty raw lines in training.
        drop, stop = -math.log2(q), -math.log2(1 - q)
        position_first, position_second = 3 * drop + 3 * stop, drop + 2 * stop
        physical = -math.log2(1 - 0.5 / 3)
        identity_first = physical - math.log2(1 / 4) - math.log2(2 / 5) - math.log2(1 / 6)
        identity_second = physical - math.log2(2 / 7)
        self.assertEqual(decoded, {"first": [["a"], []], "second": [["a"]]})
        self.assertAlmostEqual(bits["first"], position_first + identity_first)
        self.assertAlmostEqual(bits["second"], position_second + identity_second)
        self.assertEqual(detail["null_position_bits"], round(position_first + position_second, 1))
        self.assertEqual(detail["choice_code"], "unit_preimage")
        pool = {"o": 2, "d": 1, "<stop>": 2}
        self.assertEqual(preimage.call_args_list, [call(["o"], "a", {"o": "a"}, pool),
                                                   call(["d", "o"], "a", {"o": "a"}, pool)])

    def test_unseen_survivor_glyph_and_null_word_use_literal_codes(self):
        key = {"map": {"o": "a", "k": "a"}, "null_words": ["d"], "null_glyphs": []}
        sub = {"family": "nulls", "key": key, "target": {"language": "latin"}}
        dec = judge.Decoder(sub, "latin")
        train = [page("train", ["o", "o"])]
        evaluation = [page("first", ["k", "d"])]
        base = judge.Baseline(train, dec.seg)

        with (patch.object(judge.refcorpus, "train_text", return_value=["a"]),
              patch.object(judge.lm.KN, "bits", return_value=0.0),
              patch.object(judge, "preimage_bits") as preimage):
            _, _, bits, decoded, detail = judge.description_length(dec, base, train, evaluation, "latin")

        q = 0.5 / 4
        position = -math.log2(q) - 2 * math.log2(1 - q)
        identity = -math.log2(0.5 / 3) + 2 * 11  # One byte plus a three-bit length per literal.
        self.assertEqual(decoded, {"first": [["a"]]})
        self.assertAlmostEqual(bits["first"], position + identity)
        self.assertEqual(detail["choice_code"], "unit_preimage")
        preimage.assert_not_called()
