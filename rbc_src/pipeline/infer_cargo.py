import json,collections,os
b=json.load(open('/home/claude/Demandas_TRT17/rbc_src/calc/base_calc.json'))
MAP={'NÍVEL AUXILIAR':'AUXILIAR JUDICIÁRIO','NÍVEL INTERMEDIÁRIO':'TÉCNICO JUDICIÁRIO','NÍVEL SUPERIOR':'ANALISTA JUDICIÁRIO','ANALISTA JUDICIÁRIO':'ANALISTA JUDICIÁRIO','TÉCNICO JUDICIÁRIO':'TÉCNICO JUDICIÁRIO','AUXILIAR JUDICIÁRIO':'AUXILIAR JUDICIÁRIO'}
VB=collections.defaultdict(list)
for i,f,lv,cl,pd,campo,v,_ in b['serv']:
    if campo=='VB': VB[round(v,2)].append((i,f,MAP.get(lv,lv)))
D={x['case']:x for x in json.load(open('dataset.json'))}
for cid in sorted(d for d in os.listdir('casos') if os.path.isdir('casos/'+d)):
    cj=json.load(open('casos/%s/caso.json'%cid)); x=D[cid]
    votes=collections.Counter()
    for r in x['recs']:
        if r['cat']=='VB' and r['folha']=='N':
            for i,f,cg in VB.get(round(r['v'],2),[]):
                if i<=r['comp']+'-15'<=f: votes[cg]+=1
    best=votes.most_common(1)[0][0] if votes else ''
    cur=cj['servidor']['cargo']
    if 'MAGISTRADO' in cj['meta']['tags']: best='MAGISTRADO'
    if best and best!=cur:
        print(cid,cj['meta']['nome'][:28],'|',cur,'->',best,dict(votes))
        cj['servidor']['cargo']=best
    cj['servidor']['cargoVotos']=dict(votes)
    json.dump(cj,open('casos/%s/caso.json'%cid,'w'),ensure_ascii=False,indent=1)
