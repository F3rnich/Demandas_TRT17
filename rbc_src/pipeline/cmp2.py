import json,sys
A=json.load(open(sys.argv[1])); B=json.load(open(sys.argv[2]))
reg=[];gan=[]
for c in sorted(set(A)|set(B)):
  a=set(A.get(c,{}).get('mesesIguais',[])); b=set(B.get(c,{}).get('mesesIguais',[]))
  if a-b: reg.append((c,sorted(a-b)[:6],len(a-b)))
  if b-a: gan.append((c,len(b-a)))
print('ganhos',sum(x[1] for x in gan),gan); print('REGRESSOES',sum(x[2] for x in reg)); [print('  ',r) for r in reg]
