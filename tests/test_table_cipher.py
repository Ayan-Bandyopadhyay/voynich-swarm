import unittest
from vs import judge, families


class TableCipherTest(unittest.TestCase):
    def test_shifted_units_are_reversible_and_reset_per_word(self):
        key = {"map": {"ch": "a", "d": "b", "y": "c"}, "shifts": [1, 2]}
        family = families.load("table-cipher")
        seg = judge.seg_fn("eva-basic")
        cut = judge.key_units({"family": "table-cipher", "key": key}, seg)
        for word in ("dy", "dych", "xchd", ""):
            row = sorted(key["map"])
            restored = "".join(row[(row.index(g) + key["shifts"][i % 2]) % len(row)]
                               if g in row else g for i, g in enumerate(cut(word)))
            self.assertEqual(restored, word)
        self.assertEqual(family.decode_word("dy", key, seg), "aa")

    def test_table_budget_is_independent_of_substitution_restarts(self):
        from vs import grid, search_table_cipher
        power = {("english", "table-cipher"): True}
        item = {"language": "english", "family": "table-cipher", "verdict": "FAIL",
                "budget": {"max_period": 2, "sweeps": 4}}
        self.assertEqual(grid.cell_status("english", "table-cipher", [item], power)[0], "INCONCLUSIVE")
        item["budget"] = search_table_cipher.BUDGET
        self.assertEqual(grid.cell_status("english", "table-cipher", [item], power)[0], "RULED OUT")
