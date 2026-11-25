"""Views of the manuscript for scoring.

Two splits exist:
  practice  a public split drawn the same way from the public seed 'practice'. Anyone can
            use it to rehearse; it means nothing for the judge.
  heldout   the committed split. Only the scorer, who holds the seed, can build it.
Models are always trained on the complement of the evaluation pages.
"""
from functools import lru_cache
from . import ivtff, split


TRANSLITERATIONS = {"zl": "ZL3b-n.txt", "it": "IT2a-n.txt", "rf": "RF1b-e.txt", "gc": "GC2a-n.txt"}
EVA_TRANSLITERATIONS = ("zl", "it", "rf")   # same alphabet: a spec or key runs on any of them


@lru_cache(maxsize=None)
def pages(translit="zl"):
    from . import path
    return tuple(ivtff.parse(path("data", "raw", TRANSLITERATIONS[translit])))


def page_map():
    return {p.id: p for p in pages()}


def split_pages(which, translit="zl"):
    """The split is defined on ZL page ids; other transliterations use the same page ids."""
    if which == "practice":
        ev = set(split.select("practice", pages()))
    elif which == "heldout":
        ev = split.heldout_pages()
        if ev is None:
            raise SystemExit("held-out scoring needs the season seed (secrets/heldout_seed.json): scorer only")
    elif which == "all":
        return list(pages(translit)), list(pages(translit))
    else:
        raise ValueError(which)
    train = [p for p in pages(translit) if p.id not in ev]
    evalp = [p for p in pages(translit) if p.id in ev]
    return train, evalp


def lines(pgs, units=None):
    return [ln for p in pgs for ln in p.lines if (units is None or ln.unit in units) and ln.words]


def words(pgs, units=None, certain=False):
    out = []
    for ln in lines(pgs, units):
        out.extend(w for w in ln.words if not (certain and ivtff.uncertain(w)))
    return out
