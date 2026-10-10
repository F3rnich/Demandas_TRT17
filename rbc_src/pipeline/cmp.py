import re,sys
def load(f):
    d={}
    for l in open(f):
        m=re.match(r'## (\w+): (\d+)/(\d+) meses iguais(?: · GN (\d+)/(\d+))?',l)
        if m: d[m.group(1)]=tuple(int(x or 0) for x in m.groups()[1:])
        elif l.startswith('## '): d[l.split(':')[0][3:]]='FALHA '+l.split('—')[-1][:80].strip()
    return d
a=load(sys.argv[1]); b=load(sys.argv[2])
for k in sorted(set(a)|set(b)):
    if a.get(k)!=b.get(k): print(k, a.get(k),'->',b.get(k))
