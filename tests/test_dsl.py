"""Red-team tests for the measurement language (vs/dsl.py) and the fact fingerprint (vs/registry.py).
Each test is an exploit or a bug that worked before the fix named in its docstring."""
import os, random, unittest
from vs import path, dsl, registry
from vs.ivtff import Page, Line

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))
T = [{"op": ">=", "value": 0}]          # a comparison, where the test is about something else


def page(pid, lines, section="H", order=0):
    """lines: [(unit, [words])] or [words]; every P line after the first continues the paragraph."""
    p = Page(pid, order, {"I": section, "L": "A", "H": "1"})
    for i, ln in enumerate(lines):
        unit, ws = ln if isinstance(ln, tuple) else ("P", ln)
        p.lines.append(Line(f"{pid}.{i}", pid, i, unit, "0", list(ws), False, False))
    return p


def iid_pages(rng, n_pages=6, lines=30, width=8, vocab=None):
    vocab = vocab or ["daiin", "chol", "shedy", "qokeedy", "ol", "or", "aiin", "chedy", "okal", "dar"]
    return [page(f"f{i}r", [[rng.choice(vocab) for _ in range(width)] for _ in range(lines)], order=i) for i in range(n_pages)]


class HollowPassTest(unittest.TestCase):
    def setUp(self):
        self.pages = iid_pages(random.Random(1))

    def refused(self, spec, pages=None):
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(spec, pages or self.pages)

    def test_no_comparison_is_refused(self):
        """Before: a spec with no `compare` was ESTABLISHED with nothing tested."""
        self.refused({"statistic": {"mean_length": True}})
        self.refused({"statistic": {"mean_length": True}, "compare": []})

    def test_infinite_ratio_never_passes(self):
        """Before: a ratio whose denominator selection has no hit was inf and passed any threshold."""
        spec = {"statistic": {"ratio": {"feature": "word", "in": ["daiin"], "of": {"position": "line_initial"},
                                        "to": {"position": "line_final"}}},
                "compare": [{"op": ">=", "value": 1e9}]}
        pages = [page("f1r", [["daiin", "chol", "shedy"]] * 40)]
        r = dsl.evaluate(spec, pages)
        self.assertEqual(r["value"], float("inf"))
        self.assertFalse(r["pass"])

    def test_vacuous_numbers_are_refused(self):
        """Before: margin -1e9 passed below_all, p = 1 passed any null, NaN/inf thresholds were accepted."""
        st = {"entropy": "word"}
        self.refused({"statistic": st, "compare": [{"reference": "below_all", "margin": -1e9}]})
        self.refused({"statistic": st, "compare": [{"null": "shuffle_across_pages", "p": 1.0}]})
        self.refused({"statistic": st, "compare": [{"null": "shuffle_across_pages", "p": 0.01, "perms": 50}]})
        self.refused({"statistic": st, "compare": [{"op": ">=", "value": float("-inf")}]})
        self.refused({"statistic": st, "compare": [{"op": ">=", "value": float("nan")}]})

    def test_unknown_keys_are_refused(self):
        """Before: {"scope": {"scribe": "9"}} and {"select": {"units": [...]}} were silently ignored, so a
        claim titled for one scribe's labels was measured on everything."""
        self.refused({"scope": {"scribe": "9"}, "statistic": {"mean_length": True}, "compare": T})
        self.refused({"select": {"units": ["L"]}, "statistic": {"mean_length": True}, "compare": T})
        self.refused({"statistic": {"mean_length": True}, "compare": T, "note": "x"})
        self.refused({"statistic": {"entropy": {"suffix": 0}}, "compare": T})      # g[-0:] was the whole word
        self.refused({"statistic": {"near_copy": {"window": 0}}, "compare": T})

    def test_degenerate_selection_is_refused_not_zero(self):
        """Before: line-final words (one per line, so no adjacent pair) had cond_entropy 0.0 and
        repeat_ngram 0.0, which is 'below every reference language' by construction."""
        for st in ({"cond_entropy": "word"}, {"repeat_ngram": 2}, {"edge_mi": True}, {"adjacent_mi": "word"}):
            self.refused({"select": {"position": "line_final"}, "statistic": st, "compare": [{"op": "<=", "value": 0.5}]})
        self.refused({"statistic": {"mean_length": True}, "compare": T}, [page("f1r", [["daiin"] * 5])])  # 5 tokens

    def test_adjacency_is_adjacency(self):
        """Before: with uncertain words dropped, the words either side of one were counted as adjacent."""
        pages = [page("f1r", [["chol", "d?iin", "shedy"]] * 40)]
        runs = dsl.runs_of(dsl.select(dsl.tokens(pages), None))
        self.assertTrue(all(len(r) == 1 for r in runs))
        self.refused({"statistic": {"repeat_ngram": 2}, "compare": [{"op": ">=", "value": 0.9}]}, pages)

    def test_ratio_can_compare_dialects_within_a_shared_shuffle(self):
        a = page("a", [["ol", "ol", "or", "or"]] * 20)
        b = page("b", [["ol", "ol", "ol", "ol"]] * 20)
        b.meta["L"] = "B"
        arg = {"feature": "word", "in": ["ol"], "of": {"language": "A"}, "to": {"language": "B"}}
        spec = {"statistic": {"ratio": arg}, "compare": [{"null": "shuffle_across_pages", "direction": "less",
                                                          "perms": 99, "p": 0.01}]}
        result = dsl.evaluate(spec, [a, b])
        self.assertTrue(result["pass"])
        self.assertEqual(result["value"], 0.5)
        self.assertEqual(dsl.canonical(spec)["statistic"]["ratio"]["of"]["language"], "A")
        self.assertNotIn("language", dsl.canonical(spec)["select"])
        arg["of"]["language"] = "unknown"
        self.refused(spec, [a, b])

    def test_null_that_cannot_move_the_statistic_is_refused(self):
        self.refused({"statistic": {"entropy": "word"}, "compare": [{"null": "shuffle_within_line", "perms": 99}]})

    def test_cost_is_bounded(self):
        """Before: any number of 400-permutation nulls (each ~30 s per transliteration) could be listed."""
        null = {"null": "shuffle_within_page", "perms": 400}
        self.refused({"statistic": {"edge_mi": True}, "compare": [null] * 5})

    def test_not_para_first_line_is_paragraph_text(self):
        """Before: 'not_para_first_line' included every label and ring word."""
        pages = [page("f1r", [["a1", "a2"], ["b1", "b2"], ("L", ["lab"]), ("C", ["ring"])])]
        got = {t["w"] for t in dsl.select(dsl.tokens(pages), {"position": "not_para_first_line"})}
        self.assertEqual(got, {"b1", "b2"})


class NullsTest(unittest.TestCase):
    def _sections(self, label_o):
        rng = random.Random(3)
        word = lambda p_o: ("o" if rng.random() < p_o else "d") + rng.choice(["ain", "al", "ar", "or", "y"])
        z = [page(f"f7{i}r", [[word(0.8) for _ in range(8)] for _ in range(10)] + [("L", [word(label_o)]) for _ in range(12)],
                  section="Z", order=i) for i in range(4)]
        h = [page(f"f{i}r", [[word(0.1) for _ in range(8)] for _ in range(60)], section="H", order=10 + i) for i in range(4)]
        return z + h

    SPEC = {"select": {"unit": ["L"]}, "statistic": {"rate": {"feature": {"glyph_at": 0}, "in": ["o"]}},
            "compare": [{"null": "shuffle_labels", "perms": 199, "p": 0.01}]}

    def test_shuffle_labels_is_matched_on_section(self):
        """Before: labels were shuffled with running text of the whole scope, so labels that are ordinary
        words of their own section 'differed' from running text (p = 0.005): section vocabulary, not a label
        register."""
        r = dsl.evaluate(self.SPEC, self._sections(label_o=0.8))
        self.assertFalse(r["pass"], r)

    def test_a_real_label_effect_still_passes(self):
        r = dsl.evaluate(self.SPEC, self._sections(label_o=1.0))
        self.assertTrue(r["pass"], r)
        strict = dict(self.SPEC, compare=[{"null": "shuffle_labels_within_page", "perms": 199, "p": 0.01}])
        self.assertTrue(dsl.evaluate(strict, self._sections(label_o=1.0))["pass"])

    def test_shuffle_labels_leaves_other_text_in_place(self):
        """Before: every paragraph word in scope was shuffled too, so any word-order statistic was
        'significant' against shuffle_labels."""
        toks = dsl.tokens(self._sections(0.8))
        sh = dsl._shuffled(toks, "shuffle_labels", random.Random(1))
        self.assertEqual([t["w"] for t in toks if t["section"] == "H"], [t["w"] for t in sh if t["section"] == "H"])
        moved = sum(a["w"] != b["w"] for a, b in zip(toks, sh) if a["unit"] != "L")
        self.assertLessEqual(moved, sum(t["unit"] == "L" for t in toks))
        self.assertEqual(sorted(t["w"] for t in toks), sorted(t["w"] for t in sh))

    def test_adjacent_mi_ignores_page_vocabulary(self):
        """Before: the baseline was a shuffle of the whole selection, so pages with different vocabularies
        and no word order at all showed a large 'adjacent' MI (0.9 bits here)."""
        rng = random.Random(5)
        pages = [page(f"f{i}r", [[f"w{i}_{rng.randrange(6)}" for _ in range(8)] for _ in range(40)], order=i) for i in range(8)]
        v = dsl.evaluate({"statistic": {"adjacent_mi": "word"}, "compare": T[:0] + [{"op": "<=", "value": 9}]}, pages)["value"]
        self.assertLess(abs(v), 0.1)


class NewPrimitivesTest(unittest.TestCase):
    def test_glyph_cond_entropy(self):
        # one word "ab" per line, many lines: stream _ a b _ ; every glyph is determined by the one before
        pages = [page("f1r", [["ab"]] * 40)]
        st = {"glyph_cond_entropy": 1}
        self.assertAlmostEqual(dsl.statistic(st, dsl.tokens(pages), []), 0.0)
        pages = [page("f1r", [["ab"], ["ac"]] * 20)]
        # 120 transitions; the 40 after 'a' carry 1 bit, the rest none
        self.assertAlmostEqual(dsl.statistic(st, dsl.tokens(pages), []), 1 / 3)

    def test_page_reuse(self):
        pages = [page("f1r", [["a", "b", "a", "a"]] * 10), page("f2r", [["c", "d", "e", "f"]] * 10, order=1)]
        # page 1: 40 tokens, 2 first occurrences; page 2: 40 tokens, 4 first occurrences
        self.assertAlmostEqual(dsl.statistic({"page_reuse": {}}, dsl.tokens(pages), []), 74 / 80)

    def test_context_mi_sees_section_vocabulary(self):
        rng = random.Random(2)
        pages = [page(f"f{i}r", [[f"{'hz'[i % 2]}{rng.randrange(5)}" for _ in range(8)] for _ in range(20)],
                      section="HZ"[i % 2], order=i) for i in range(6)]
        spec = {"statistic": {"context_mi": {"feature": "word", "by": "section"}},
                "compare": [{"null": "shuffle_across_pages", "perms": 99, "p": 0.01}]}
        r = dsl.evaluate(spec, pages)
        self.assertTrue(r["pass"])
        self.assertAlmostEqual(r["value"], 1.0, places=2)
        with self.assertRaises(dsl.SpecError):      # plug-in MI against another script means nothing
            dsl.evaluate(dict(spec, compare=[{"reference": "above_all"}]), pages)


class FingerprintTest(unittest.TestCase):
    def item(self, spec):
        return {"type": "fact", "detail": {"spec": spec}, "provenance": {}}

    def test_different_specs_are_different_claims(self):
        """Before: every spec fact had the fingerprint ('fact', None, 'null'), so the second spec fact ever
        submitted was refused as a DUPLICATE of the first (after being scored on the hidden pages)."""
        a = self.item({"statistic": {"mean_length": True}, "compare": T})
        b = self.item({"statistic": {"entropy": "word"}, "compare": T})
        self.assertNotEqual(registry.fingerprint(a), registry.fingerprint(b))

    def test_resubmissions_are_the_same_claim(self):
        """A moved threshold (the hidden value is published with the first verdict), a re-rolled null
        (another perms count draws other permutations), reordered keys and spelled-out defaults."""
        a = {"select": {"unit": ["P", "L"]}, "statistic": {"rate": {"feature": "word", "in": ["daiin", "ol"]}},
             "compare": [{"op": ">=", "value": 0.02}, {"null": "shuffle_within_page", "perms": 400, "p": 0.01}]}
        b = {"compare": [{"null": "shuffle_within_page", "perms": 399, "p": 0.05, "direction": "greater"}, {"op": ">", "value": 0.019}],
             "statistic": {"rate": {"in": ["ol", "daiin"], "feature": "word"}},
             "select": {"unit": ["L", "P"], "certain": True, "position": "any"}, "scope": {}}
        self.assertEqual(registry.fingerprint(self.item(a)), registry.fingerprint(self.item(b)))
        c = dict(a, compare=[{"op": "<=", "value": 0.02}])      # the opposite claim is another claim
        self.assertNotEqual(registry.fingerprint(self.item(a)), registry.fingerprint(self.item(c)))


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class ReferenceTest(unittest.TestCase):
    def test_reference_is_matched_in_shape(self):
        """Before: references were always flat 8-word lines. The Latin reference text itself, written in
        2-word lines, came out 'below every reference language' on word conditional entropy by 0.44 bits
        (1.97 against its own 2.40): fewer pairs per word, nothing else."""
        from vs.facts import ref_words
        ws = ref_words("latin", 6000)
        pages = [page(f"f{i}r", [ws[i * 600 + j: i * 600 + j + 2] for j in range(0, 600, 2)], order=i) for i in range(10)]
        spec = {"statistic": {"cond_entropy": "word"}, "compare": [{"reference": "below_all", "margin": 0.2}]}
        r = dsl.evaluate(spec, pages)
        self.assertFalse(r["pass"], r)
        self.assertAlmostEqual(r["value"], r["detail"]["reference"]["latin"], places=4)

    def test_reference_is_matched_in_size(self):
        """Before: a selection larger than a reference text was compared with the whole (smaller) text."""
        from vs import corpus
        spec = {"statistic": {"hapax_share": True}, "compare": [{"reference": "below_all"}]}
        with self.assertRaises(dsl.SpecError):
            dsl.evaluate(spec, list(corpus.pages()))
        r = dsl.evaluate(spec, corpus.split_pages("practice")[1])
        self.assertTrue(all(lang in r["detail"]["reference"] for lang in ("latin", "italian", "german")))

    def test_the_fact_on_the_record_is_unchanged(self):
        """F-001's spec measures what it measured before (practice split)."""
        from vs import corpus
        spec = {"scope": {"language": "B"}, "select": {"certain": True, "position": "line_final", "unit": ["P"]},
                "statistic": {"ratio": {"feature": {"glyph_at": -1}, "in": ["m"],
                                        "of": {"certain": True, "position": "line_final", "unit": ["P"]},
                                        "to": {"certain": True, "position": "mid_line", "unit": ["P"]}}},
                "compare": [{"op": ">=", "value": 10}, {"direction": "greater", "null": "shuffle_within_line", "p": 0.01, "perms": 199}]}
        r = dsl.evaluate(spec, corpus.split_pages("practice")[1])
        self.assertEqual((r["value"], r["pass"], r["detail"]["shuffle_within_line"]["p"]), (61.623767, True, 0.005))


if __name__ == "__main__":
    unittest.main()
