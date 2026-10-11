# Descrição das rubricas do sistema antigo por código (para fichas exportadas do banco sem descrição: "SQL Results",
# colunas ANO_PAG, MES_PAG, COD_RUBRICA…). Gera calc/rubricas_cod.json a partir das fichas em planilha do corpus.
# Só código, período e descrição da rubrica (tabela do sistema de folha); nenhum dado pessoal.
import json,collections
D=json.load(open('dataset.json'))
m=collections.defaultdict(lambda: collections.defaultdict(list))
for x in D:
  for r in x['recs']:
    if r['fonte']=='planilha' and r['desc'] and str(r['cod']).isdigit(): m[str(int(r['cod']))][r['desc']].append(r['ano'])
out={}
for c,ds in m.items():
  out[c]=sorted([[min(a),max(a),d] for d,a in ds.items()], key=lambda e:(e[0],-len(ds[e[2]])))
json.dump(out,open('/home/claude/Demandas_TRT17/rbc_src/calc/rubricas_cod.json','w'),ensure_ascii=False,separators=(',',':'))
print(len(out))
