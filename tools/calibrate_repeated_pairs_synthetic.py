import json,random
from vs import dsl
from tests.test_dsl import page
s={'select':{'unit':['P'],'certain':True},'statistic':{'repeated_pair_types':True},'compare':[{'null':'shuffle_within_line','perms':39,'p':.05}]}
out={}
for mode in ('null','motif'):
 a=[]
 for seed in range(20):
  r=random.Random(seed)
  base=[[f'a{i}',f'b{i}',f'c{i}',f'd{i}'] for i in range(50)]
  for row in base:r.shuffle(row)
  lines=[row[:] for row in base for _ in range(3)]
  if mode=='null':
   for row in lines:r.shuffle(row)
  v=dsl.evaluate(s,[page('p',lines)]); a.append(v['detail']['shuffle_within_line']['p'])
 out[mode]={'passes':sum(p<=.05 for p in a),'p':a}
print(json.dumps(out))
