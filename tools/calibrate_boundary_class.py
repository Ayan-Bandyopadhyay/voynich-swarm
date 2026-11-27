"""Small deterministic boundary-class checks; not a general power assessment.

Run from the repo root with PYTHONPATH=. python3 tools/calibrate_boundary_class.py.
Uses pinned public reference corpora and synthetic words only, not manuscript pages.
"""
from random import Random
from vs import dsl, refcorpus
from vs.ivtff import Line, Page


def page(pid, lines):
    p = Page(pid, 0, {'I': 'H', 'L': 'A', 'H': '1'})
    p.lines = [Line(f'{pid}.{i}', pid, i, 'P', '0', words, False, False)
               for i, words in enumerate(lines)]
    return p


def chunks(words, n=8):
    return [words[i:i+n] for i in range(0, len(words), n)]


def main():
    spec = {'select': {'unit': ['P']}, 'statistic': {'boundary_class_rate': True},
            'compare': [{'null': 'shuffle_within_line', 'perms': 99, 'p': .05}]}
    train = [page('train', [['qa', 'ay']] * 100)]
    for planted in (False, True):
        passes = 0
        for seed in range(20):
            rng = Random(seed)
            lines = []
            for _ in range(50):
                line = ['ay', 'qa'] * 4
                if not planted:
                    rng.shuffle(line)
                lines.append(line)
            passes += dsl.evaluate(spec, [page('eval', lines)], train)['pass']
        print('planted' if planted else 'independent_null', passes, '/ 20')
    for language in ('latin', 'italian', 'english'):
        tr = ' '.join(refcorpus.train_text(language)).split()[:3000]
        ev = ' '.join(refcorpus.control_text(language)).split()[:1000]
        r = dsl.evaluate(spec, [page('eval', chunks(ev))], [page('train', chunks(tr))])
        print(language, 'rate', r['value'], 'p', r['detail']['shuffle_within_line']['p'],
              'pairs', r['detail']['boundary_class_rate']['pairs'],
              'unknown', r['detail']['boundary_class_rate']['unknown_pairs'])


if __name__ == '__main__':
    main()
