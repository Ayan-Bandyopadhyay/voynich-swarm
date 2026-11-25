import unittest

from vs import grid, search


class HomophoneBudgetTest(unittest.TestCase):
    def test_earlier_nahuatl_search_does_not_count_as_calibrated(self):
        item = {"language": "nahuatl", "family": "substitution", "verdict": "FAIL",
                "budget": dict(search.BUDGET)}
        power = {("nahuatl", "substitution"): True}
        self.assertEqual(grid.cell_status("nahuatl", "substitution", [item], power)[0],
                         "INCONCLUSIVE")
        item["budget"] = search.cell_budget("nahuatl", "substitution")
        self.assertEqual(grid.cell_status("nahuatl", "substitution", [item], power)[0],
                         "RULED OUT")
        self.assertEqual(search.cell_budget("nahuatl", "verbose"), search.BUDGET)
        self.assertEqual(search.cell_budget("hebrew", "substitution"), search.BUDGET)
