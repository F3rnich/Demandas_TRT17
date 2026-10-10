# -*- coding: utf-8 -*-
"""Gera os entregáveis (xlsx + csv) a partir de raw.json."""
import sys, json, csv, os, datetime as dt, collections, re
OUT = sys.argv[1]
d = json.load(open(f'{OUT}/raw.json'))
rows, alerts, params, ir, regras, listas = d['rows'], d['alerts'], d['params'], d['ir'], d['regras'], d['correlacao']
D = lambda s: dt.date.fromisoformat(s) if s else None

# ------------------------------------------------------------ ajustes de vigência pontuais
DEC = 'Decisão DIPROF de 09/10/2026'
# rótulo correto das FC na coluna "integral" de 2023–2026 (a função vem da coluna de valor da mesma linha)
rown_ = lambda c: int(re.sub(r'\D', '', c.split(':')[0]))
_fun = {(r['aba_origem'], rown_(r['celula_origem'])): r['funcao'] for r in rows
        if r['grupo'] == 'FUNCAO_COMISSIONADA' and r['rubrica'] in ('FC_VALOR', 'FC_OPCAO_65PCT') and r['aba_origem'] in ('2023', '2024', '2025', '2026')}
for r in rows:
    if r['grupo'] == 'FUNCAO_COMISSIONADA' and r['aba_origem'] in ('2023', '2024', '2025', '2026') and r['rubrica'] in ('FC_INTEGRAL', 'FC_INTEGRAL_DERIVADO'):
        f = _fun.get((r['aba_origem'], rown_(r['celula_origem'])))
        if f and f != r.get('funcao'): r['funcao'] = f
        if (r.get('funcao') or '').startswith('FC'):
            r['rubrica'] = 'FC_INTEGRAL_DERIVADO'; r['status'] = 'nao_usar'
            r['observacao'] = f'Coluna "integral" calculada na planilha como FC ÷ 0,65. FC tem valor único: usar FC_VALOR da tabela ({DEC}).'

for r in rows:
    if r['grupo'] == 'FUNCAO_COMISSIONADA' and r['vigencia_inicio'] == '2008-12-01':
        f = r.get('funcao') or ''
        if f.startswith('FC') and r['modalidade'] == 'OPTANTE':       # FC tem valor único desde a Lei 11.416/2006
            r['rubrica'], r['modalidade'] = 'FC_VALOR', 'UNICO'
        if f.startswith('CJ') and r['modalidade'] == 'OPTANTE':       # opção pelo efetivo = 65% (Lei 11.416/2006)
            r['rubrica'] = 'FC_OPCAO_65PCT'
        r['vigencia_fim'] = '2016-07-20' if f.startswith('FC') else '2015-12-31'
        r['observacao'] = f'Sem reajuste de FC/CJ de 2009 a 2022; tabela de dez/2008 mantida até a tabela seguinte da planilha ({DEC}).'
    if r['grupo'] == 'FUNCAO_COMISSIONADA' and r['aba_origem'] == '2016' and r['vigencia_inicio'] == '2016-07-21':
        r['vigencia_fim'] = '2023-01-31'
        r['observacao'] = f'Tabela da Lei 13.317/16 mantida até a da Lei 14.523/2023 (fev/2023); sem reajuste de FC/CJ no período ({DEC}).'
    if r['grupo'] == 'SERVIDOR_EFETIVO' and r['aba_origem'] == '2003' and r['celula_origem'] == 'D102':
        r['valor'] = 2358.42
        r['observacao'] = f'Total corrigido de 2.385,42 para 2.358,42 (soma das parcelas) — {DEC}.'
    if r['grupo'] == 'VPNI_QUINTOS':
        r['observacao'] = (r.get('observacao') or '') + ' Vigência final não informada; VPNI só se altera por revisão geral.'

DEC2 = 'Decisão DIPROF de 09/10/2026 (2ª rodada)'
for r in rows:
    # DAS 1995: o 1º bloco "MAR/DEZ/95" é a tabela anterior à Lei 9.030/95 (efeitos a partir de 01/03/1995) acrescida de 11,98%
    if r['grupo'] == 'DAS' and r['aba_origem'] == '1995' and 38 <= rown_(r['celula_origem']) <= 43:
        r['vigencia_inicio'], r['vigencia_fim'] = '1995-01-01', '1995-02-28'
        r['observacao'] = 'Título da planilha diz MAR/DEZ/95, mas são os valores anteriores à Lei 9.030/95 (+11,98%); a Lei 9.030/95 tem efeitos a partir de 01/03/1995 (2º bloco).'
    if r['grupo'] == 'DAS' and r['aba_origem'] == '1995' and 48 <= rown_(r['celula_origem']) <= 53:
        r['observacao'] = 'Valores da Lei 9.030/95 (efeitos a partir de 01/03/1995) acrescidos de 11,98% (ex.: DAS-1 176,64 × 1,1198 = 197,80).'
    # décimos de 2006 e FC "integral" de 2006–2008: a tabela de funções vale o ano todo
    if r['grupo'] == 'DECIMOS_QUINTOS' and r['aba_origem'] == '2006' and r['vigencia_fim'] == '2006-05-31':
        r['vigencia_fim'] = '2006-12-31'; r['observacao'] = f'Tabela de décimos vale para o ano todo ({DEC2}).'
    if (r['grupo'] == 'FUNCAO_COMISSIONADA' and r['aba_origem'] in ('2006', '2007', '2008') and r.get('modalidade') == 'INTEGRAL'
            and (r.get('funcao') or '').startswith('FC') and r['vigencia_inicio'][5:] == '01-01'):
        r['vigencia_fim'] = r['vigencia_inicio'][:4] + '-12-31'; r['observacao'] = f'Valor integral da FC vale para o ano todo ({DEC2}).'

# parâmetros: VPI (mai/2003–dez/2018, sem pagamento de jan/2015 a mar/2016) e AQ anterior a 2026 (Lei 11.416/2006, art. 15)
for p in params:
    if p['parametro'] == 'VPI_LEI_10698_2003':
        p['vigencia_fim'] = '2014-12-31'
        p['observacao'] = f'Paga de mai/2003 a dez/2014 e de abr/2016 a dez/2018; sem pagamento de jan/2015 a mar/2016. Houve outros períodos sem pagamento para alguns servidores: conferir a ficha ({DEC2}).'
vpi = dict(next(p for p in params if p['parametro'] == 'VPI_LEI_10698_2003'))
vpi.update(vigencia_inicio='2016-04-01', vigencia_fim='2018-12-31')
params.append(vpi)
def _P(nome, ini, fim, valor, base, obs):
    params.append(dict(parametro=nome, vigencia_inicio=ini, vigencia_fim=fim, valor=valor, unidade='fator s/ VB', base_legal=base, aba_origem='-', celula_origem='-', observacao=obs))
_aq = 'Devido a partir da apresentação do título (art. 15, § 3º). Data inicial de 01/06/2006 = início dos efeitos da Lei 11.416/2006 na base; confirmar. ' + DEC2
_P('AQ_PCT_DOUTORADO', '2006-06-01', '2025-12-31', 0.125, 'Lei 11.416/2006, art. 15, I', _aq)
_P('AQ_PCT_MESTRADO', '2006-06-01', '2025-12-31', 0.10, 'Lei 11.416/2006, art. 15, II', _aq)
_P('AQ_PCT_ESPECIALIZACAO', '2006-06-01', '2025-12-31', 0.075, 'Lei 11.416/2006, art. 15, III', _aq + ' Doutorado, mestrado e especialização não se acumulam.')
_P('AQ_PCT_TREINAMENTO_POR_120H', '2006-06-01', '2025-12-31', 0.01, 'Lei 11.416/2006, art. 15, V', 'Até 3% (três conjuntos de 120 h); cada conjunto vale por 4 anos. Acumula com os demais. ' + DEC2)
_P('AQ_PCT_GRADUACAO_TECNICO', '2016-07-21', '2023-09-19', 0.05, 'Lei 11.416/2006, art. 15, VI (Lei 13.317/2016)', 'Técnico Judiciário com curso superior. Convertido em VPNI pela Lei 14.687/2023 (20/09/2023). ' + DEC2)


# ------------------------------------------------------------ correções propostas para tabelas anteriores a 07/1994 (RBC cobre todo o período; 09/10/2026)
A_CONF = ' — proposta da análise, a confirmar pela DIPROF.'
def _cel(aba, cel): return next(r for r in rows if r['aba_origem'] == aba and r['celula_origem'] == cel)
def _set(aba, cel, v, obs):
    r = _cel(aba, cel); old = r['valor']; r['valor'] = round(v, 6); r['status'] = 'ok'
    br = lambda x: f'{x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    r['observacao'] = ((r.get('observacao') or '') + ' ' + f'Corrigido de {br(old)} para {br(v)}: {obs}{A_CONF}').strip()
# 1992 G30 (NA-27, fev/1992): a fórmula soma 7.878,77 onde o padrão da tabela é +35% (193.939,35 × 0,35 = 67.878,77)
_set('1992', 'G30', 261818.12, 'a 2ª parcela da fórmula (=193.939,35 + 7.878,77) deveria ser 67.878,77 (35% de 193.939,35, como nas linhas vizinhas)')
_set('1992', 'H30', 261818.12 * 1.7, 'recalculado (=G30×1,7)')
_set('1992', 'I30', 261818.12 * 2.7, 'recalculado (=H30+G30)')
# 1992 G63 (NI-35, fev/1992): a GE da mesma linha (H63 = 731.965,02, digitada) é exatamente 430.567,66 × 1,7
_set('1992', 'G63', 430567.66, 'a gratificação extraordinária da mesma linha (H63 = 731.965,02) é 430.567,66 × 1,7; erro no 1º dígito')
_set('1992', 'I63', 430567.66 + 731965.02, 'recalculado (=H63+G63)')
# 1994 G119 (NI D-I, mar/1994 URV): faltou um dígito; 116,26 / 111,49 = 1,0428, a mesma razão entre D-III e D-II (121,24 / 116,26)
_g = 111.49
_set('1994', 'G119', _g, 'faltou um dígito; a razão D-II/D-I fica igual à das demais referências (1,0428)')
_set('1994', 'H119', _g * 0.2886, 'recalculado (=G119×0,2886)')
_set('1994', 'I119', (_g * 1.2886) * 1.7, 'recalculado (=(H119+G119)×1,7)')
_set('1994', 'J119', _g * 1.2886 * 2.7, 'recalculado (=I119+H119+G119)')
# aba 1990: até 15/03/1990 a moeda era o cruzado novo (NCz$), depois o cruzeiro (Cr$), na paridade 1:1
for r in rows:
    if r['aba_origem'] == '1990' and r.get('moeda') == 'NCz$':
        r['moeda'] = 'Cr$'; r['unidade'] = 'Cr$'
        r['observacao'] = ((r.get('observacao') or '') + ' Moeda: NCz$ até 15/03/1990 e Cr$ depois (paridade 1:1).').strip()

# situação de cada alerta após as decisões da DIPROF
RESOLV = {
    ('2008', 'A14:H25'): ('resolvido', 'Não houve reajuste de FC/CJ de 2009 a 2022. FC: tabela de dez/2008 até 20/07/2016; CJ: dez/2008 até 31/12/2015 e a de 01/01/2016 até 20/07/2016; FC e CJ: tabela de 21/07/2016 até 31/01/2023.'),
    ('2016', 'B15:D35'): ('resolvido', 'Tabela de 21/07/2016 mantida até 31/01/2023 (sem parcelas posteriores para FC/CJ).'),
    ('2017', 'D8:F10'): ('resolvido', 'Sem reajuste em 2017–2018: vale a tabela de 2016 (mesmos valores da Lei 13.091/2015) até 31/12/2018.'),
    ('2003', 'D102'): ('resolvido', 'Total corrigido para R$ 2.358,42.'),
    ('2025', 'H29:H34'): ('resolvido', 'FC tem valor único: usar a coluna de valor da tabela; a coluna "integral" (FC ÷ 0,65) continua fora do cálculo.'),
    ('2025', 'D87:D123'): ('aceito', 'A DIPROF informa que a falta de arredondamento não interfere no resultado.'),
    ('2025', 'F25:F34'): ('aceito', 'A DIPROF informa que a falta de arredondamento não interfere no resultado.'),
    ('1990', 'A2:A3'): ('a_confirmar', 'A RBC cobre todo o período (correção DIPROF de 09/10/2026). Mantida como tabela de 1990 com vigência no ano inteiro; informar a data de início real.'),
    ('1992', 'G30'): ('a_confirmar', 'Proposta aplicada: 261.818,12 (H30 e I30 recalculados). A fórmula original soma 7.878,77 onde deveria somar 67.878,77 (35%).'),
    ('1992', 'G63'): ('a_confirmar', 'Proposta aplicada: 430.567,66 (I63 recalculado). A GE digitada na mesma linha (731.965,02) é exatamente 430.567,66 × 1,7.'),
    ('1994', 'G119'): ('a_confirmar', 'Proposta aplicada: 111,49 (H119, I119 e J119 recalculados). A razão D-II/D-I passa a ser igual à das demais referências.'),
    ('1994', 'D7'): ('a_confirmar', 'Mantida a leitura 745.810,70 (texto "745.810.70" convertido).'),
    ('1991', 'L68'): ('a_confirmar', 'Célula sem valor na planilha ("sem informação"): informar o valor, se houver servidor nessa referência.'),
    ('1991', 'Q68'): ('a_confirmar', 'Célula sem valor na planilha ("sem informação"): informar o valor, se houver servidor nessa referência.'),
    ('1992', 'Z3:AE3'): ('a_confirmar', 'Jul/1992 sem tabela: mantida a de 01/06/1992. Confirmar.'),
    ('1992', 'AJ4:AV4'): ('a_confirmar', 'Mudança de NA/NI/NS-xx para classe + padrão em 01/09/1992 sem correlação na planilha: a referência de cada servidor vem do relatório de progressão. Enviar a tabela de correlação, se houver.'),
    ('1993', 'S1:W24'): ('a_confirmar', 'Importado o bloco A26:Q49. Confirmar W5 (12.673.117,60 × 12.673.117,80) e V24 (3.350.292,11 × 3.350.492,11).'),
    ('1993', 'A101'): ('tratado', 'Moeda sinalizada na coluna moeda (CR$ a partir de 01/08/1993).'),
    ('1994', 'A4:F42'): ('tratado', 'Moeda sinalizada na coluna moeda (CR$).'),
    ('1990', 'C39'): ('tratado', 'Tratada como a mesma rubrica (GRAT_EXTRAORDINARIA).'),
    ('1995', 'A35:K53'): ('resolvido', '1º bloco = jan–fev/1995 (valores anteriores à Lei 9.030/95, +11,98%); 2º bloco = mar–dez/1995 (Lei 9.030/95, efeitos a partir de 01/03/1995, +11,98%). Conferido com o texto da lei.'),
    ('2026', 'J39:N48'): ('resolvido', 'AQ anterior a 2026 pelos percentuais da Lei 11.416/2006, art. 15, sobre o vencimento: doutorado 12,5%, mestrado 10%, especialização 7,5%, treinamento 1% por 120 h (até 3%); 5% para técnico com graduação de 21/07/2016 a 19/09/2023. A partir de 2026, modelo do Valor de Referência.'),
    ('2002', 'A88'): ('resolvido', 'GAJ de 12% de jun/2002 a jun/2004 confirmada.'),
    ('2003', 'A45'): ('resolvido', 'VPI de mai/2003 a dez/2018, sem pagamento de jan/2015 a mar/2016; conferir na ficha outros períodos sem pagamento.'),
    ('2006', 'A30:K42'): ('resolvido', 'Tabela de décimos de 2006 vale para o ano todo.'),
    ('2006', 'F22:H27'): ('resolvido', 'Valor integral das FC de 2006–2008 vale para o ano todo.'),
    ('2015', 'K12:L12'): ('resolvido', 'Usar 12,23%, conforme a tabela.'),
}
for a in alerts:
    k = (a['aba'], a['celula'])
    if k in RESOLV: a['situacao'], a['decisao_diprof'] = RESOLV[k]
    elif a['aba'] in ('1990', '1991', '1992', '1993'):
        a['situacao'], a['decisao_diprof'] = 'a_confirmar', 'A RBC cobre todo o período: conferir.'
    elif a['aba'] in ('1995', '1996', '1997', '1998', '1999') and a['tipo'] == 'vigência genérica':
        a['situacao'], a['decisao_diprof'] = 'aceito', 'Tabela atribuída ao ano inteiro, como proposto.'
    elif a['gravidade'] == 'baixa' or (a['aba'], a['celula']) in {('2000', 'C13:H13'), ('2000', 'B29:K29'), ('2001', 'B26'), ('2011', 'K15'), ('2026', 'K1:P9'), ('2009', 'A4:A13'), ('2003', 'A45:A46'), ('2003', 'F90'), ('2023', 'A24'), ('2018', 'H23:H25')}:
        a['situacao'], a['decisao_diprof'] = 'tratado', 'Tratado na importação; não exige decisão.'
    else:
        a.setdefault('situacao', 'aberto'); a.setdefault('decisao_diprof', '')

# ------------------------------------------------------------ ids e colunas finais
COLS = ['id', 'grupo', 'vigencia_inicio', 'vigencia_fim', 'moeda', 'cargo', 'ref', 'classe', 'padrao', 'funcao', 'modalidade', 'fracao',
        'rubrica', 'unidade', 'valor', 'e_total', 'status', 'base_legal', 'vigencia_texto', 'observacao', 'aba_origem', 'celula_origem', 'origem_formula']
for i, r in enumerate(rows, 1):
    r['id'] = f'V{i:05d}'
    r['unidade'] = r.get('unidade') or ('R$' if r.get('moeda') == 'R$' else r.get('moeda'))
    r['e_total'] = bool(r.get('e_total'))
    if r.get('padrao') is not None: r['padrao'] = str(r['padrao']).zfill(2) if str(r['padrao']).isdigit() else str(r['padrao'])
    if r.get('cargo'): r['cargo'] = re.sub(r'\s+', ' ', str(r['cargo'])).strip().upper()

# ------------------------------------------------------------ validações
def add_alert(aba, cel, tipo, msg, g='média'):
    if any(a['aba'] == aba and a['celula'] == cel for a in alerts): return
    alerts.append(dict(aba=aba, celula=cel, tipo=tipo, gravidade=g, descricao=msg))

def rown(c): return int(re.sub(r'\D', '', c.split(':')[0]))
grp = collections.defaultdict(dict)
for r in rows:
    if r['grupo'] in ('SERVIDOR_EFETIVO', 'MAGISTRADO', 'DECIMOS_QUINTOS', 'FUNCAO_COMISSIONADA', 'GRATIFICACAO_GABINETE', 'DAS'):
        k = (r['aba_origem'], rown(r['celula_origem']), r['vigencia_inicio'], r.get('cargo'), r.get('modalidade'), r.get('fracao'), r.get('funcao'))
        grp[k][r['rubrica']] = r
ADD = {'VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'GRAT_JUDICIARIA', 'ABONO', 'GAJ', 'APJ', 'REPRESENTACAO_MENSAL', 'PAE', 'PAE_AUXILIO_MORADIA',
       'PAE_AUX_MORADIA_ESCALONADO_5PCT', 'PARCELA_AUTONOMA_EQUIVALENCIA', 'PARCELA_ATO_TST_GP_109_2001', 'PARCELA_STF_195_2000',
       'DECIMOS_VALOR', 'FC_OPCAO_70PCT', 'FC_VALOR_BASE', 'FC_GAJ', 'FC_APJ', 'GRAT_GABINETE', 'DIFERENCA', 'GADF', 'DAS_VENCIMENTO', 'DAS_DIFERENCA'}
nchk = nerr = 0
for k, rb in grp.items():
    for tot_name in ('TOTAL', 'DECIMOS_TOTAL', 'FC_TOTAL', 'FC_TOTAL_BRUTO', 'TOTAL_BRUTO', 'SOMA', 'DAS_SUBTOTAL'):
        if tot_name not in rb: continue
        if tot_name in ('TOTAL',) and 'TOTAL_BRUTO' in rb:
            calc = rb['TOTAL_BRUTO']['valor'] - rb.get('REDUTOR', {'valor': 0})['valor']
        elif tot_name == 'TOTAL' and 'FC_TOTAL_BRUTO' in rb:
            calc = rb['FC_TOTAL_BRUTO']['valor'] - rb.get('REDUTOR', {'valor': 0})['valor']
        elif tot_name == 'TOTAL' and 'SOMA' in rb:
            calc = rb['SOMA']['valor'] + rb.get('GADF', {'valor': 0})['valor']
        elif tot_name == 'SOMA':
            calc = sum(rb[x]['valor'] for x in ('GRAT_GABINETE', 'DIFERENCA') if x in rb)
        elif tot_name == 'DAS_SUBTOTAL':
            calc = sum(rb[x]['valor'] for x in ('DAS_VENCIMENTO', 'DAS_DIFERENCA') if x in rb)
        else:
            comps = [x for x in rb if x in ADD]
            if not comps: continue
            calc = sum(rb[x]['valor'] for x in comps)
            if tot_name in ('TOTAL', 'DECIMOS_TOTAL'): calc -= rb.get('REDUTOR', {'valor': 0})['valor'] + rb.get('DECIMOS_REDUTOR', {'valor': 0})['valor']
        tv = rb[tot_name]['valor']; nchk += 1
        if abs(calc - tv) > max(0.05, abs(tv) * 0.0005):
            nerr += 1
            t = rb[tot_name]
            add_alert(t['aba_origem'], t['celula_origem'], 'validação: total ≠ soma',
                      f"{t.get('cargo') or t.get('funcao') or ''} {t.get('ref') or ((t.get('classe') or '') + (t.get('padrao') or ''))} ({t['rubrica']}) — total {tv:,.2f} × soma das parcelas {calc:,.2f} (dif. {tv - calc:,.2f}).", 'média')
            t['status'] = 'verificar'

# monotonicidade do VB dentro de cada tabela
blocks = collections.defaultdict(list)
for r in rows:
    if r['grupo'] == 'SERVIDOR_EFETIVO' and r['rubrica'] == 'VB':
        blocks[(r['aba_origem'], r['vigencia_inicio'], r['cargo'], r['celula_origem'][0:2].rstrip('0123456789'))].append(r)
nmono = 0
for k, lst in blocks.items():
    lst.sort(key=lambda r: rown(r['celula_origem']))
    vals = [r['valor'] for r in lst]
    asc = vals[-1] > vals[0]
    for a, b in zip(lst, lst[1:]):
        bad = (b['valor'] <= a['valor']) if asc else (b['valor'] >= a['valor'])
        ratio = b['valor'] / a['valor'] if a['valor'] else 0
        if bad or ratio > 1.3 or ratio < 0.77:
            nmono += 1
            if b['celula_origem'] == 'G31' and b['aba_origem'] == '1992': b['status'] = 'ok'; continue
            add_alert(b['aba_origem'], b['celula_origem'], 'validação: salto/inversão de VB',
                      f"{b['cargo']} {b.get('ref') or ((b.get('classe') or '') + (b.get('padrao') or ''))}: VB {b['valor']:,.2f} após {a['valor']:,.2f} ({a['celula_origem']}) — conferir.", 'alta')
            b['status'] = 'verificar'

# ------------------------------------------------------------ vigência de parâmetros encadeada
by = collections.defaultdict(list)
for p in params: by[p['parametro']].append(p)
for k, lst in by.items():
    lst.sort(key=lambda p: p['vigencia_inicio'])
    for a, b in zip(lst, lst[1:]):
        nb = D(b['vigencia_inicio']) - dt.timedelta(days=1)
        if a['vigencia_fim'] is None or D(a['vigencia_fim']) > nb: a['vigencia_fim'] = nb.isoformat()
for i, p in enumerate(params, 1): p['id'] = f'P{i:04d}'

# ------------------------------------------------------------ expansão mensal (competências)
def meses(a, b):
    y, m = a
    while (y, m) <= b:
        yield dt.date(y, m, 1); m += 1
        if m == 13: y, m = y + 1, 1
def cobre(r, dia):
    ini = D(r['vigencia_inicio']); fim = D(r['vigencia_fim']) if r['vigencia_fim'] else dt.date(2099, 12, 31)
    return ini <= dia <= fim
def mudanca(r_ini_list, comp):
    fimmes = (comp.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    return sorted({x for x in r_ini_list if comp < D(x) <= fimmes})

ini_all = collections.defaultdict(set)
for r in rows: ini_all[r['grupo']].add(r['vigencia_inicio'])
FIM = (2026, 12)

def expand(grupo, keyf, rubs, comp_ini=(1990, 1)):
    tabs = collections.defaultdict(list)
    for r in rows:
        if r['grupo'] == grupo and r['status'] != 'nao_usar': tabs[keyf(r)].append(r)
    out = []
    for key, lst in sorted(tabs.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        first = min(D(r['vigencia_inicio']) for r in lst)
        last = max((D(r['vigencia_fim']) if r['vigencia_fim'] else dt.date(2099, 12, 31)) for r in lst)
        for comp in meses(comp_ini, FIM):
            if comp < first.replace(day=1) or comp > last: continue
            cand = [r for r in lst if cobre(r, comp)]
            if not cand:
                later = [r for r in lst if D(r['vigencia_inicio']) > comp and D(r['vigencia_inicio']).replace(day=1) == comp]
                cand = later
            rec = dict(competencia=comp.strftime('%Y-%m'))
            for i, k in enumerate(key_names[grupo]): rec[k] = key[i]
            if not cand:
                rec['situacao'] = 'SEM_DADO_NA_PLANILHA'; out.append(rec); continue
            vi = max(r['vigencia_inicio'] for r in cand)
            sel = [r for r in cand if r['vigencia_inicio'] == vi]
            rec['moeda'] = sel[0]['moeda']; rec['vigencia_tabela'] = vi
            for r in sel:
                if r['rubrica'] in rubs: rec[r['rubrica']] = r['valor']
            rec['ids_origem'] = ' '.join(r['id'] for r in sel if r['rubrica'] in rubs)
            mud = mudanca(ini_all[grupo], comp)
            rec['situacao'] = 'OK' if not mud else 'MUDANCA_NO_MES'
            rec['nova_tabela_em'] = ', '.join(mud)
            if any(r['status'] == 'verificar' for r in sel): rec['situacao'] += '|VERIFICAR_VALOR'
            out.append(rec)
    return out

key_names = {'SERVIDOR_EFETIVO': ['cargo', 'classe', 'padrao', 'ref'], 'MAGISTRADO': ['cargo'], 'FUNCAO_COMISSIONADA': ['funcao', 'modalidade', 'rubrica_fc']}
SRUB = ['VB', 'GAJ', 'APJ', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'GRAT_JUDICIARIA', 'ABONO', 'REDUTOR', 'GAS', 'GAE', 'TOTAL_BRUTO', 'TOTAL']
comp_serv = expand('SERVIDOR_EFETIVO', lambda r: (r['cargo'], r.get('classe'), r.get('padrao'), r.get('ref')), SRUB)
# magistrado: normaliza nome
MAGN = {'MINIST. STF': 'MINISTRO DO STF', 'MINISTRO STF': 'MINISTRO DO STF', 'MINIST. TST': 'MINISTRO DO TST', 'MINISTRO TST': 'MINISTRO DO TST',
        'JUIZ DE TRT': 'DESEMBARGADOR DO TRABALHO (JUIZ DE TRT)', 'DESEMBARGADOR': 'DESEMBARGADOR DO TRABALHO (JUIZ DE TRT)', 'DESEMBARGADOR DO TRABALHO': 'DESEMBARGADOR DO TRABALHO (JUIZ DE TRT)',
        'JUIZ DE VARA': 'JUIZ TITULAR DE VARA (JUIZ DE VARA/JCJ)', 'JUIZ DE JCJ': 'JUIZ TITULAR DE VARA (JUIZ DE VARA/JCJ)', 'JUIZ TITULAR DE VARA DO TRABALHO': 'JUIZ TITULAR DE VARA (JUIZ DE VARA/JCJ)',
        'JUIZ SUBST.': 'JUIZ DO TRABALHO SUBSTITUTO', 'JUIZ SUBSTITUTO': 'JUIZ DO TRABALHO SUBSTITUTO', 'JUIZ DO TRABALHO SUBSTITUTO': 'JUIZ DO TRABALHO SUBSTITUTO',
        'JUIZ CLASSISTA DE VARA': 'JUIZ CLASSISTA (POR SESSÃO)', 'JUIZ CLASSISTA DE VARA/JCJ': 'JUIZ CLASSISTA (POR SESSÃO)'}
for r in rows:
    if r['grupo'] == 'MAGISTRADO': r['cargo_padronizado'] = MAGN.get(r['cargo'], r['cargo'])
MRUB = ['SUBSIDIO', 'SUBSTITUICAO', 'VB', 'REPRESENTACAO_MENSAL', 'PAE', 'PAE_AUXILIO_MORADIA', 'PAE_AUX_MORADIA_ESCALONADO_5PCT',
        'PARCELA_AUTONOMA_EQUIVALENCIA', 'PARCELA_ATO_TST_GP_109_2001', 'PARCELA_STF_195_2000', 'VALOR_POR_SESSAO', 'TOTAL']
comp_mag = expand('MAGISTRADO', lambda r: (r['cargo_padronizado'],), MRUB)
for r in rows:
    if r['grupo'] == 'FUNCAO_COMISSIONADA':
        r['_fc_key'] = r['rubrica']
FRUB = ['FC_OPCAO_70PCT', 'FC_OPCAO_65PCT', 'FC_INTEGRAL', 'FC_VALOR', 'FC_VALOR_BASE', 'FC_GAJ', 'FC_APJ', 'FC_TOTAL', 'FC_TOTAL_BRUTO', 'REDUTOR', 'TOTAL']
comp_fc = expand('FUNCAO_COMISSIONADA', lambda r: (r['funcao'], r['modalidade'], 'ver colunas'), FRUB)
# lacunas FC explícitas 2009-01..2022-12 (exceto 2016-07..2016-10)
fc_keys = sorted({(r['funcao'], r['modalidade']) for r in rows if r['grupo'] == 'FUNCAO_COMISSIONADA' and r['status'] != 'nao_usar'})
have = {(c['competencia'], c['funcao'], c['modalidade']) for c in comp_fc if c.get('situacao') != 'SEM_DADO_NA_PLANILHA'}
for comp in meses((1997, 1), FIM):
    for f, m in fc_keys:
        k = (comp.strftime('%Y-%m'), f, m)
        if k not in have and not any(c['competencia'] == k[0] and c['funcao'] == f and c['modalidade'] == m for c in comp_fc if c.get('situacao') == 'SEM_DADO_NA_PLANILHA'):
            pass
comp_fc = [c for c in comp_fc if c.get('situacao') != 'SEM_DADO_NA_PLANILHA']
lac = []
for comp in meses((1997, 1), FIM):
    cs = comp.strftime('%Y-%m')
    if not any(c['competencia'] == cs for c in comp_fc[:0]): pass
months_with_fc = {c['competencia'] for c in comp_fc}
for comp in meses((1997, 1), FIM):
    cs = comp.strftime('%Y-%m')
    if cs not in months_with_fc:
        lac.append(dict(competencia=cs, funcao='TODAS', modalidade='-', rubrica_fc='-', situacao='SEM_DADO_NA_PLANILHA'))
comp_fc += lac
comp_fc.sort(key=lambda c: (c['competencia'], str(c['funcao']), str(c['modalidade'])))

# parâmetros mensais
def pval(nome, comp):
    for p in by.get(nome, []):
        if D(p['vigencia_inicio']) <= comp and (p['vigencia_fim'] is None or comp <= D(p['vigencia_fim'])): return p['valor']
    for p in by.get(nome, []):
        if D(p['vigencia_inicio']).replace(day=1) == comp: return p['valor']
    return None
pm = []
for comp in meses((1990, 1), FIM):
    pm.append(dict(competencia=comp.strftime('%Y-%m'), teto_rgps=pval('TETO_RGPS', comp), salario_minimo=pval('SALARIO_MINIMO', comp),
                   gaj_fator_sobre_vb=pval('GAJ_PERCENTUAL_SOBRE_VB', comp), gae_gas_fator_implantacao=pval('GAE_GAS_PERCENTUAL_IMPLANTACAO', comp),
                   vpi_lei_10698=pval('VPI_LEI_10698_2003', comp), aq_pct_doutorado=pval('AQ_PCT_DOUTORADO', comp), aq_pct_mestrado=pval('AQ_PCT_MESTRADO', comp),
                   aq_pct_especializacao=pval('AQ_PCT_ESPECIALIZACAO', comp), aq_pct_treinamento_120h=pval('AQ_PCT_TREINAMENTO_POR_120H', comp),
                   aq_pct_graduacao_tecnico=pval('AQ_PCT_GRADUACAO_TECNICO', comp), aq_valor_referencia=pval('AQ_VALOR_REFERENCIA_VR', comp),
                   contribuicao_limitada_teto=pval('CONTRIBUICAO_LIMITADA_AO_TETO', comp)))

# ------------------------------------------------------------ cobertura servidor: meses sem tabela
serv_months = {c['competencia'] for c in comp_serv if c.get('situacao', '').startswith(('OK', 'MUDANCA'))}
gaps = [c.strftime('%Y-%m') for c in meses((1990, 1), FIM) if c.strftime('%Y-%m') not in serv_months]
if gaps: add_alert('-', '-', 'lacuna de cobertura (servidores)', f'Competências sem tabela de cargo efetivo: {", ".join(gaps)}', 'alta')
mag_months = {c['competencia'] for c in comp_mag if c.get('situacao', '').startswith(('OK', 'MUDANCA'))}
gm = [c.strftime('%Y-%m') for c in meses((1990, 1), FIM) if c.strftime('%Y-%m') not in mag_months]
if gm: add_alert('-', '-', 'lacuna de cobertura (magistrados)', f'Competências sem tabela de magistrados: {", ".join(gm)}', 'alta')

for a in alerts:
    if 'situacao' not in a:
        if a['tipo'].startswith('lacuna de cobertura') and all(m < '1994-07' for m in re.findall(r'\d{4}-\d{2}', a['descricao'])):
            a['situacao'], a['decisao_diprof'] = 'a_confirmar', 'Meses anteriores a 07/1994 sem tabela na planilha: enviar as tabelas, se houver RBC de magistrado nesse período.'
        else: a['situacao'], a['decisao_diprof'] = 'aberto', ''
for i, a in enumerate(alerts, 1): a['id'] = f'A{i:03d}'
G = {'alta': 0, 'média': 1, 'baixa': 2}
alerts.sort(key=lambda a: (G[a['gravidade']], a['aba']))

json.dump(dict(rows=rows, alerts=alerts, params=params, ir=ir, regras=regras, listas=listas, comp_serv=comp_serv, comp_mag=comp_mag,
               comp_fc=comp_fc, pm=pm, COLS=COLS, SRUB=SRUB, MRUB=MRUB, FRUB=FRUB, stats=dict(nchk=nchk, nerr=nerr, nmono=nmono)),
          open(f'{OUT}/final.json', 'w'), ensure_ascii=False, default=str)
print('valores', len(rows), '| somas checadas', nchk, 'divergentes', nerr, '| saltos VB', nmono, '| alertas', len(alerts))
print('comp_serv', len(comp_serv), 'comp_mag', len(comp_mag), 'comp_fc', len(comp_fc), 'gaps serv', gaps[:20], 'gaps mag', gm[:20])
