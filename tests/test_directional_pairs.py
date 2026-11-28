"""Directional pair ratio: denominator, filtering, gaps, invariance and power."""
import random
import unittest
from vs import dsl
from vs.ivtff import Line, Page


def page(lines):
    p = Page('f1r', 0, {'I':'H', 'L':'A', 'H':'1'})
    p.lines = [Line(f'f1r.{i}', p.id, i, 'P', '0', ws, False, False) for i, ws in enumerate(lines)]
    return p


def toks(lines):
    return dsl.select(dsl.tokens([page(lines)]), None)


def pair_stat(drop=0, window=1, excess=1):
    return {'directional_pairs': {'window':window, 'drop_top':drop, 'excess':excess}}


class DirectionalPairsTest(unittest.TestCase):
    def test_explicit_unordered_denominator_and_strict_excess(self):
        ts = toks([['a','b','c','a','b']])
        c = dsl._directional_pair_counts(ts, pair_stat()['directional_pairs'])
        self.assertEqual(c, {'retained_tokens':5,'removed_types':0,'pair_types':3,'skewed_types':1})
        balanced = toks([['a','b'] for _ in range(12)] + [['b','a'] for _ in range(12)])
        self.assertEqual(dsl._directional_pair_counts(balanced, pair_stat(excess=0)['directional_pairs'])['skewed_types'], 0)

    def test_stop_removal_closes_only_intentional_gaps(self):
        # The frequent x is removed; a-x-b becomes a-b, but an uncertain
        # token and a line break remain barriers rather than new adjacencies.
        ts = toks([['a','x','b','u?','c'], ['d','x','e'], ['x'] * 10])
        c = dsl._directional_pair_counts(ts, pair_stat(drop=1, excess=0)['directional_pairs'])
        self.assertEqual(c['removed_types'], 1)
        self.assertEqual(c['pair_types'], 2)
        self.assertEqual(c['skewed_types'], 2)

    def test_cutoff_ties_remove_all_tied_types(self):
        ts = toks([['a','b','a','b','c']])
        self.assertEqual(dsl._stop_types(ts, 1), {'a','b'})
        renamed = [dict(t, w={'a':'z','b':'x','c':'a'}[t['w']]) for t in ts]
        self.assertEqual(dsl._stop_types(renamed, 1), {'z','x'})

    def test_two_unique_word_definitions(self):
        ps = [page([['common'] * 10 + [f'w{i}' for i in range(30)]])]
        def spec(measure):
            return {'statistic':{'filtered_vocab':{'measure':measure,'drop_top':0}},
                    'compare':[{'op':'>=','value':0}]}
        a = dsl.evaluate(spec('type_token'), ps)
        b = dsl.evaluate(spec('singleton_token'), ps)
        self.assertEqual(a['value'], .775)
        self.assertEqual(b['value'], .75)
        self.assertEqual(a['detail']['filtered_vocab']['singleton_types'],30)

    def test_substitution_invariance_including_cutoff_ties(self):
        rng = random.Random(45)
        data = [[rng.choice([f'w{i}' for i in range(80)]) for _ in range(100)] for _ in range(8)]
        ids = list({w for row in data for w in row})
        mapping = dict(zip(ids, [f'z{i}' for i in reversed(range(len(ids)))]))
        other = [[mapping[w] for w in row] for row in data]
        for stat in (pair_stat(drop=1,window=3,excess=2),
                     {'filtered_vocab':{'measure':'type_token','drop_top':1}},
                     {'filtered_vocab':{'measure':'singleton_token','drop_top':1}}):
            spec={'statistic':stat,'compare':[{'op':'>=','value':0}]}
            self.assertEqual(dsl.evaluate(spec,[page(data)])['value'], dsl.evaluate(spec,[page(other)])['value'])

    def test_asymmetric_planted_sequence_beats_line_shuffle(self):
        seq = [item for i in range(40) for item in (f'a{i}',f'b{i}')]
        ps = [page([seq[:] for _ in range(20)])]
        spec={'statistic':pair_stat(excess=5),
              'compare':[{'null':'shuffle_within_line','perms':99,'p':.01,'direction':'greater'}]}
        r=dsl.evaluate(spec,ps)
        self.assertTrue(r['pass'],r)
        self.assertEqual(r['detail']['shuffle_within_line']['p'],.01)

    def test_sparse_and_bad_specs_refused(self):
        ps=[page([['a','b']*100])]
        spec={'statistic':pair_stat(),'compare':[{'op':'>=','value':0}]}
        with self.assertRaises(dsl.SpecError): dsl.evaluate(spec,ps)
        for bad in ({'window':0,'drop_top':0,'excess':1},{'window':11,'drop_top':0,'excess':1},
                    {'window':1,'drop_top':True,'excess':1},{'window':1,'drop_top':0,'excess':-1},
                    {'window':1,'drop_top':0,'excess':1,'wrong':2}):
            with self.assertRaises(dsl.SpecError): dsl.check_statistic({'directional_pairs':bad})
        with self.assertRaises(dsl.SpecError):
            dsl.check_statistic({'filtered_vocab':{'measure':'unique','drop_top':0}})

    def test_inert_null_is_refused(self):
        seq = [f'w{i}' for i in range(80)]
        spec={'statistic':pair_stat(excess=1000),
              'compare':[{'null':'shuffle_within_line','perms':99,'p':.01}]}
        with self.assertRaisesRegex(dsl.SpecError, 'cannot move'):
            dsl.evaluate(spec, [page([seq[:] for _ in range(10)])])

    def test_moving_pair_threshold_is_not_a_new_claim(self):
        a={'statistic':pair_stat(excess=2),'compare':[{'op':'>','value':.01}]}
        b={'statistic':pair_stat(excess=5),'compare':[{'op':'>','value':.02}]}
        self.assertEqual(dsl.canonical(a),dsl.canonical(b))


if __name__=='__main__': unittest.main()
