"""Fact attacks with cut "book" (P-G-007, form B): the procedure writes a whole book and the scorer
lays a random draw of its pages, kept in book order, onto the evaluation pages (vs/redteam.py)."""
import unittest
from vs import corpus, dsl, redteam
from tests.test_fact_attack_cut import F001, table_lines

ANY = {"id": "F-x", "type": "fact", "detail": {"spec": {"statistic": {"mean_length": True},
                                                       "compare": [{"op": ">=", "value": 0}]}}}


def pages_of(lines, size=24):
    return [lines[i:i + size] for i in range(0, len(lines), size)]


class FactAttackBook(unittest.TestCase):
    def test_book_cut_keeps_line_ends(self):
        book = pages_of(table_lines(n=len(corpus.pages()) * 24))
        r = redteam.fact_attack("F-001", [], "practice", F001, cut="book", book=book)
        self.assertTrue(r["success"], r)
        self.assertEqual(r["cut"], "book")

    def test_book_guards(self):
        short = pages_of(table_lines(n=240))
        self.assertIn("refused", redteam.fact_attack("F-001", [], "practice", F001, cut="book", book=short))
        book = pages_of(table_lines(n=len(corpus.pages()) * 24))
        self.assertIn("refused", redteam.fact_attack("F-001", [], "practice", F001, cut="book", book=book,
                                                     book_first_lines=book[:3]))

    def test_draw_is_fixed_and_in_book_order(self):
        # every line of book page i is the marker word wN (N = i); each evaluation page must start
        # at its drawn page, the draws must rise through the book, and the practice draw must not vary
        n = len(corpus.pages()) * 2
        book = [[[f"w{i}"] * 8] * 30 for i in range(n)]
        seen, orig = [], dsl.evaluate
        dsl.evaluate = lambda spec, pages: (seen.append(pages), orig(spec, pages))[1]
        try:
            redteam.fact_attack("F-x", [], "practice", ANY, cut="book", book=book)
            redteam.fact_attack("F-x", [], "practice", ANY, cut="book", book=book)
        finally:
            dsl.evaluate = orig
        fake1, fake2 = seen[1], seen[3]
        first = lambda pages: [int(next(ln.words[0] for ln in p.lines if ln.words)[1:]) for p in pages
                               if any(ln.words for ln in p.lines)]
        starts = first(fake1)
        self.assertEqual(starts, first(fake2))
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(set(starts)), len(starts))


if __name__ == "__main__":
    unittest.main()
