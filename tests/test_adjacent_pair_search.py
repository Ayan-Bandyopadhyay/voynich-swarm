import itertools
import unittest
from unittest.mock import patch

from vs import grid, ivtff, lm, search


class GermanAdjacentPairSearchTest(unittest.TestCase):
    def test_search_splits_a_collapsed_pair_without_changing_legacy_replay(self):
        symbols = ['a', 'b', 'c', lm.WB]
        table = dict.fromkeys(itertools.product(symbols, repeat=3), -2)
        table[lm.WB, 'a', 'a'] = table['a', 'a', lm.WB] = -1
        table[lm.WB, 'b', 'c'] = table['b', 'c', lm.WB] = 0
        line = ivtff.Line('c0.1', 'c0', 1, 'P', '0', ['xy'], True, True)
        pages = [ivtff.Page('c0', 0, {}, [line])]
        initial = {'x': 'a', 'y': 'a'}

        with (patch.object(search, 'trigram_table', return_value=(table, symbols)),
              patch.object(search, 'climb', return_value=(initial, -2))):
            refined = search.search_cell('german', 'substitution', pages)
            legacy = search.search_cell('german', 'substitution', pages, budget=search.BUDGET)
            other = search.search_cell('english', 'substitution', pages, budget=refined['search']['budget'])

        self.assertEqual(refined['key']['map'], {'x': 'b', 'y': 'c'})
        self.assertEqual(refined['search']['objective_bits'], 0)
        self.assertEqual(refined['search']['budget']['substitution_pair_candidates'], 16)
        self.assertEqual(refined['search']['budget']['substitution_pair_sweeps'], 3)
        for key in (legacy, other):
            self.assertEqual(key['key']['map'], initial)
            self.assertEqual(key['search']['objective_bits'], 2)

    def test_older_german_keys_do_not_count_as_searches_with_the_new_budget(self):
        item = {'language': 'german', 'family': 'substitution', 'verdict': 'FAIL',
                'budget': search.BUDGET}
        power = {('german', 'substitution'): True}
        self.assertEqual(grid.cell_status('german', 'substitution', [item], power)[0], 'INCONCLUSIVE')
        item['budget'] = search.cell_budget('german', 'substitution')
        self.assertEqual(grid.cell_status('german', 'substitution', [item], power)[0], 'RULED OUT')


if __name__ == '__main__':
    unittest.main()
