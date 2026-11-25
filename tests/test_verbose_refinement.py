import unittest
from vs import grid, search


class VerboseRefinementTest(unittest.TestCase):
    def test_previous_spanish_budget_does_not_establish_power_for_new_search(self):
        item = {"language": "spanish", "family": "verbose", "verdict": "FAIL", "budget": search.BUDGET}
        power = {("spanish", "verbose"): True}
        self.assertEqual(grid.cell_status("spanish", "verbose", [item], power)[0], "INCONCLUSIVE")
        item["budget"] = search.cell_budget("spanish", "verbose")
        self.assertEqual(grid.cell_status("spanish", "verbose", [item], power)[0], "RULED OUT")
        self.assertEqual(search.cell_budget("spanish", "substitution"), search.BUDGET)

    def test_each_calibrated_search_requires_its_own_settings(self):
        for lang in ("italian", "french", "german"):
            budget = search.cell_budget(lang, "verbose")
            item = {"language": lang, "family": "verbose", "verdict": "FAIL", "budget": budget}
            power = {(lang, "verbose"): True}
            self.assertEqual(grid.cell_status(lang, "verbose", [item], power)[0], "RULED OUT")
            item["budget"] = {k: v for k, v in budget.items() if k != "verbose_singleton_limit"}
            self.assertEqual(grid.cell_status(lang, "verbose", [item], power)[0], "INCONCLUSIVE")
