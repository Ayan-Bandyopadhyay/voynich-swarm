"""Small synthetic calibration for the matched-rightwardness page bootstrap.

Run from the repo root, e.g. python3 tools/calibrate_rightwardness.py --pages 30 --trials 200.
This only tests an independent-coin null and one strong alternative; it is not a general
coverage proof. Pages have 16 independent lines of five tokens, with a matched pair at
positions 1 and 3; under the null their order is random. The two groups always have equal
frequency, unlike real samples with sparse or page-dependent vocabulary.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vs import dsl
from vs.ivtff import Line, Page


def book(npages, seed, effect):
    rng = random.Random(seed)
    pages = []
    for i in range(npages):
        p = Page(f'f{i}r', i, {'I': 'H', 'L': 'A', 'H': '1'})
        for j in range(16):
            a, b = 'shedy', 'chedy'
            if not effect and rng.randrange(2):
                a, b = b, a
            ws = ['xx', a, 'xx', b, 'xx']
            p.lines.append(Line(f'{p.id}.{j}', p.id, j, 'P', '0', ws, False, False))
        pages.append(p)
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', type=int, default=30)
    parser.add_argument('--trials', type=int, default=100)
    parser.add_argument('--seed', type=int, default=1000)
    args = parser.parse_args()
    if args.pages < 10 or args.trials < 1:
        parser.error('need at least ten pages and one trial')
    spec = {'statistic': {'matched_rightwardness': {'contrast': 'sh/ch', 'min_line': 5, 'max_line': 5}},
            'compare': [{'page_bootstrap': 'lower', 'value': 0}]}
    result = {'pages': args.pages, 'trials': args.trials, 'seed_start': args.seed, 'pass_counts': {}}
    for effect in (False, True):
        verdicts = [dsl.evaluate(spec, book(args.pages, args.seed + i, effect))['pass'] for i in range(args.trials)]
        result['pass_counts']['strong_effect' if effect else 'iid_null'] = sum(verdicts)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
