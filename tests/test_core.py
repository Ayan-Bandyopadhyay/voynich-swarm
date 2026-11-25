import json, os, unittest
from vs import path, ivtff, split, controls, judge, refcorpus

HAVE_DATA = os.path.exists(path("data", "raw", "ZL3b-n.txt"))


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class CoreTest(unittest.TestCase):
    def test_parse(self):
        pages = ivtff.parse()
        self.assertEqual(len(pages), 226)
        self.assertEqual(sum(len(p.words()) for p in pages), 38486)
        self.assertEqual(pages[0].lines[0].words[0], "fachys")

    def test_segment(self):
        self.assertEqual(ivtff.segment("qokcheedy"), ["q", "o", "k", "ch", "e", "e", "d", "y"])
        self.assertEqual(ivtff.segment("cthor"), ["cth", "o", "r"])

    def test_commitment_scheme(self):
        pages = ivtff.parse()
        held = split.select("abc", pages)
        self.assertEqual(len(held), 34)
        self.assertEqual(held, split.select("abc", pages), "deterministic")
        c = split.commitment("abc", held)
        self.assertNotEqual(c, split.commitment("abd", split.select("abd", pages)))
        pub = json.load(open(path("heldout", "COMMITMENT.json")))
        self.assertEqual(len(pub["commitment_sha256"]), 64)

    def test_normalize(self):
        self.assertEqual(refcorpus.normalize("Iuuenis, VIVIT!", "latin"), "iuuenis uiuit")
        self.assertEqual(refcorpus.normalize("שָׁלוֹם", "hebrew"), "שלומ")


@unittest.skipUnless(HAVE_DATA, "run python3 -m vs fetch first")
class JudgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tr, cls.ev, cls.true = controls.make("latin", "homophonic")

    def test_true_key_passes_a_b_kill(self):
        r = judge.evaluate(self.true, self.tr, self.ev, "control")
        self.assertTrue(r["a_compresses"]["pass"])
        self.assertTrue(r["b_reads"]["pass"])
        self.assertTrue(r["kill_tests"]["pass"])
        self.assertEqual(r["verdict"], "FAIL", "no confirmed anchors yet, so never a full PASS")
        self.assertEqual(r["failed"], ["c_pictures"])

    def test_red_team_rejected(self):
        for k in controls.red_team_keys("latin"):
            r = judge.evaluate(k, self.tr, self.ev, "control")
            self.assertFalse(r["a_compresses"]["pass"], k["id"])
            self.assertFalse(r["kill_tests"]["pass"], k["id"])

    def test_deterministic(self):
        a = judge.evaluate(self.true, self.tr, self.ev, "control")
        b = judge.evaluate(self.true, self.tr, self.ev, "control")
        self.assertEqual(json.dumps(a, sort_keys=True, default=str), json.dumps(b, sort_keys=True, default=str))

    def test_unknown_family_refused(self):
        with self.assertRaises(SystemExit):
            judge.evaluate(dict(self.true, family="exec"), self.tr, self.ev, "control")


if __name__ == "__main__":
    unittest.main()
