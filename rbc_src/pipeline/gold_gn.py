import os,re,json,subprocess,docx,unicodedata
ROOT='/home/claude/corpus'
out=[]
for d,_,fs in os.walk(ROOT):
    for f in fs:
        p=os.path.join(d,f); e=f.lower().rsplit('.',1)[-1]
        if e not in('docx','pdf','doc'): continue
        try:
            if e=='docx': t='\n'.join(x.text for x in docx.Document(p).paragraphs)
            elif e=='pdf': t=subprocess.run(['pdftotext',p,'-'],capture_output=True,text=True).stdout
            else: continue
        except Exception: continue
        t=unicodedata.normalize('NFC',t)
        if not re.search(r't[íi]tulo de Gratifica[çc][ãa]o Natalina',t,re.I): continue
        flat=re.sub(r'\s+',' ',t)
        vals={}
        for m in re.finditer(r'(Cr\$|CR\$|R\$)\s*([\d.]+,\d{1,2})\s*\([^)]*\),?\s*(?:em|no ano de|referente a|relativo a)\s*(\d{4})',flat):
            vals[m.group(3)]=(m.group(1),float(m.group(2).replace('.','').replace(',','.')))
        em=re.search(r'emitida em (\d{1,2}/\d{1,2}/\d{4})',flat)
        out.append({'arquivo':os.path.relpath(p,ROOT),'valores':vals,'ref':em.group(1) if em else None})
json.dump(out,open('golds_gn.json','w'),ensure_ascii=False,indent=1)
for o in out: print(o['arquivo'][-80:],o['valores'])
