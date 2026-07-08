#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_paineis_forca.py — Gera dados_paineis_forca.json para os painéis 07–13
do hub Demandas_TRT17 a partir da base de pessoal da SGP (xlsx local).

USO:
    python build_paineis_forca.py /caminho/para/Base_atualizada.xlsx

REGRAS LGPD (aplicadas na origem — nenhum dado individual sai deste script):
  1. Nenhum identificador (NOME, CPF, MATRICULA, NASCIMENTO) é gravado no JSON.
  2. Supressão de células pequenas: qualquer categoria publicada com 0 < n < 5
     é agregada em "Outros" ou omitida (k-anonimato, k=5).
  3. Raça/cor só é publicada agrupada: Branca / Negra (pretos+pardos) / Outras ou NI.
  4. Deficiência, doença grave e identidade de gênero NÃO são exportadas
     (categorias com n<5 na base atual — reidentificáveis).
  5. Nenhum cruzamento de atributo sensível com unidade administrativa.

A BASE NUNCA ENTRA NO REPOSITÓRIO. Apenas este script e o JSON agregado.
"""
import sys, json
import pandas as pd
import numpy as np

K_MIN = 5  # k-anonimato

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
    df = pd.read_excel(path, sheet_name="dados")
    df["REFERENCIA"] = pd.to_datetime(df["REFERENCIA"])
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

    out = {"gerado_de": "base local SGP (não versionada)",
           "ultima_referencia": ult_ref, "k_anonimato": K_MIN}

    # ---------------- P07 — Evolução histórica (servidores) ----------------
    serie_total = srv.groupby("ref").size()
    por_area = srv.pivot_table(index="ref", columns="AREA", values="MATRICULA",
                               aggfunc="count").fillna(0).astype(int)
    por_vinc = srv.pivot_table(index="ref", columns="TIPO_SERVIDOR",
                               values="MATRICULA", aggfunc="count").fillna(0).astype(int)
    keep = [c for c in por_vinc.columns if por_vinc[c].max() >= K_MIN]
    drop = [c for c in por_vinc.columns if c not in keep]
    if drop:
        por_vinc["Outros"] = por_vinc[drop].sum(axis=1)
        por_vinc = por_vinc.drop(columns=drop)
    grau = srv[srv["GRAU"].isin(["1º", "2º"])]
    por_grau = grau.pivot_table(index="ref", columns="GRAU", values="MATRICULA",
                                aggfunc="count").fillna(0).astype(int)
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

    # ---------------- P08 — Envelhecimento ----------------
    bins = [0, 30, 35, 40, 45, 50, 55, 60, 200]
    labs = ["< 30", "30–34", "35–39", "40–44", "45–49", "50–54", "55–59", "60 +"]
    ult["fx"] = pd.cut(ult["IDADE"], bins=bins, labels=labs, right=False)
    pir = {}
    for sx, nome in [("M", "Masculino"), ("F", "Feminino")]:
        s = ult[ult["SEXO"] == sx]["fx"].value_counts().reindex(labs).fillna(0)
        pir[nome] = [sup(v) if v else 0 for v in s]
    anos = sorted(ft["ano"].unique())
    ft_dez = ft.sort_values("REFERENCIA").groupby(["ano", "MATRICULA"]).tail(1)
    idade_media = ft_dez.groupby("ano")["IDADE"].mean().round(1)
    p55 = ft_dez.groupby("ano").apply(
        lambda g: round(100 * (g["IDADE"] >= 55).mean(), 1), include_groups=False)
    fx_area = ult.pivot_table(index="AREA", columns=pd.cut(
        ult["IDADE"], [0, 45, 55, 200], labels=["< 45", "45–54", "55 +"], right=False),
        values="MATRICULA", aggfunc="count", observed=True).fillna(0).astype(int)
    out["p08"] = {
        "faixas": labs, "piramide": pir,
        "anos": [int(a) for a in anos],
        "idade_media": [float(idade_media.get(a, np.nan)) for a in anos],
        "pct_55mais": [float(p55.get(a, np.nan)) for a in anos],
        "idade_por_area": {str(i): [sup(v) if v else 0 for v in fx_area.loc[i]]
                           for i in fx_area.index},
        "idade_area_faixas": list(fx_area.columns.astype(str)),
        "idade_media_atual": round(float(ult["IDADE"].mean()), 1),
        "n_55mais_atual": int((ult["IDADE"] >= 55).sum()),
        "n_60mais_atual": int((ult["IDADE"] >= 60).sum()),
        "total_atual": int(len(ult)),
    }

    # ---------------- P09 — Equidade em comissionamentos (força de servidores) ----------------
    com = srv_ult[srv_ult["CODIGO_COMISSAO"].notna()]
    def paridade(col, grupos):
        r = {}
        for g in grupos:
            n_f = int((srv_ult[col] == g).sum()); n_c = int((com[col] == g).sum())
            if n_f < K_MIN: continue
            pf = 100 * n_f / len(srv_ult); pc = 100 * n_c / len(com)
            vm = com.loc[com[col] == g, "VALOR"]
            r[g] = {"n_forca": n_f, "pct_forca": round(pf, 1),
                    "n_com": sup(n_c), "pct_com": round(pc, 1),
                    "indice_paridade": round(pc / pf, 2) if pf else None,
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
            pf = (g[col] == val).mean(); pc = (c[col] == val).mean()
            ip_serie[chave].append(round(pc / pf, 2) if pf > 0 else None)
    out["p09"]["serie_paridade"] = ip_serie

    # ---------------- P10 — Tempo até a primeira comissão ----------------
    snap0 = ft["REFERENCIA"].min()
    fim_obs = ft["REFERENCIA"].max()
    first = ft.groupby("MATRICULA")["REFERENCIA"].min()
    last = ft.groupby("MATRICULA")["REFERENCIA"].max()
    coorte = first[first > snap0].index  # entrada observável
    fc1 = ft[ft["CODIGO_COMISSAO"].notna()].groupby("MATRICULA")["REFERENCIA"].min()
    atrib = ft.sort_values("REFERENCIA").groupby("MATRICULA").first()  # atributos na entrada
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
    def km_curve(sub):
        """% acumulado que recebeu FC até t anos (incidência simples entre observados ≥ t)."""
        pts = []
        for t in [x / 2 for x in range(0, 21)]:  # 0 a 10 anos, passo 0,5
            risco = sub[(sub["t_obs"] >= t) | (sub["evento"] & (sub["t"] <= t))]
            if len(risco) < K_MIN: pts.append(None); continue
            ev = ((risco["evento"]) & (risco["t"] <= t)).sum()
            pts.append(round(100 * ev / len(risco), 1))
        return pts
    def mediana_grp(col, grupos):
        r = {}
        for g in grupos:
            s = sem_fc_inicial[(sem_fc_inicial[col] == g) & sem_fc_inicial["evento"]]["t"]
            r[g] = {"n": sup(len(s)),
                    "mediana_anos": round(float(s.median()), 1) if len(s) >= K_MIN else None}
        return r
    out["p10"] = {
        "n_coorte": int(len(co)),
        "n_chegou_com_fc": int(co["chegou"].sum()),
        "n_entrou_sem_fc": int(len(sem_fc_inicial)),
        "n_conquistou_depois": int(sem_fc_inicial["evento"].sum()),
        "mediana_geral_anos": round(float(
            sem_fc_inicial[sem_fc_inicial["evento"]]["t"].median()), 1),
        "eixo_anos": [x / 2 for x in range(0, 21)],
        "curva_geral": km_curve(sem_fc_inicial),
        "curva_sexo": {g: km_curve(sem_fc_inicial[sem_fc_inicial["sexo"] == g]) for g in ["F", "M"]},
        "curva_raca": {g: km_curve(sem_fc_inicial[sem_fc_inicial["raca"] == g])
                       for g in ["Branca", "Negra"]},
        "mediana_sexo": mediana_grp("sexo", ["F", "M"]),
        "mediana_raca": mediana_grp("raca", ["Branca", "Negra"]),
        "coorte_desde": str(sorted(first[first > snap0])[0].date()) if len(coorte) else None,
    }

    # ---------------- P11 — Custo dos comissionamentos ----------------
    comt = ft[ft["CODIGO_COMISSAO"].notna()]
    custo = comt.groupby("ref")["VALOR"].sum()
    qtd = comt.groupby("ref").size()
    tipos = ult[ult["CODIGO_COMISSAO"].notna()].groupby("NOME_COMISSAO").agg(
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
        "nota": "Valores nominais (sem correção inflacionária).",
    }

    # ---------------- P12 — Qualificação × cargo ----------------
    ordem_esc = ["ENSINO FUNDAMENTAL", "ENSINO MÉDIO", "SUPERIOR INCOMPLETO",
                 "GRADUAÇÃO", "SUPERIOR", "ESPECIALIZAÇÃO", "MESTRADO", "DOUTORADO"]
    def cargo_agg(c):
        c = str(c).upper()
        if "ANALISTA" in c: return "Analista Judiciário"
        if "TÉCNICO" in c or "TECNICO" in c: return "Técnico Judiciário"
        return "Demais"
    ult["cargo_g"] = ult["CARGO"].map(cargo_agg)
    esc = ult.pivot_table(index="ESCOLARIDADE", columns="cargo_g", values="MATRICULA",
                          aggfunc="count").fillna(0).astype(int)
    esc = esc.reindex([e for e in ordem_esc if e in esc.index])
    pos = ["ESPECIALIZAÇÃO", "MESTRADO", "DOUTORADO"]
    serie_pos = ft_dez.groupby("ano").apply(
        lambda g: round(100 * g["ESCOLARIDADE"].isin(pos).mean(), 1), include_groups=False)
    out["p12"] = {
        "escolaridades": list(esc.index),
        "cargos": list(esc.columns),
        "matriz": {c: [sup(v) if v else 0 for v in esc[c]] for c in esc.columns},
        "anos": [int(a) for a in anos],
        "pct_pos_graduados": [float(serie_pos.get(a, np.nan)) for a in anos],
        "pct_pos_atual": round(100 * ult["ESCOLARIDADE"].isin(pos).mean(), 1),
        "pct_pos_tecnicos": round(100 * ult.loc[ult["cargo_g"] == "Técnico Judiciário",
                                                "ESCOLARIDADE"].isin(pos).mean(), 1),
    }

    # ---------------- P13 — Conformidade estrutural Res. CSJT 296/2021 ----------------
    _EJUD = r"Escola Judicial|Capacita[çc][ãa]o de Magistrado|Capacita[çc][ãa]o de Servidor"
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
    com_u = sult[sult["tem_com"]]
    niveis = ["CJ-4", "CJ-3", "CJ-2", "CJ-1", "FC-06", "FC-05", "FC-04", "FC-03", "FC-02"]
    por_nivel = [{"nivel": n, "n": int((com_u["CODIGO_COMISSAO"] == n).sum())} for n in niveis]
    por_nivel = [x for x in por_nivel if x["n"] > 0]
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

    try:
        bu = pd.read_excel(path, sheet_name="Base unidades")
        gmap = dict(zip(bu["UNIDADE ADMINISTRATIVA"].astype(str).str.strip().str.upper(), bu["GRAU"]))
    except Exception:
        gmap = {}
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

    with open("dados_paineis_forca.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK — dados_paineis_forca.json gerado ({ult_ref}, {len(ult)} servidores no último snapshot)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python build_paineis_forca.py <Base.xlsx>")
    main(sys.argv[1])
