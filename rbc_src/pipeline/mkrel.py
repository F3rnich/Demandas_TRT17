import json,os,subprocess,re,unicodedata
C={c['id']:c for c in json.load(open('cases.json'))}
def n(s): return unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().upper().strip()
G=json.load(open('golds_gn.json')) if os.path.exists('golds_gn.json') else []
for cid in sorted(d for d in os.listdir('casos') if os.path.isdir('casos/'+d)):
    cj=json.load(open('casos/%s/caso.json'%cid)); c=C[cid]
    same=[cc for cc in C.values() if n(cc['nome'])==n(c['nome'])]
    rel=[]
    for cc in same:
        for f in cc['ctcs']:
            p='/home/claude/corpus/'+f
            t=subprocess.run(['pdftotext',p,'-'],capture_output=True,text=True).stdout
            if len(t.strip())>200 and re.search(r'TEMPO\s+DE\s+(CONTRIBUI|SERVI)',t,re.I) and not re.search(r'BASES DE C.LCULO',t[:1500]): rel.append(p)
    d='casos/'+cid
    for f in os.listdir(d):
        if f.startswith('ctc') and os.path.islink(d+'/'+f): os.remove(d+'/'+f)
    names=[]
    for i,p in enumerate(rel[:3]):
        nm='ctc%02d.pdf'%i; os.symlink(p,d+'/'+nm); names.append(nm)
    cj['relatorios']=names
    # certidão complementar de 13º (gabarito)
    pastas=[cc['pasta'] for cc in same]
    gg=[x for x in G if x['valores'] and any(x['arquivo'].startswith(p+'/') for p in pastas)]
    if gg: cj['gnCert']={y:v[1] for y,v in gg[-1]['valores'].items()}
    else: cj.pop('gnCert',None)
    json.dump(cj,open('casos/%s/caso.json'%cid,'w'),ensure_ascii=False,indent=1)
print('ok')
