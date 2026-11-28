"""Letters written as whole words: the family, the respaced reading, the control and the search."""
import os, random, unittest
from vs import path, views
from vs.families import letter_words

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))
KEY = {"prefix": {"qo": "a", "ch": "b", "q": "c"}, "suffix": {"dy": "d", "aiin": "e", "y": "f"}}


class FamilyTest(unittest.TestCase):
    def test_a_word_is_a_prefix_a_suffix_or_both(self):
        d = lambda w: letter_words.decode_word(w, KEY, None)
        self.assertEqual(d("qody"), "ad")
        self.assertEqual(d("ch"), "b")
        self.assertEqual(d("aiin"), "e")
        self.assertEqual(d("qy"), "cf", "the longest prefix whose remainder is a suffix")
        self.assertEqual(d("qoxx"), "", "a word that cannot be cut carries nothing")
        self.assertEqual(letter_words.units("qody", KEY), ["<qo", ">dy"])

    def test_only_this_family_is_respaced_and_its_key_has_two_tables(self):
        ok = {"family": "letter-words", "plaintext": "respaced", "key": KEY}
        views.check(ok)
        for bad in ({**ok, "plaintext": "words"}, {"family": "substitution", "plaintext": "respaced", "key": {"map": {}}},
                    {**ok, "key": {"map": {}}}, {**ok, "spaces": "ignored"}):
            with self.assertRaises(SystemExit):
                views.check(bad)


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class RespacedTest(unittest.TestCase):
    def test_the_cut_finds_the_words_of_a_stream(self):
        from vs import respace
        self.assertEqual(respace.cut("inprincipioeratuerbum", "latin"), ["in", "principio", "erat", "uerbum"])
        m = respace.metrics("latin", ["inprincipioeratuerbumetuerbumeratapuddeum"])
        self.assertGreater(m["cov"], 0.8)
        rng = random.Random(1)
        noise = "".join(rng.choice("abcdefghilmnopqrstux") for _ in range(400))
        self.assertLess(respace.metrics("latin", [noise])["cov"], 0.5)
        self.assertGreater(respace.metrics("latin", [noise])["H"], m["H"] + 1.0)

    def test_the_search_recovers_the_planted_key_at_two_percent_noise(self):
        from collections import Counter
        from vs import controls, search
        tr, _ev, true = controls.make("latin", "letter-words", noise=controls.NOISE)
        found = search.search_cell("latin", "letter-words", tr, tag="test")
        self.assertEqual(found["plaintext"], "respaced")
        self.assertEqual(found["search"]["front_glyphs"], sorted(["q", "o", "k", "t", "p", "f", "ch", "sh", "cth", "ckh"]))
        count, right = Counter(), Counter()
        for p in tr:
            for ln in p.lines:
                for w in ln.words:
                    count[w] += 1
        seg = None
        same = sum(n for w, n in count.items()
                   if letter_words.decode_word(w, found["key"], seg) == letter_words.decode_word(w, true["key"], seg))
        self.assertGreater(same / sum(count.values()), 0.97)

    def test_the_true_key_passes_and_a_scrambled_key_fails(self):
        from vs import controls, judge
        tr, ev, true = controls.make("latin", "letter-words", noise=controls.NOISE)
        r = judge.evaluate(true, tr, ev, "control")
        self.assertTrue(r["a_compresses"]["pass"] and r["b_reads"]["pass"] and r["kill_tests"]["pass"], r["failed"])
        self.assertTrue(r["d_not_illusion"]["pass"], r["d_not_illusion"])
        rng = random.Random(7)
        wrong = {**true, "key": {t: dict(zip(m, rng.sample(list(m.values()), len(m)))) for t, m in true["key"].items()}}
        bad = judge.evaluate(wrong, tr, ev, "control")
        self.assertFalse(bad["a_compresses"]["pass"])
        self.assertFalse(bad["b_reads"]["pass"])


if __name__ == "__main__":
    unittest.main()
