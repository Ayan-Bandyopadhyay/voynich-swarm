import math
import random
import unittest
from collections import Counter
from vs import dsl
from tests.test_dsl import page


class RepeatedPairTypesTest(unittest.TestCase):
    def spec(self, null=False):
        return {'select': {'unit': ['P'], 'certain': True}, 'statistic': {'repeated_pair_types': True},
                'compare': [{'null': 'shuffle_within_line', 'perms': 99, 'p': .05} if null else {'op': '>=', 'value': 0}]}

    def test_distinct_types_not_occurrences_and_direction(self):
        # aa->bb occurs 39 times, bb->aa 38 and bb->cc once.
        p = page('p', [['aa', 'bb'] * 39 + ['cc']])
        self.assertAlmostEqual(dsl.evaluate(self.spec(), [p])['value'], 2 / 3, places=6)

    def test_gaps_are_not_bridged_or_moved(self):
        p = page('p', [['aa', 'bb', '?', 'cc', 'dd']] * 20 + [('L', ['xx', 'yy'])])
        ts = dsl.tokens([p]); sh = dsl._shuffled(ts, 'shuffle_within_line', random.Random(4), 'repeated_pair_types')
        for line in dsl.lines_of(sh)[:20]:
            self.assertEqual(line[2]['w'], '?')
            self.assertEqual(Counter(t['w'] for t in line[:2]), Counter(['aa', 'bb']))
            self.assertEqual(Counter(t['w'] for t in line[3:]), Counter(['cc', 'dd']))
        self.assertEqual([t['w'] for t in dsl.lines_of(sh)[-1]], ['xx', 'yy'])
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(self.spec(), [page('p', [['aa', '?', 'bb']] * 40)])

    def test_schema_and_null_can_detect_planted_order(self):
        for sel in ({}, {'unit':['P'], 'position':'line_final'}, {'unit':['P'], 'certain':False}, {'unit':['P'], 'language':'A'}):
            s=self.spec(); s['select']=sel
            with self.assertRaises(dsl.SpecError): dsl.check(s)
        s=self.spec(True); s['compare'][0]['null']='shuffle_within_page'
        with self.assertRaises(dsl.SpecError): dsl.check(s)
        # Repeat ordered motifs across lines; shuffle keeps each line's words.
        p=page('p', [[f'a{i}', f'b{i}', f'c{i}', f'd{i}'] for i in range(50)] * 3)
        self.assertTrue(dsl.evaluate(self.spec(True), [p])['pass'])

if __name__ == '__main__': unittest.main()
