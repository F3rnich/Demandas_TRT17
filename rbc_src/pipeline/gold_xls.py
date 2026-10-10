import os,re,json,xlrd,openpyxl,datetime,warnings
warnings.filterwarnings('ignore')
ROOT='/home/claude/corpus'
def rows_of(p):
    out=[]
    if p.lower().endswith('.xls'):
        b=xlrd.open_workbook(p)
        for sh in b.sheets(): out.append((sh.name,[sh.row_values(r) for r in range(sh.nrows)],b.datemode))
    else:
        wb=openpyxl.load_workbook(p,data_only=True,read_only=True)
        for ws in wb.worksheets: out.append((ws.title,[list(r) for r in ws.iter_rows(values_only=True)],0))
    return out
def mes(v,dm):
    if isinstance(v,datetime.datetime): return '%d-%02d'%(v.year,v.month)
    if isinstance(v,(int,float)) and 20000<v<60000:
        d=datetime.datetime(1899,12,30)+datetime.timedelta(days=v); return '%d-%02d'%(d.year,d.month)
    if isinstance(v,str):
        m=re.match(r'^\s*(\d{1,2})/(\d{4})\s*$',v)
        if m: return '%s-%02d'%(m.group(2),int(m.group(1)))
    return None
def parse(p):
    best=None
    for nome,rows,dm in rows_of(p):
        for i,r in enumerate(rows[:40]):
            cells=[str(x or '').strip().lower() for x in r]
            if not cells or not re.match(r'^m[eê]s',cells[0] if cells else ''): continue
            cr=[j for j,c in enumerate(cells) if re.search(r'remunera|base de c',c)]
            if not cr: continue
            j=cr[0]; mensal={}; gn={}; ult=None
            for r2 in rows[i+1:]:
                if not r2 or len(r2)<=j: continue
                k=mes(r2[0],dm); v=r2[j]
                if k:
                    ult=k
                    if isinstance(v,(int,float)) and v>0: mensal[k]=round(v+1e-9,2)
                elif ult and isinstance(r2[0],str) and re.search(r'GN|13|NATAL',r2[0].upper()) and isinstance(v,(int,float)) and v>0:
                    gn[ult[:4]]=round(v+1e-9,2)
            tit=' '.join(str(r[0] or '') for r in rows[:6] if r)
            if mensal and (not best or len(mensal)>len(best['mensal'])): best={'aba':nome,'mensal':mensal,'gn':gn,'titulo':tit}
    return best
out=[]
for d,_,fs in os.walk(ROOT):
    for f in fs:
        if not re.search(r'\.(xlsx?)$',f,re.I) or not re.search(r'RBC|RRC|RCP',f,re.I) or re.search(r'rascunho|c[oó]pia',f,re.I): continue
        p=os.path.join(d,f)
        try: r=parse(p)
        except Exception as e: continue
        if r: r['arquivo']=os.path.relpath(p,ROOT); r['mtime']=os.path.getmtime(p); out.append(r)
json.dump(out,open('golds_xls.json','w'),ensure_ascii=False)
print(len(out))
for o in out[:200]:
    if o['arquivo'].startswith(('RBC/','RRC/')): print(len(o['mensal']),len(o['gn']),o['aba'],o['arquivo'][-70:])
