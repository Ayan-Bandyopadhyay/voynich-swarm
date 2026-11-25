"""The status of a language x cipher cell, derived from the record and the test's calibration.

  PASS          a key in this cell passes the full test (held for human release)
  OPEN          a key passes compression, reading and the kill tests (needs anchors)
  RULED OUT     a key failed, its search used the pinned budget or more, and the same search at
                the pinned budget cracks this language's positive control
                (results/heldout/controls.json): the search works here, so the failure means
                something. For verbose ciphers, power is demonstrated for 2-glyph units only.
  INCONCLUSIVE  keys failed, but the search has no demonstrated power in this cell
  UNTESTED      no key yet
"""
import json, os
from . import path, registry, search


def _power():
    fn = path("results", "heldout", "controls.json")
    if not os.path.exists(fn):
        return {}
    return {(r["language"], r["family"]): r["search_cracks_control"] for r in json.load(open(fn))}


def cell_status(lang, fam, items=None, power=None):
    items = [i for i in (items if items is not None else registry.read("grid")) if i.get("language") == lang and i.get("family") == fam]
    if not items:
        return "UNTESTED", []
    power = power if power is not None else _power()
    if any(i["verdict"] == "PASS" for i in items):
        return "PASS", items
    if any(i["verdict"] == "OPEN" for i in items):
        return "OPEN", items
    pinned = dict(search.BUDGET)

    def at_least_pinned(b):
        """Same search (seed, merges, segmentation hypotheses) at the pinned budget or more."""
        if not b:
            return False
        for k, v in pinned.items():
            if k in ("restarts", "iterations"):
                if (b.get(k) or 0) < v:
                    return False
            elif k.startswith("verbose_"):
                if fam != "verbose":
                    continue  # verbose-only settings do not bear on other families
                if k == "verbose_segmentations":
                    if not set(v) <= set(b.get(k) or []):
                        return False
                elif b.get(k) != v:
                    return False
            elif b.get(k) != v:
                return False
        return True
    for i in items:
        if i["verdict"] == "FAIL" and at_least_pinned(i.get("budget")) and power.get((lang, fam)):
            return "RULED OUT", items
    return "INCONCLUSIVE", items
