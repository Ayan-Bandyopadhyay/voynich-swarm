"""Training-derived boundary classes must stay fixed on evaluation and nulls."""
import random
import unittest
from vs import dsl
from vs.ivtff import Page, Line


def page(pid, lines):
    p = Page(pid, 0, {'I': 'H', 'L': 'A', 'H': '1'})
    p.lines = [Line(f'{pid}.{i}', pid, i, 'P', '0', ws, False, False)
               for i, ws in enumerate(lines, 1)]
    return p


SPEC = {'select': {'unit': ['P'], 'certain': True},
        'statistic': {'boundary_class_rate': True},
        'compare': [{'op': '>', 'value': .5}]}


class BoundaryClassesTest(unittest.TestCase):
    def setUp(self):
        self.train = [page('train', [['qa', 'ay'] for _ in range(100)])]

    def test_separate_training_and_exact_rate(self):
        ev = [page('eval', [['ay', 'qa'] for _ in range(40)])]
        r = dsl.evaluate(SPEC, ev, self.train)
        self.assertEqual(r['value'], 1.0)
        self.assertEqual(r['detail']['boundary_class_rate']['pairs'], 40)
        self.assertTrue(r['pass'])
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(SPEC, ev)
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(SPEC, ev, ev)

    def test_uncertain_words_and_short_words_are_barriers(self):
        ev = [page('eval', [['ay', '?', 'qa'], ['ay', 'q', 'qa']] + [['ay', 'qa']] * 40)]
        r = dsl.evaluate(SPEC, ev, self.train)
        self.assertEqual(r['value'], 1.0)
        self.assertEqual(r['detail']['boundary_class_rate']['pairs'], 40)
        tokens = dsl.tokens(ev)
        sh = dsl._shuffled(tokens, 'shuffle_within_line', random.Random(2), 'boundary_class_rate')
        self.assertEqual([t['w'] for t in sh[:6]], ['ay', '?', 'qa', 'ay', 'q', 'qa'])

    def test_classes_cannot_be_learned_from_evaluation(self):
        ev = [page('eval', [['qa', 'ay'] for _ in range(40)])]
        result = dsl.evaluate(SPEC, ev, self.train)
        self.assertEqual(result['value'], 0.0)
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(SPEC, ev, [page('tiny', [['qa', 'ay']])])

    def test_null_and_reference_restrictions(self):
        spec = dict(SPEC, compare=[{'null': 'shuffle_within_page', 'perms': 99, 'p': .05}])
        with self.assertRaises(dsl.SpecError):
            dsl.check(spec)
        with self.assertRaises(dsl.SpecError):
            dsl.check(dict(SPEC, compare=[{'reference': 'above_all'}]))


if __name__ == '__main__':
    unittest.main()
