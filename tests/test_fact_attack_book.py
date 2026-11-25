"""Fact attacks may send cut "book": the text is laid onto every page of the manuscript and the fact is
measured on the evaluation pages of it (vs/redteam.py).

With cut "lines" the text runs end to end over a sample of pages. A writer who changes word stock
every 150 lines then looks as if pages fifteen apart in the BOOK shared vocabulary, because
neighbouring sampled pages hold neighbouring text. Laid onto the whole book, the same text loses it."""
import random, unittest
from vs import corpus, redteam

NEAR = {"id": "F-011", "type": "fact", "detail": {"spec": {
    "select": {"unit": ["P"], "certain": True},
    "statistic": {"page_similarity": {"within": 15, "min_words": 40}},
    "compare": [{"null": "shuffle_across_pages", "direction": "greater", "perms": 99, "p": 0.01}]}}}


def short_memory(n, seed=408, block=150):
    """A writer with no long-range structure: every 150 lines it starts a fresh stock of 30 words."""
    rng = random.Random(seed)
    return [[f"b{i // block}x{rng.randrange(30)}" for _ in range(9)] for i in range(n)]


class Book(unittest.TestCase):
    def test_short_memory_is_not_long_range_structure(self):
        lines = short_memory(6000)
        end_to_end = redteam.fact_attack("F-011", lines, "practice", NEAR, cut="lines")
        whole_book = redteam.fact_attack("F-011", lines, "practice", NEAR, cut="book")
        self.assertTrue(end_to_end["success"])                    # 150 lines span several sampled pages
        self.assertGreater(end_to_end["synthetic"]["value"], 0.5)
        self.assertNotIn("refused", whole_book)
        self.assertLess(whole_book["synthetic"]["value"], 0.05)   # but hardly more than one sampled page of a book

    def test_book_fills_the_evaluation_pages_with_their_share(self):
        total = sum(1 for p in corpus.pages() for ln in p.lines if ln.words)
        lines = short_memory(total)
        r = redteam.fact_attack("F-011", lines, "practice", NEAR, cut="book")
        self.assertNotIn("refused", r)
        self.assertIn("refused", redteam.fact_attack("F-011", lines[:total - 1], "practice", NEAR, cut="book"))
        openers = redteam._count_openers(list(corpus.pages()))
        first = short_memory(openers, seed=1)
        self.assertNotIn("refused", redteam.fact_attack("F-011", lines[:total - openers], "practice", NEAR, cut="book", first_lines=first))
        self.assertIn("refused", redteam.fact_attack("F-011", lines, "practice", NEAR, cut="book", first_lines=first[:-1]))


if __name__ == "__main__":
    unittest.main()
