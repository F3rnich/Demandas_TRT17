import os,re,json,subprocess,docx,sys
from datetime import date
ROOT='/home/claude/corpus'
MESES=['JANEIRO','FEVEREIRO','MARÇO','ABRIL','MAIO','JUNHO','JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO']
MN={m:i+1 for i,m in enumerate(MESES)}; MN['MARCO']=3
MESEXT={'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
TOK=re.compile(r'(?:R\$|CR\$|Cr\$|URV)?\s*-?\d{1,3}(?:\.\d{3})*,\d{1,2}|(?<![A-Za-zÀ-ú])X(?![A-Za-zÀ-ú])|(?:R\$|CR\$|Cr\$)\s*-(?=\s|$)|—|–')
def num(t):
    t=t.strip()
    if t in('X','—','–') or re.fullmatch(r'(R\$|CR\$|Cr\$)\s*-',t): return None
    m=re.search(r'-?\d{1,3}(?:\.\d{3})*,\d{1,2}',t); 
    return float(m.group(0).replace('.','').replace(',','.')) if m else None
def moeda(t):
    m=re.match(r'\s*(CR\$|Cr\$|URV|R\$)',t); return m.group(1) if m else ''
def meta_from_text(tx):
    md={}
    h=re.search(r'DATA DE IN[IÍ]CIO(.*?)(Ano:|JANEIRO)',tx,re.S)
    if h:
        ds=re.findall(r'(\d{1,2})[º°o]?/(\d{2})/(\d{4})',h.group(1))
        ds=sorted(set('%s-%s-%02d'%(y,m,int(d)) for d,m,y in ds))
        if ds: md['inicio']=ds[0]
        if len(ds)>1: md['fim']=ds[1]
        md['_hdr']=True

    m=re.search(r'IN[IÍ]CIO DA\s+(?:CONTRIBUI[ÇC][ÃA]O/ADMISS[ÃA]O:?)?.*?(\d{1,2})[º°o]?/(\d{2})/(\d{4})',tx,re.S)
    if m and not md.get('_hdr'): md['inicio']='%s-%s-%02d'%(m.group(3),m.group(2),int(m.group(1)))
    m=re.search(r'(?:EXONERA[ÇC][ÃA]O|VAC[ÂA]NCIA|DESLIGAMENTO|APOSENTADORIA)[^:]*:?\s*(\d{1,2})[º°o]?/(\d{2})/(\d{4})',tx,re.S)
    if m and not md.get('_hdr'): md['fim']='%s-%s-%02d'%(m.group(3),m.group(2),int(m.group(1)))
    m=re.search(r'REFERENTE\s+[ÀA]\s+(.{0,120}?)(?:\n|ÓRGÃO|$)',tx)
    if m: md['ref']=m.group(1).strip()
    ds=re.findall(r'Vit[óo]ria,\s*(\d{1,2})[º°]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})',tx,re.I)
    ds=[date(int(y),MESEXT.get(mm.lower(),1),int(d)) for d,mm,y in ds if mm.lower() in MESEXT]
    if ds: md['emissao']=max(ds).isoformat()
    m=re.search(r'CERTID[ÃA]O\s+[A-Z/ ]*N[°º]\s*(\d+/\d{4})',tx)
    if m: md['certidao']=m.group(1)
    m=re.search(r'NOME DO SERVIDOR:?\s*(?:\|\s*)?([A-ZÀ-Ú][A-ZÀ-Ú .\']{5,80}?)\s*(?:\||MATR|\n|$)',tx)
    if m: md['servidor']=m.group(1).strip()
    md['gn_titulo']=bool(re.search(r'GRATIFICA[ÇC][ÃA]O NATALINA',tx[:600]))
    return md
def parse_grid(rows):
    """rows: list of list of cell strings (first = label). Returns mensal, gn, moedas"""
    mensal={}; gn={}; moed={}; anos=[]
    for r in rows:
        lab=(r[0] or '').upper().strip()
        anosr=[int(x) for c in r for x in re.findall(r'Ano:\s*(\d{4})',c)]
        if anosr: anos=anosr; continue
        if not anos: continue
        lab1=re.sub(r'\s+',' ',lab)
        vals=r[1:]
        if lab1 in MN:
            for a,v in zip(anos,vals):
                x=num(v); 
                if x is not None: mensal['%d-%02d'%(a,MN[lab1])]=x; moed['%d-%02d'%(a,MN[lab1])]=moeda(v)
        elif 'NATALINA' in lab1 or '13' in lab1 or 'GRATIFICA' in lab1:
            for a,v in zip(anos,vals):
                x=num(v)
                if x is not None and str(a) not in gn: gn[str(a)]=x
    return mensal,gn,moed
def from_docx(p):
    d=docx.Document(p); tx='\n'.join(x.text for x in d.paragraphs)
    rows=[]
    for t in d.tables:
        for r in t.rows:
            seen=[]; cells=[]
            for c in r.cells:
                if c._tc in seen: continue
                seen.append(c._tc); cells.append(c.text.strip().replace('\n',' '))
            rows.append(cells); tx+='\n'+' | '.join(cells)
    m,g,mo=parse_grid(rows)
    return tx,m,g,mo
def from_pdf(p):
    tx=subprocess.run(['pdftotext','-layout',p,'-'],capture_output=True,text=True).stdout
    rows=[]; pend=None; gnp=0
    lines=tx.split('\n')
    for i,l in enumerate(lines):
        s=l.strip()
        if re.search(r'Ano:\s*\d{4}',s): rows.append(['']+re.findall(r'Ano:\s*\d{4}',s)); continue
        up=s.upper()
        mm=re.match(r'(JANEIRO|FEVEREIRO|MAR[ÇC]O|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\b(.*)',up)
        if mm:
            lab=mm.group(1).replace('MARCO','MARÇO'); rows.append([lab]+TOK.findall(s[len(mm.group(1)):])); continue
        if re.search(r'13º|GRATIFICA|NATALINA',up):
            toks=TOK.findall(re.sub(r'13º|13°','',s))
            if toks: rows.append(['GRATIFICAÇÃO NATALINA']+toks); gnp=0
            else: gnp=3
            continue
        if gnp>0:
            gnp-=1
            toks=TOK.findall(s)
            if toks and not re.search(r'[A-Za-z]{4}',re.sub(r'R\$|CR\$|Cr\$|URV','',s)): rows.append(['GRATIFICAÇÃO NATALINA']+toks); gnp=0
    m,g,mo=parse_grid(rows)
    return tx,m,g,mo

import pdfplumber
MESL=['JANEIRO','FEVEREIRO','MARÇO','MARCO','ABRIL','MAIO','JUNHO','JULHO','AGOSTO','SETEMBRO','OUTUBRO','NOVEMBRO','DEZEMBRO']
def from_pdf2(p):
    """grade mês × ano por posição: colunas pelos rótulos 'Ano: AAAA', linhas pela faixa vertical de cada mês"""
    mensal={}; gn={}; moed={}; tx=''
    with pdfplumber.open(p) as pdf:
        for pg in pdf.pages:
            t=pg.extract_text() or ''; tx+=t+'\n'
            ws=pg.extract_words(keep_blank_chars=False,use_text_flow=False,x_tolerance=1.5)
            # blocos: cada linha de "Ano:" inicia um bloco
            anos=[]
            for i,w in enumerate(ws):
                if w['text'].startswith('Ano:'):
                    y=w['text'][4:] or (ws[i+1]['text'] if i+1<len(ws) else '')
                    x1=w['x1'] if w['text'][4:] else ws[i+1]['x1']
                    if re.fullmatch(r'\d{4}',y): anos.append((w['top'],(w['x0']+x1)/2,int(y)))
            if not anos: continue
            tops=sorted(set(round(a[0]) for a in anos))
            blocos=[]
            for tp in tops:
                cols=sorted([(cx,y) for t0,cx,y in anos if abs(t0-tp)<3])
                blocos.append((tp,cols))
            for bi,(tp,cols) in enumerate(blocos):
                fimb=blocos[bi+1][0] if bi+1<len(blocos) else 1e9
                labs=[(w['top'],w['text'].upper()) for w in ws if tp<w['top']<fimb and w['x0']<cols[0][0]-30 and (w['text'].upper() in MESL or re.match(r'13|GRATIFICA|NATALINA',w['text'].upper()))]
                # rótulos de linha ordenados; GN = primeiro rótulo 13/GRATIFICA/NATALINA
                rows=[]
                for t0,l in sorted(labs):
                    if l in MESL: rows.append([t0,'M',MN.get(l.replace('MARCO','MARÇO'),3)])
                    elif not any(r[1]=='G' for r in rows): rows.append([t0,'G',None])
                if not rows: continue
                # faixa de cada linha: do meio entre o rótulo anterior e este até o meio com o próximo
                for i,r in enumerate(rows):
                    a=(rows[i-1][0]+r[0])/2 if i else r[0]-8
                    b=(r[0]+rows[i+1][0])/2 if i+1<len(rows) else (r[0]+30 if r[1]=='G' else r[0]+14)
                    toks=[w for w in ws if a<=w['top']<b and w['x0']>cols[0][0]-70]
                    porcol={}
                    for w in toks:
                        cx=(w['x0']+w['x1'])/2; c=min(cols,key=lambda c:abs(c[0]-cx))
                        porcol.setdefault(c[1],[]).append(w['text'])
                    for y,tt in porcol.items():
                        s2=' '.join(tt); m=re.search(r'-?\d{1,3}(?:\.\d{3})*,\d{1,2}',s2)
                        if not m: continue
                        v=float(m.group(0).replace('.','').replace(',','.'))
                        if r[1]=='M':
                            k='%d-%02d'%(y,r[2]); mensal[k]=v; mo=re.search(r'(CR\$|Cr\$|URV|R\$)',s2); 
                            if mo: moed[k]=mo.group(1)
                        else: gn[str(y)]=v
    return tx,mensal,gn,moed
def scan():
    out=[]
    for d,_,fs in os.walk(ROOT):
        for f in fs:
            p=os.path.join(d,f); e=f.lower().rsplit('.',1)[-1]
            if e not in('docx','pdf'): continue
            try:
                if e=='docx': tx,m,g,mo=from_docx(p)
                else:
                    tx,m,g,mo=from_pdf(p)
                    if re.search(r'BASES DE C[ÁA]LCULO|REMUNERA[ÇC][ÕO]ES DE CONTRIBUI',tx[:3000],re.I):
                      try:
                        _,m2,g2,mo2=from_pdf2(p); m.update(m2); g.update(g2); mo.update(mo2)
                      except Exception: pass
            except Exception as ex: continue
            if not re.search(r'BASES DE C[ÁA]LCULO|REMUNERA[ÇC][ÕO]ES DE CONTRIBUI|GRATIFICA[ÇC][ÃA]O NATALINA',tx[:3000],re.I): continue
            if not m and not g: continue
            md=meta_from_text(tx); md.update(arquivo=os.path.relpath(p,ROOT),fmt=e,n_mes=len(m),n_gn=len(g),sem_efeito='SEM_EFEITO' in f.upper() or 'SEM EFEITO' in tx.upper()[:2000])
            md['mensal']=m; md['gn']=g; md['moeda']={k:v for k,v in mo.items() if v and v!='R$'}
            out.append(md)
    return out
if __name__=='__main__':
    o=scan(); json.dump(o,open('/home/claude/work/golds.json','w'),ensure_ascii=False,indent=0)
    for x in sorted(o,key=lambda x:x['arquivo']): print(x['fmt'],x['n_mes'],x['n_gn'],x.get('emissao'),x.get('inicio'),x.get('fim'),'SEMEF' if x['sem_efeito'] else '',x['arquivo'][-95:])
