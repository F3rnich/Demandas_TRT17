import json,re,unicodedata,math,collections
R=json.load(open('rubricas.json'))
def norm(s): s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper(); s=re.sub(r'[^A-Z0-9%]+',' ',s); return re.sub(r'\s+',' ',s).strip()
def vec(s):
    s=' '+norm(s)+' '; f=collections.Counter(s[i:i+3] for i in range(len(s)-2)); n=math.sqrt(sum(v*v for v in f.values())); return {k:v/n for k,v in f.items()}
def cos(a,b): return sum(v*b.get(k,0) for k,v in a.items())
data=[(vec(r['desc']),r['cat'],r['desc']) for r in R if r['cat']!='CLASSIFICAR' and r['desc'].strip()]
res=[]
for i,(v,c,d) in enumerate(data):
    best=max(((cos(v,w),cc,dd) for j,(w,cc,dd) in enumerate(data) if j!=i),key=lambda x:x[0])
    res.append((best[0],best[1]==c))
print('1-NN LOO: %.1f%%'%(100*sum(x[1] for x in res)/len(res)))
for th in (0.5,0.6,0.7,0.8):
    sel=[x for x in res if x[0]>=th]; print('  sim >= %.1f: cobre %d/%d, acerta %.1f%%'%(th,len(sel),len(res),100*sum(x[1] for x in sel)/max(1,len(sel))))
