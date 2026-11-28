import json
from vs import corpus,dsl,generators,ivtff
spec={'select':{'unit':['P'],'certain':True},'statistic':{'repeated_pair_types':True},'compare':[{'null':'shuffle_within_line','perms':39,'p':.05,'direction':'greater'}]}
out={}
for tr in ('zl','it'):
 train,ev=corpus.split_pages('practice',tr)
 tests={'manuscript':[ev]}
 for name,fn in [('self_citation',generators.g_self_citation),('grille',generators.g_grille),('line_chain',generators.g_line_chain)]:
  tests[name]=[fn(train,ev,seed=n) for n in range(1,6)]
  for generated in tests[name]:
   for src, dst in zip(ev, generated):
    for a,b in zip(src.lines,dst.lines):
     b.words=[x if not x or ivtff.uncertain(x) else y for x,y in zip(a.words,b.words)]
 out[tr]={}
 for name,sets in tests.items():
  vals=[]
  for pages in sets:
   try:
    r=dsl.evaluate(spec,pages); vals.append({'value':r['value'],'p':r['detail']['shuffle_within_line']['p']})
   except dsl.SpecError as e: vals.append({'error':str(e)})
  out[tr][name]=vals
  print(tr,name,vals,flush=True)
print(json.dumps(out, indent=2))
