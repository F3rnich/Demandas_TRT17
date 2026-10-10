import json,itertools,collections,sys
import sys
R=json.load(open(sys.argv[1] if len(sys.argv)>1 else 'casos/_resultado.json')); D={x['case']:x for x in json.load(open('dataset.json'))}
REM=set(['VB','DIF2886','GEXTRA','GAJ','APJ','REDUTOR','ATS','VPI','VPI_DED','VPNI','VPNI_JUD','FC','SUBST','V1323_VB','V1323_GAJ','V1323_ATS','V1323_VPNI','V1323_FC','AQ','AQ_TREIN','GAE','GAS','FALTAS','V1198','CLASSIFICAR'])
causas=collections.Counter(); ex=collections.defaultdict(list); flips=collections.Counter()
for cid,r in R.items():
    if 'falha' in r: continue
    x=D[cid]; by=collections.defaultdict(lambda:collections.defaultdict(float)); has=set()
    for q in x['recs']:
        has.add(q['comp'])
        if q['cat'] in REM and q['folha']=='N' and q['seq']==0: by[q['comp']][q['cat']]+=q['v']
    for dv in r['divergencias']:
        k=dv['mes']; d=dv['dif']
        if dv['calc'] in (None,0): c='sem_calculo'
        elif k not in has: c='sem_ficha'
        else:
            items=[(a,round(v,2)) for a,v in by[k].items() if abs(v)>0.005]
            c=None
            for m in (1,2):
                for comb in itertools.combinations(items,m):
                    s=sum(v for _,v in comb)
                    if abs(abs(d)-abs(s))<=0.05:
                        c=('sobra_' if d>0 else 'falta_')+'+'.join(sorted(a for a,_ in comb)); break
                if c: break
            if not c:
                rel=abs(d)/max(dv['dip'],1)
                c='centavos' if abs(d)<=1 else ('pequena<2%' if rel<0.02 else 'grande')
        era='<1994-07' if k<'1994-07' else '1994-2001' if k<'2002' else '2002-2012' if k<'2013' else '2013+'
        causas[(era,c)]+=1; ex[(era,c)].append((cid,k,d))
for (era,c),n in sorted(causas.items(),key=lambda x:-x[1])[:60]:
    cs=collections.Counter(e[0] for e in ex[(era,c)])
    print(str(n).rjust(4),era.ljust(10),c.ljust(28),dict(cs.most_common(5)))
