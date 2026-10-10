# uso: python3 mk_base_calc.py <final.json> <saida.json>
# Exporta a base compacta usada pela tabela esperada (sem dados pessoais)
import json, sys
d = json.load(open(sys.argv[1]))
def pad(p):
    p = str(p or '').strip()
    return str(int(p)) if p.isdigit() else p.upper()
serv, fc, dec, gab, v1323 = [], [], [], [], []
for r in d['rows']:
    if r['status'] == 'nao_usar' or r.get('e_total') and r['rubrica'] not in ('TOTAL',): pass
    if r['status'] == 'nao_usar': continue
    g = r['grupo']
    if g == 'SERVIDOR_EFETIVO' and r['rubrica'] in ('VB','GAJ','APJ','DIF_28_86','GRAT_EXTRAORDINARIA','GRAT_JUDICIARIA','ABONO','REDUTOR','GAS','GAE') :
        serv.append([r['vigencia_inicio'], r['vigencia_fim'], r['cargo'], (r.get('classe') or '').upper(), pad(r.get('padrao')), r['rubrica'], round(r['valor'], 6), r['id']])
    elif g == 'FUNCAO_COMISSIONADA':
        fc.append([r['vigencia_inicio'], r['vigencia_fim'], r['funcao'], r['modalidade'], r['rubrica'], round(r['valor'], 6), r['id']])
    elif g in ('DECIMOS_QUINTOS', 'VPNI_QUINTOS'):
        dec.append([r['vigencia_inicio'], r['vigencia_fim'], r['funcao'], r.get('fracao'), r['rubrica'], round(r['valor'], 6), r['id'], g])
    elif g == 'VPI_13_23':
        v1323.append([r['vigencia_inicio'], r['vigencia_fim'], r.get('cargo') or '', (r.get('classe') or '').upper(), pad(r.get('padrao')), r.get('funcao') or '', r['rubrica'], round(r['valor'], 6), r['id']])
    elif g == 'GRATIFICACAO_GABINETE':
        gab.append([r['vigencia_inicio'], r['vigencia_fim'], r['funcao'], r.get('modalidade'), r['rubrica'], round(r['valor'], 6), r['id']])
par = [[p['parametro'], str(p['vigencia_inicio'])[:10], (str(p['vigencia_fim'])[:10] if p['vigencia_fim'] else None), p['valor']] for p in d['params']
       if not p['parametro'].startswith('IR_')]
out = dict(serv=serv, fc=fc, dec=dec, gab=gab, v1323=v1323, par=par)
json.dump(out, open(sys.argv[2],'w'), ensure_ascii=False, separators=(',', ':'))
print({k: len(v) for k, v in out.items()})
