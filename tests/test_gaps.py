import unittest

from vs import gaps
from vs.ivtff import Line, Page


def page(pid, lines):
    result = Page(pid, 0, {})
    for i, (unit, words, start, end) in enumerate(lines, 1):
        result.lines.append(Line(f"{pid}.{i}", pid, i, unit, "0", words, start, end))
    return result


class ParagraphGapsTest(unittest.TestCase):
    def test_both_editions_must_admit_the_entire_line(self):
        first = page("a", [("P", ["o", "ocho"], False, False),
                           ("P", ["or"], False, False),
                           ("P", ["o", "ocho"], False, False)])
        second = page("a", [("P", ["o", "ocho"], False, False),
                            ("P", ["or", "o?"], False, False),
                            ("P", ["o", "ocho"], False, False)])
        retained = gaps.eligible_line_ids([first]) & gaps.eligible_line_ids([second])
        self.assertEqual(retained, {"a.1", "a.3"})
        for folio in (first, second):
            runs = gaps.paragraph_runs([folio], retained)
            self.assertEqual(runs, [["o", "ocho"], ["o", "ocho"]])
            hits = [gaps.hit_positions(run, "o") for run in runs]
            self.assertEqual(gaps.gap_curve(hits * 20, (1,)), {1: (None, 0)})

    def test_layout_ignores_labels_and_respects_paragraph_and_page_boundaries(self):
        first = page("a", [("P", ["o"], False, False), ("L", ["or"], False, False),
                           ("P", ["ocho"], False, False), ("P", ["y"], True, True),
                           ("P", ["or"], False, False), ("P", [], False, False),
                           ("P", ["dy"], False, False)])
        second = page("b", [("P", ["ok"], False, False)])
        retained = gaps.eligible_line_ids([first, second])
        self.assertEqual(gaps.paragraph_runs([first, second], retained),
                         [["o", "ocho"], ["y"], ["or"], ["dy"], ["ok"]])

    def test_centering_uses_all_gaps_and_requires_enough_pairs(self):
        hits = gaps.hit_positions(["o", "ocho", "o"], "o")
        self.assertEqual(hits, [0, 2, 5, 7])
        self.assertEqual(gaps.gap_curve([hits] * 12, (1, 2)), {1: (None, 24), 2: (None, 0)})
        value, count = gaps.gap_curve([hits] * 15, (1,))[1]
        self.assertEqual(count, 30)
        self.assertAlmostEqual(value, -4 / 5)

    def test_invariant_word_order_gives_equal_lag_mean_and_p_one(self):
        word = "o" + "".join("a" * (gap - 1) + "o" for gap in range(1, 8))
        result = gaps.word_order_test([[word]] * 25, "o", permutations=19)
        self.assertEqual(result["lags"], [1, 2, 3, 4, 5])
        self.assertAlmostEqual(result["observed"], -554 / 3705)
        self.assertEqual(result["observed"], result["null_mean"])
        self.assertEqual(result["p"], 1)
