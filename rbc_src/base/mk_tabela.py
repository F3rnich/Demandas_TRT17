# uso: python3 mk_tabela.py <final.json> <saida.json>
import json, sys
d=json.load(open(sys.argv[1]))
M={'VB':'VB','GAJ':'GAJ','GRAT_EXTRAORDINARIA':'GEXTRA','DIF_28_86':'DIF2886','APJ':'APJ'}
T={}
for r in d['rows']:
    if r['grupo']!='SERVIDOR_EFETIVO' or r['rubrica'] not in M or r['status']=='nao_usar': continue
    ref=r.get('ref') or ((r.get('classe') or '')+(r.get('padrao') or ''))
    if (r['vigencia_fim'] or '9999') < '1994-04-01' or not ref: continue
    k=(r['vigencia_inicio'],r['vigencia_fim'],r['cargo'],ref)
    T.setdefault(k,{})[M[r['rubrica']]]=round(r['valor'],2)
out=[dict(i=k[0],f=k[1],c=k[2],r=k[3],v=x.get('VB'),**{c:x[c] for c in x if c!='VB'}) for k,x in sorted(T.items()) if 'VB' in x]
json.dump(out,open(sys.argv[2],'w'),ensure_ascii=False,separators=(',',':'))
print(len(out), out[-1])
