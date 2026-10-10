import json,re,itertools,collections,unicodedata,os
cases=json.load(open('cases.json'))
def n(s): return re.sub(r'[^A-Z ]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().upper())
REMUN=['VB','DIF2886','GEXTRA','GAJ','APJ','REDUTOR','ATS','VPI','VPI_DED','VPNI','VPNI_JUD','FC','SUBST','V1323_VB','V1323_GAJ','V1323_ATS','V1323_VPNI','V1323_FC','AQ','AQ_TREIN','GAE','GAS','FALTAS','V1198','CLASSIFICAR']
def pick_gold(c):
    gs=[g for g in c['golds'] if (not g.get('servidor') or len(set(n(c['nome']).split())&set(n(g['servidor']).split()))>=2) and g.get('emissao')]
    if not gs: return None
    gs.sort(key=lambda g:(g['emissao'],g['n_mes']+g['n_gn'],g['fmt']=='docx'))
    return gs[-1]
golds={x['arquivo']:x for x in json.load(open('golds.json'))}
XLS=json.load(open('golds_xls.json'))
# agrupa por pessoa
pessoas=collections.defaultdict(list)
for c in cases: pessoas[n(c['nome']).strip()].append(c)
out=[]
for p,cs in pessoas.items():
    gl=[(pick_gold(c),c) for c in cs]; gl=[x for x in gl if x[0]]
    if gl:
        g,c=max(gl,key=lambda x:x[0]['emissao'])
        G=golds[g['arquivo']]
    else:
        # sem certidão legível: planilha de trabalho da DIPROF (coluna "Remuneração")
        tok=set(w for w in n(cs[0]['nome']).split() if len(w)>2)
        xs=[x for x in XLS if any(x['arquivo'].startswith(cc['pasta']+'/') for cc in cs) and len(tok & set(n(x.get('titulo','')).split()))>=2]
        if not xs: continue
        G=max(xs,key=lambda x:(bool(re.search(r'/(1\.|ultima)',x['arquivo'],re.I)),x['mtime'],len(x['mensal'])))
        c=next(cc for cc in cs if G['arquivo'].startswith(cc['pasta']+'/'))
        g={'arquivo':G['arquivo'],'fmt':'planilha','emissao':None,'inicio':None,'fim':None}
    recs=[]
    for cc in cs:
        f='recs/%s.json'%cc['id']
        if os.path.exists(f): recs+=json.load(open(f))['recs']
    # dedup
    seen=set(); R=[]
    for r in recs:
        k=(r['comp'],r['folha'],r.get('tipoFolha'),r['cod'],r['seq'],round(r['v'],2),r.get('pago'))
        if k in seen: continue
        seen.add(k); R.append(r)
    out.append(dict(pessoa=p,case=c['id'],nome=c['nome'],tags=sorted(set(t for cc in cs for t in cc['tags'])),preparo=c['preparo'],gold=g,mensal=G['mensal'],gn=G['gn'],moeda=G.get('moeda',{}),recs=R))
json.dump(out,open('dataset.json','w'),ensure_ascii=False)
print(len(out),'pessoas com gabarito;', sum(len(x['mensal']) for x in out),'meses;',sum(len(x['gn']) for x in out),'GN')
