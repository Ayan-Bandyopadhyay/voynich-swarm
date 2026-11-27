"""Matched rightwardness: layout, ambiguity, sample guards and block uncertainty."""
import random
import unittest
from vs import dsl
from vs.ivtff import Page, Line


def pages(effect=True, seed=22, n_pages=12):
    rng = random.Random(seed)
    out = []
    for i in range(n_pages):
        p = Page(f'f{i}r', i, {'I': 'H', 'L': 'A', 'H': '1'})
        for j in range(16):
            words = ['xx', 'shedy', 'xx', 'chedy', 'xx']
            if not effect and rng.randrange(2):
                words[1], words[3] = words[3], words[1]
            p.lines.append(Line(f'f{i}r.{j}', p.id, j, 'P', '0', words, False, False))
        out.append(p)
    return out


class MatchedRightwardness(unittest.TestCase):
    def spec(self, contrast='sh/ch', minimum=3, maximum=9):
        return {'statistic': {'matched_rightwardness': {'contrast': contrast, 'min_line': minimum, 'max_line': maximum}},
                'compare': [{'page_bootstrap': 'lower', 'value': 0}]}

    def test_effect_and_null_with_page_bootstrap(self):
        effect = dsl.evaluate(self.spec(), pages())
        self.assertEqual(effect['value'], .5)
        self.assertTrue(effect['pass'])
        self.assertEqual(effect['detail']['page_bootstrap:lower']['lower'], .5)
        self.assertEqual(effect['detail']['matched_rightwardness'], {'first': 192, 'second': 192, 'pages': 12})
        null = dsl.evaluate(self.spec(), pages(False))
        self.assertFalse(null['pass'])
        self.assertLessEqual(null['detail']['page_bootstrap:lower']['lower'], 0)
        self.assertGreaterEqual(null['detail']['page_bootstrap:lower']['upper'], 0)

    def test_eligible_lines_and_original_positions(self):
        ps = pages()
        ps[0].lines[0].words[1] = 'sh?dy'
        result = dsl.evaluate(self.spec(), ps)
        self.assertEqual(result['value'], .5)
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(self.spec(minimum=6), ps)
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(self.spec(), ps[:4])
        with self.assertRaisesRegex(dsl.SpecError, 'at least 10 pages'):
            dsl.evaluate(self.spec(), ps[:9])

    def test_qo_o_prefix_and_upper_bound(self):
        ps = pages()
        for p in ps:
            for line in p.lines:
                line.words[1], line.words[3] = 'qokey', 'okey'
        spec = self.spec('qo/o')
        self.assertEqual(dsl.evaluate(spec, ps)['value'], .5)
        spec['compare'] = [{'page_bootstrap': 'upper', 'value': .6}]
        self.assertTrue(dsl.evaluate(spec, ps)['pass'])

    def test_pooled_effect_can_reflect_page_composition(self):
        # Both classes occupy the SAME position within each page, but their page
        # frequencies differ. The statistic deliberately reports the pooled effect;
        # page resampling does not turn it into a within-page comparison.
        ps = []
        for i in range(12):
            p = Page(f'f{i}r', i, {'I': 'H', 'L': 'A', 'H': '1'})
            for j in range(20):
                w = ('shedy' if j < 18 else 'chedy') if i < 6 else ('chedy' if j < 18 else 'shedy')
                words = ['xx'] * 5
                words[1 if i < 6 else 3] = w
                p.lines.append(Line(f'{p.id}.{j}', p.id, j, 'P', '0', words, False, False))
            ps.append(p)
        result = dsl.evaluate(self.spec(), ps)
        self.assertAlmostEqual(result['value'], .4)
        self.assertTrue(result['pass'])

    def test_sparse_bootstrap_replicates_are_not_silently_dropped(self):
        ps = []
        for i in range(10):
            p = Page(f'f{i}r', i, {'I': 'H', 'L': 'A', 'H': '1'})
            for j in range(40):
                w = 'shedy' if i == 0 else 'chedy'
                p.lines.append(Line(f'{p.id}.{j}', p.id, j, 'P', '0', ['x', w, 'x'], False, False))
            ps.append(p)
        with self.assertRaisesRegex(dsl.SpecError, 'bootstrap produced an undefined'):
            dsl.evaluate(self.spec(), ps)

    def test_k_t_ambiguous_word_is_not_double_counted(self):
        # ktk has both ttk and kkk as counterparts and is excluded entirely.
        ts = []
        for pg in range(6):
            for _ in range(20):
                for k,w in ((1,'ktk'), (2,'ttk'), (3,'kkk')):
                    ts.append({'page':pg,'unit':'P','n':5,'k':k,'w':w})
        value = dsl._matched_rightwardness(ts, {'contrast':'k/t','min_line':5,'max_line':5})
        self.assertEqual(value, -.25)

    def test_validation_and_canonical(self):
        spec = self.spec()
        self.assertEqual(dsl.canonical(spec)['tests'], ['page_bootstrap:lower'])
        for bad in ({'contrast':'x','min_line':3,'max_line':8}, {'contrast':'sh/ch','min_line':9,'max_line':3},
                    {'contrast':'qo/o','min_line':True,'max_line':8}):
            with self.assertRaises(dsl.SpecError): dsl.check_statistic({'matched_rightwardness':bad})
        with self.assertRaises(dsl.SpecError):
            dsl.check({'statistic': {'mean_length':True}, 'compare':[{'page_bootstrap':'lower','value':0}]})


if __name__ == '__main__':
    unittest.main()
