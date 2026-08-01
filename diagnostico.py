#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnostico.py — Inspeciona a estrutura da base ANTES de rodar o build.

USO:
    python diagnostico.py
    python diagnostico.py "Base atualizada.ods"
    python diagnostico.py "G:\\Drives compartilhados\\...\\Base atualizada.xlsx"

Nao grava nada e nao imprime dado individual: so nomes de aba, nomes de
coluna, contagens e faixa de competencias.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_paineis_forca import resolver_base, abas, ler_aba  # noqa: E402

COLS_EXIGIDAS = [
    "REFERENCIA", "MATRICULA", "TIPO_SERVIDOR", "SITUACAO_FUNCIONAL",
    "CARGO", "RAÇA", "SEXO", "IDADE", "ESCOLARIDADE", "AREA",
    "CODIGO_COMISSAO", "NOME_COMISSAO", "VALOR", "UNIDADE_ADMINISTRATIVA",
]


def norm(s):
    return str(s).strip().lower()


def main(alvo=None):
    path = resolver_base(alvo)
    print(f"arquivo : {path}")
    print(f"formato : {path.suffix}   tamanho: {path.stat().st_size/1024:.0f} KB")

    nomes = abas(path)
    print(f"\nabas ({len(nomes)}):")
    for a in nomes:
        externa = a.startswith("'file:///") or a.startswith("file:///")
        marca = "  [LINK EXTERNO - conteudo em cache]" if externa else ""
        print(f"  - {a}{marca}")

    # escolhe a aba de dados: a que tiver REFERENCIA
    aba_dados = None
    for a in nomes:
        try:
            amostra = pd.read_excel(path, sheet_name=a, nrows=1,
                                    engine={".ods": "odf"}.get(
                                        path.suffix.lower(), "openpyxl"))
        except Exception:
            continue
        if any(norm(c) == "referencia" for c in amostra.columns):
            aba_dados = a
            break

    if aba_dados is None:
        print("\n[!] Nenhuma aba com coluna REFERENCIA. Nada a diagnosticar.")
        return

    print(f"\naba de dados detectada: '{aba_dados}'")
    df = ler_aba(path, aba_dados)
    print(f"linhas  : {len(df):,}".replace(",", "."))
    print(f"colunas : {len(df.columns)}")

    # --- colunas -----------------------------------------------------------
    presentes = {norm(c): c for c in df.columns}
    faltando = [c for c in COLS_EXIGIDAS if norm(c) not in presentes]
    extras = [c for c in df.columns
              if norm(c) not in {norm(x) for x in COLS_EXIGIDAS}]

    print("\ncolunas exigidas pelo build:")
    for c in COLS_EXIGIDAS:
        real = presentes.get(norm(c))
        if real is None:
            print(f"  [FALTA] {c}")
        elif real != c:
            print(f"  [ok*]   {c}  (na planilha: '{real}' — grafia difere)")
        else:
            print(f"  [ok]    {c}")
    if extras:
        print(f"\ncolunas extras (ignoradas): {extras}")

    # --- cobertura temporal ------------------------------------------------
    col_ref = presentes.get("referencia")
    if col_ref:
        ref = pd.to_datetime(df[col_ref], errors="coerce")
        validas = ref.notna().sum()
        comp = sorted(ref.dropna().dt.strftime("%Y-%m").unique())
        print("\ncobertura temporal:")
        print(f"  REFERENCIA validas : {validas:,} de {len(df):,}".replace(",", "."))
        print(f"  competencias        : {len(comp)}")
        if comp:
            print(f"  primeira / ultima   : {comp[0]}  ->  {comp[-1]}")
        if len(comp) <= 3:
            print("\n  [!] ATENCAO: poucas competencias. Os paineis 6, 7 e 10 sao")
            print("      series temporais e precisam do historico completo.")
            print("      Rodar o build assim SUBSTITUI o historico publicado.")

        # linhas por competencia (so as 6 ultimas)
        cont = ref.dropna().dt.strftime("%Y-%m").value_counts().sort_index()
        print("\n  linhas por competencia (ultimas 6):")
        for k, v in cont.tail(6).items():
            print(f"    {k}: {v}")

    # --- idade x referencia ------------------------------------------------
    col_idade = presentes.get("idade")
    col_mat = presentes.get("matricula")
    if col_idade and col_ref:
        ult = ref.max()
        sub = df.loc[ref == ult, col_idade]
        idades = pd.to_numeric(sub, errors="coerce").dropna()
        if len(idades):
            print(f"\nIDADE na ultima competencia ({ult:%Y-%m}):")
            print(f"  min {idades.min():.0f} | media {idades.mean():.1f} | max {idades.max():.0f}")

    # teste de ancoragem: TODAY() vs REFERENCIA
    if col_idade and col_ref and col_mat:
        t = pd.DataFrame({
            "mat": df[col_mat],
            "ref": ref,
            "idade": pd.to_numeric(df[col_idade], errors="coerce"),
        }).dropna()
        if len(t):
            g = t.groupby("mat").agg(
                n_comp=("ref", "nunique"),
                n_idades=("idade", "nunique"),
                span_anos=("ref", lambda s: (s.max() - s.min()).days / 365.25),
            )
            # so quem tem historico longo o suficiente para o teste discriminar
            g = g[g["span_anos"] >= 3]
            print("\nancoragem da coluna IDADE:")
            if not len(g):
                print("  [?] historico curto demais para testar.")
            else:
                const = (g["n_idades"] == 1).mean()
                esperado = g["span_anos"].median()
                obtido = g["n_idades"].median()
                print(f"  matriculas com >=3 anos de historico : {len(g)}")
                print(f"  valores distintos de IDADE (mediana) : {obtido:.0f}")
                print(f"  esperado se ancorada em REFERENCIA   : ~{esperado:.0f}")
                print(f"  matriculas com IDADE constante       : {const*100:.1f}%")
                if const > 0.5 or obtido <= 1:
                    print("\n  [!] IDADE parece ancorada em TODAY(): nao varia ao longo")
                    print("      do historico. O painel 8 (envelhecimento demografico)")
                    print("      fica errado. Corrija na planilha antes do build.")
                else:
                    print("\n  [ok] IDADE varia com a competencia — ancoragem correta.")

    print("\n" + ("-" * 60))
    if faltando:
        print(f"RESULTADO: {len(faltando)} coluna(s) faltando -> o build vai quebrar.")
        print(f"           {faltando}")
    else:
        print("RESULTADO: estrutura de colunas OK para o build.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
