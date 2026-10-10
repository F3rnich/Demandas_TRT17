import os,re,json,unicodedata,hashlib
ROOT='/home/claude/corpus'
golds=json.load(open('golds.json'))
def norm(s): return re.sub(r'\s+',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()).strip()
cases=[]
for par in sorted(os.listdir(ROOT)):
    for c in sorted(os.listdir(os.path.join(ROOT,par))):
        d=os.path.join(ROOT,par,c)
        if not os.path.isdir(d): continue
        files=[os.path.relpath(os.path.join(a,f),ROOT) for a,_,fs in os.walk(d) for f in fs]
        nome=re.sub(r'^(RBC|RCP|CTC|RRC)( e (RBC|RCP))?(- INSS)?\s*-?\s*(RCP\s*-\s*)?','',c).strip()
        nome=re.split(r'\s+-\s+|\s+\d{4}\s+a|\s+T[ée]cnico|\s+Lan[cç]|\s+Calc|\s+Conf|\s+CTC',nome)[0].strip()
        tags=[]
        for k,rx in [('GN','\\bGN\\b|NATALINA'),('MAGISTRADO','JUIZ'),('CLASSISTA','CLASSISTA'),('TETO','TETO'),('NAOFEZ','NAO FEZ'),('SEMONUS','SEM ONUS'),('DECLCOMPL','DECLARACAO COMPLEMENTAR'),('REVISAO','REVIS|RETIFIC|REEMITID|ALTERACAO|REFEITA|REFERENTE A CTC')]:
            if re.search(rx,norm(c)): tags.append(k)
        prep=re.findall(r'(Lan[cç]|Calc|Conf)\s*([A-Z][a-z]?)',c)
        g=[x for x in golds if x['arquivo'].startswith(os.path.relpath(d,ROOT)+'/') and not x['sem_efeito']]
        fichas=[f for f in files if re.search(r'ficha|big grid|holerite',norm(os.path.basename(f)).lower()) and f.lower().endswith(('.xls','.xlsx','.pdf'))]
        ctcs=[f for f in files if re.search(r'CTC|DTC|TEMPO.DE.CONTRIB|DECLARACAO',norm(os.path.basename(f))) and f.lower().endswith('.pdf') and not re.search(r'E-?MAIL|RBC|RRC',norm(os.path.basename(f)))]
        trab=[f for f in files if re.search(r'RBC|RRC|MEMORIA',norm(os.path.basename(f))) and f.lower().endswith(('.xls','.xlsx'))]
        cases.append(dict(id=hashlib.md5(c.encode()).hexdigest()[:6],pasta=os.path.relpath(d,ROOT),nome=nome,pessoa=norm(nome),tags=tags,preparo=['%s%s'%p for p in prep],golds=[{k:x.get(k) for k in('arquivo','fmt','emissao','inicio','fim','n_mes','n_gn','ref','servidor')} for x in g],fichas=fichas,ctcs=ctcs,trabalho=trab,n_arq=len(files)))
json.dump(cases,open('cases.json','w'),ensure_ascii=False,indent=1)
for x in cases: print(x['id'],len(x['golds']),len(x['fichas']),len(x['ctcs']),len(x['trabalho']),','.join(x['tags']),'|',x['nome'][:40],'|',' '.join(x['preparo']))
