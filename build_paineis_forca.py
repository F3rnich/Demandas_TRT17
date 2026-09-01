#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_paineis_forca.py — Gera dados_paineis_forca.json para os painéis 07–13
do hub Demandas_TRT17 a partir da base de pessoal da SGP (xlsx local).

USO:
    python build_paineis_forca.py "Base atualizada.ods"
    python build_paineis_forca.py "BASE JULHO"     (extensao opcional)
    python build_paineis_forca.py                  (localiza sozinho na pasta)

FORMATOS: .ods, .xlsx, .xlsm, .xls. Para .ods, instale odfpy
(pip install odfpy); sem ele o script converte via LibreOffice headless
em pasta temporaria, sem alterar o arquivo original.

REGRAS LGPD (aplicadas na origem — nenhum dado individual sai deste script):
  1. Nenhum identificador (NOME, CPF, MATRICULA, NASCIMENTO) é gravado no JSON.
  2. Supressão de células pequenas: qualquer categoria de ATRIBUTO PESSOAL
     publicada com 0 < n < 5 é agregada ou omitida (k-anonimato, k=5).
     Contagem de LOTAÇÃO DE UNIDADE administrativa não é cruzamento de atributo
     pessoal e não entra nesta regra: é dado de estrutura, consta de ato
     administrativo público, e o art. 14 da Res. CSJT 296/2021 exige justamente
     a lotação da Escola Judicial como indicador de conformidade. Ver
     AREAS_INSTITUCIONAIS. Decisão de política de dados, não de código.
  3. Raça/cor só é publicada agrupada: Branca / Negra (pretos+pardos) / Outras ou NI.
  4. Deficiência, doença grave e identidade de gênero NÃO são exportadas
     (categorias com n<5 na base atual — reidentificáveis).
  5. Nenhum cruzamento de atributo sensível com unidade administrativa.

A BASE NUNCA ENTRA NO REPOSITÓRIO. Apenas este script e o JSON agregado.
"""
# -------------------------------------------------------------------------
# MAPA_PAINEIS — chave do JSON  x  numero do painel no hub
#
# As chaves sao IDENTIFICADORES OPACOS E ESTAVEIS. Elas NAO acompanham o
# numero de exibicao do painel: esse numero ja andou uma vez (remocao do
# painel Copa) e vai andar de novo se algum painel entrar ou sair da lista.
#
# NAO renomeie as chaves para 'acertar' a numeracao: isso quebraria os HTMLs
# consumidores, o checks.json e a comparacao retroativa do atualizar.py — e o
# desalinhamento voltaria na proxima mudanca.
#
# Chaves novas NAO seguem mais o padrao pNN justamente por isso: use um nome
# semantico (ver "risco_sucessorio"), que nenhuma renumeracao invalida.
#
#   chave            | painel | titulo                         | arquivo
#   -----------------+--------+--------------------------------+--------------------------------------------
#   p07              |   6    | Evolução da força de trabalho  | dashboard_evolucao_forca_trabalho.html
#   p08              |   7    | Envelhecimento demográfico     | dashboard_envelhecimento_demografico.html
#   p09              |   8    | Equidade nos comissionamentos  | dashboard_equidade_comissionamentos.html
#   p10              |   9    | Tempo até a primeira comissão  | dashboard_tempo_primeira_comissao.html
#   p11              |   10   | Custo dos comissionamentos     | dashboard_custo_comissionamentos.html
#   p12              |   11   | Qualificação por cargo         | dashboard_qualificacao_cargo.html
#   p13              |   12   | Apoio indireto — Res. CSJT 296 | dashboard_apoio_indireto_csjt296.html
#   risco_sucessorio |   17   | Risco sucessório               | dashboard_risco_sucessorio.html
#
# O Painel 17 e MISTO: so a tabela etaria vem daqui. As demais secoes sao
# apuracao manual (matriz de criticidade e registro de designacao previa),
# que nao existem na base de pessoal — vao carimbadas como tal no HTML.
# -------------------------------------------------------------------------
MAPA_PAINEIS = {
    "p07": ( 6, "Evolução da força de trabalho", "dashboard_evolucao_forca_trabalho.html"),
    "p08": ( 7, "Envelhecimento demográfico", "dashboard_envelhecimento_demografico.html"),
    "p09": ( 8, "Equidade nos comissionamentos", "dashboard_equidade_comissionamentos.html"),
    "p10": ( 9, "Tempo até a primeira comissão", "dashboard_tempo_primeira_comissao.html"),
    "p11": (10, "Custo dos comissionamentos", "dashboard_custo_comissionamentos.html"),
    "p12": (11, "Qualificação por cargo", "dashboard_qualificacao_cargo.html"),
    "p13": (12, "Apoio indireto — Res. CSJT 296", "dashboard_apoio_indireto_csjt296.html"),
    "risco_sucessorio": (17, "Risco sucessório", "dashboard_risco_sucessorio.html"),
}

import sys, json, os, shutil, subprocess, tempfile
from pathlib import Path
import pandas as pd
import numpy as np

K_MIN = 5  # k-anonimato

# Colunas de contagem por unidade que ficam FORA da regra k=5 pela regra 2 do
# cabecalho: sao lotacao de unidade administrativa, nao atributo pessoal.
AREAS_INSTITUCIONAIS = {"EJUD"}

# Unidades da Escola Judicial — FONTE UNICA. Nao duplicar esta regex em
# outros scripts: importe daqui (from build_paineis_forca import EJUD_RE).
EJUD_RE = r"Escola Judicial|Capacita[çc][ãa]o de Magistrado|Capacita[çc][ãa]o de Servidor"

# ---------------------------------------------------------------------------
# Leitura de planilha independente de formato (.ods, .xlsx, .xlsm, .xls)
# ---------------------------------------------------------------------------

_EXT_OK = {".ods", ".xlsx", ".xlsm", ".xltx", ".xls"}
_ENGINE = {".ods": "odf", ".xlsx": "openpyxl", ".xlsm": "openpyxl",
           ".xltx": "openpyxl", ".xls": "xlrd"}
_SOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice", "/usr/bin/libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]
_CONVERTIDO = {}  # cache: original -> xlsx temporario


def resolver_base(nome=None, pasta="."):
    """
    Localiza a planilha ignorando extensao. Aceita caminho completo, nome sem
    extensao, ou nada (procura qualquer planilha na pasta, preferindo nomes
    que comecem com 'base').
    """
    pasta = Path(pasta)
    if nome:
        p = Path(nome)
        if p.exists() and p.suffix:
            return p.resolve()
        pasta = p.parent if str(p.parent) != "." else pasta
        alvo = p.stem.strip().lower()
    else:
        alvo = None

    cands = [f for f in pasta.iterdir()
             if f.is_file() and f.suffix.lower() in _EXT_OK
             and not f.name.startswith("~$")]

    if alvo:
        exatos = [f for f in cands if f.stem.strip().lower() == alvo]
        cands = exatos or [f for f in cands
                           if f.stem.strip().lower().startswith(alvo)]
    else:
        base = [f for f in cands if f.stem.strip().lower().startswith("base")]
        cands = base or cands

    if not cands:
        disp = sorted(f.name for f in pasta.iterdir()
                      if f.is_file() and f.suffix.lower() in _EXT_OK)
        sys.exit(f"ERRO: nenhuma planilha {'para ' + repr(nome) if nome else ''} "
                 f"encontrada em {pasta.resolve()}.\n"
                 f"Planilhas na pasta: {disp or '(nenhuma)'}")

    cands.sort(key=lambda f: (0 if f.suffix.lower() != ".xls" else 1,
                              -f.stat().st_mtime))
    if len(cands) > 1:
        print(f"[aviso] {len(cands)} planilhas casam; usando {cands[0].name}")
        for f in cands[1:]:
            print(f"        (ignorada: {f.name})")
    return cands[0].resolve()


def _achar_soffice():
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if exe:
        return exe
    return next((c for c in _SOFFICE if os.path.exists(c)), None)


def _converter(path):
    """Converte para xlsx em pasta temporaria. Nao altera o original."""
    path = Path(path)
    if path in _CONVERTIDO:
        return _CONVERTIDO[path]
    exe = _achar_soffice()
    if not exe:
        sys.exit(f"ERRO: nao consigo ler '{path.name}'. Falta o engine para "
                 f"'{path.suffix}' e o LibreOffice nao foi encontrado.\n"
                 f"Resolva com:  pip install odfpy   (para .ods)\n"
                 f"          ou:  pip install xlrd    (para .xls antigo)")
    dest = Path(tempfile.mkdtemp(prefix="conv_base_"))
    print(f"[info] convertendo {path.name} -> xlsx (temporario)...")
    proc = subprocess.run([exe, "--headless", "--convert-to", "xlsx",
                           "--outdir", str(dest), str(path)],
                          capture_output=True, text=True)
    saida = dest / (path.stem + ".xlsx")
    if not saida.exists():
        sys.exit("ERRO: conversao pelo LibreOffice falhou. Feche o arquivo se "
                 f"estiver aberto e tente de novo.\n{proc.stderr}")
    _CONVERTIDO[path] = saida
    return saida


def abas(path):
    """Nomes das abas da planilha."""
    path = Path(path)
    eng = _ENGINE.get(path.suffix.lower())
    try:
        with pd.ExcelFile(path, engine=eng) as xl:
            return list(xl.sheet_names)
    except ImportError:
        with pd.ExcelFile(_converter(path), engine="openpyxl") as xl:
            return list(xl.sheet_names)


def ler_aba(path, sheet, obrigatoria=True):
    """
    Le uma aba de qualquer formato suportado. Casa o nome da aba ignorando
    caixa e espacos. Se obrigatoria=False, devolve None quando ausente.
    """
    path = Path(path)
    if path.suffix.lower() not in _EXT_OK:
        sys.exit(f"ERRO: extensao nao suportada: '{path.suffix}'. "
                 f"Suportadas: {sorted(_EXT_OK)}")

    disponiveis = abas(path)
    real = next((a for a in disponiveis
                 if a.strip().lower() == str(sheet).strip().lower()), None)
    if real is None:
        if not obrigatoria:
            return None
        sys.exit(f"ERRO: aba '{sheet}' nao existe em {path.name}.\n"
                 f"Abas disponiveis: {disponiveis}\n"
                 f"Renomeie a aba na planilha ou ajuste o nome no script.")

    eng = _ENGINE.get(path.suffix.lower())
    try:
        return pd.read_excel(path, sheet_name=real, engine=eng)
    except ImportError:
        return pd.read_excel(_converter(path), sheet_name=real,
                             engine="openpyxl")


def guardar_k(tab, rotulo, isentas=frozenset()):
    """Aborta se alguma coluna publicada tiver celula 0<n<K_MIN em algum mes.

    NAO conserta em silencio: a agregacao correta depende do significado das
    colunas — juntar "Requisitado" com "Sem vinculo efetivo" e o agrupamento do
    art. 5 da Res. CSJT 296, enquanto uma dobra automatica pelo menor valor
    destruiria a serie de T.I. para salvar a da Escola Judicial. Quando esta
    guarda disparar, decida a agregacao e escreva-a aqui.
    """
    ruins = {}
    for c in tab.columns:
        if c in isentas:
            continue
        n = int(((tab[c] > 0) & (tab[c] < K_MIN)).sum())
        if n:
            ruins[c] = n
    if ruins:
        sys.exit("ERRO k=%d em %s: %s.\nCelulas com 0<n<%d nao podem ser "
                 "publicadas. Ver regra 2 no cabecalho deste arquivo."
                 % (K_MIN, rotulo,
                    ", ".join("'%s' em %d mes(es)" % (c, n) for c, n in ruins.items()),
                    K_MIN))


def sem_dup_comissao(d):
    """Uma linha por (ref, MATRICULA) entre os ocupantes de FC/CJ.

    A base traz 32 pares (12 pessoas, 20 referencias entre 2021-11 e 2024-02)
    com DOIS codigos de comissao no mesmo instantaneo de fim de mes, mesma
    unidade e mesma data de REFERENCIA — nao e troca de funcao no meio do mes.
    O padrao dominante e CJ-3 + FC-04 (26 dos 32 pares), razao de valor ~4x.
    Conta-se a pessoa UMA vez e mantem-se o posto de MAIOR valor (o CJ),
    tratando a linha de FC como residuo da opcao.

    Sem isto, groupby("ref").size() conta LANCAMENTOS e nao pessoas, e o custo
    mensal soma as duas linhas: ate 3 pessoas e R$ 6.168,84 a mais num mes
    (0,353%), R$ 63.981,10 no acumulado da serie.
    """
    return (d.sort_values("VALOR", ascending=False)
             .drop_duplicates(subset=["ref", "MATRICULA"], keep="first"))


def sup(n):
    """Suprime contagens 0<n<K_MIN (retorna None)."""
    n = int(n)
    return n if (n == 0 or n >= K_MIN) else None

def raca_grp(v):
    if pd.isna(v): return "Outras/NI"
    v = str(v).upper()
    if "BRANCO" in v: return "Branca"
    if "NEGRO" in v:  return "Negra"
    return "Outras/NI"

def main(path):
    path = resolver_base(path)
    print(f"[info] base: {path.name}  ({path.stat().st_size/1024:.0f} KB)")
    df = ler_aba(path, "dados")
    df["REFERENCIA"] = pd.to_datetime(df["REFERENCIA"], errors="coerce")
    n_ruim = int(df["REFERENCIA"].isna().sum())
    if n_ruim:
        print(f"[aviso] {n_ruim} linha(s) com REFERENCIA vazia/invalida — descartadas "
              f"({n_ruim/len(df)*100:.2f}% da base).")
        df = df[df["REFERENCIA"].notna()].copy()
    df["ref"] = df["REFERENCIA"].dt.strftime("%Y-%m")
    df["ano"] = df["REFERENCIA"].dt.year
    refs = sorted(df["ref"].unique())
    ult_ref = refs[-1]

    est = df["TIPO_SERVIDOR"].eq("Estagiário")
    ft = df[~est].copy()                 # força de trabalho (sem estagiários)
    ult = ft[ft["ref"] == ult_ref].copy()  # último snapshot
    ult["raca_g"] = ult["RAÇA"].map(raca_grp)
    ft["raca_g"] = ft["RAÇA"].map(raca_grp)

    # base "servidores com lotação ativa" = sem estagiários, sem removidos-para, sem magistrados
    MAG = df["CARGO"].str.contains("JUIZ|DESEMBARGADOR", case=False, na=False)
    REMPARA = df["SITUACAO_FUNCIONAL"].eq("Removido para")
    srv = df[(~est) & (~REMPARA) & (~MAG)].copy()
    srv["raca_g"] = srv["RAÇA"].map(raca_grp)
    srv["ano"] = srv["REFERENCIA"].dt.year
    anos_all = sorted(srv["ano"].unique())
    srv_ult = srv[srv["ref"] == ult_ref].copy()
    srv_dez = srv.sort_values("REFERENCIA").groupby(["ano", "MATRICULA"]).tail(1)

    # INVARIANTE: nenhum magistrado e nenhum servidor removido para outro orgao
    # ocupa FC/CJ. Verificado nas 140 referencias da base (2015-01 a 2026-08):
    # zero ocorrencias. E por isso que o p11 dava o numero certo mesmo usando o
    # universo errado. Se deixar de valer, "quem entra no custo" vira decisao de
    # politica (despesa institucional x acesso dos servidores) e nao pode ser
    # resolvida em silencio por um filtro: o pipeline para e alguem decide.
    _intru = df[(~est) & df["CODIGO_COMISSAO"].notna() & (MAG | REMPARA)]
    if len(_intru):
        _m = sorted(_intru["ref"].unique())
        sys.exit(f"ERRO: {len(_intru)} ocupante(s) de FC/CJ sao magistrados ou "
                 f"removidos-para, em {len(_m)} referencia(s) ({_m[0]}..{_m[-1]}).\n"
                 f"Isso nunca ocorreu nesta base. Decida antes de publicar se o "
                 f"custo do painel 10 mede despesa institucional (inclui) ou "
                 f"acesso dos servidores (exclui) — ver p09 e art. 6 do p13.")

    # GRAU por unidade administrativa (fonte confiável — mesma usada no art. 7º/P13).
    # A coluna "GRAU" crua da aba "dados" (XLOOKUP na planilha-fonte) NÃO é usada aqui:
    # fica sem match para praticamente todo o histórico (ver nota de bug em memória).
    try:
        bu = ler_aba(path, "Base unidades", obrigatoria=False)
        if bu is None:
            raise KeyError("aba 'Base unidades' ausente")
        gmap = dict(zip(bu["UNIDADE ADMINISTRATIVA"].astype(str).str.strip().str.upper(), bu["GRAU"]))
    except Exception:
        gmap = {}
    srv["grau_u"] = srv["UNIDADE_ADMINISTRATIVA"].astype(str).str.strip().str.upper().map(gmap)

    out = {"gerado_de": "base local SGP (não versionada)",
           "ultima_referencia": ult_ref, "k_anonimato": K_MIN}

    # ---------------- p07 → Painel 6 — Evolução histórica (servidores) ----------------
    serie_total = srv.groupby("ref").size()
    por_area = srv.pivot_table(index="ref", columns="AREA", values="MATRICULA",
                               aggfunc="count").fillna(0).astype(int)
    por_vinc = srv.pivot_table(index="ref", columns="TIPO_SERVIDOR",
                               values="MATRICULA", aggfunc="count").fillna(0).astype(int)
    # A regra anterior mantinha a coluna se o MAXIMO da serie fosse >= K_MIN,
    # o que publicava "Sem vinculo efetivo" com 2 a 4 pessoas em 87 dos 140
    # meses. O art. 5 da Res. CSJT 296 ja trata requisitados e comissionados
    # sem vinculo como um grupo unico ("fora das carreiras judiciarias
    # federais"); juntos o par nunca fica abaixo de 41.
    PAR_ART5 = ["Requisitado", "Sem vínculo efetivo"]
    _p5 = [c for c in PAR_ART5 if c in por_vinc.columns]
    if len(_p5) > 1:
        por_vinc["Requisitado ou sem vínculo efetivo"] = por_vinc[_p5].sum(axis=1)
        por_vinc = por_vinc.drop(columns=_p5)
    grau = srv[srv["grau_u"].isin(["1º", "2º"])]
    por_grau = grau.pivot_table(index="ref", columns="grau_u", values="MATRICULA",
                                aggfunc="count").fillna(0).astype(int)
    guardar_k(por_area, "p07.por_area", AREAS_INSTITUCIONAIS)
    guardar_k(por_vinc, "p07.por_vinculo")
    guardar_k(por_grau, "p07.por_grau")
    out["p07"] = {
        "refs": refs,
        "total": [int(serie_total.get(r, 0)) for r in refs],
        "por_area": {c: [int(por_area.loc[r, c]) if r in por_area.index else 0 for r in refs]
                     for c in por_area.columns},
        "por_vinculo": {c: [int(por_vinc.loc[r, c]) if r in por_vinc.index else 0 for r in refs]
                        for c in por_vinc.columns},
        "por_grau": {c: [int(por_grau.loc[r, c]) if r in por_grau.index else 0 for r in refs]
                     for c in por_grau.columns},
    }

    # ---------------- p08 → Painel 7 — Envelhecimento ----------------
    bins = [0, 30, 35, 40, 45, 50, 55, 60, 200]
    labs = ["< 30", "30–34", "35–39", "40–44", "45–49", "50–54", "55–59", "60 +"]
    srv_ult["fx"] = pd.cut(srv_ult["IDADE"], bins=bins, labels=labs, right=False)
    pir = {}
    for sx, nome in [("M", "Masculino"), ("F", "Feminino")]:
        s = srv_ult[srv_ult["SEXO"] == sx]["fx"].value_counts().reindex(labs).fillna(0)
        pir[nome] = [sup(v) if v else 0 for v in s]
    idade_media = srv_dez.groupby("ano")["IDADE"].mean().round(1)
    p55 = srv_dez.groupby("ano").apply(
        lambda g: round(100 * (g["IDADE"] >= 55).mean(), 1), include_groups=False)
    fx_area = srv_ult.pivot_table(index="AREA", columns=pd.cut(
        srv_ult["IDADE"], [0, 45, 55, 200], labels=["< 45", "45–54", "55 +"], right=False),
        values="MATRICULA", aggfunc="count", observed=True).fillna(0).astype(int)
    out["p08"] = {
        "faixas": labs, "piramide": pir,
        "anos": [int(a) for a in anos_all],
        "idade_media": [float(idade_media.get(a, np.nan)) for a in anos_all],
        "pct_55mais": [float(p55.get(a, np.nan)) for a in anos_all],
        "idade_por_area": {str(i): [sup(v) if v else 0 for v in fx_area.loc[i]]
                           for i in fx_area.index},
        "idade_area_faixas": list(fx_area.columns.astype(str)),
        "idade_media_atual": round(float(srv_ult["IDADE"].mean()), 1),
        "n_55mais_atual": int((srv_ult["IDADE"] >= 55).sum()),
        "n_60mais_atual": int((srv_ult["IDADE"] >= 60).sum()),
        "total_atual": int(len(srv_ult)),
    }

    # ---------------- p09 → Painel 8 — Equidade em comissionamentos (força de servidores) ----------------
    com = sem_dup_comissao(srv_ult[srv_ult["CODIGO_COMISSAO"].notna()])
    def paridade(col, grupos):
        r = {}
        for g in grupos:
            n_f = int((srv_ult[col] == g).sum()); n_c = int((com[col] == g).sum())
            if n_f < K_MIN: continue
            pf = 100 * n_f / len(srv_ult); pc = 100 * n_c / len(com)
            vm = com.loc[com[col] == g, "VALOR"]
            # n_com passava pelo sup(), mas pct_com e indice_paridade saiam
            # crus — e total_comissionados e n_forca sao publicados, entao
            # n_com = pct_com * total / 100 devolvia o valor exato. A supressao
            # era decorativa: os derivados tem de cair junto.
            oculto = n_c < K_MIN
            r[g] = {"n_forca": n_f, "pct_forca": round(pf, 1),
                    "n_com": None if oculto else n_c,
                    "pct_com": None if oculto else round(pc, 1),
                    "indice_paridade": None if (oculto or not pf) else round(pc / pf, 2),
                    "valor_medio_fc": round(float(vm.mean()), 2) if len(vm) >= K_MIN else None}
        return r
    out["p09"] = {
        "total_forca": int(len(srv_ult)), "total_comissionados": int(len(com)),
        "valor_medio_geral": round(float(com["VALOR"].mean()), 2),
        "sexo": paridade("SEXO", ["F", "M"]),
        "raca": paridade("raca_g", ["Branca", "Negra", "Outras/NI"]),
        "nota": "Índice de paridade = %% do grupo entre comissionados ÷ %% do grupo na força de servidores. 1,00 = proporcional.",
    }
    ip_serie = {"anos": [], "F": [], "Negra": []}
    for a in anos_all:
        g = srv_dez[srv_dez["ano"] == a]
        c = g[g["CODIGO_COMISSAO"].notna()]
        if len(c) < K_MIN: continue
        ip_serie["anos"].append(int(a))
        for chave, col, val in [("F", "SEXO", "F"), ("Negra", "raca_g", "Negra")]:
            n_sub = int((c[col] == val).sum())   # o grupo ENTRE comissionados
            pf = (g[col] == val).mean(); pc = (c[col] == val).mean()
            ip_serie[chave].append(round(pc / pf, 2)
                                   if (n_sub >= K_MIN and pf > 0) else None)
    out["p09"]["serie_paridade"] = ip_serie

    # ---------------- p10 → Painel 9 — Tempo até a primeira comissão ----------------
    # Universo = srv, como no p09 e no art. 6 do p13. Com `ft`, a coorte
    # carregava 16 magistrados e 1 removido-para que NUNCA recebem FC/CJ: 17
    # nao-eventos permanentes que so faziam o denominador crescer. O efeito era
    # grande e para baixo — em 3 anos a curva geral ia de 66,8% para 60,4%, e o
    # gap por sexo encolhia de 21,8 para 18,9 p.p. num painel sobre equidade.
    snap0 = srv["REFERENCIA"].min()
    first = srv.groupby("MATRICULA")["REFERENCIA"].min()
    last = srv.groupby("MATRICULA")["REFERENCIA"].max()
    coorte = first[first > snap0].index  # entrada observável
    fc1 = srv[srv["CODIGO_COMISSAO"].notna()].groupby("MATRICULA")["REFERENCIA"].min()
    atrib = srv.sort_values("REFERENCIA").groupby("MATRICULA").first()  # atributos na entrada
    rows = []
    for m in coorte:
        ent = first[m]
        evento = m in fc1.index
        chegou_com_fc = evento and fc1[m] == ent
        t_evt = (fc1[m] - ent).days / 365.25 if evento else None
        t_obs = (last[m] - ent).days / 365.25
        rows.append({"m": m, "chegou": chegou_com_fc, "evento": evento,
                     "t": t_evt, "t_obs": t_obs,
                     "sexo": atrib.loc[m, "SEXO"], "raca": raca_grp(atrib.loc[m, "RAÇA"])})
    co = pd.DataFrame(rows)
    sem_fc_inicial = co[~co["chegou"]]
    EIXO_ANOS = [x / 2 for x in range(0, 21)]  # 0 a 10 anos, passo 0,5

    def km_curve(sub, return_n=False):
        """% acumulado que recebeu FC/CJ até t anos — Kaplan-Meier (produto-limite).

        Cada indivíduo contribui com (tempo, evento): tempo = tempo até a 1a comissao
        se o evento ocorreu, ou tempo observado sem comissao (censura à direita) caso
        contrário. O risco é atualizado incrementalmente a cada tempo de evento
        (n_i = quem ainda estava em observação e sem evento até ali), em vez de
        excluir em bloco quem não atingiu t anos de observação — o método anterior
        ("incidência simples entre observados ≥ t") inflava a cauda da curva porque
        removia do denominador, à medida que t crescia, justamente quem saiu do
        quadro sem nunca ter recebido comissão (censura potencialmente informativa:
        mediana de tempo até 1a comissão, entre quem recebe, é < 1 ano — indício de
        que quem não é promovido rápido tende também a sair do tribunal).
        """
        tempos = [(float(r["t"]), 1) if r["evento"] else (float(r["t_obs"]), 0)
                  for _, r in sub.iterrows()]
        n_total = len(tempos)
        event_times = sorted({t for t, e in tempos if e == 1})
        km_steps = []  # (tempo_evento, sobrevivencia_apos, n_risco_no_evento)
        surv = 1.0
        for t_i in event_times:
            n_i = sum(1 for t, e in tempos if t >= t_i)
            d_i = sum(1 for t, e in tempos if t == t_i and e == 1)
            if n_i >= K_MIN:
                surv *= (1 - d_i / n_i)
            km_steps.append((t_i, surv, n_i))
        pts, n_pts = [], []
        for t in EIXO_ANOS:
            n_risco_t = sum(1 for tt, e in tempos if tt >= t)
            n_pts.append(n_risco_t)
            if n_risco_t < K_MIN:
                pts.append(None); continue
            s_t = 1.0
            for t_i, surv, n_i in km_steps:
                if t_i <= t and n_i >= K_MIN:
                    s_t = surv
                elif t_i > t:
                    break
            pts.append(round(100 * (1 - s_t), 1))
        return (pts, n_pts) if return_n else pts
    def mediana_grp(col, grupos):
        r = {}
        for g in grupos:
            s = sem_fc_inicial[(sem_fc_inicial[col] == g) & sem_fc_inicial["evento"]]["t"]
            r[g] = {"n": sup(len(s)),
                    "mediana_anos": round(float(s.median()), 1) if len(s) >= K_MIN else None}
        return r
    curva_geral, n_risco_geral = km_curve(sem_fc_inicial, return_n=True)
    n_risco_geral = [sup(n) for n in n_risco_geral]
    out["p10"] = {
        "n_coorte": int(len(co)),
        "n_chegou_com_fc": int(co["chegou"].sum()),
        "n_entrou_sem_fc": int(len(sem_fc_inicial)),
        "n_conquistou_depois": int(sem_fc_inicial["evento"].sum()),
        "mediana_geral_anos": round(float(
            sem_fc_inicial[sem_fc_inicial["evento"]]["t"].median()), 1),
        "eixo_anos": EIXO_ANOS,
        "curva_geral": curva_geral,
        "n_risco_geral": n_risco_geral,
        "curva_sexo": {g: km_curve(sem_fc_inicial[sem_fc_inicial["sexo"] == g]) for g in ["F", "M"]},
        "curva_raca": {g: km_curve(sem_fc_inicial[sem_fc_inicial["raca"] == g])
                       for g in ["Branca", "Negra"]},
        "mediana_sexo": mediana_grp("sexo", ["F", "M"]),
        "mediana_raca": mediana_grp("raca", ["Branca", "Negra"]),
        "coorte_desde": str(sorted(first[first > snap0])[0].date()) if len(coorte) else None,
    }

    # ---------------- p11 → Painel 10 — Custo dos comissionamentos ----------------
    # universo igual ao do p09 e do art. 6 do p13 (srv), e uma linha por pessoa
    comt = sem_dup_comissao(srv[srv["CODIGO_COMISSAO"].notna()])
    custo = comt.groupby("ref")["VALOR"].sum()
    qtd = comt.groupby("ref").size()
    tipos = sem_dup_comissao(srv_ult[srv_ult["CODIGO_COMISSAO"].notna()]).groupby("NOME_COMISSAO").agg(
        n=("MATRICULA", "count"), custo=("VALOR", "sum")).sort_values("custo", ascending=False)
    grandes = tipos[tipos["n"] >= K_MIN]
    outras_n = int(tipos[tipos["n"] < K_MIN]["n"].sum())
    outras_c = float(tipos[tipos["n"] < K_MIN]["custo"].sum())
    lista = [{"tipo": i, "n": int(r["n"]), "custo": round(float(r["custo"]), 2)}
             for i, r in grandes.iterrows()]
    if outras_n:
        lista.append({"tipo": "Demais funções (agregado)", "n": outras_n,
                      "custo": round(outras_c, 2)})
    out["p11"] = {
        "refs": refs,
        "custo_mensal": [round(float(custo.get(r, 0)), 2) for r in refs],
        "qtd_comissionados": [int(qtd.get(r, 0)) for r in refs],
        "por_tipo_atual": lista,
        "custo_atual": round(float(custo.get(ult_ref, 0)), 2),
        "valor_medio_atual": round(float(custo.get(ult_ref, 0) / max(qtd.get(ult_ref, 1), 1)), 2),
        "nota": "Valores nominais (sem correção inflacionária). Universo: servidores "
                "com lotação ativa (exclui estagiários, removidos para outros órgãos e "
                "magistrados). Um ocupante conta uma vez por mês: quando o registro traz "
                "dois códigos no mesmo instantâneo, prevalece o posto de maior valor.",
    }

    # ---------------- p12 → Painel 11 — Qualificação × cargo ----------------
    ordem_esc = ["ENSINO FUNDAMENTAL", "ENSINO MÉDIO", "SUPERIOR INCOMPLETO",
                 "GRADUAÇÃO", "SUPERIOR", "ESPECIALIZAÇÃO", "MESTRADO", "DOUTORADO"]
    def cargo_agg(c):
        c = str(c).upper()
        if "ANALISTA" in c: return "Analista Judiciário"
        if "TÉCNICO" in c or "TECNICO" in c: return "Técnico Judiciário"
        return "Demais"
    srv_ult["cargo_g"] = srv_ult["CARGO"].map(cargo_agg)
    esc = srv_ult.pivot_table(index="ESCOLARIDADE", columns="cargo_g", values="MATRICULA",
                          aggfunc="count").fillna(0).astype(int)
    esc = esc.reindex([e for e in ordem_esc if e in esc.index])
    pos = ["ESPECIALIZAÇÃO", "MESTRADO", "DOUTORADO"]
    serie_pos = srv_dez.groupby("ano").apply(
        lambda g: round(100 * g["ESCOLARIDADE"].isin(pos).mean(), 1), include_groups=False)
    out["p12"] = {
        "escolaridades": list(esc.index),
        "cargos": list(esc.columns),
        "matriz": {c: [sup(v) if v else 0 for v in esc[c]] for c in esc.columns},
        "anos": [int(a) for a in anos_all],
        "pct_pos_graduados": [float(serie_pos.get(a, np.nan)) for a in anos_all],
        "pct_pos_atual": round(100 * srv_ult["ESCOLARIDADE"].isin(pos).mean(), 1),
        "pct_pos_tecnicos": round(100 * srv_ult.loc[srv_ult["cargo_g"] == "Técnico Judiciário",
                                                "ESCOLARIDADE"].isin(pos).mean(), 1),
    }

    # ---------------- p13 → Painel 12 — Conformidade estrutural Res. CSJT 296/2021 ----------------
    _EJUD = EJUD_RE
    srv["ejud"] = srv["UNIDADE_ADMINISTRATIVA"].str.contains(_EJUD, case=False, na=False, regex=True)
    srv["tem_com"] = srv["CODIGO_COMISSAO"].notna()
    sult = srv[srv["ref"] == ult_ref]
    # público-alvo do art. 14 = servidores ativos + magistrados providos ativos
    pubalvo = df[(~est) & (~REMPARA)].copy()
    pubalvo["ejud"] = pubalvo["UNIDADE_ADMINISTRATIVA"].str.contains(_EJUD, case=False, na=False, regex=True)
    pubalvo["is_mag"] = pubalvo["CARGO"].str.contains("JUIZ|DESEMBARGADOR", case=False, na=False)
    pult = pubalvo[pubalvo["ref"] == ult_ref]

    def _serS(fn): return [fn(srv[srv["ref"] == r]) for r in refs]
    def _serP(fn): return [fn(pubalvo[pubalvo["ref"] == r]) for r in refs]

    def _a5(g):
        return round(100 * g["TIPO_SERVIDOR"].isin(["Requisitado", "Sem vínculo efetivo"]).sum() / len(g), 2) if len(g) else None
    art5 = {"pct": _serS(_a5), "teto": 20.0, "pct_atual": _a5(sult),
            "n_atual": int(sult["TIPO_SERVIDOR"].isin(["Requisitado", "Sem vínculo efetivo"]).sum()),
            "forca_atual": int(len(sult))}

    def _a6(g):
        efet = (g["TIPO_SERVIDOR"] == "Cargo efetivo").sum()
        return round(100 * g["tem_com"].sum() / efet, 2) if efet else None
    com_u = sem_dup_comissao(sult[sult["tem_com"]])
    niveis = ["CJ-4", "CJ-3", "CJ-2", "CJ-1", "FC-06", "FC-05", "FC-04", "FC-03", "FC-02"]
    _pn = [{"nivel": n, "n": int((com_u["CODIGO_COMISSAO"] == n).sum())} for n in niveis]
    _pn = [x for x in _pn if x["n"] > 0]
    # k=5: os niveis com poucos ocupantes vao para um balde unico, como o p11 ja
    # faz com "Demais funcoes". Dobra em ordem crescente ate o balde chegar a
    # K_MIN — senao o balde seria ele proprio uma celula pequena, e o total
    # publicado (n_com) o devolveria por subtracao.
    _ord = sorted(_pn, key=lambda x: x["n"])
    _balde, _fica = [], []
    for x in _ord:
        if x["n"] < K_MIN or (_balde and sum(y["n"] for y in _balde) < K_MIN):
            _balde.append(x)
        else:
            _fica.append(x)
    por_nivel = [x for x in _pn if x in _fica]
    if _balde:
        _s = sum(x["n"] for x in _balde)
        if _s < K_MIN:
            sys.exit("ERRO k=%d: 'Demais níveis' ficaria com n=%d." % (K_MIN, _s))
        por_nivel.append({"nivel": "Demais níveis (agregado)", "n": _s})
    art6 = {"pct": _serS(_a6), "teto": 80.0, "proxy": True, "pct_atual": _a6(sult),
            "n_com": int(len(com_u)), "n_efet": int((sult["TIPO_SERVIDOR"] == "Cargo efetivo").sum()),
            "n_cj": int(com_u["CODIGO_COMISSAO"].str.startswith("CJ", na=False).sum()),
            "n_fc": int(com_u["CODIGO_COMISSAO"].str.startswith("FC", na=False).sum()), "por_nivel": por_nivel}

    def _a12(g):
        b = g[(g["AREA"] != "T.I.") & (~g["ejud"])]
        d = b["AREA"].isin(["Meio", "Fim"]).sum()
        return round(100 * (b["AREA"] == "Meio").sum() / d, 2) if d else None
    b12u = sult[(sult["AREA"] != "T.I.") & (~sult["ejud"])]
    art12 = {"pct": _serS(_a12), "faixa_min": 20.0, "faixa_max": 30.0, "pct_atual": _a12(sult),
             "n_meio": int((b12u["AREA"] == "Meio").sum()), "n_fim": int((b12u["AREA"] == "Fim").sum()),
             "n_tic": int((sult["AREA"] == "T.I.").sum()), "n_ejud": int(sult["ejud"].sum())}

    def _a14(g):
        return round(100 * g["ejud"].sum() / len(g), 3) if len(g) else None
    art14 = {"pct": _serP(_a14), "faixa_min": 0.7, "faixa_max": 1.0, "pct_atual": _a14(pult),
             "n_ejud": int(pult["ejud"].sum()), "publico_alvo": int(len(pult)),
             "n_magistrados": int(pult["is_mag"].sum()),
             "faixa_n_min": round(0.007 * len(pult), 1), "faixa_n_max": round(0.010 * len(pult), 1)}

    fim_u = sult[sult["AREA"] == "Fim"].copy()
    fim_u["grau"] = fim_u["UNIDADE_ADMINISTRATIVA"].astype(str).str.strip().str.upper().map(gmap)
    g1 = int((fim_u["grau"] == "1º").sum()); g2 = int((fim_u["grau"] == "2º").sum())
    art7 = {"grau1": g1, "grau2": g2, "nd": int(len(fim_u) - g1 - g2), "total": int(len(fim_u))}

    out["p13"] = {
        "refs": refs, "ultima_referencia": ult_ref, "forca_atual": int(len(sult)),
        "art5": art5, "art6": art6, "art12": art12, "art14": art14, "art7": art7,
        "notas": {
            "forca": "Força de trabalho de servidores = servidores com lotação ativa no TRT-17 (exclui estagiários, servidores removidos para outros órgãos e magistrados).",
            "art5": "Fora das carreiras judiciárias federais = requisitados de outros órgãos + comissionados sem vínculo. Teto de 20% (art. 5º).",
            "art6": "Cargos em comissão (CJ) + funções comissionadas (FC) ÷ cargos efetivos de servidores providos com lotação ativa. Teto de 80% (art. 6º). PROXY: a norma mede o quantitativo de cargos efetivos AUTORIZADOS (inclui vagos); a base traz apenas postos ocupados, o que superestima a razão. Não se emite veredito de conformidade.",
            "art12": "Servidores da área meio ÷ (área fim + meio), excluídos T.I.C. e Escola Judicial (art. 12, parágrafo único). Faixa 20%–30% para tribunais de pequeno porte.",
            "art14": "Lotação da Escola Judicial ÷ público-alvo (magistrados providos + força de servidores, conforme Anexo IV). Faixa 0,7%–1,0% para tribunais de pequeno porte (art. 14, caput, III).",
            "art7": "DESCRITIVO — distribuição da força de apoio direto de servidores (área fim) entre 1º e 2º graus. NÃO é aferição de conformidade: o art. 7º exige proporção à média de casos novos por grau, dado não presente nesta base.",
        },
    }

    # ---------------- risco_sucessorio → Painel 17 — Quadro etário ----------------
    # Universo: o MESMO srv dos paineis 6-12 (sem estagiarios, sem removidos-para,
    # sem magistrados), restrito ao vinculo "Cargo efetivo". Equivale a
    # "servidores efetivos ativos, exceto magistrados" — e coincide, por
    # construcao, com p07["por_vinculo"]["Cargo efetivo"] da ultima referencia.
    # So esta secao do Painel 17 sai daqui; o resto do painel e apuracao manual.
    ef = srv_ult[srv_ult["TIPO_SERVIDOR"] == "Cargo efetivo"]
    rs_bins = [0, 40, 50, 55, 60, 65, 200]
    rs_labs = ["Até 39 anos", "40 a 49 anos", "50 a 54 anos",
               "55 a 59 anos", "60 a 64 anos", "65 anos ou mais"]
    rs_fx = (pd.cut(ef["IDADE"], rs_bins, labels=rs_labs, right=False)
             .value_counts().reindex(rs_labs).fillna(0))
    out["risco_sucessorio"] = {
        "ultima_referencia": ult_ref,
        "universo": "Servidores efetivos ativos, exceto magistrados "
                    "(vínculo \"Cargo efetivo\" na força de servidores com lotação ativa; "
                    "exclui estagiários e servidores removidos para outros órgãos).",
        "faixas": rs_labs,
        "contagens": [sup(v) if v else 0 for v in rs_fx],
        "total": int(len(ef)),
        "idade_mediana": round(float(ef["IDADE"].median()), 1),
        "idade_media": round(float(ef["IDADE"].mean()), 1),
        "n_55mais": int((ef["IDADE"] >= 55).sum()),
        "n_60mais": int((ef["IDADE"] >= 60).sum()),
    }

    with open("dados_paineis_forca.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK — dados_paineis_forca.json gerado ({ult_ref}, {len(srv_ult)} servidores no último snapshot)")

if __name__ == "__main__":
    # argumento opcional: se omitido, localiza a planilha na pasta atual
    main(sys.argv[1] if len(sys.argv) > 1 else None)
