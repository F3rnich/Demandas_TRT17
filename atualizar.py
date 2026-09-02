#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
atualizar.py — Atualizacao mensal dos paineis de forca de trabalho.

Encadeia tudo em um comando:
    1. localiza a base (qualquer formato) e valida a estrutura
    2. checa coerencia AREA x UNIDADE_ADMINISTRATIVA (pega erro de rotulo)
    3. roda o build (gera dados_paineis_forca.json)
    4. compara com o JSON publicado: histórico retroativo + coerencia p07/p13
    5. pede confirmacao e faz o deploy

USO:
    python atualizar.py                 (interativo, pede confirmacao)
    python atualizar.py --sim           (nao pergunta, faz o deploy)
    python atualizar.py --so-checar     (para antes do deploy)

TOKEN: lido de %GITHUB_PAT%. Configure UMA VEZ no Windows com:
    setx GITHUB_PAT "seu_token_aqui"
e abra um CMD novo depois.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_paineis_forca import (resolver_base, abas, ler_aba,  # noqa: E402
                                 EJUD_RE)

REPO = "F3rnich/Demandas_TRT17"
JSON_NOME = "dados_paineis_forca.json"
COLS = ["REFERENCIA", "MATRICULA", "TIPO_SERVIDOR", "SITUACAO_FUNCIONAL",
        "CARGO", "RAÇA", "SEXO", "IDADE", "ESCOLARIDADE", "AREA",
        "CODIGO_COMISSAO", "NOME_COMISSAO", "VALOR", "UNIDADE_ADMINISTRATIVA"]

AVISOS: list[str] = []
ERROS: list[str] = []


def titulo(t):
    print(f"\n{'=' * 62}\n{t}\n{'=' * 62}")


def norm(s):
    return str(s).strip().lower()


# ---------------------------------------------------------------------------
# 1-2. Validacao da base
# ---------------------------------------------------------------------------

def checar_base():
    titulo("1. BASE")
    path = resolver_base(None)
    kb = path.stat().st_size / 1024
    print(f"  arquivo : {path.name}  ({kb:,.0f} KB)".replace(",", "."))

    nomes = abas(path)
    externas = [a for a in nomes if "file:///" in a]
    if externas:
        ERROS.append("A planilha tem abas que sao LINK EXTERNO (conteudo em "
                     "cache, procedencia incerta). Use o arquivo de origem.")
        for a in externas:
            print(f"  [!] aba com link externo: {a[:70]}...")

    aba_dados = next((a for a in nomes if norm(a) == "dados"), None)
    if aba_dados is None:
        for a in nomes:
            try:
                am = pd.read_excel(path, sheet_name=a, nrows=1,
                                   engine={".ods": "odf"}.get(path.suffix.lower(),
                                                              "openpyxl"))
            except Exception:
                continue
            if any(norm(c) == "referencia" for c in am.columns):
                aba_dados = a
                AVISOS.append(f"Aba de dados chama-se '{a}', nao 'dados'.")
                break
    if aba_dados is None:
        ERROS.append(f"Nenhuma aba com REFERENCIA. Abas: {nomes}")
        return path, None

    df = ler_aba(path, aba_dados)
    print(f"  aba     : {aba_dados}")
    print(f"  linhas  : {len(df):,}".replace(",", "."))

    presentes = {norm(c): c for c in df.columns}
    falta = [c for c in COLS if norm(c) not in presentes]
    if falta:
        ERROS.append(f"Colunas faltando: {falta}")
    else:
        print("  colunas : todas as 14 exigidas presentes")

    # --- cobertura temporal ---
    ref = pd.to_datetime(df[presentes["referencia"]], errors="coerce")
    comp = sorted(ref.dropna().dt.strftime("%Y-%m").unique())
    invalidas = int(ref.isna().sum())
    print(f"  periodo : {comp[0]} -> {comp[-1]}  ({len(comp)} competencias)")
    if invalidas:
        print(f"  [i] {invalidas} linha(s) com REFERENCIA vazia (serao descartadas)")
    if len(comp) < 12:
        ERROS.append(f"Apenas {len(comp)} competencia(s). Os paineis 6, 7 e 10 "
                     "sao series temporais e precisam do historico completo. "
                     "Parece um recorte mensal, nao a base acumulada.")

    # --- ancoragem da IDADE ---
    if not falta:
        t = pd.DataFrame({"mat": df[presentes["matricula"]], "ref": ref,
                          "idade": pd.to_numeric(df[presentes["idade"]],
                                                 errors="coerce")}).dropna()
        g = t.groupby("mat").agg(n=("idade", "nunique"),
                                 span=("ref", lambda s: (s.max() - s.min()).days / 365.25))
        g = g[g["span"] >= 3]
        if len(g) and (g["n"] == 1).mean() > 0.5:
            ERROS.append("Coluna IDADE nao varia ao longo do historico — parece "
                         "ancorada em TODAY(). O painel 8 ficaria errado.")
        elif len(g):
            print("  idade   : varia com a competencia (ancoragem correta)")

    # --- coerencia AREA x UNIDADE_ADMINISTRATIVA (o erro de hoje) ---
    if not falta:
        ult = ref.max()
        # MESMOS filtros do p13 (srv): sem estagiarios, sem removidos-para,
        # sem magistrados. Sem isso a contagem nao e comparavel.
        est = df[presentes["tipo_servidor"]].eq("Estagiário")
        rempara = df[presentes["situacao_funcional"]].eq("Removido para")
        mag = df[presentes["cargo"]].str.contains("JUIZ|DESEMBARGADOR",
                                                  case=False, na=False)
        u = df[(ref == ult) & (~est) & (~rempara) & (~mag)]
        na_ejud = u[presentes["unidade_administrativa"]].astype(str).str.contains(
            EJUD_RE, case=False, na=False, regex=True)
        rot_ejud = u[presentes["area"]].astype(str).str.upper().str.contains("EJUD", na=False)
        n_unid, n_rot = int(na_ejud.sum()), int(rot_ejud.sum())
        divergem = int((na_ejud & ~rot_ejud).sum() + (~na_ejud & rot_ejud).sum())
        print(f"  EJUD    : {n_unid} por lotacao / {n_rot} por rotulo AREA"
              + (f"  [{divergem} divergem — prevalece a lotacao]" if divergem
                 else "  [coerente]"))
        if divergem:
            # Ate 01/09/2026 isso era ERRO bloqueante, e com razao: o p07 lia a
            # coluna AREA e o p13 lia a EJUD_RE, entao os paineis 6 e 12
            # mostravam numeros diferentes. Desde 02/09/2026 o build deriva a
            # Escola Judicial da EJUD_RE — a FONTE UNICA — tambem no p07 e no
            # p08, e a coerencia entre os dois paineis e conferida adiante, no
            # comparar(). Aqui virou aviso: nao bloqueia mais.
            print(f"  [aviso] {divergem} servidor(es) com a coluna AREA "
                  f"divergindo da UNIDADE_ADMINISTRATIVA na EJUD em "
                  f"{ult:%Y-%m}. Nao bloqueia — o build usa a EJUD_RE. Ainda "
                  f"assim vale corrigir a coluna na origem: ela e derivada de "
                  f"formula e desanda a cada gravacao da planilha.")
    return path, comp[-1] if comp else None


# ---------------------------------------------------------------------------
# 3. Build
# ---------------------------------------------------------------------------

def rodar_build():
    titulo("2. BUILD")
    r = subprocess.run([sys.executable, "build_paineis_forca.py"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip()[-1500:])
    if r.returncode != 0 or not Path(JSON_NOME).exists():
        ERROS.append("O build falhou.")
        return False
    return True


# ---------------------------------------------------------------------------
# 4. Comparacao com o publicado
# ---------------------------------------------------------------------------

def baixar_publicado(token):
    url = f"https://api.github.com/repos/{REPO}/contents/{JSON_NOME}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return json.loads(base64.b64decode(d["content"]).decode("utf-8"))


def comparar(token):
    titulo("3. COMPARACAO COM O PUBLICADO")
    novo = json.loads(Path(JSON_NOME).read_text(encoding="utf-8"))
    try:
        pub = baixar_publicado(token)
    except Exception as e:
        ERROS.append(
            f"Nao consegui baixar o JSON publicado para comparar ({e}).\n"
            "      A comparacao retroativa e a trava que garante que o historico\n"
            "      nao foi alterado — sem ela, publicar seria as cegas.\n"
            "      HTTP 401 = token invalido. Confira com:  echo %GITHUB_PAT%")
        return novo

    print(f"  publicado: {pub.get('ultima_referencia')}   novo: {novo.get('ultima_referencia')}")
    pa, pn = pub["p07"], novo["p07"]
    ia = {r: i for i, r in enumerate(pa["refs"])}
    inn = {r: i for i, r in enumerate(pn["refs"])}
    comum = [r for r in pa["refs"] if r in inn]

    div = []
    for k, va in pa.items():
        if isinstance(va, list) and len(va) == len(pa["refs"]):
            div += [(k, r) for r in comum if va[ia[r]] != pn[k][inn[r]]]
        elif isinstance(va, dict):
            for sk, sv in va.items():
                if isinstance(sv, list) and len(sv) == len(pa["refs"]):
                    div += [(f"{k}.{sk}", r) for r in comum
                            if sv[ia[r]] != pn[k][sk][inn[r]]]
    if div:
        AVISOS.append(f"{len(div)} valor(es) do HISTORICO mudaram em relacao ao "
                      f"publicado. Se voce so acrescentou a competencia nova, "
                      f"isso nao deveria acontecer. Ex.: {div[:5]}")
        print(f"  [!] historico: {len(div)} divergencias retroativas")
    else:
        print(f"  historico: identico em {len(comum)} competencias")

    # coerencia p07 x p13 no ultimo ponto
    a12 = novo["p13"]["art12"]
    pares = [("EJUD", pn["por_area"].get("EJUD", [None])[-1], a12["n_ejud"]),
             ("Meio", pn["por_area"]["Meio"][-1], a12["n_meio"]),
             ("Fim", pn["por_area"]["Fim"][-1], a12["n_fim"]),
             ("T.I.", pn["por_area"]["T.I."][-1], a12["n_tic"])]
    ruins = [n for n, x, y in pares if x != y]
    if ruins:
        ERROS.append(f"Painel 6 e painel 12 discordam em: {ruins}. "
                     "Nao publique — indica erro de classificacao na base.")
    else:
        print("  paineis 6 e 12: coerentes")

    # resumo do mes
    print(f"\n  forca de trabalho : {pub['p13']['forca_atual']} -> {novo['p13']['forca_atual']}")
    for art, rot in [("art5", "art. 5"), ("art6", "art. 6"),
                     ("art12", "art. 12"), ("art14", "art. 14")]:
        print(f"  {rot:8s} : {pub['p13'][art]['pct_atual']} -> {novo['p13'][art]['pct_atual']}")
    return novo


# ---------------------------------------------------------------------------
# 5. Deploy
# ---------------------------------------------------------------------------

def deploy(ref, auto):
    titulo("4. DEPLOY")
    if not auto:
        r = input("  Publicar no hub? [s/N] ").strip().lower()
        if r not in ("s", "sim", "y"):
            print("  Cancelado. O JSON esta gerado na pasta.")
            return
    msg = f"atualiza dados forca de trabalho - {ref}"
    r = subprocess.run([sys.executable, "deploy.py", msg, JSON_NOME],
                       capture_output=True, text=True)
    print((r.stdout or r.stderr).strip()[-3000:])


# ---------------------------------------------------------------------------

def main():
    auto = "--sim" in sys.argv
    so_checar = "--so-checar" in sys.argv

    token = os.environ.get("GITHUB_PAT", "").strip()
    if not token and not so_checar:
        print("ERRO: variavel GITHUB_PAT nao configurada.\n"
              "  Rode UMA VEZ (com o token de verdade, sem aspas):\n"
              "     setx GITHUB_PAT <cole_aqui_o_token>\n"
              "  Depois feche e abra o CMD.")
        return 1
    if token in ("seu_token", "seu_token_aqui", "<seu_token>"):
        print("ERRO: GITHUB_PAT esta com o texto de exemplo, nao com o token.\n"
              "  Rode:  setx GITHUB_PAT <token_de_verdade>")
        return 1

    if not so_checar:
        faltam = [f for f in ("deploy.py", "validate_checks.py", "checks.json")
                  if not Path(f).exists()]
        if faltam:
            print(f"ERRO: faltam arquivos nesta pasta: {faltam}\n"
                  "  Sao necessarios para o deploy. Baixe-os do repositorio\n"
                  f"  https://github.com/{REPO}")
            return 1

    path, ult = checar_base()
    if ERROS:
        titulo("PARADO — corrija antes de continuar")
        for e in ERROS:
            print(f"  [X] {e}")
        return 1
    for a in AVISOS:
        print(f"  [aviso] {a}")

    if not rodar_build():
        for e in ERROS:
            print(f"  [X] {e}")
        return 1

    comparar(token)

    if ERROS:
        titulo("PARADO — nao publicar")
        for e in ERROS:
            print(f"  [X] {e}")
        return 1
    for a in AVISOS:
        print(f"\n  [aviso] {a}")

    if so_checar:
        titulo("OK — checagens passaram (deploy nao executado)")
        return 0

    deploy(ult, auto)
    return 0


if __name__ == "__main__":
    try:
        cod = main()
    except Exception as exc:
        print(f"\nERRO INESPERADO: {type(exc).__name__}: {exc}")
        cod = 1
    if sys.stdout.isatty() or os.name == "nt":
        input("\nPressione ENTER para fechar...")
    sys.exit(cod)
