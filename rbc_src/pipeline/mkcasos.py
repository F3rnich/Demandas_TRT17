import json,os,re,subprocess,unicodedata,calendar,collections
D=json.load(open('dataset.json')); C={c['id']:c for c in json.load(open('cases.json'))}
ROOT='/home/claude/corpus'; OUT='/home/claude/work/casos'
def n(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().upper()
def ctc_text(c):
    t=''
    for f in c['ctcs']:
        t+=subprocess.run(['pdftotext','-layout',os.path.join(ROOT,f),'-'],capture_output=True,text=True).stdout
    return n(t)
os.makedirs(OUT,exist_ok=True)
resumo=[]
for x in D:
    cid=x['case']; c=C[cid]
    pessoa_cases=[cc for cc in C.values() if n(cc['nome']).strip()==n(c['nome']).strip()] or [c]
    fichas=[]
    for cc in pessoa_cases:
        p='recs/%s.json'%cc['id']
        if not os.path.exists(p): continue
        for l in json.load(open(p))['log']:
            if 'comps novas' in l: fichas.append(l.split(': ')[0])
    ks=sorted(k for k,v in x['mensal'].items() if v>0)
    if not ks: continue
    g=x['gold']; ini=g.get('inicio') or ''; fim=g.get('fim') or ''
    if not ini or ini[:7]!=ks[0]: ini=ks[0]+'-01'
    if not fim or fim[:7]!=ks[-1]:
        y,m=map(int,ks[-1].split('-')); fim='%s-%02d'%(ks[-1],calendar.monthrange(y,m)[1])
    txt=n(c['pasta'])+' '+ctc_text(c)
    recs=x['recs']; cats=collections.Counter(r['cat'] for r in recs)
    descs=' '.join(set(n(r['desc']) for r in recs))
    cargo=''
    m=re.search(r'CARGO( EFETIVO)?:?\s*\|?\s*(ANALISTA|TECNICO|AUXILIAR|JUIZ)',txt)
    if m: cargo=m.group(2)
    elif re.search(r'\bANAL',n(c['pasta'])): cargo='ANALISTA'
    elif re.search(r'\bTEC|AUX-TEC|AGENTE',n(c['pasta'])): cargo='TECNICO'
    elif re.search(r'ANALISTA JUDICIARIO',txt): cargo='ANALISTA'
    elif re.search(r'TECNICO JUDICIARIO',txt): cargo='TECNICO'
    elif re.search(r'AUXILIAR JUDICIARIO',txt): cargo='AUXILIAR'
    cargo={'ANALISTA':'ANALISTA JUDICIÁRIO','TECNICO':'TÉCNICO JUDICIÁRIO','AUXILIAR':'AUXILIAR JUDICIÁRIO','JUIZ':'JUIZ','':''}[cargo]
    esp=''
    if cats.get('GAE') or re.search(r'OFICIAL',n(c['pasta'])): esp='OFICIAL'
    if cats.get('GAS') or re.search(r'AGENTE|SEGURANCA',n(c['pasta'])): esp='SEGURANCA'
    d=os.path.join(OUT,cid); os.makedirs(d,exist_ok=True)
    for f in os.listdir(d):
        if f.startswith('f') and os.path.islink(os.path.join(d,f)): os.remove(os.path.join(d,f))
    nomes=[]
    for i,f in enumerate(fichas):
        ext=f.rsplit('.',1)[-1].lower(); nm='f%02d.%s'%(i,ext); os.symlink(os.path.join(ROOT,f),os.path.join(d,nm)); nomes.append(nm)
    json.dump({'mensal':{k:x['mensal'][k] for k in ks},'gn':x['gn'],'moeda':x.get('moeda',{}),'arquivo':g['arquivo']},open(os.path.join(d,'gabarito.json'),'w'),ensure_ascii=False)
    caso={'servidor':{'cargo':cargo,'especialidade':esp,'inicio':ini,'fim':fim},'fichas':nomes,'rbc':{'json':'gabarito.json'},'meta':{'nome':x['nome'],'tags':x['tags'],'preparo':x['preparo']}}
    json.dump(caso,open(os.path.join(d,'caso.json'),'w'),ensure_ascii=False,indent=1)
    resumo.append((cid,x['nome'][:28],cargo,esp,ini,fim,len(nomes)))
for r in resumo: print(*r)
