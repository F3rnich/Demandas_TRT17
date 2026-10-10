import json,sys,collections,os
D={x['case']:x for x in json.load(open('dataset.json'))}
FORA={'03000a','b3f006','fb3920'}
def tipo(cid):
    p='casos/%s/caso.json'%cid
    return json.load(open(p))['meta'].get('gabarito','?') if os.path.exists(p) else '?'
def resumo(fres, rot):
    R=json.load(open(fres)); t=collections.Counter()
    for cid,r in R.items():
        if cid in FORA or cid not in D: continue
        g='cert' if tipo(cid) in('docx','pdf') else 'plan'
        if 'falha' in r: t[g+'falha']+=1; continue
        com=set(rec['comp'] for rec in D[cid]['recs'])
        iguais=set(r['mesesIguais'])
        for k in iguais|set(d['mes'] for d in r['divergencias']):
            f=g+('_com' if k in com else '_sem'); t[f+'_tot']+=1; t[f+'_ok']+=k in iguais
        if r.get('gn'): t[g+'gn_tot']+=r['gn']['total']; t[g+'gn_ok']+=r['gn']['iguais']
    pc=lambda a,b: '%d/%d (%.1f%%)'%(t[a],t[b],100*t[a]/max(1,t[b]))
    for g in ('cert','plan'):
        print(rot.ljust(10),g,'com ficha',pc(g+'_com_ok',g+'_com_tot'),'| sem ficha',pc(g+'_sem_ok',g+'_sem_tot'),'| GN',pc(g+'gn_ok',g+'gn_tot'),'| falhas',t[g+'falha'])
for f,r in zip(sys.argv[1::2],sys.argv[2::2]): resumo(f,r)
