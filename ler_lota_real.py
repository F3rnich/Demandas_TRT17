# -*- coding: utf-8 -*-
"""
ler_lota_real.py -- le as planilhas "Lota Real <ano>.xlsx" (SGP) e devolve o
total de cargos em comissao (CJ) e funcoes comissionadas (FC) AUTORIZADOS por
nivel e por mes, ocupados ou nao.

Por que existe: a base de pessoal (Base atualizada.xlsx) so traz quem ocupa um
posto -- nao diz quantos postos existem no total. A Lota Real e diferente: cada
bloco de unidade lista TODO posto FC/CJ da unidade, ocupado ou vago. Vago =
linha com NOME em branco (ou "?"/"????", convencao da SGP para "posto vago,
aguardando ocupante" -- confirmado por Leo em 18/09/2026) e CARGO/FUNCAO
preenchidos. Isso da o total autorizado por nivel, mes a mes, sem estimar nada
-- o mesmo espirito do ler_vagos.py para o art. 6, so que por nivel de CJ/FC em
vez de cargo efetivo.

Cobertura: jan/2022 a set/2026 (53 dos 57 meses do art. 6; os 4 primeiros meses
de 2022 nao tem quadro de vagos em ler_vagos.py, mas aqui tem cobertura cheia).
Nao ha arquivo anterior a 2022 mapeado (existem Lota Real 2015-2021, mas nao
foram auditados -- ver secao MESES abaixo para estender).

ESTRUTURA DA PLANILHA (um arquivo por ano, uma aba por mes):
  - Cada unidade comeca com uma linha so com o NOME da unidade (CARGO e FUNCAO
    em branco).
  - Cada posto e uma linha: NOME (ocupante, ou vazio/"?"/"????" se vago),
    CARGO (cargo efetivo de origem, quando ha ocupante) e FUNCAO (a comissao,
    normalmente "<titulo> - <NIVEL>", ex. "ASSISTENTE DE JUIZ - FC-05").
  - Fecha com uma linha "TOTAL ..." (varios formatos: "TOTAL AUTORIZADO :",
    "TOTAL : N", "Total : N servidores (RA .../...)") -- serve so de nota para
    quem le a planilha; nao e usada aqui como fonte de verdade (aparece em
    poucas unidades, ver AUDITORIA_2026-09-18.md).

MESES COM MAIS DE UMA ABA (transicao no meio do mes, ex. portaria publicada):
  usa-se a ULTIMA revisao (a aba mais a direita no arquivo), que representa o
  estado de fim de mes. Ex.: 2025-01 usa "JAN apos Transicao PRESI 24.1", nao
  a "JAN" simples nem "JAN apos remocoes 07.01".

NIVEL SEM SUFIXO EXPLICITO: nem toda linha grava o nivel dentro do texto da
FUNCAO (ex. "CHEFE DE DIVISAO" sem "- CJ-01"). Nesses casos usa-se MAPA_FALLBACK,
construido cruzando o mesmo texto de funcao em meses onde ele aparece CM nivel
explicito -- curado a mao, exclui todo caso em que o mesmo texto mapeou para
mais de um nivel em momentos diferentes (ambiguo; nenhum desses apareceu de
fato sem nivel explicito nos 57 meses auditados, entao a exclusao nao custa
cobertura, so seguranca).

GUARDA: toda linha com CARGO ou FUNCAO preenchidos que nao bate nivel direto,
nem MAPA_FALLBACK, nem um padrao conhecido de cargo SEM comissao (servidor de
carreira comum, magistrado, nota de transferencia) aborta o modulo. Isso evita
que uma funcao comissionada nova (nivel novo, ou grafia nunca vista) seja
silenciosamente ignorada e o total saia contado a menos.

TITULOS DE CHEFIA SEM NIVEL EXPLICITO EM JAN-AGO/2022: nesses 8 meses (antes
de a planilha passar a anexar o nivel no texto da FUNCAO) uma dezena de cargos
de chefia (Secretario-Geral da Presidencia, Secretario de Administracao,
Secretario de Gestao de Pessoas, Secretario de TIC, Secretario da Corregedoria,
Coordenador da Coordenadoria de Recurso de Revista, Assessor de Desembargador/a
por nome) aparecem sem sufixo e sem paralelo em nenhum outro mes da serie (ou
seja, nao dava pra inferir do proprio arquivo). Classificacao confirmada por
Leo em 18/09/2026 e incorporada ao MAPA_FALLBACK: Secretario-Geral da
Presidencia = CJ-04; demais "Secretario de/da ..." = CJ-03; Coordenador da
Coordenadoria de Recurso de Revista = CJ-02; Assessor de Desembargador/a
(qualquer nome) = CJ-02.

DIRETOR / VICE-DIRETOR: aparecem em TODOS os 57 meses (um de cada, por unidade)
sem nivel e sem bater em nenhum padrao. Confirmado por Leo em 18/09/2026: NAO e
comissionamento de servidor -- e a identificacao de qual magistrado(a) dirige
o forum/unidade, fora do escopo deste painel. Tratado em SEM_COMISSAO_RE.

VALIDACAO (18/09/2026): comparado ocupado-por-nivel de set/2026 contra a
Apuracao_Forca_Trabalho_TRT17_14-09-2026.docx (base independente da DIGER,
740 servidores). CJ bate exato nos 4 niveis (93=93); FC fecha com diferenca de
2 postos no total (456 vs 454, 0,4%) -- ruido esperado entre duas planilhas
mantidas por pessoas diferentes, nao investigado alem disso por decisao de
Leo. Modulo roda limpo (LIMITE_ALARMES=0) nos 57 meses, jan/2022 a set/2026,
sem meses sem cobertura.
"""
import re, sys
from pathlib import Path
from collections import defaultdict

PASTA = Path("Lota Real")

NIVEL_RE = re.compile(r'\b(CJ|FC)[\s\-]?0?(\d)\b', re.IGNORECASE)
TOTAL_RE = re.compile(r'^TOTAL\b', re.IGNORECASE)          # linha de fechamento de unidade
NOTA_RE = re.compile(r'^\*')                                # nota solta tipo "*fulano esta ocupando..."
PLACEHOLDER_RE = re.compile(r'^\?+$')                        # "?"/"????" = vago aguardando ocupante

# Niveis do build_paineis_forca.py (art. 6, por_nivel): CJ-4..CJ-1, FC-6..FC-2.
# FC-01 existiu ate 2023 e desapareceu da estrutura -- ver AUDITORIA; mantido
# aqui pois a serie cobre 2022 pra frente e FC-01 tem meses com posto vago.
TODOS_NIVEIS = ["CJ-01", "CJ-02", "CJ-03", "CJ-04",
                "FC-01", "FC-02", "FC-03", "FC-04", "FC-05", "FC-06"]

# funcao-base (sem sufixo de nivel) -> nivel, para linhas sem o codigo explicito.
# Curado em 18/09/2026 a partir dos 57 meses jan/2022-set/2026: cada entrada
# apareceu com o MESMO nivel em todo mes onde teve sufixo explicito. Bases
# ambiguas (ASSISTENTE, ASSISTENTE ESPECIALIZADO, ASSISTENTE TECNICO,
# ASSISTENTE-TECNICO, COORDENADOR -- mapeiam pra nivel diferente dependendo do
# mes/unidade) foram excluidas de proposito: nenhuma delas apareceu sem nivel
# explicito nos 57 meses auditados, entao excluir nao custa cobertura.
MAPA_FALLBACK = {
    "SECRETARIO": "CJ-03",
    "ASSISTENTE DE SECRETARIA": "FC-04",
    "CHEFE DE DIVISAO": "CJ-01",
    "CHEFE DE SETOR": "FC-04",
    "SECRETARIO DE AUDIENCIA": "FC-04",
    "SECRETARIO DE SESSAO": "FC-04",
    "ASSISTENTE DE MAGISTRADO": "FC-04",
    "SEC.GER.PRES": "CJ-04",
    "CALCULISTA": "FC-04",
    "ASSESSOR DA PRESIDENCIA": "CJ-03",
    "ASSESSOR": "CJ-02",
    "ASSESSOR.": "CJ-03",
    "CHEFE DE SERVICO": "FC-04",
    "DIR. GERAL": "CJ-04",
    "ASSSISTENTE": "FC-02",             # erro de digitacao recorrente ("ASSSISTENTE")
    "DIR. SECR.": "CJ-03",
    "AUXILIAR ESPECIALIZADO": "FC-01",
    "AUXILIAR": "FC-02",
    "AUXLIAR": "FC-02",                 # erro de digitacao recorrente ("AUXLIAR")
    "ASSISTENTE DE GABINETE": "FC-05",
    "CHEFE DE NUCLEO": "FC-06",
    "CHEFE DE SECAO": "FC-05",
    "CHEFE DESECAO": "FC-05",           # erro de digitacao recorrente ("DESECAO")
    "ASSESSOR JURIDICO DA PRESIDENCIA": "CJ-03",
    "ASSESSOR-CHEFE": "CJ-03",
    "CONCILIADOR": "FC-04",
    "SECRETARIO DA CORREGEDORIA REGIONAL": "CJ-03",
    "ASSISTENTE DE JUIZ": "FC-05",
    "SECRETARIO-GERAL JUDICIARIO": "CJ-04",
    "DIRETOR-GERAL": "CJ-04",
    "PREGOEIRO": "FC-05",
    "DIRETOR DE SECRETARIA": "CJ-03",
    "ASSISTENTE DE GABINETE DE PRIMEIRO GRAU": "FC-04",
    "AGENTE DE CONTRATACAO": "FC-05",

    # confirmado por Leo em 18/09/2026 -- titulos de chefia de jan-ago/2022
    # (a partir de set/2022 a planilha passa a anexar o nivel explicito nesses
    # mesmos titulos, entao eles somem da guarda dali em diante)
    "ASSESSOR DE DESEMBARGADOR MARCELLO MACIEL MANCILHA": "CJ-02",
    "ASSESSOR DE DESEMBARGADORA ANA PAULA TAUCEDA BRANCO": "CJ-02",
    "ASSESSOR DESEMBARGADOR CLAUDIO ARMANDO COUCE DE MENEZES": "CJ-02",
    "ASSESSOR DESEMBARGADOR GERSON FERNANDO DA SYLVEIRA NOVAIS": "CJ-02",
    "ASSESSOR DESEMBARGADOR JOSE CARLOS RIZK": "CJ-02",
    "ASSESSOR DESEMBARGADOR MARIO CANTARINO": "CJ-02",
    "ASSESSOR DESEMBARGADOR VALERIO SOARES HERINGER": "CJ-02",
    "ASSESSOR DESEMBARGADORA ALZENIR BOLLESI DE PLA LOEFFLER": "CJ-02",
    "ASSESSOR DESEMBARGADORA CLAUDIA CARDOSO DE SOUZA": "CJ-02",
    "ASSESSOR DESEMBARGADORA DANIELE CORREA SANTA CATARINA": "CJ-02",
    "ASSESSOR DESEMBARGADORA MARISE MEDEIROS CAVALCANTI CHAMBERLAIN": "CJ-02",
    "ASSESSOR DESEMBARGADORA SONIA DAS DORES DIONISIO MENDES": "CJ-02",
    "ASSESSOR DESEMBARGADORA WANDA LUCIA COSTA LEITE FRANCA DECUZZI": "CJ-02",
    "ASSESSOR JUIZA CONVOCADA MARISE MEDEIROS CAVALCANTI CHAMBERLAIN": "CJ-02",
    "COORDENADOR DA COORDENADORIA DE RECURSO DE REVISTA": "CJ-02",
    "SECRETARIO DA CORREGEDORIA": "CJ-03",
    "SECRETARIO DA SECR. EXTR. DE FISC. A OBRA DA FUT. SEDE": "CJ-03",
    "SECRETARIO DE ADMINISTRACAO": "CJ-03",
    "SECRETARIO DE GESTAO DE PESSOAS": "CJ-03",
    "SECRETARIO DE TECNOLOGIA DA INFORMACAO E COMUNICACAO": "CJ-03",
    "SECRETARIO-GERAL DA PRESIDENCIA": "CJ-04",
}

# Padroes de CARGO/FUNCAO de quem NAO tem comissao (carreira comum, magistrado,
# nota de historico) -- usados so pela guarda, pra distinguir "sem comissao,
# esperado" de "sem nivel reconhecido, precisa olhar". Nao entra na contagem de
# nenhum jeito; so decide se a linha nao-reconhecida e um alarme ou nao.
SEM_COMISSAO_RE = re.compile(
    r'^\*?(ANL|ANAL|ANA)[\.\s]|^T[ÉE]CN?[\.\s\-]|^JUIZ|^DESEMB|^\*?REMOV|'
    r'^REQ\.?|^R[\.\-\s]|^-?\s*PR?E?F\.?\s*MUN|^IESP|^TRT\s*\d|^DAS$|^AUX\.|'
    r'^EXE[.,]?\s*MAND|^AGENTE\s*PC|^PM\s|^DIRETOR$|^VICE-DIRETOR$', re.IGNORECASE)

# nota administrativa solta (data de posse/afastamento, aposentadoria, licenca,
# ato de nomeacao) -- nao e comissao, so metadado de RH escrito na coluna errada.
NOTA_ADMIN_RE = re.compile(
    r'\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|POSSE|LICEN|APOSENTAD|REVERS[ÃA]O|'
    r'ATUANDO|CONTA\s+NA\s+LOTA|^ATO\s*\d|NOMEAD|^CARGO$|^[ÍI]S$|'
    r'^A\s+PARTIR\s+DE|^SEM\s+FUN[CÇ][ÃA]O|^CONVOCAD[AO]\s+PARA|'
    r'^INDICAD[AO]\s+PARA|^PROMO[CÇ][ÃA]O|^TST$|^SESA$|MINIST\.?\s*COMUNIC',
    re.IGNORECASE)


def _norm(s):
    import unicodedata
    s = re.sub(r'\s+', ' ', str(s).strip().upper())
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


def _strip_nivel(s):
    s2 = NIVEL_RE.sub('', s)
    return re.sub(r'[\-\s]+$', '', s2).strip()


# prefixos de funcao/cargo cujo nivel nao muda com o sufixo que segue (o
# sufixo so identifica A UNIDADE -- "DIRETOR DE SECRETARIA DA 3a VARA",
# "... DE COLATINA" etc -- nunca aparecem com CJ/FC explicito em nenhum dos
# 57 meses da serie, mas o cargo generico "DIRETOR DE SECRETARIA" (sem
# unidade) ja esta confirmado como CJ-03 em MAPA_FALLBACK; a funcao e a
# mesma, so varia a vara/comarca, entao aplicamos o mesmo nivel por prefixo)
PREFIXO_FALLBACK = {
    "DIRETOR DE SECRETARIA": "CJ-03",
}


def _nivel_de(funcao, cargo):
    for campo in (funcao, cargo):
        if campo:
            m = NIVEL_RE.search(str(campo))
            if m:
                return f"{m.group(1).upper()}-0{m.group(2)}"
    for campo in (funcao, cargo):
        if campo and str(campo).strip():
            base = _norm(_strip_nivel(str(campo)))
            if base in MAPA_FALLBACK:
                return MAPA_FALLBACK[base]
    for campo in (funcao, cargo):
        if campo and str(campo).strip():
            base = _norm(_strip_nivel(str(campo)))
            for prefixo, nivel in PREFIXO_FALLBACK.items():
                if base.startswith(prefixo):
                    return nivel
    return None


def _is_blank(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _parse_aba(ws):
    """Devolve (contagem por nivel {ocupado,vago}, lista de linhas alarmantes)."""
    contagem = defaultdict(lambda: {"ocupado": 0, "vago": 0})
    alarmes = []  # (cargo, funcao) sem nivel, sem fallback, sem padrao conhecido de "sem comissao"

    for row in ws.iter_rows(values_only=True):
        nome = row[0] if len(row) > 0 else None
        cargo = row[1] if len(row) > 1 else None
        funcao = row[2] if len(row) > 2 else None

        if _is_blank(nome) and _is_blank(cargo) and _is_blank(funcao):
            continue
        nome_s = str(nome).strip() if nome is not None else ""

        if nome_s.upper() == "NOME" and str(cargo).strip().upper() == "CARGO":
            continue  # cabecalho de coluna repetido
        if nome_s and _is_blank(cargo) and _is_blank(funcao):
            continue  # cabecalho de unidade OU linha de "TOTAL ..." OU nota "*..."

        nivel = _nivel_de(funcao, cargo)
        if nivel:
            ocupado = bool(nome_s) and not PLACEHOLDER_RE.match(nome_s)
            contagem[nivel]["ocupado" if ocupado else "vago"] += 1
            continue

        # sem nivel: so e alarme se NENHUM dos dois campos (cargo, funcao) for
        # explicavel por um padrao conhecido -- cargo sem comissao, ou nota
        # administrativa solta (data, licenca, aposentadoria, etc.)
        import datetime as _dt
        def _explicavel(campo):
            if campo is None or isinstance(campo, (_dt.date, _dt.datetime)):
                return True
            texto = str(campo).strip()
            if not texto:
                return True
            return bool(SEM_COMISSAO_RE.match(texto) or NOTA_ADMIN_RE.search(texto))
        if not (_explicavel(cargo) and _explicavel(funcao)):
            alarmes.append((cargo, funcao))

    return contagem, alarmes


# (arquivo, aba, "AAAA-MM"). Meses com mais de uma aba (transicao no meio do
# mes): usa-se a ULTIMA revisao. Ao adicionar um novo ano, so acrescentar aqui
# -- nao ha deteccao automatica de aba por decisao (nomes de aba sao livres e
# inconsistentes demais pra confiar em heuristica; ver cabecalho do modulo).
MESES = [
    ("Lota Real 2022.xlsx", "JAN", "2022-01"),
    ("Lota Real 2022.xlsx", "FEV", "2022-02"),
    ("Lota Real 2022.xlsx", "MAR", "2022-03"),
    ("Lota Real 2022.xlsx", "ABR", "2022-04"),
    ("Lota Real 2022.xlsx", "MAI", "2022-05"),
    ("Lota Real 2022.xlsx", "JUN", "2022-06"),
    ("Lota Real 2022.xlsx", "JULH", "2022-07"),
    ("Lota Real 2022.xlsx", "AGO", "2022-08"),
    ("Lota Real 2022.xlsx", "SET", "2022-09"),
    ("Lota Real 2022.xlsx", "OUT", "2022-10"),
    ("Lota Real 2022.xlsx", "NOV", "2022-11"),
    ("Lota Real 2022.xlsx", "DEZ22", "2022-12"),

    ("Lota Real 2023.xlsx", "JAN", "2023-01"),
    ("Lota Real 2023.xlsx", "FEV", "2023-02"),
    ("Lota Real 2023.xlsx", "MAR", "2023-03"),
    ("Lota Real 2023.xlsx", "ABR", "2023-04"),
    ("Lota Real 2023.xlsx", "MAI", "2023-05"),
    ("Lota Real 2023.xlsx", "JUN", "2023-06"),
    ("Lota Real 2023.xlsx", "JUL", "2023-07"),
    ("Lota Real 2023.xlsx", "AGO", "2023-08"),
    ("Lota Real 2023.xlsx", "SET", "2023-09"),
    ("Lota Real 2023.xlsx", "OUT", "2023-10"),
    ("Lota Real 2023.xlsx", "NOV", "2023-11"),

    ("Lota Real 2024.xlsx", "DEZ", "2023-12"),
    ("Lota Real 2024.xlsx", "JAN", "2024-01"),
    ("Lota Real 2024.xlsx", "FEV-após 08-02", "2024-02"),
    ("Lota Real 2024.xlsx", "MAR", "2024-03"),
    ("Lota Real 2024.xlsx", "ABR", "2024-04"),
    ("Lota Real 2024.xlsx", "MAI", "2024-05"),
    ("Lota Real 2024.xlsx", "JUN", "2024-06"),
    ("Lota Real 2024.xlsx", "JUL", "2024-07"),
    ("Lota Real 2024.xlsx", "AGO", "2024-08"),
    ("Lota Real 2024.xlsx", "SET", "2024-09"),
    ("Lota Real 2024.xlsx", "OUT", "2024-10"),
    ("Lota Real 2024.xlsx", "NOV", "2024-11"),
    ("Lota Real 2024.xlsx", "DEZ.2024", "2024-12"),

    ("Lota Real-LR- 2025.xlsx", "JAN após Transição PRESI 24.1", "2025-01"),
    ("Lota Real-LR- 2025.xlsx", "FEV", "2025-02"),
    ("Lota Real-LR- 2025.xlsx", "MAR", "2025-03"),
    ("Lota Real-LR- 2025.xlsx", "ABR", "2025-04"),
    ("Lota Real-LR- 2025.xlsx", "MAI", "2025-05"),
    ("Lota Real-LR- 2025.xlsx", "JUN", "2025-06"),
    ("Lota Real-LR- 2025.xlsx", "JUL", "2025-07"),
    ("Lota Real-LR- 2025.xlsx", "AGO", "2025-08"),
    ("Lota Real-LR- 2025.xlsx", "SET", "2025-09"),
    ("Lota Real-LR- 2025.xlsx", "OUT", "2025-10"),
    ("Lota Real-LR- 2025.xlsx", "NOV", "2025-11"),
    ("Lota Real-LR- 2025.xlsx", "DEZ", "2025-12"),

    ("Lota Real-LR- 2026.xlsx", "JAN", "2026-01"),
    ("Lota Real-LR- 2026.xlsx", "FEV", "2026-02"),
    ("Lota Real-LR- 2026.xlsx", "MAR", "2026-03"),
    ("Lota Real-LR- 2026.xlsx", "ABR", "2026-04"),
    ("Lota Real-LR- 2026.xlsx", "MAI", "2026-05"),
    ("Lota Real-LR- 2026.xlsx", "JUN", "2026-06"),
    ("Lota Real-LR- 2026.xlsx", "JUL", "2026-07"),
    ("Lota Real-LR- 2026.xlsx", "AGO", "2026-08"),
    ("Lota Real-LR- 2026.xlsx", "SET ", "2026-09"),   # aba tem espaco no nome, e literal
]

# limite de linhas-alarme toleradas por mes antes de abortar. 0 nos 57 meses
# auditados; qualquer coisa acima disso e sinal de nivel novo ou grafia nunca
# vista que precisa entrar no MAPA_FALLBACK ou no SEM_COMISSAO_RE.
LIMITE_ALARMES = 0


def ler(pasta=PASTA, verboso=False):
    import openpyxl
    pasta = Path(pasta)
    if not pasta.is_dir():
        sys.exit("ERRO: pasta %s nao existe." % pasta)

    reg = {}
    cache = {}
    for arquivo, aba, ref in MESES:
        caminho = pasta / arquivo
        if not caminho.exists():
            sys.exit("ERRO: %s nao existe em %s (mes %s)." % (arquivo, pasta, ref))
        if arquivo not in cache:
            cache[arquivo] = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        wb = cache[arquivo]
        if aba not in wb.sheetnames:
            sys.exit("ERRO: aba %r nao existe em %s (mes %s). Abas disponiveis: %s"
                      % (aba, arquivo, ref, wb.sheetnames))
        ws = wb[aba]
        contagem, alarmes = _parse_aba(ws)

        if len(alarmes) > LIMITE_ALARMES:
            from collections import Counter
            amostra = Counter(alarmes).most_common(10)
            sys.exit(
                "ERRO: %s (%s / %s) tem %d linha(s) com CARGO/FUNCAO preenchidos, sem\n"
                "nivel CJ/FC reconhecido, sem entrada no MAPA_FALLBACK e sem bater nenhum\n"
                "padrao conhecido de cargo sem comissao (SEM_COMISSAO_RE).\n"
                "Amostra (cargo, funcao) x ocorrencias:\n%s\n"
                "Se for comissao de verdade (nivel novo ou grafia nova), adicionar ao\n"
                "MAPA_FALLBACK. Se for cargo comum, estender SEM_COMISSAO_RE."
                % (ref, arquivo, aba, len(alarmes),
                   "\n".join("  x%d: %r" % (n, r) for r, n in amostra)))

        niveis = {}
        for niv in TODOS_NIVEIS:
            if niv in contagem:
                o, v = contagem[niv]["ocupado"], contagem[niv]["vago"]
                niveis[niv] = {"ocupado": o, "vago": v, "total": o + v}
        total_ocupado = sum(v["ocupado"] for v in niveis.values())
        total_vago = sum(v["vago"] for v in niveis.values())
        reg[ref] = {
            "arquivo": arquivo, "aba": aba, "niveis": niveis,
            "total_ocupado": total_ocupado, "total_vago": total_vago,
            "total_geral": total_ocupado + total_vago,
        }
        if verboso:
            print("  %s (%s/%s): ocupado=%d vago=%d total=%d"
                  % (ref, arquivo, aba.strip(), total_ocupado, total_vago,
                     total_ocupado + total_vago))

    for wb in cache.values():
        wb.close()
    return reg


if __name__ == "__main__":
    reg = ler(verboso=True)
    print("\n%d mes(es) processado(s): %s a %s" % (len(reg), min(reg), max(reg)))
    falt = sorted({"%d-%02d" % (a, m) for a in range(2022, 2027) for m in range(1, 13)
                   if min(reg) <= "%d-%02d" % (a, m) <= max(reg)} - set(reg))
    print("meses sem cobertura: %s" % (", ".join(falt) or "nenhum"))
