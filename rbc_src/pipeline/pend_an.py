import json,sys
R=json.load(open(sys.argv[1]))
def addm(k,n):
    y,m=int(k[:4]),int(k[5:]); t=y*12+m-1+n; return '%04d-%02d'%(t//12,t%12+1)
tot=0;exp=0
for c,r in sorted(R.items()):
  u=r.get('uso')
  if not u or not u['pend']: continue
  res={d['mes']:round(d['dip']-d['calc'],2) for d in r['divergencias']}
  iguais=set(r['mesesIguais'])
  # agrupa pend por mês
  by={}
  for comp,cat,v,mot in u['pendL']: by.setdefault(comp,[]).append((cat,v))
  for comp,l in by.items():
    tot+=1
    s=sum(v for _,v in l)
    found=None
    for back in range(0,37):
      for ln in range(1,25):
        st=addm(comp,-back-ln+1) if False else None
      break
    # janela [a..b] com b<=comp
    for b in range(0,6):
      kb=addm(comp,-b); acc=0
      for ln in range(0,36):
        k=addm(kb,-ln)
        acc+=res.get(k,0)
        if abs(acc-s)<=max(0.1,abs(s)*0.01) and res.get(k,0)!=0: found=(k,kb,round(acc,2)); break
      if found: break
    # mês da própria comp igual? (já certo sem o valor) 
    st='igual' if comp in iguais else ('div %.2f'%res[comp] if comp in res else 'fora')
    if found: exp+=1
    print(c,comp,[(a,round(v,2)) for a,v in l],'soma',round(s,2),'| mês:',st,'| janela:',found)
print(tot,exp)
