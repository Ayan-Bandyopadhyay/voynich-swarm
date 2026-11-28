"""Public-practice calibration for directional_pairs and filtered_vocab.

This uses fixed 3,000/9,000-token windows and public practice-training line-run
shapes. It is an exploratory sensitivity check, not a registered held-out fact.
Run: python3 tools/calibrate_directional_pairs.py > calibration.json
"""
import hashlib
import json
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from vs import corpus, dsl, refcorpus
from vs.ivtff import Line, Page

SIZES=(3000,9000)
LANGUAGES=('latin','italian','english','medieval_czech')
SEEDS=(31,57,83)
SHUFFLES=10
PAIR={'directional_pairs':{'window':3,'drop_top':1,'excess':5}}
TYPE={'filtered_vocab':{'measure':'type_token','drop_top':1}}
SINGLE={'filtered_vocab':{'measure':'singleton_token','drop_top':1}}


def layout(witness, size):
    train,_=corpus.split_pages('practice',witness)
    selected=dsl.select(dsl.tokens(train),{'unit':['P']})
    runs=dsl.runs_of(selected)
    lens=[]; remaining=size
    for run in runs:
        if not remaining: break
        take=min(len(run),remaining);lens.append(take);remaining-=take
    if remaining:raise ValueError('insufficient training tokens')
    return lens, [t['w'] for run in runs for t in run][:size]


def page(words, lens):
    p=Page('synthetic',0,{'I':'H','L':'A','H':'1'});i=0
    for j,n in enumerate(lens):
        p.lines.append(Line(f'synthetic.{j}',p.id,j,'P','0',words[i:i+n],False,False));i+=n
    assert i==len(words)
    return p


def cipher(words, mode, seed):
    rng=random.Random(seed); alphabet=sorted(set(''.join(words)))
    labels=[f'g{i:04d}' for i in range(3*len(alphabet))];rng.shuffle(labels)
    key={ch:labels[i*3:(i+1)*3] for i,ch in enumerate(alphabet)}
    return [''.join(key[ch][0 if mode=='simple' else rng.randrange(3)] for ch in w) for w in words]


def score(words,lens):
    ts=dsl.tokens([page(words,lens)])
    a=dsl.statistic(PAIR,ts,ts);b=dsl.statistic(TYPE,ts,ts);c=dsl.statistic(SINGLE,ts,ts)
    if any(x!=x for x in (a,b,c)):raise ValueError('undefined sample')
    return {'directional_pairs':a,'type_token':b,'singleton_token':c,
            'support':dsl._directional_pair_counts(ts,PAIR['directional_pairs'])}


def trial(words,lens,seed):
    rows={}; transformed={'plain':words,'simple':cipher(words,'simple',seed),'homophonic':cipher(words,'homophonic',seed)}
    for mode,ws in transformed.items():
        result=score(ws,lens);null=[]
        for i in range(SHUFFLES):
            shuffled=ws[:];random.Random(f'{seed}/{mode}/{i}').shuffle(shuffled)
            null.append(score(shuffled,lens)['directional_pairs'])
        result['global_shuffle_mean']=statistics.mean(null);result['global_shuffle_min']=min(null);result['global_shuffle_max']=max(null)
        rows[mode]=result
    for k in ('directional_pairs','type_token','singleton_token'):
        assert rows['plain'][k]==rows['simple'][k],(k,rows)
    return rows


def synthetic_calibration():
    """A strong repeated A-before-B signal and an iid finite-sample null."""
    spec={'statistic':{'directional_pairs':{'window':1,'drop_top':0,'excess':5}},
          'compare':[{'null':'shuffle_within_line','perms':99,'p':.01,'direction':'greater'}]}
    result={}
    for mode in ('planted','iid'):
        counts={'pass':0,'fail':0,'refused_inert':0}
        for seed in range(2000,2020):
            rng=random.Random(seed); p=Page('toy',0,{'I':'H','L':'A','H':'1'})
            pool=[f'w{i}' for i in range(80)]
            for i in range(20):
                if mode=='planted':
                    order=list(range(40));rng.shuffle(order)
                    ws=[word for k in order for word in (f'w{2*k}',f'w{2*k+1}')]
                else:
                    ws=[rng.choice(pool) for _ in range(80)]
                p.lines.append(Line(f'toy.{i}',p.id,i,'P','0',ws,False,False))
            try:
                verdict=dsl.evaluate(spec,[p])['pass']
                counts['pass' if verdict else 'fail']+=1
            except dsl.SpecError as exc:
                if 'cannot move' not in str(exc):raise
                counts['refused_inert']+=1
        result[mode]=counts
    return {'spec':spec,'trials_per_mode':20,'seed_start':2000,'results':result}


def main():
    with open('pins/sources.json', encoding='utf-8') as f:
        pins=json.load(f)
    required=[e for e in pins['sources'] if e['id'] in ('zl','it')]
    required += [e for e in pins['reference_corpora'] if e['lang'] in LANGUAGES and not e.get('skip_reason')]
    for entry in required:
        with open(entry['file'],'rb') as f:
            assert hashlib.sha256(f.read()).hexdigest()==entry['sha256'], entry['id']
    out={'sizes':SIZES,'languages':LANGUAGES,'seeds':SEEDS,'shuffles':SHUFFLES,
         'pair':PAIR,'type':TYPE,'singleton':SINGLE,'natural':{},'witnesses':{}}
    out['synthetic']=synthetic_calibration()
    for size in SIZES:
        lens,_=layout('zl',size);out['natural'][size]={}
        for lang in LANGUAGES:
            source=' '.join(refcorpus.train_text(lang)).split()
            assert len(source)>=size*len(SEEDS)
            out['natural'][size][lang]=[trial(source[i*size:(i+1)*size],lens,seed) for i,seed in enumerate(SEEDS)]
        for witness in ('zl','it'):
            wlens,ws=layout(witness,size)
            out['witnesses'].setdefault(witness,{})[size]=trial(ws,wlens,SEEDS[0])
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
