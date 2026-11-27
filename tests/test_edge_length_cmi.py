"""Analytical and adversarial checks for conditional edge association."""
import math
import random
import unittest
from collections import Counter
from vs import dsl
from tests.test_dsl import page


class EdgeLengthCMITest(unittest.TestCase):
    def spec(self, null=False):
        return {"select": {"unit": ["P"], "certain": True}, "statistic": {"edge_length_cmi": True},
                "compare": ([{"null": "shuffle_within_line_length", "perms": 99, "p": .01}]
                            if null else [{"op": ">=", "value": 0}])}

    def test_one_bit_and_length_only_confound(self):
        same_length = [page("p", [["aa", "aa"], ["rr", "rr"]] * 20)]
        self.assertEqual(dsl.evaluate(self.spec(), same_length)["value"], 1)
        # Edges are perfectly correlated, but lengths alone explain the correlation.
        confound = [page("p", [["a", "a"], ["rr", "rr"]] * 20)]
        self.assertEqual(dsl.evaluate(self.spec(), confound)["value"], 0)
        self.assertEqual(dsl.evaluate({"statistic": {"edge_mi": True},
                                      "compare": [{"op": ">=", "value": 0}]}, confound)["value"], 1)

    def test_weighted_strata_not_unweighted_mean(self):
        # 30 correlated pairs of length2 give1bit,10constant pairs of length1 give0.
        pages = [page("p", [["aa", "aa"], ["rr", "rr"]] * 15 + [["a", "a"]] * 10)]
        self.assertEqual(dsl.evaluate(self.spec(), pages)["value"], .75)

    def test_uncertain_unselected_and_empty_words_do_not_bridge(self):
        for middle in ("?", "*", ""):
            pages = [page("p", [["aa", middle, "rr"]] * 40)]
            with self.assertRaises(dsl.SpecError):
                dsl.evaluate(self.spec(), pages)
        pages = [page("p", [["aa"], ("L", ["aa", "rr"]), ["rr"]] * 40)]
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(self.spec(), pages)
        toks = dsl.tokens([page("p", [["aa", "oo", "rr"]] * 40)])
        toks = [t for t in toks if t["k"] != 1]
        self.assertTrue(math.isnan(dsl.statistic({"edge_length_cmi": True}, toks, toks)))

    def test_null_preserves_positions_lengths_units_and_each_line_inventory(self):
        pages = [page("p", [["ch", "a", "o", "?", "aa", "rr", ""], ("L", ["ch", "a"])])]
        ts = dsl.tokens(pages)
        sh = dsl._shuffled(ts, "shuffle_within_line_length", random.Random(7))
        self.assertNotEqual([t["w"] for t in ts], [t["w"] for t in sh])
        for a, b in zip(ts, sh):
            self.assertEqual({k:v for k,v in a.items() if k != "w"}, {k:v for k,v in b.items() if k != "w"})
            self.assertEqual(len(dsl.SEG(a["w"])), len(dsl.SEG(b["w"])))
            if a["unit"] != "P" or not a["w"] or dsl.UNCERTAIN(a["w"]):
                self.assertEqual(a["w"], b["w"])
        for a, b in zip(dsl.lines_of(ts), dsl.lines_of(sh)):
            self.assertEqual(Counter(t["w"] for t in a), Counter(t["w"] for t in b))
        # EVA ch is one unit and must be permitted to exchange with a/o.
        self.assertEqual(len(dsl.SEG("ch")), 1)
        self.assertNotEqual(ts[0]["w"], sh[0]["w"])

    def test_constant_or_too_small_movable_null_is_refused(self):
        for pages in ([page("p", [["a", "rr"]] * 40)],
                      [page("p", [["aa", "aa"]] * 40 + [["aa", "rr"]])]):
            with self.assertRaises(dsl.SpecError):
                dsl.evaluate(self.spec(null=True), pages)
        # Different words can shuffle but have identical edge glyphs.
        with self.assertRaisesRegex(dsl.SpecError, "cannot move"):
            dsl.evaluate(self.spec(null=True), [page("p", [["aaa", "ara"]] * 40)])

    def test_schema_and_fingerprint(self):
        for select in ({}, {"unit":["P"], "certain":False}, {"unit":["P"], "position":"line_initial"}):
            spec = self.spec(); spec["select"] = select
            with self.assertRaises(dsl.SpecError): dsl.check(spec)
        spec=self.spec(null=True); spec["compare"][0]["null"]="shuffle_within_line"
        with self.assertRaises(dsl.SpecError): dsl.check(spec)
        spec=self.spec(null=True); spec["statistic"]={"edge_mi":True}
        with self.assertRaises(dsl.SpecError): dsl.check(spec)
        spec=self.spec(null=True); changed=self.spec(null=True);changed["compare"][0].update(perms=199,p=.005)
        self.assertEqual(dsl.canonical(spec), dsl.canonical(changed))

    def test_association_survives_independent_entropy_formula_and_permutation(self):
        rng=random.Random(6)
        pages=[page("p", [["aa"] * 4 + ["rr"] * 4 +
                         [rng.choice(["a", "r"]) for _ in range(3)] for _ in range(80)])]
        ts=dsl.select(dsl.tokens(pages), {"unit":["P"]})
        pairs=dsl._edge_length_pairs(ts)
        rows=[(len(dsl.SEG(a["w"])),len(dsl.SEG(b["w"])),dsl.SEG(a["w"])[-1],dsl.SEG(b["w"])[0]) for a,b in pairs]
        def entropy(keys):
            c=Counter(keys);n=sum(c.values());return -sum(v/n*math.log2(v/n) for v in c.values())
        independent=entropy(z[:3] for z in rows)+entropy((z[0],z[1],z[3]) for z in rows)-entropy(z[:2] for z in rows)-entropy(rows)
        self.assertAlmostEqual(dsl.statistic({"edge_length_cmi":True},ts,ts), independent, places=12)
        result=dsl.evaluate(self.spec(null=True),pages)
        self.assertTrue(result["pass"])
        self.assertEqual(result["detail"]["shuffle_within_line_length"]["p"], .01)


if __name__ == "__main__":
    unittest.main()
