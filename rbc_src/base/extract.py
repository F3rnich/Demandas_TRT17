# -*- coding: utf-8 -*-
"""Extrai a planilha TABELA_REMUNERAÇÃO (DIPROF/TRT-17) para uma base longa normalizada.
Uso: python3 -I extract.py <xlsx_entrada> <dir_saida>
"""
import sys, re, json, datetime as dt
import openpyxl
from openpyxl.utils import column_index_from_string as ci, get_column_letter as gl

SRC, OUT = sys.argv[1], sys.argv[2]
WBV = openpyxl.load_workbook(SRC, data_only=True)
WBF = openpyxl.load_workbook(SRC, data_only=False)

ROWS, ALERTS = [], []
D = lambda s: dt.date(*map(int, s.split('-'))) if s else None


def moeda_por_data(d):
    if d is None: return None
    if d < dt.date(1990, 3, 16): return 'NCz$'
    if d < dt.date(1993, 8, 1): return 'Cr$'
    if d < dt.date(1994, 7, 1): return 'CR$'
    return 'R$'


def alert(sheet, cell, tipo, msg, gravidade='média'):
    ALERTS.append(dict(aba=sheet, celula=cell, tipo=tipo, gravidade=gravidade, descricao=msg))


ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}


def parse_ref(s):
    """Retorna (classe, padrao) a partir de códigos tipo NA-03, AIII, C-35, C 35, C13."""
    s = str(s).strip().upper().replace(' ', '')
    m = re.match(r'^(N[AIS])-?(\d+)$', s)
    if m: return None, m.group(2).zfill(2)
    m = re.match(r'^([A-D])(I{1,3}|IV|VI|V)$', s)
    if m: return m.group(1), m.group(2)
    m = re.match(r'^([A-D])-?(\d+)$', s)
    if m: return m.group(1), m.group(2).zfill(2)
    return None, None


def norm_func(s):
    s = str(s).strip().upper().replace('–', '-')
    m = re.match(r'^(FC|CJ|DAS)\s*-?\s*0?(\d+)$', s)
    if m: return f'{m.group(1)}-{int(m.group(2)):02d}'
    return s


def num(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return float(v)
    return None


def emit(sheet, cell, valor, meta, **kw):
    r = dict(meta); r.update(kw)
    r['aba_origem'] = sheet; r['celula_origem'] = cell; r['valor'] = round(valor, 6)
    f = WBF[sheet][cell].value
    r['origem_formula'] = f if isinstance(f, str) and f.startswith('=') else ''
    ROWS.append(r)


def block(sheet, r1, keys, cols, r2=None, stop_blank=True, **meta):
    """keys: lista de (col, campo, fill). cols: {col: {rubrica, ...extras}}"""
    wsv = WBV[sheet]
    last = {}
    r = r1
    r2 = r2 or wsv.max_row
    meta.setdefault('moeda', moeda_por_data(D(meta.get('vigencia_inicio'))))
    while r <= r2:
        kv = {}
        for col, campo, fill in keys:
            v = wsv[f'{col}{r}'].value
            if isinstance(v, str): v = v.strip()
            if v in (None, ''):
                v = last.get(campo) if fill else None
            else:
                last[campo] = v
            kv[campo] = v
        vals = {c: wsv[f'{c}{r}'].value for c in cols}
        if stop_blank and all(v in (None, '') for v in vals.values()) and all(wsv[f'{c}{r}'].value in (None, '') for c, _, _ in keys):
            break
        for c, spec in cols.items():
            v = vals[c]
            if v in (None, '', '-'): continue
            n = num(v)
            if n is None and isinstance(v, str) and re.match(r'^\s*\d{1,3}([.,]\d{3})*[.,]\d{2}\s*$', v):
                n = float(re.sub(r'[.,]', '', v.strip())[:-2] + '.' + v.strip()[-2:])
                alert(sheet, f'{c}{r}', 'valor com digitação inválida', f'Valor digitado como texto "{v}"; convertido para {n:.2f}. Conferir.', 'alta')
                spec = dict(spec, observacao=f'Original em texto "{v}"; convertido.')
            if n is None:
                alert(sheet, f'{c}{r}', 'valor não numérico', f'Célula contém texto "{v}" onde se esperava valor ({spec.get("rubrica")}); não importado.', 'alta')
                continue
            rec = dict(kv)
            # derivar classe/padrão
            if 'ref' in rec and rec['ref'] is not None and 'padrao' not in rec:
                cl, pd = parse_ref(rec['ref'])
                rec['classe'], rec['padrao'] = cl, pd
            if 'funcao' in rec and rec['funcao']:
                rec['funcao'] = norm_func(rec['funcao'])
            sp = dict(spec)
            spec = cols[c]
            emit(sheet, f'{c}{r}', n, meta, **rec, **sp)
        r += 1
    return r


def R(rubrica, **kw):
    d = dict(rubrica=rubrica); d.update(kw); return d


def niveis_ref_block(sheet, start_row, col_ref, rub_cols, vig, base, cargo, fim=None, **extra):
    """Blocos 1990-1992: REF | VENC | GRAT | TOTAL."""
    cols = {}
    c0 = ci(col_ref)
    for i, rub in enumerate(rub_cols, start=1):
        cols[gl(c0 + i)] = R(rub, e_total=(rub == 'TOTAL'))
    block(sheet, start_row, [(col_ref, 'ref', False)], cols, grupo='SERVIDOR_EFETIVO', cargo=cargo,
          vigencia_inicio=vig, vigencia_fim=fim, base_legal=base, **extra)


# ---------------------------------------------------------------- 1990
NV = [('NÍVEL AUXILIAR', 6), ('NÍVEL INTERMEDIÁRIO', 40), ('NÍVEL SUPERIOR', 68)]
for cargo, r in NV:
    niveis_ref_block('1990', r, 'A', ['VB', 'GRAT_EXTRAORDINARIA', 'TOTAL'], '1990-01-01', 'Anterior à Lei 8.162/91 (ver alerta)', cargo,
                     fim='1990-12-31', vigencia_texto='Aba 1990 (cabeçalho diz "VIGENTE 01/01/1991" — ver alerta)')
alert('1990', 'A2:A3', 'vigência inconsistente',
      'Cabeçalho da aba 1990 repete "LEI 8.162/91 - 81%" e "VIGENTE 01/01/1991", mas os valores são 81% menores que os da aba 1991 com a mesma vigência (ex.: NA-03 17.783,40 × 1,81 = 32.187,95). Tratado como tabela de 1990 (anterior ao reajuste de jan/1991). Data exata de início em 1990 não informada.', 'alta')
alert('1990', 'C39', 'rótulo divergente', 'Gratificação Extraordinária rotulada "1?0%" no nível auxiliar e "170%" nos demais; tratada como a mesma rubrica (GRAT_EXTRAORDINARIA).', 'baixa')

# ---------------------------------------------------------------- 1991
V91 = [('A', '1991-01-01', '1991-01-31', 'Lei 8.162/91, art. 1º (81%)'),
       ('F', '1991-02-01', '1991-04-30', 'Lei 8.178/91, art. 7º (9,36%)'),
       ('K', '1991-05-01', '1991-06-30', 'MP 296/1991 e Ato Declaratório nº 1/1991 Pres. Senado (30%)'),
       ('P', '1991-07-01', '1991-10-31', 'Lei 8.216/91, arts. 1º e 2º (20%)'),
       ('U', '1991-11-01', '1991-11-30', 'Lei 8.270/91, arts. 2º e 26 (35%) e Lei 8.272/91, art. 1º'),
       ('Z', '1991-12-01', '1991-12-31', 'Lei 8.270/91, art. 1º (20%)')]
for col, ini, fim, base in V91:
    for cargo, r in [('NÍVEL AUXILIAR', 6), ('NÍVEL INTERMEDIÁRIO', 40), ('NÍVEL SUPERIOR', 68)]:
        niveis_ref_block('1991', r, col, ['VB', 'GRAT_EXTRAORDINARIA', 'TOTAL'], ini, base, cargo, fim=fim)

# ---------------------------------------------------------------- 1992
V92 = [('A', '1992-01-01', '1992-01-31', 'Lei 8.390/91, art. 2º'),
       ('F', '1992-02-01', '1992-02-29', 'Lei 8.390/91, art. 2º'),
       ('K', '1992-03-01', '1992-03-31', 'Lei 8.390/91, art. 2º'),
       ('P', '1992-04-01', '1992-04-30', 'Lei 8.417/92, art. 2º'),
       ('U', '1992-05-01', '1992-05-31', 'Lei 8.417/92, art. 2º'),
       ('Z', '1992-06-01', '1992-07-31', 'Lei 8.417/92, art. 2º'),
       ('AE', '1992-08-01', '1992-08-31', 'Lei 8.460/92, art. 1º')]
for col, ini, fim, base in V92:
    for cargo, r in [('NÍVEL AUXILIAR', 6), ('NÍVEL INTERMEDIÁRIO', 40), ('NÍVEL SUPERIOR', 68)]:
        niveis_ref_block('1992', r, col, ['VB', 'GRAT_EXTRAORDINARIA', 'TOTAL'], ini, base, cargo, fim=fim)
for c0, ini, fim, base in [('AJ', '1992-09-01', '1992-09-30', 'Lei 8.460/92, art. 2º e Lei 7.758/89'),
                           ('AV', '1992-10-01', '1992-12-31', 'Lei 8.460/92 e Lei 7.758/89')]:
    k = ci(c0)
    cols = {}
    for j, cargo in enumerate(['NÍVEL AUXILIAR', 'NÍVEL INTERMEDIÁRIO', 'NÍVEL SUPERIOR']):
        b = k + 2 + 3 * j
        cols[gl(b)] = R('VB', cargo=cargo)
        cols[gl(b + 1)] = R('GRAT_EXTRAORDINARIA', cargo=cargo)
        cols[gl(b + 2)] = R('TOTAL', cargo=cargo, e_total=True)
    block('1992', 6, [(c0, 'classe', True), (gl(k + 1), 'padrao', False)], cols, grupo='SERVIDOR_EFETIVO',
          vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)
alert('1992', 'G30', 'erro de digitação provável', 'Fev/1992, NA-27: VB 201.818,12 (e total I30). Pelo índice do mês (×1,25 sobre jan/1992 = 209.454,50) o esperado é 261.818,12 — erro no 1º dígito. Mantido o valor da planilha com status "verificar".', 'alta')
alert('1992', 'G63', 'erro de digitação provável', 'Fev/1992, NI-35: VB 330.567,66. Esperado 430.567,66 (344.454,13 × 1,25) — erro no 1º dígito. Mantido com status "verificar".', 'alta')
alert('1992', 'Z3:AE3', 'lacuna de vigência', 'Não há tabela para julho/1992; considerou-se vigente em jul/1992 a tabela de 01/06/1992.', 'média')
alert('1992', 'AJ4:AV4', 'mudança de estrutura', 'A partir de 01/09/1992 a referência passa de NA/NI/NS-xx para Classe (A–D) + Padrão (I–VI). Não há tabela de correlação na planilha.', 'média')

# ---------------------------------------------------------------- 1993
def bloco_classe_padrao(sheet, r_dados, col_classe, grupos, ini, fim, base, vtexto=None, moeda=None):
    cols = {}
    for cargo, mapping in grupos:
        for c, rub in mapping.items():
            cols[c] = R(rub, cargo=cargo, e_total=(rub == 'TOTAL'))
    kw = dict(grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, vigencia_texto=vtexto)
    if moeda: kw['moeda'] = moeda
    k = ci(col_classe)
    block(sheet, r_dados, [(col_classe, 'classe', True), (gl(k + 1), 'padrao', False)], cols, **kw)

G5 = lambda a, b, c: [('NÍVEL AUXILIAR', dict(zip(a, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'GRAT_JUDICIARIA', 'TOTAL']))),
                      ('NÍVEL INTERMEDIÁRIO', dict(zip(b, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'GRAT_JUDICIARIA', 'TOTAL']))),
                      ('NÍVEL SUPERIOR', dict(zip(c, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'GRAT_JUDICIARIA', 'TOTAL'])))]
G4 = lambda a, b, c: [('NÍVEL AUXILIAR', dict(zip(a, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'TOTAL']))),
                      ('NÍVEL INTERMEDIÁRIO', dict(zip(b, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'TOTAL']))),
                      ('NÍVEL SUPERIOR', dict(zip(c, ['VB', 'DIF_28_86', 'GRAT_EXTRAORDINARIA', 'TOTAL'])))]
bloco_classe_padrao('1993', 5, 'A', G5('CDEFG', 'HIJKL', 'MNOPQ'), '1993-01-01', '1993-02-28',
                    'Lei 8.622/93, arts. 1º a 3º e Lei 8.460/92 (28,86%; 100% + Cr$ 102.000,00 incorporado)')
bloco_classe_padrao('1993', 30, 'A', G5('CDEFG', 'HIJKL', 'MNOPQ'), '1993-03-01', '1993-04-30', 'Leis 8.622/93 e 8.627/93')
bloco_classe_padrao('1993', 55, 'A', G5('CDEFG', 'HIJKL', 'MNOPQ'), '1993-05-01', '1993-06-30', 'Lei 8.460/92')
bloco_classe_padrao('1993', 80, 'A', G4('CDEF', 'GHIJ', 'KLMN'), '1993-07-01', '1993-07-31', 'Lei 8.460/92')
bloco_classe_padrao('1993', 105, 'A', G4('CDEF', 'GHIJ', 'KLMN'), '1993-08-01', '1993-08-31', 'Lei 8.460/92')
bloco_classe_padrao('1993', 130, 'A', G4('CDEF', 'GHIJ', 'KLMN'), '1993-09-01', '1993-10-31', 'Lei 8.460/92; Lei 8.676/93')
bloco_classe_padrao('1993', 155, 'A', G4('CDEF', 'GHIJ', 'KLMN'), '1993-11-01', '1993-12-31', 'Lei 8.460/92; Lei 8.676/93')
alert('1993', 'S1:W24', 'bloco duplicado', 'Bloco S1:W24 ("VIGENTE 01/03/1993", só vencimento) repete o bloco A26:Q49; não importado. Duas células divergem do bloco importado: W5 = 12.673.117,60 × M30 = 12.673.117,80 e V24 = 3.350.292,11 × H49 = 3.350.492,11 — conferir qual está correta.', 'média')
alert('1993', 'A101', 'troca de moeda', 'A partir de 01/08/1993 os valores estão em cruzeiro real (CR$ = Cr$ 1.000). Campo "moeda" sinaliza.', 'média')

# ---------------------------------------------------------------- 1994
def magist(sheet, r1, cols, ini, fim, base, vtexto=None, moeda=None, r2=None, **extra):
    kw = dict(grupo='MAGISTRADO', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, vigencia_texto=vtexto, **extra)
    if moeda: kw['moeda'] = moeda
    block(sheet, r1, [('A', 'cargo', False)], cols, r2=r2, **kw)

MAG94 = {'B': R('VB'), 'C': R('PERC_REPRESENTACAO', unidade='%'), 'D': R('REPRESENTACAO_MENSAL'), 'E': R('PAE'), 'F': R('TOTAL', e_total=True)}
magist('1994', 7, MAG94, '1994-04-01', '1994-04-30', 'Não informada na planilha', moeda='CR$', r2=11)
magist('1994', 17, MAG94, '1994-05-01', '1994-05-31', 'Não informada na planilha', moeda='CR$', r2=21)
magist('1994', 27, MAG94, '1994-06-01', '1994-06-30', 'Não informada na planilha', moeda='CR$', r2=31)
magist('1994', 37, MAG94, '1994-07-01', '1994-12-31', 'Não informada na planilha', moeda='R$', r2=41)
for r, v, ini, fim, m in [(12, 108275.47, '1994-04-01', '1994-04-30', 'CR$'), (22, 153959.68, '1994-05-01', '1994-05-31', 'CR$'),
                          (32, 221961.87, '1994-06-01', '1994-06-30', 'CR$'), (42, 116.29, '1994-07-01', '1994-12-31', 'R$')]:
    emit('1994', f'A{r}', v, dict(grupo='MAGISTRADO', vigencia_inicio=ini, vigencia_fim=fim, moeda=m, base_legal='Não informada na planilha'),
         cargo='JUIZ CLASSISTA DE VARA', rubrica='VALOR_POR_SESSAO', observacao='Valor por sessão a que comparecer; extraído de texto da célula.')
alert('1994', 'A4:F42', 'moeda magistrados', 'Tabelas de magistrados abr–jun/1994 estão em CR$ (sem conversão em URV, conforme observação H6).', 'média')
G4c = G4('CDEF', 'GHIJ', 'KLMN')
bloco_classe_padrao('1994', 50, 'A', G4c, '1994-01-01', '1994-01-31', 'Portaria Interministerial CSJT nº 6')
bloco_classe_padrao('1994', 75, 'A', [('NÍVEL AUXILIAR', dict(zip('CDEFG', ['VB', 'DIF_28_86', 'ABONO', 'GRAT_EXTRAORDINARIA', 'TOTAL']))),
                                     ('NÍVEL INTERMEDIÁRIO', dict(zip('HIJKL', ['VB', 'DIF_28_86', 'ABONO', 'GRAT_EXTRAORDINARIA', 'TOTAL']))),
                                     ('NÍVEL SUPERIOR', dict(zip('MNOPQ', ['VB', 'DIF_28_86', 'ABONO', 'GRAT_EXTRAORDINARIA', 'TOTAL'])))],
                    '1994-02-01', '1994-02-28', 'MP 433/94, convalidada pela MP 456/94 (abono de 5% sobre vencimento)')
bloco_classe_padrao('1994', 100, 'A', G4c, '1994-03-01', '1994-03-31', 'Lei 8.880/94, art. 22 e seguintes', vtexto='01/03/1994 em URV - Tabela CJF e TRT 17ª', moeda='URV')
bloco_classe_padrao('1994', 125, 'A', G4c, '1994-04-01', '1994-12-31', 'Lei 8.880/94', vtexto='A partir de Abril em REAL - com 11,98%', moeda='URV (R$ a partir de 07/1994)')
alert('1994', 'G119', 'valor suspeito', 'Nível intermediário D-I em mar/1994 (URV) = 11,49 (e H/I/J da mesma linha ~10× menores que o esperado); provável erro de digitação (esperado ≈ 111,49). Mantido como está.', 'alta')
alert('1994-nao utilizar', '-', 'aba descartada', 'Aba marcada "nao utilizar" não foi importada.', 'baixa')

# ---------------------------------------------------------------- 1995 a 1999 (magistrados)
MAGPAE = lambda vb, pc, rep, pae, aux, esc, tot: {vb: R('VB'), pc: R('PERC_REPRESENTACAO', unidade='%'), rep: R('REPRESENTACAO_MENSAL'),
                                                   pae: R('PAE'), aux: R('PAE_AUXILIO_MORADIA'), esc: R('PAE_AUX_MORADIA_ESCALONADO_5PCT'), tot: R('TOTAL', e_total=True)}
magist('1995', 5, {'C': R('VB'), 'D': R('PERC_REPRESENTACAO', unidade='fator'), 'E': R('REPRESENTACAO_MENSAL'), 'G': R('PAE'), 'I': R('TOTAL', e_total=True)},
       '1995-01-01', '1995-01-31', 'Não informada na planilha', r2=8)
magist('1995', 13, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1995-02-01', '1995-02-28', 'Não informada na planilha', r2=16)
magist('1995', 21, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1995-03-01', '1995-07-31', 'Não informada na planilha', r2=24)
magist('1995', 29, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1995-08-01', '1995-12-31', 'Não informada na planilha', r2=32)
alert('1995', 'D5:D8', 'unidade inconsistente', 'Percentual de representação em jan/1995 está como fator (2,12) e nos demais blocos como percentual (212). Campo "unidade" diferencia.', 'baixa')
for sh, r, ini, fim in [('1995', 9, '1995-01-01', '1995-01-31'), ('1995', 17, '1995-02-01', '1995-02-28'), ('1995', 25, '1995-03-01', '1995-07-31'),
                        ('1995', 33, '1995-08-01', '1995-12-31'), ('1996', 9, '1996-01-01', '1996-01-31'), ('1996', 18, '1996-02-01', '1996-12-31'),
                        ('1997', 9, '1997-01-01', '1997-12-31'), ('1998', 9, '1998-01-01', '1998-12-31'), ('1999', 10, '1999-01-01', '1999-12-31'),
                        ('2000', 11, '2000-01-01', '2000-12-31')]:
    txt = str(WBV[sh][f'A{r}'].value)
    m = re.search(r'(\d{1,3}),(\d{2})\s*$', txt)
    if m:
        emit(sh, f'A{r}', float(f'{m.group(1)}.{m.group(2)}'), dict(grupo='MAGISTRADO', vigencia_inicio=ini, vigencia_fim=fim, moeda='R$', base_legal='Não informada na planilha'),
             cargo='JUIZ CLASSISTA DE VARA/JCJ', rubrica='VALOR_POR_SESSAO', observacao='Valor por sessão; extraído do texto da célula.')
    m = re.search(r'R\$\s*([\d.]+),(\d{2})', txt)
    if m and not re.search(r'(\d{1,3}),(\d{2})\s*$', txt):
        emit(sh, f'A{r}', float(m.group(1).replace('.', '') + '.' + m.group(2)), dict(grupo='MAGISTRADO', vigencia_inicio=ini, vigencia_fim=fim, moeda='R$', base_legal='Não informada na planilha'),
             cargo='JUIZ CLASSISTA DE VARA/JCJ', rubrica='VALOR_POR_SESSAO', observacao='Valor por sessão; extraído do texto da célula.')
magist('1996', 5, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1996-01-01', '1996-01-31', 'Não informada na planilha', r2=8)
magist('1996', 14, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1996-02-01', '1996-12-31', 'Não informada na planilha', r2=17)
magist('1997', 5, MAGPAE('C', 'D', 'E', 'G', 'I', 'J', 'K'), '1997-01-01', '1997-12-31', 'Não informada na planilha', r2=8,
       observacao='Em 1997 a PAE foi alterada a partir da folha de out/1997 (ver nota A10 da aba).')
alert('1997', 'A10', 'informação incompleta', 'Nota informa que a PAE foi alterada em out/1997 (retroativa a jan/97), mas o valor foi DEVOLVIDO depois. Tabela importada como vigente o ano todo, sem a alteração.', 'baixa')
MAG98 = {'C': R('VB'), 'D': R('PERC_REPRESENTACAO', unidade='%'), 'E': R('REPRESENTACAO_MENSAL'), 'G': R('PARCELA_AUTONOMA_EQUIVALENCIA'), 'I': R('TOTAL', e_total=True)}
magist('1998', 5, MAG98, '1998-01-01', '1998-12-31', 'Não informada na planilha', r2=8)
magist('1999', 5, MAG98, '1999-01-01', '1999-12-31', 'Não informada na planilha', r2=9)

# ---------------------------------------------------------------- 1995/1996: DAS, gratificação de gabinete, cargos
DAS1 = {'B': R('DAS_VENCIMENTO'), 'C': R('DAS_DIFERENCA'), 'D': R('DAS_SUBTOTAL', e_total=True), 'E': R('DAS_PERC_REPRESENTACAO', unidade='fator'),
        'F': R('DAS_REPRESENTACAO_MENSAL'), 'G': R('DAS_55PCT'), 'H': R('GADF_PERC', unidade='fator'), 'I': R('GADF'), 'J': R('GADF_55PCT')}
block('1995', 38, [('A', 'funcao', False)], DAS1, r2=43, grupo='DAS', vigencia_inicio='1995-03-01', vigencia_fim='1995-12-31', base_legal='Não informada na planilha',
      vigencia_texto='DAS - MAR/DEZ/95 (1º bloco)')
DAS2 = dict(DAS1); DAS2['B'] = R('DAS_VENCIMENTO')
block('1995', 48, [('A', 'funcao', False)], DAS2, r2=53, grupo='DAS', vigencia_inicio='1995-03-01', vigencia_fim='1995-12-31', base_legal='Lei 9.030/95',
      vigencia_texto='DAS - MAR/DEZ/95 (2º bloco)', observacao='Para DAS-04 a DAS-06 o valor em B é a retribuição única (Lei 9.030/95).')
alert('1995', 'A35:K53', 'blocos conflitantes', 'Dois blocos de DAS com o mesmo título "MAR/DEZ/95" e valores diferentes (ex.: DAS-01 venc. 115,84 × 197,80). O 2º cita Lei 9.030/95 — provavelmente o 1º vale para jan/fev/95. Ambos importados; confirmar.', 'alta')
block('1996', 24, [('A', 'funcao', False)], DAS2, r2=29, grupo='DAS', vigencia_inicio='1996-01-01', vigencia_fim='1996-12-31', base_legal='Lei 9.030/95',
      observacao='Para DAS-04 a DAS-06 o valor em B é a retribuição única (Lei 9.030/95). Observar opção pelo cargo efetivo (25%).')
GG = {'B': R('GRAT_GABINETE'), 'C': R('DIFERENCA'), 'D': R('SOMA', e_total=True), 'E': R('GADF'), 'F': R('TOTAL', e_total=True)}
for sh, r, mod, ini, fim in [('1995', 57, 'COM VÍNCULO', '1995-01-01', '1995-02-28'), ('1995', 65, 'COM VÍNCULO', '1995-03-01', '1995-12-31'),
                             ('1995', 73, 'SEM VÍNCULO', '1995-01-01', '1995-02-28'), ('1995', 81, 'SEM VÍNCULO', '1995-03-01', '1995-12-31'),
                             ('1996', 35, 'COM VÍNCULO', '1996-01-01', '1996-12-31'), ('1996', 43, 'SEM VÍNCULO', '1996-01-01', '1996-12-31')]:
    block(sh, r, [('A', 'funcao', False)], GG, r2=r + 4, grupo='GRATIFICACAO_GABINETE', modalidade=mod, vigencia_inicio=ini, vigencia_fim=fim,
          base_legal='Não informada na planilha')
CARG95 = lambda: None
for sh, r_aj, r_aux, ini, fim in [('1995', 89, 112, '1995-01-01', '1995-12-31'), ('1996', 51, 74, '1996-01-01', '1996-12-31')]:
    block(sh, r_aj, [('A', 'ref', False)], {'B': R('VB', cargo='ANALISTA JUDICIÁRIO'), 'C': R('DIF_28_86', cargo='ANALISTA JUDICIÁRIO'),
                                             'D': R('GRAT_EXTRAORDINARIA', cargo='ANALISTA JUDICIÁRIO'), 'E': R('TOTAL', cargo='ANALISTA JUDICIÁRIO', e_total=True)},
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Não informada na planilha')
    block(sh, r_aj, [('F', 'ref', False)], {'G': R('VB', cargo='TÉCNICO JUDICIÁRIO'), 'H': R('DIF_28_86', cargo='TÉCNICO JUDICIÁRIO'),
                                             'I': R('GRAT_EXTRAORDINARIA', cargo='TÉCNICO JUDICIÁRIO'), 'J': R('TOTAL', cargo='TÉCNICO JUDICIÁRIO', e_total=True)},
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Não informada na planilha')
    block(sh, r_aux, [('A', 'ref', False)], {'B': R('VB', cargo='AUXILIAR JUDICIÁRIO'), 'C': R('DIF_28_86', cargo='AUXILIAR JUDICIÁRIO'),
                                              'D': R('GRAT_EXTRAORDINARIA', cargo='AUXILIAR JUDICIÁRIO'), 'E': R('TOTAL', cargo='AUXILIAR JUDICIÁRIO', e_total=True)},
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Não informada na planilha')
alert('1995', 'A87:J131', 'vigência genérica', 'Tabelas de cargos efetivos de 1995 e 1996 não informam data de vigência; atribuída ao ano inteiro da aba. Valores de 1995 e 1996 são idênticos.', 'média')
alert('1996', 'L27', 'dado pessoal', 'Observação cita nome de servidor como exemplo; nome omitido na base.', 'baixa')

# ---------------------------------------------------------------- 1997-1999 (PCS Lei 9.421/96)
def fc_9421(sh, r1, r2, ini, fim):
    block(sh, r1, [('A', 'funcao', False)], {'B': R('FC_OPCAO_70PCT', modalidade='OPTANTE'), 'C': R('REDUTOR', modalidade='OPTANTE'),
                                             'D': R('TOTAL', modalidade='OPTANTE', e_total=True)},
          r2=r2, grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 9.421/96')
    block(sh, r1, [('F', 'funcao', True)], {'G': R('FC_VALOR_BASE', modalidade='INTEGRAL'), 'H': R('FC_GAJ', modalidade='INTEGRAL'),
                                            'I': R('FC_APJ', modalidade='INTEGRAL'), 'J': R('FC_TOTAL_BRUTO', modalidade='INTEGRAL', e_total=True),
                                            'K': R('REDUTOR', modalidade='INTEGRAL'), 'L': R('TOTAL', modalidade='INTEGRAL', e_total=True)},
          r2=r2, grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 9.421/96')


def decimos_vrt(sh, r1, r2, fracs, ini, fim, base='Lei 9.421/96'):
    cols = {}
    for i, fr in enumerate(fracs):
        b = ci('B') + 3 * i
        cols[gl(b)] = R('DECIMOS_VALOR', fracao=fr)
        cols[gl(b + 1)] = R('DECIMOS_REDUTOR', fracao=fr)
        cols[gl(b + 2)] = R('DECIMOS_TOTAL', fracao=fr, e_total=True)
    block(sh, r1, [('A', 'funcao', False)], cols, r2=r2, grupo='DECIMOS_QUINTOS', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)


def cargos_9421(sh, r1, r_aux, ini, fim, com_redutor=True, col_ref_tec='H'):
    if com_redutor:
        aj = {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL_BRUTO', 'F': 'REDUTOR', 'G': 'TOTAL'}
        tj = {'I': 'VB', 'J': 'GAJ', 'K': 'APJ', 'L': 'TOTAL_BRUTO', 'M': 'REDUTOR', 'N': 'TOTAL'}
    for cargo, keycol, mp in [('ANALISTA JUDICIÁRIO', 'A', aj), ('TÉCNICO JUDICIÁRIO', col_ref_tec, tj)]:
        block(sh, r1, [(keycol, 'ref', False)], {c: R(v, cargo=cargo, e_total=v.startswith('TOTAL')) for c, v in mp.items()}, r2=r1 + 14,
              grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 9.421/96')
    block(sh, r_aux, [('A', 'ref', False)], {c: R(v, cargo='AUXILIAR JUDICIÁRIO', e_total=v.startswith('TOTAL')) for c, v in aj.items()}, r2=r_aux + 14,
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 9.421/96')

for sh, rfc, rd1, rd2, rc, raux in [('1997', 16, 29, 42, 56, 74), ('1998', 15, 28, 41, 55, 73), ('1999', 16, 30, 43, 58, 76)]:
    ini, fim = f'{sh}-01-01', f'{sh}-12-31'
    fc_9421(sh, rfc, rfc + 7, ini, fim)
    decimos_vrt(sh, rd1, rd1 + 9, ['1/10', '2/10', '3/10', '4/10', '5/10'], ini, fim)
    decimos_vrt(sh, rd2, rd2 + 9, ['6/10', '7/10', '8/10', '9/10', '10/10'], ini, fim)
    cargos_9421(sh, rc, raux, ini, fim)
    alert(sh, '-', 'vigência genérica', f'Tabelas de FC, décimos e cargos efetivos da aba {sh} não informam data de vigência; atribuída ao ano inteiro.', 'média')

# ---------------------------------------------------------------- 2000-2002 (FC com GAJ/APJ, décimos simples)
def fc_2000(sh, r1, r2, ini, fim, cols_opt, cols_int, base='Lei 9.421/96'):
    fo, vo = cols_opt
    block(sh, r1, [(fo, 'funcao', False)], {vo: R('FC_OPCAO_70PCT', modalidade='OPTANTE')}, r2=r2,
          grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)
    fi, mp = cols_int
    block(sh, r1, [(fi, 'funcao', False)], {c: R(v, modalidade='INTEGRAL', unidade=('%' if v == 'FC_PERC_GAJ' else None), e_total=(v == 'FC_TOTAL'))
                                            for c, v in mp.items()}, r2=r2, grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)


def decimos_simples(sh, r1, r2, ini, fim, base='Lei 9.421/96'):
    cols = {gl(ci('B') + i): R('DECIMOS', fracao=f'{i + 1}/10') for i in range(10)}
    block(sh, r1, [('A', 'funcao', False)], cols, r2=r2, grupo='DECIMOS_QUINTOS', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)


def cargos_simples(sh, r_aj, r_aux, ini, fim, aj_map, tj_key, tj_map, aux_map, base, r_aj_n=15, r_aux_n=15, obs=None):
    block(sh, r_aj, [('A', 'ref', False)], {c: R(v, cargo='ANALISTA JUDICIÁRIO', e_total=v.startswith('TOTAL')) for c, v in aj_map.items()}, r2=r_aj + r_aj_n - 1,
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, observacao=obs)
    block(sh, r_aj, [(tj_key, 'ref', False)], {c: R(v, cargo='TÉCNICO JUDICIÁRIO', e_total=v.startswith('TOTAL')) for c, v in tj_map.items()}, r2=r_aj + r_aj_n - 1,
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, observacao=obs)
    block(sh, r_aux, [('A', 'ref', False)], {c: R(v, cargo='AUXILIAR JUDICIÁRIO', e_total=v.startswith('TOTAL')) for c, v in aux_map.items()}, r2=r_aux + r_aux_n - 1,
          grupo='SERVIDOR_EFETIVO', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, observacao=obs)

# 2000
MAG00 = {'C': R('VB'), 'E': R('PERC_REPRESENTACAO', unidade='%'), 'F': R('REPRESENTACAO_MENSAL'), 'H': R('PARCELA_AUTONOMA_EQUIVALENCIA'), 'K': R('TOTAL', e_total=True)}
magist('2000', 6, MAG00, '2000-01-01', '2000-12-31', 'Não informada na planilha', r2=10)
alert('2000', 'C13:H13', 'valores sem rótulo', 'Linha 13 traz valores soltos (480,00; 931,20; 5.119,47) sem rótulo; não importados.', 'média')
fc_2000('2000', 19, 26, '2000-01-01', '2000-12-31', ('A', 'C'), ('E', {'F': 'FC_VALOR_BASE', 'H': 'FC_PERC_GAJ', 'I': 'FC_GAJ', 'J': 'FC_APJ', 'K': 'FC_TOTAL'}))
block('2000', 19, [('A', 'funcao', False)], {'B': R('FC_VALOR_BASE', modalidade='OPTANTE')}, r2=26, grupo='FUNCAO_COMISSIONADA',
      vigencia_inicio='2000-01-01', vigencia_fim='2000-12-31', base_legal='Lei 9.421/96')
decimos_simples('2000', 31, 40, '2000-01-01', '2000-12-31')
alert('2000', 'B29:K29', 'cabeçalho corrompido', 'Frações 1/10…10/10 foram convertidas pelo Excel em datas (01/10/2007…10/10/2007). Interpretadas como frações.', 'média')
cargos_simples('2000', 45, 64, '2000-01-01', '2000-12-31', {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'G', {'H': 'VB', 'I': 'GAJ', 'J': 'APJ', 'K': 'TOTAL'},
               {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'Lei 9.421/96')
# 2001
MAG01 = {'C': R('VB'), 'E': R('PERC_REPRESENTACAO', unidade='%'), 'F': R('REPRESENTACAO_MENSAL'), 'H': R('PARCELA_AUTONOMA_EQUIVALENCIA'),
         'K': R('PARCELA_ATO_TST_GP_109_2001'), 'L': R('TOTAL', e_total=True)}
magist('2001', 6, MAG01, '2001-01-01', '2001-12-31', 'Ato TST.GP n.º 109/2001 (parcela)', r2=10)
INT01 = {'D': 'FC_VALOR_BASE', 'F': 'FC_PERC_GAJ', 'G': 'FC_GAJ', 'H': 'FC_APJ', 'I': 'FC_TOTAL'}
fc_2000('2001', 18, 25, '2001-01-01', '2001-12-31', ('A', 'B'), ('C', INT01))
alert('2001', 'B26', 'valor sem rótulo', 'Valor 12.626,43 isolado abaixo da tabela de FC, sem rótulo; não importado.', 'média')
decimos_simples('2001', 31, 40, '2001-01-01', '2001-12-31')
cargos_simples('2001', 45, 63, '2001-01-01', '2001-12-31', {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'F', {'G': 'VB', 'H': 'GAJ', 'I': 'APJ', 'J': 'TOTAL'},
               {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'Lei 9.421/96')
# 2002
MAG02a = {'C': R('VB'), 'E': R('PERC_REPRESENTACAO', unidade='%'), 'F': R('REPRESENTACAO_MENSAL'), 'H': R('PARCELA_AUTONOMA_EQUIVALENCIA'),
          'K': R('PARCELA_STF_195_2000'), 'L': R('TOTAL', e_total=True)}
magist('2002', 6, MAG02a, '2002-01-01', '2002-05-31', 'Não informada na planilha', r2=10)
magist('2002', 16, {'C': R('VB'), 'E': R('PERC_REPRESENTACAO', unidade='%'), 'F': R('REPRESENTACAO_MENSAL'), 'H': R('TOTAL', e_total=True)},
       '2002-06-01', '2002-12-31', 'Lei 10.474/2002', r2=20)
fc_2000('2002', 28, 35, '2002-01-01', '2002-12-31', ('A', 'B'), ('C', INT01))
decimos_simples('2002', 40, 49, '2002-01-01', '2002-12-31')
alert('2002', 'K39', 'cabeçalho corrompido', 'Fração 10/10 convertida em data pelo Excel; interpretada como 10/10.', 'baixa')
cargos_simples('2002', 54, 72, '2002-01-01', '2002-05-31', {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'F', {'G': 'VB', 'H': 'GAJ', 'I': 'APJ', 'J': 'TOTAL'},
               {'B': 'VB', 'C': 'GAJ', 'D': 'APJ', 'E': 'TOTAL'}, 'Lei 9.421/96')
cargos_simples('2002', 90, 109, '2002-06-01', '2002-12-31', {'B': 'VB', 'C': 'GAJ', 'D': 'TOTAL'}, 'E', {'F': 'VB', 'G': 'GAJ', 'H': 'TOTAL'},
               {'B': 'VB', 'C': 'GAJ', 'D': 'TOTAL'}, 'Lei 10.475/2002')

# ---------------------------------------------------------------- 2003-2008
MAGRM = {'C': R('VB'), 'D': R('PERC_REPRESENTACAO', unidade='fator'), 'E': R('REPRESENTACAO_MENSAL'), 'F': R('TOTAL', e_total=True)}
magist('2003', 7, MAGRM, '2003-01-01', '2003-12-31', 'Lei 10.474/2002', r2=11)
magist('2004', 6, MAGRM, '2004-01-01', '2004-12-31', 'Lei 10.474/2002', r2=10)
SUBS = {'C': R('SUBSIDIO'), 'E': R('SUBSTITUICAO')}
magist('2005', 6, SUBS, '2005-01-01', '2005-12-31', 'Lei 11.143/2005', r2=10,
       observacao='Subsídio fixado pela Lei 11.143/2005 (efeitos a partir de jan/2005, conforme planilha).')
magist('2006', 7, SUBS, '2006-01-01', '2006-12-31', 'Lei 11.143/2005', r2=11)
magist('2007', 4, SUBS, '2007-01-01', '2007-12-31', 'Lei 11.143/2005', r2=8)
magist('2008', 3, SUBS, '2008-01-01', '2008-12-31', 'Lei 11.143/2005', r2=7)
alert('2006', 'C8', 'valor ausente', 'Subsídio do Ministro do TST em branco nas abas 2006–2008.', 'baixa')


def fc_opt_int(sh, r1, r2, ini, fim, base, opt=('A', 'B'), integ=('C', 'D'), pct='70', modal_nome=('OPTANTE', 'INTEGRAL'), obs=None):
    block(sh, r1, [(opt[0], 'funcao', False)], {opt[1]: R(f'FC_OPCAO_{pct}PCT', modalidade=modal_nome[0])}, r2=r2,
          grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, observacao=obs)
    block(sh, r1, [(integ[0], 'funcao', True)], {integ[1]: R('FC_INTEGRAL', modalidade=modal_nome[1])}, r2=r2,
          grupo='FUNCAO_COMISSIONADA', vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, observacao=obs)


fc_opt_int('2003', 18, 27, '2003-01-01', '2003-12-31', 'Lei 9.421/96 (valores Lei 10.475/2002)')
fc_opt_int('2004', 17, 26, '2004-01-01', '2004-12-31', 'Lei 9.421/96 (valores Lei 10.475/2002)')
fc_opt_int('2005', 17, 26, '2005-01-01', '2005-12-31', 'Lei 9.421/96 (valores Lei 10.475/2002)')
decimos_simples('2003', 32, 41, '2003-01-01', '2003-12-31')
decimos_simples('2004', 30, 39, '2004-01-01', '2004-12-31')
decimos_simples('2005', 30, 39, '2005-01-01', '2005-12-31')
decimos_simples('2006', 33, 42, '2006-01-01', '2006-05-31', base='Lei 9.421/96; Lei 11.416/06')
alert('2006', 'A30:K42', 'vigência genérica', 'Tabela de décimos de 2006 corresponde aos valores integrais de JAN/MAI (CJ-04 10/10 = 7.791,17); importada com vigência jan–mai/2006. Não há décimos para jun/2006 em diante.', 'média')
for sh, r1, r2, per in [('2006', 18, 27, [('B', 'F', '2006-01-01', '2006-05-31'), ('C', 'G', '2006-06-01', '2006-11-30'), ('D', 'H', '2006-12-01', '2006-12-31')]),
                        ('2007', 17, 26, [('B', 'F', '2007-01-01', '2007-05-31'), ('C', 'G', '2007-06-01', '2007-11-30'), ('D', 'H', '2007-12-01', '2007-12-31')]),
                        ('2008', 16, 25, [('B', 'F', '2008-01-01', '2008-06-30'), ('C', 'G', '2008-07-01', '2008-11-30'), ('D', 'H', '2008-12-01', '2008-12-31')])]:
    for co, cint, ini, fim in per:
        block(sh, r1, [('A', 'funcao', False)], {co: R('FC_OPCAO_70PCT', modalidade='OPTANTE')}, r2=r2, grupo='FUNCAO_COMISSIONADA',
              vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 11.416/06 (implantação escalonada)')
        block(sh, r1, [('E', 'funcao', False)], {cint: R('FC_INTEGRAL', modalidade='INTEGRAL')}, r2=r2, grupo='FUNCAO_COMISSIONADA',
              vigencia_inicio=ini, vigencia_fim=fim, base_legal='Lei 11.416/06 (implantação escalonada)')
alert('2006', 'F22:H27', 'valores ausentes', 'FC-06 a FC-01 "integral" só têm valor para JAN/MAI nas abas 2006–2008 (colunas JUN/NOV e DEZ vazias).', 'média')
alert('2008', 'A14:H25', 'lacuna 2009–2022', 'Não há tabelas de FC/CJ nas abas 2009 a 2022 (exceto CJ/FC de 2016 e VPI/VPNI de 2015–2016). Última tabela: dez/2008. Para essas competências a IA deve sinalizar ausência de dado.', 'alta')

CG3 = ({'B': 'VB', 'C': 'GAJ', 'D': 'TOTAL'}, 'E', {'F': 'VB', 'G': 'GAJ', 'H': 'TOTAL'}, {'B': 'VB', 'C': 'GAJ', 'D': 'TOTAL'})
for sh, raj, raux, ini, fim, base, n in [
    ('2003', 49, 68, '2003-01-01', '2003-05-31', 'Lei 10.475/2002', 15),
    ('2003', 88, 107, '2003-06-01', '2003-12-31', 'Lei 10.475/2002', 15),
    ('2004', 45, 64, '2004-01-01', '2004-06-30', 'Lei 10.475/2002 (GAJ 12%)', 15),
    ('2004', 84, 103, '2004-07-01', '2004-12-31', 'Lei 10.944/04 (GAJ 20% a partir de 01/07/2004)', 15),
    ('2005', 45, 64, '2005-01-01', '2005-10-31', 'Lei 10.475/02 (GAJ 20%)', 15),
    ('2005', 84, 102, '2005-11-01', '2005-12-31', 'Lei 10.944/04 (GAJ 30% a partir de 01/11/2005)', 15),
    ('2006', 53, 72, '2006-01-01', '2006-05-31', 'Lei 10.475/02 (GAJ 30%)', 15),
    ('2006', 92, 111, '2006-06-01', '2006-11-30', 'Lei 10.944/04 (GAJ 33%)', 15),
    ('2006', 131, 150, '2006-12-01', '2006-12-31', 'Lei 10.944/04 (GAJ 36%)', 15),
    ('2007', 33, 52, '2007-01-01', '2007-06-30', 'Lei 10.944/04 (GAJ 36%)', 15),
    ('2007', 73, 92, '2007-07-01', '2007-11-30', 'Lei 10.944/04 (GAJ 39%)', 15),
    ('2007', 113, 132, '2007-12-01', '2007-12-31', 'Lei 11.416/06 (GAJ 42%)', 15),
    ('2008', 32, 51, '2008-01-01', '2008-06-30', 'Lei 11.416/06 (GAJ 42%)', 15),
    ('2008', 72, 91, '2008-07-01', '2008-11-30', 'Lei 11.416/06 (GAJ 46%)', 15),
    ('2008', 112, 132, '2008-12-01', '2012-12-30', 'Lei 11.416/06 (GAJ 50%)', 15)]:
    cargos_simples(sh, raj, raux, ini, fim, CG3[0], CG3[1], CG3[2], CG3[3], base, r_aj_n=n, r_aux_n=n)
alert('2003', 'A45:A46', 'rubrica fora da tabela', 'VPI (Lei 10.698/03) de R$ 59,87 a partir de mai/2003 (rubrica 400) consta só como observação; incluída na tabela de parâmetros.', 'média')
alert('2008', 'A108', 'vigência longa', 'Tabela "DEZEMBRO/2008 a DEZEMBRO/2012" vale até 30/12/2012; em 31/12/2012 vale a tabela da aba 2012 (Lei 12.774/12).', 'baixa')

# ---------------------------------------------------------------- 2009-2026 magistrados
for sh, r1, r2, ini, fim, base, cols in [
    ('2009', 7, 11, '2009-01-01', '2009-08-31', 'Lei 11.143/2005', SUBS),
    ('2009', 16, 20, '2009-09-01', '2010-01-31', 'Lei 12.041/2009', SUBS),
    ('2009', 26, 30, '2010-02-01', '2012-12-31', 'Lei 12.041/2009', SUBS),
    ('2013', 8, 12, '2013-01-01', '2013-12-31', 'Lei 12.771/2012', SUBS),
    ('2014', 6, 10, '2014-01-01', '2014-12-31', 'Lei 12.771/2012', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')}),
    ('2015', 10, 12, '2015-01-01', '2018-12-31', 'Leis 9.655/1998 e 13.091/2015', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')}),
    ('2019', 8, 10, '2019-01-01', '2023-03-31', 'Lei 13.752/2018', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')}),
    ('2023', 20, 22, '2023-04-01', '2024-01-31', 'Lei 14.520/2023 e Lei 10.474/2002', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')}),
    ('2024', 17, 19, '2024-02-01', '2025-01-31', 'Lei 14.520/2023 e Lei 10.474/2002', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')}),
    ('2025', 17, 19, '2025-02-01', None, 'Lei 14.520/2023 e Lei 10.474/2002', {'D': R('SUBSIDIO'), 'F': R('SUBSTITUICAO')})]:
    magist(sh, r1, cols, ini, fim, base, r2=r2)
for sh, cell, ini, fim, base, cargo in [
    ('2015', 'C7', '2015-01-01', '2018-12-31', 'Lei 13.091/2015', 'MINISTRO DO STF'), ('2015', 'C8', '2015-01-01', '2018-12-31', 'Lei 13.091/2015', 'MINISTRO DO TST'),
    ('2019', 'C5', '2019-01-01', '2023-03-31', 'Lei 13.752/2018', 'MINISTRO DO STF'), ('2019', 'C6', '2019-01-01', '2023-03-31', 'Lei 13.752/2018', 'MINISTRO DO TST'),
    ('2023', 'C17', '2023-04-01', '2024-01-31', 'Lei 14.520/2023', 'MINISTRO DO STF'), ('2023', 'C18', '2023-04-01', '2024-01-31', 'Lei 14.520/2023', 'MINISTRO DO TST'),
    ('2024', 'C14', '2024-02-01', '2025-01-31', 'Lei 14.520/2023', 'MINISTRO DO STF'), ('2024', 'C15', '2024-02-01', '2025-01-31', 'Lei 14.520/2023', 'MINISTRO DO TST'),
    ('2025', 'C14', '2025-02-01', None, 'Lei 14.520/2023', 'MINISTRO DO STF'), ('2025', 'C15', '2025-02-01', None, 'Lei 14.520/2023', 'MINISTRO DO TST')]:
    emit(sh, cell, float(WBV[sh][cell].value), dict(grupo='MAGISTRADO', vigencia_inicio=ini, vigencia_fim=fim, moeda='R$', base_legal=base), cargo=cargo, rubrica='SUBSIDIO')
alert('2009', 'A4:A13', 'vigência sobreposta', 'Bloco "DE 01/01/2006 A 30/09/2009" sobrepõe-se ao bloco "DE 01/09/2009 A 31/01/2010" em set/2009. Adotado fim em 31/08/2009.', 'média')
alert('2017', 'D8:F10', 'valores ausentes', 'Abas 2017 e 2018: subsídios de Desembargador e Juízes em branco. Mantida a tabela de 2015 (Lei 13.091/2015) até 31/12/2018.', 'alta')
alert('2015', 'C7:F12', 'abas repetidas', 'Abas 2010–2012, 2016, 2020–2022 repetem tabelas de magistrados já importadas de outras abas; não foram duplicadas.', 'baixa')
alert('2026', 'A1:F9', 'tabela repetida', 'Aba 2026 repete o subsídio a partir de 1º/2/2025; importado uma vez (vigência aberta).', 'baixa')

# ---------------------------------------------------------------- 2012-2026 cargos efetivos (Classe/Padrão)
def cargos_cp(sh, r1, r2, ini, fim, base, cols=None, vtexto=None, obs=None):
    cols = cols or {'D': R('VB'), 'E': R('GAJ'), 'F': R('TOTAL', e_total=True)}
    block(sh, r1, [('A', 'cargo', True), ('B', 'classe', True), ('C', 'padrao', False)], cols, r2=r2, grupo='SERVIDOR_EFETIVO',
          vigencia_inicio=ini, vigencia_fim=fim, base_legal=base, vigencia_texto=vtexto, observacao=obs)

cargos_cp('2012', 19, 57, '2012-12-31', '2012-12-31', 'Lei 12.774/2012 (GAJ 50%)', vtexto='TABELA VÁLIDA APENAS PARA O DIA 31/12/2012')
cargos_cp('2013', 18, 56, '2013-01-01', '2013-12-31', 'Lei 12.774/2012 (GAJ 62%)')
cargos_cp('2014', 18, 56, '2014-01-01', '2014-12-31', 'Lei 12.774/2012 (GAJ 75,2%)')
cargos_cp('2015', 19, 57, '2015-01-01', '2016-07-20', 'Leis 11.416/2006 e 12.774/2012 (GAJ 90%)')
alert('2013', 'E18:E56', 'arredondamento', 'GAJ de 2013–2014 com 4 casas decimais (sem arredondamento); valores pagos em folha podem diferir em centavos.', 'baixa')
cargos_cp('2016', 42, 80, '2016-07-21', '2016-10-31', 'Lei 13.317/2016 (GAJ 104%)')
cargos_cp('2016', 85, 123, '2016-11-01', '2017-05-31', 'Lei 13.317/2016 (GAJ 108%)')
cargos_cp('2017', 16, 54, '2017-06-01', '2017-10-31', 'Lei 13.317/2016 (GAJ 113%)')
cargos_cp('2017', 59, 97, '2017-11-01', '2018-05-31', 'Lei 13.317/2016 (GAJ 122%)')
cargos_cp('2018', 16, 54, '2018-06-01', '2018-10-31', 'Lei 13.317/2016 (GAJ 125%)')
cargos_cp('2018', 59, 97, '2018-11-01', '2018-12-31', 'Lei 13.317/2016 (GAJ 130%)')
cargos_cp('2019', 16, 54, '2019-01-01', '2023-01-31', 'Lei 13.317/2016 (GAJ 140%)')
cargos_cp('2023', 43, 81, '2023-02-01', '2024-01-31', 'Lei 14.523/2023 (GAJ 140%)')
cargos_cp('2024', 85, 123, '2024-02-01', '2025-01-31', 'Lei 14.523/2023 (GAJ 140%)')
cargos_cp('2025', 85, 123, '2025-02-01', '2026-06-30', 'Lei 14.523/2023 (GAJ 140%)')
cargos_cp('2026', 95, 133, '2026-07-01', None, 'Lei 15.293/2025 (GAJ 140%)',
          cols={'D': R('VB'), 'E': R('GAJ'), 'F': R('TOTAL', e_total=True), 'G': R('GAS'), 'H': R('GAE')},
          obs='GAS (35%) aplica-se a Técnico Judiciário – Agente de Polícia Judicial; GAE (35%) a Analista Judiciário – Oficial de Justiça Avaliador Federal (colunas G/H).')
alert('2018', 'H23:H25', 'nota de pagamento', 'VB do Analista C-13 de 01/06/2018 a 31/10/2018 é R$ 7.512,00 (tabela CSJT), não R$ 7.514,00 como pago; diferença restituída na folha de dez/2018.', 'média')
alert('2025', 'D87:D123', 'fórmulas sem arredondamento', 'Vários vencimentos básicos a partir de 1º/2/2025 vêm de fórmula ="2024"!Dxx*1,0613 sem ROUND (ex.: AJ C-11 = 8.758,7285). O valor legal publicado é arredondado a 2 casas; a base mantém o valor da planilha e o campo origem_formula sinaliza. Conferir com a Lei 14.523/2023 (Anexo).', 'alta')
alert('2026', 'A27:F69', 'tabela repetida', 'Aba 2026, tabela "a partir de 1º/2/2025", repete a da aba 2025; importada uma vez (até 30/06/2026).', 'baixa')
alert('2016', 'A42:F123', 'abas repetidas', 'Abas 2020–2022 repetem a tabela de 01/01/2019 (aba 2019); importada uma vez com vigência 01/2019–01/2023.', 'baixa')

# ---------------------------------------------------------------- FC/CJ 2016, 2023-2026
block('2016', 17, [('B', 'funcao', False)], {'C': R('FC_INTEGRAL', modalidade='INTEGRAL'), 'D': R('FC_OPCAO_65PCT', modalidade='OPTANTE')}, r2=20,
      grupo='FUNCAO_COMISSIONADA', vigencia_inicio='2016-01-01', vigencia_fim='2016-07-20', base_legal='Lei 11.416/06', vigencia_texto='CJ - até 20/07/2016')
block('2016', 24, [('B', 'funcao', False)], {'C': R('FC_INTEGRAL', modalidade='INTEGRAL'), 'D': R('FC_OPCAO_65PCT', modalidade='OPTANTE')}, r2=27,
      grupo='FUNCAO_COMISSIONADA', vigencia_inicio='2016-07-21', vigencia_fim=None, base_legal='Lei 13.317/16', vigencia_texto='CJ - Reajuste Lei 13.317/16',
      observacao='Planilha não indica fim; valores escalonados da Lei 13.317/16 para CJ não constam.')
block('2016', 30, [('C', 'funcao', False)], {'D': R('FC_VALOR', modalidade='UNICO')}, r2=35, grupo='FUNCAO_COMISSIONADA',
      vigencia_inicio='2016-07-21', vigencia_fim=None, base_legal='Lei 13.317/16', observacao='Planilha não indica vigência; presumida igual à da tabela de CJ reajustada.')
alert('2016', 'B15:D35', 'vigência incerta', 'Tabelas de CJ/FC de 2016 sem vigência clara e sem as parcelas seguintes do escalonamento da Lei 13.317/16 (2017–2019).', 'alta')
for sh, r1, r2, ini, fim, cols_opt, cols_int, base in [
    ('2023', 28, 37, '2023-02-01', '2024-01-31', ('A', 'B'), ('C', 'D'), 'Lei 14.523/2023'),
    ('2024', 25, 34, '2024-02-01', '2025-01-31', ('E', 'F'), ('G', 'H'), 'Lei 14.523/2023'),
    ('2025', 25, 34, '2025-02-01', '2026-06-30', ('E', 'F'), ('G', 'H'), 'Lei 14.523/2023'),
    ('2026', 79, 88, '2026-07-01', None, ('A', 'B'), ('C', 'D'), 'Lei 15.293/2025')]:
    fo, vo = cols_opt; fi, vi = cols_int
    # CJ: optante (65%) e integral; FC: valor único (coluna "optante")
    block(sh, r1, [(fo, 'funcao', False)], {vo: R('FC_CJ_VALOR', modalidade='VER_FUNCAO')}, r2=r2, grupo='FUNCAO_COMISSIONADA',
          vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)
    block(sh, r1, [(fi, 'funcao', True)], {vi: R('FC_CJ_INTEGRAL_COL', modalidade='VER_FUNCAO')}, r2=r2, grupo='FUNCAO_COMISSIONADA',
          vigencia_inicio=ini, vigencia_fim=fim, base_legal=base)
alert('2025', 'H29:H34', 'valor derivado sem base legal', 'Nas abas 2025/2026 a coluna "INTEGRAL" das FC-06…FC-01 foi preenchida com FC ÷ 0,65 (ex.: FC-06 3.663,71 ÷ 0,65 = 5.636,48). FC não tem opção de 65% — o valor legal da FC é o da coluna "Valor". Esses registros foram marcados como "nao_usar".', 'alta')
alert('2025', 'F25:F34', 'fórmulas sem arredondamento', 'Valores de CJ/FC a partir de 1º/2/2025 com 4+ casas decimais (fórmula). Conferir com o anexo da Lei 14.523/2023.', 'média')
alert('2023', 'A24', 'vigência', 'Tabela de FC/CJ de 2023 sem data explícita; adotado 1º/2/2023 (mesma data da tabela de cargos efetivos da Lei 14.523/2023).', 'média')

# ---------------------------------------------------------------- VPI / VPNI (2015)
for cargo, kcol, cols in [('NÍVEL SUPERIOR', 'I', {'J': 'VB_REF_VPI', 'K': 'VPI_12_23', 'L': 'GAJ_SOBRE_VPI'}),
                          ('NÍVEL INTERMEDIÁRIO', 'N', {'O': 'VB_REF_VPI', 'P': 'VPI_12_23', 'Q': 'GAJ_SOBRE_VPI'})]:
    block('2015', 13, [(kcol, 'ref', False)], {c: R(v, cargo=cargo) for c, v in cols.items()}, r2=25, grupo='VPI_13_23',
          vigencia_inicio='2015-01-01', vigencia_fim='2016-03-31', base_legal='Decisão judicial (VPI 13,23%)', observacao='Pago a alguns servidores — conferir folha.')
block('2015', 30, [('I', 'ref', False)], {'J': R('VB_REF_VPI', cargo='NÍVEL AUXILIAR'), 'K': R('VPI_12_23', cargo='NÍVEL AUXILIAR'), 'L': R('GAJ_SOBRE_VPI', cargo='NÍVEL AUXILIAR')},
      r2=42, grupo='VPI_13_23', vigencia_inicio='2015-01-01', vigencia_fim='2016-03-31', base_legal='Decisão judicial (VPI 13,23%)', observacao='Pago a alguns servidores — conferir folha.')
block('2015', 30, [('N', 'funcao', False)], {'O': R('FC_CC_REF_VPI'), 'P': R('VPI_12_23')}, r2=39, grupo='VPI_13_23',
      vigencia_inicio='2015-01-01', vigencia_fim='2016-03-31', base_legal='Decisão judicial (VPI 13,23%)', observacao='Pago a alguns servidores — conferir folha.')
block('2015', 47, [('I', 'funcao', False)], {'J': R('VPNI', fracao='10/10'), 'K': R('VPNI', fracao='5/5'), 'L': R('VPNI', fracao='4/5'), 'M': R('VPNI', fracao='3/5'),
                                             'N': R('VPNI', fracao='2/5'), 'O': R('VPNI', fracao='1/5')}, r2=56, grupo='VPNI_QUINTOS',
      vigencia_inicio='2015-01-01', vigencia_fim=None, base_legal='Não informada na planilha', observacao='Tabela de VPNI (quintos/décimos incorporados).')
alert('2015', 'K12:L12', 'rótulo divergente', 'Título diz "VPI 13,23%" mas colunas dizem "VPI(12,23%)" e "GAJ(12%)". Rubrica nomeada VPI_12_23 conforme coluna; conferir percentual.', 'média')
alert('2016', 'H16:AG32', 'tabela repetida', 'Tabelas de VPI e VPNI da aba 2016 repetem as da aba 2015; não duplicadas.', 'baixa')


# =============================================================== PARÂMETROS
PARAMS, IR = [], []
MES = {'jan': 1, 'fev': 2, 'mar': 3, 'março': 3, 'abr': 4, 'abril': 4, 'mai': 5, 'maio': 5, 'jun': 6, 'junho': 6, 'jul': 7, 'julho': 7,
       'ago': 8, 'agosto': 8, 'set': 9, 'setembro': 9, 'out': 10, 'nov': 11, 'dez': 12}
import calendar
def fim_mes(y, m): return dt.date(y, m, calendar.monthrange(y, m)[1])

def periodo(txt, ano_aba):
    t = txt.lower()
    m = re.search(r'a partir de 1º/(\d{1,2})/(\d{4})', t)
    if m: return dt.date(int(m.group(2)), int(m.group(1)), 1), None
    m = re.search(r'([a-zç]+)\s+a\s+([a-zç]+)/(\d{2,4})', t)
    if m:
        y = int(m.group(3)); y = (y + 2000 if y < 50 else y + 1900) if y < 100 else y
        return dt.date(y, MES[m.group(1)], 1), fim_mes(y, MES[m.group(2)])
    m = re.search(r'\b([a-zç]+)/(\d{2,4})', t)
    if m and m.group(1) in MES:
        y = int(m.group(2)); y = (y + 2000 if y < 50 else y + 1900) if y < 100 else y
        return dt.date(y, MES[m.group(1)], 1), fim_mes(y, MES[m.group(1)])
    return dt.date(int(ano_aba), 1, 1), dt.date(int(ano_aba), 12, 31)

def P(param, ini, fim, valor, unidade, base, aba, cel, obs=None):
    PARAMS.append(dict(parametro=param, vigencia_inicio=ini, vigencia_fim=fim, valor=valor, unidade=unidade, base_legal=base, aba_origem=aba, celula_origem=cel, observacao=obs))

for ws in WBV:
    if ws.title in ('1994-nao utilizar', 'ANOTAÇÕES'): continue
    for row in ws.iter_rows():
        for c in row:
            v = c.value
            if not isinstance(v, str): continue
            low = v.lower()
            if not re.search(r'teto inss|sal[aá]rio m[ií]nimo', low) or c.coordinate == 'A128': continue
            nums = [x for x in row if x.column > c.column and x.value is not None]
            if not nums: continue
            val = nums[0].value
            if isinstance(val, str):
                mm = re.search(r'([\d.]+),(\d{2})', val)
                if not mm: continue
                val = float(mm.group(1).replace('.', '') + '.' + mm.group(2))
                alert(ws.title, nums[0].coordinate, 'valor com digitação inválida', f'Salário mínimo digitado como texto "{val}"; convertido.', 'baixa')
            ini, fim = periodo(v, ws.title)
            base = next((str(x.value).strip() for x in nums[1:] if isinstance(x.value, str) and re.search(r'lei|mp|decreto', x.value, re.I)), None)
            if 'teto' in low:
                P('TETO_RGPS', ini, fim, float(val), 'R$', None, ws.title, nums[0].coordinate)
                lim = [x for x in nums[1:] if isinstance(x.value, (int, float))]
                if lim:
                    P('CONTRIBUICAO_LIMITADA_AO_TETO', ini, fim, float(lim[0].value), 'R$', 'Previdência limitada ao teto (RPC/Funpresp-Jud)', ws.title, lim[0].coordinate,
                      'Valor de contribuição do servidor sujeito ao teto do RGPS (coluna "Previdência limitada ao teto").')
            else:
                P('SALARIO_MINIMO', ini, fim, float(val), 'R$', base, ws.title, nums[0].coordinate)

# Ajustes de vigência de parâmetros sem período (abas 2010+ "Teto INSS:" = ano todo) e 2023 SM
alert('2020', 'O10', 'lixo de digitação', 'Célula O10 contém apenas "u" (no lugar de "Previdência limitada ao teto").', 'baixa')
alert('2011', 'K15', 'faixa de IR incorreta', 'Tabela IR abr–dez/2011: 3ª faixa "até 4.664,68" — o correto (Lei 12.469/2011) é até 3.911,63, coerente com a 4ª faixa "acima de 3.911,63". Corrigido na tabela_ir.', 'média')

# VR / AQ (2026)
for r0, ini, fim, base in [(42, '2026-01-01', '2026-06-30', 'Lei 15.292/2025; Portaria Conjunta n.º 1/2026'), (106, '2026-07-01', None, 'Lei 15.293/2025; Portaria Conjunta n.º 1/2026')]:
    nomes = ['AQ_VALOR_REFERENCIA_VR', 'AQ_DOUTORADO', 'AQ_MESTRADO', 'AQ_POS_GRADUACAO_POR_CURSO', 'AQ_SEGUNDA_GRADUACAO', 'AQ_CERTIFICACAO_POR_CERT', 'AQ_CAPACITACAO_POR_120H']
    obs = [ 'VR = 6,5% do valor integral da CJ-1', '5 × VR', '3,5 × VR', '1 VR por curso, limitado a 2', '1 × VR', '0,5 VR por certificação, máx. 2', '0,2 VR a cada 120h, máx. 3']
    for i, (n, o) in enumerate(zip(nomes, obs)):
        cel = f'N{r0 + i}'
        P(n, D(ini), D(fim), float(WBV['2026'][cel].value), 'R$', base, '2026', cel, o)
alert('2026', 'J39:N48', 'AQ antes de 2026', 'A planilha só traz o Adicional de Qualificação no modelo de Valor de Referência (a partir de 01/01/2026). O AQ anterior (percentual sobre o vencimento básico, Lei 11.416/2006) não está tabelado.', 'alta')
P('TETO_CONSTITUCIONAL', dt.date(2004, 1, 1), dt.date(2004, 12, 31), 19115.19, 'R$', None, '2004', 'K6', 'Rótulo "TETO CONSTITUCIONAL" na aba 2004; vigência exata não informada.')
# VPI Lei 10.698/03
P('VPI_LEI_10698_2003', dt.date(2003, 5, 1), dt.date(2016, 7, 20), 59.87, 'R$', 'Lei 10.698/2003', '2003', 'A45:A46',
  'Rubrica 400. Absorvida pela Lei 13.317/2016 (nota aba 2016 H38). ANOTAÇÕES: paga mar/2003–dez/2014 e, para alguns servidores, abr/2016–dez/2018 (passivo pago em out/2024); jan/2015–mar/2016 não recebida (rubricas 1330/1331).')
alert('2003', 'A45', 'datas conflitantes (VPI)', 'Aba 2003 diz VPI a partir de mai/2003; ANOTAÇÕES diz mar/2003. Aba 2016 diz absorvida pela Lei 13.317/16 (jul/2016); ANOTAÇÕES cita pagamento até dez/2018 para alguns servidores. Vigência no parâmetro: 05/2003–07/2016; confirmar caso a caso.', 'média')
# GAJ (%) por período (Lei 13.317/16) e GAE/GAS escalonamento (Lei 11.416/06)
for r in range(41, 48):
    d0 = WBV['2016'][f'H{r}'].value; f = WBV['2016'][f'I{r}'].value
    if isinstance(d0, dt.datetime): P('GAJ_PERCENTUAL_SOBRE_VB', d0.date(), None, float(f), 'fator', 'Lei 13.317/2016', '2016', f'I{r}', 'Fator da GAJ sobre o vencimento básico a partir da data.')
for r in range(51, 56):
    d0 = WBV['2006'][f'K{r}'].value; f = WBV['2006'][f'J{r}'].value
    if isinstance(d0, dt.datetime): P('GAE_GAS_PERCENTUAL_IMPLANTACAO', d0.date(), None, float(f), 'fator', 'Lei 11.416/2006, art. 30 §2º', '2006', f'J{r}', 'Percentual escalonado de implantação da GAE/GAS.')
for ini, fim, pct, base in [('2002-06-01', '2004-06-30', 0.12, 'Lei 10.475/2002'), ('2004-07-01', '2005-10-31', 0.20, 'Lei 10.944/2004'),
                            ('2005-11-01', '2006-05-31', 0.30, 'Lei 10.944/2004'), ('2006-06-01', '2006-11-30', 0.33, 'Lei 10.944/2004'),
                            ('2006-12-01', '2007-06-30', 0.36, 'Lei 10.944/2004'), ('2007-07-01', '2007-11-30', 0.39, 'Lei 10.944/2004'),
                            ('2007-12-01', '2008-06-30', 0.42, 'Lei 11.416/2006'), ('2008-07-01', '2008-11-30', 0.46, 'Lei 11.416/2006'),
                            ('2008-12-01', '2012-12-31', 0.50, 'Lei 11.416/2006'), ('2013-01-01', '2013-12-31', 0.62, 'Lei 12.774/2012'),
                            ('2014-01-01', '2014-12-31', 0.752, 'Lei 12.774/2012'), ('2015-01-01', '2016-07-20', 0.90, 'Lei 12.774/2012')]:
    P('GAJ_PERCENTUAL_SOBRE_VB', D(ini), D(fim), pct, 'fator', base, '-', 'títulos dos blocos', 'Extraído dos títulos dos blocos de cargos ("GAJ xx% a partir de ...").')
alert('2002', 'A88', 'GAJ 2002–2004', 'Percentual da GAJ jun/2002–jun/2004 (12%) inferido do rótulo "GAJ 12%" da aba 2004; aba 2002/2003 não indica o percentual.', 'média')

# Tabelas de IR
def ir_table(sh, lab_col, r1, r2, ini, fim, base):
    ws = WBV[sh]; k = ci(lab_col); faixa = 0
    for r in range(r1, r2 + 1):
        lab = ws.cell(r, k).value
        nums = [ws.cell(r, j).value for j in range(k + 1, k + 9) if isinstance(ws.cell(r, j).value, (int, float))]
        if not isinstance(lab, str) or not nums: continue
        l = lab.strip().lower()
        if l == 'de':
            faixa += 1; de, ate, aliq, ded = nums[:4]
            if sh == '2011' and r == 15: ate = 3911.62
            IR.append(dict(vigencia_inicio=D(ini), vigencia_fim=D(fim), faixa=faixa, base_de=de, base_ate=ate, aliquota=aliq, parcela_deduzir=ded, base_legal=base, aba_origem=sh, linha_origem=r))
        elif l.startswith('acima'):
            faixa += 1
            IR.append(dict(vigencia_inicio=D(ini), vigencia_fim=D(fim), faixa=faixa, base_de=nums[0], base_ate=None, aliquota=nums[-2], parcela_deduzir=nums[-1], base_legal=base, aba_origem=sh, linha_origem=r))
        elif 'dependente' in l:
            P('IR_DEDUCAO_DEPENDENTE', D(ini), D(fim), float(nums[0]), 'R$', base, sh, f'{lab_col}{r}')
        elif '65 anos' in l:
            P('IR_ISENCAO_INATIVO_65', D(ini), D(fim), float(nums[0]), 'R$', base, sh, f'{lab_col}{r}')
        elif 'simplificado' in l:
            P('IR_DESCONTO_SIMPLIFICADO', D(ini), D(fim), round(float(nums[0]), 2), 'R$', base, sh, f'{lab_col}{r}')
for args in [('2007', 'J', 12, 14, '2007-01-01', '2007-12-31', 'Lei 11.482/2007'), ('2008', 'J', 11, 13, '2008-01-01', '2008-12-31', 'Lei 11.482/2007'),
             ('2009', 'H', 16, 20, '2009-01-01', '2009-12-31', 'Lei 11.945/2009'), ('2010', 'H', 7, 11, '2010-01-01', '2010-12-31', 'Lei 11.945/2009'),
             ('2011', 'H', 4, 8, '2011-01-01', '2011-03-31', 'Lei 11.945/2009'), ('2011', 'H', 13, 17, '2011-04-01', '2011-12-31', 'Lei 12.469/2011'),
             ('2012', 'H', 7, 11, '2012-01-01', '2012-12-31', 'Lei 12.469/2011'), ('2013', 'H', 8, 12, '2013-01-01', '2013-12-31', 'Lei 12.469/2011'),
             ('2014', 'H', 7, 12, '2014-01-01', '2015-03-31', 'Lei 12.469/2011'), ('2015', 'Z', 5, 10, '2015-04-01', '2023-04-30', 'Lei 13.149/2015'),
             ('2023', 'K', 13, 19, '2023-05-01', '2024-01-31', 'Lei 14.663/2023'), ('2024', 'K', 13, 19, '2024-02-01', '2025-04-30', 'Lei 14.848/2024'),
             ('2026', 'J', 3, 9, '2025-05-01', None, 'Lei 15.191/2025')]:
    ir_table(*args)
alert('2026', 'K1:P9', 'IR 2026', 'A tabela de IR mais recente na planilha é a de 1º/5/2025 (Lei 15.191/2025); não contempla a redução do imposto para rendimentos até R$ 5.000 a partir de 2026 (Lei 15.270/2025). IR não compõe a RBC, mas a IA não deve usar esta tabela para 2026 sem atualização.', 'média')

# Regras/anotações de incidência (aba ANOTAÇÕES)
REGRAS = []
wa = WBV['ANOTAÇÕES']
for r in range(4, 29):
    parts = [str(wa.cell(r, j).value).strip() for j in range(1, 19) if wa.cell(r, j).value not in (None, '')]
    if parts: REGRAS.append(dict(fonte=f'ANOTAÇÕES!A{r}:R{r}', texto=' '.join(parts)))
CORR = []
for r in range(4, 17):
    a, b, w = wa[f'T{r}'].value, wa[f'V{r}'].value, wa[f'W{r}'].value
    if a: CORR.append(dict(lista='T (coluna T da aba ANOTAÇÕES)', funcao=str(a).strip(), nivel_fc=None, celula=f'T{r}'))
    if b: CORR.append(dict(lista='V/W (colunas V e W da aba ANOTAÇÕES)', funcao=str(b).strip(), nivel_fc=w, celula=f'V{r}'))
alert('ANOTAÇÕES', 'T4:W16', 'lista sem explicação', 'Colunas T e V/W listam denominações de funções com nível FC, sem título. Não há correspondência linha a linha evidente entre T e V; exportadas como listas separadas.', 'baixa')

# =============================================================== PÓS-PROCESSAMENTO
for r in ROWS:
    f = r.get('funcao')
    if r.get('rubrica') in ('FC_CJ_VALOR', 'FC_CJ_INTEGRAL_COL') and f:
        if f.startswith('CJ'):
            r['modalidade'] = 'OPTANTE' if r['rubrica'] == 'FC_CJ_VALOR' else 'INTEGRAL'
            r['rubrica'] = 'FC_OPCAO_65PCT' if r['rubrica'] == 'FC_CJ_VALOR' else 'FC_INTEGRAL'
        else:
            if r['rubrica'] == 'FC_CJ_VALOR':
                r['modalidade'] = 'UNICO'; r['rubrica'] = 'FC_VALOR'
            else:
                r['modalidade'] = 'INTEGRAL'; r['rubrica'] = 'FC_INTEGRAL_DERIVADO'
                r['status'] = 'nao_usar'
                r['observacao'] = 'Valor calculado na planilha como FC ÷ 0,65; sem base legal. Usar FC_VALOR.'
    if r.get('ref') is not None and r.get('cargo') is None and r.get('grupo') == 'SERVIDOR_EFETIVO':
        pass
    r.setdefault('status', 'ok')

json.dump(dict(rows=ROWS, alerts=ALERTS, params=PARAMS, ir=IR, regras=REGRAS, correlacao=CORR), open(f'{OUT}/raw.json', 'w'), ensure_ascii=False, default=str)
print(len(ROWS), 'registros;', len(ALERTS), 'alertas')
