"""Voynich Swarm -- mechanical judges for claims about Beinecke MS 408.

Standard library only, so the season environment is just a pinned Python.
"""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON = "S2"


def path(*p):
    return os.path.join(ROOT, *p)
