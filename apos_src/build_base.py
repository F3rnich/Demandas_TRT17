#!/usr/bin/env python3
"""
build_base.py — gera dados_aposentadoria.json (raiz do repo): parâmetros da
calculadora de aposentadoria, sem nenhum dado pessoal.

Conteúdo
  inpc            variação % mensal do INPC desde 07/1994 (BCB/SGS 188 = IBGE)
  teto_rgps       teto do RGPS por competência
  salario_minimo  salário mínimo por competência
  tabelas         vencimento básico + GAJ por cargo/classe/padrão, por vigência
  subsidios       subsídio de magistrado por cargo, por vigência

Uso (no computador do Leo, com internet):
  python apos_src/build_base.py                     # atualiza o INPC pelo BCB e gera o JSON
  python apos_src/build_base.py --offline           # usa só os arquivos de apos_src/fontes
  python apos_src/build_base.py --diprof Base_Remuneracao_RBC_TRT17.xlsx
                                                    # reextrai teto/SM/tabelas da base da DIPROF
Depois: python deploy.py "Base da aposentadoria - <mês>" dados_aposentadoria.json apos_src/fontes/inpc_bcb188.json:apos_src/fontes/inpc_bcb188.json
"""
import json, sys, datetime, pathlib, urllib.request

AQUI = pathlib.Path(__file__).resolve().parent
FONTES = AQUI / "fontes"
SAIDA = AQUI.parent / "dados_aposentadoria.json"
URL_BCB = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.188/dados?formato=json&dataInicial=01/07/1994"


def atualizar_inpc():
    with urllib.request.urlopen(urllib.request.Request(URL_BCB, headers={"User-Agent": "build_base.py"}), timeout=60) as r:
        dados = json.load(r)
    serie = {f"{x['data'][6:10]}-{x['data'][3:5]}": float(x["valor"]) for x in dados}
    serie = {k: v for k, v in sorted(serie.items()) if k >= "1994-07"}
    antigo = json.loads((FONTES / "inpc_bcb188.json").read_text(encoding="utf-8"))["serie"]
    # revisões de meses já publicados são raras; avisar se houver
    rev = [k for k in antigo if k in serie and abs(antigo[k] - serie[k]) > 1e-9]
    if rev:
        print("AVISO: valores revistos pelo BCB em", rev[:10])
    if len(serie) < len(antigo):
        sys.exit("ERRO: série do BCB veio menor que a armazenada — abortado.")
    (FONTES / "inpc_bcb188.json").write_text(json.dumps({
        "fonte": "Banco Central do Brasil, SGS série 188 (INPC/IBGE, variação % mensal)",
        "obtido_em": datetime.date.today().isoformat(), "serie": serie}, indent=0), encoding="utf-8")
    print(f"INPC: {len(serie)} meses, até {max(serie)}")


def extrair_diprof(caminho):
    import openpyxl
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    def linhas(n):
        it = wb[n].iter_rows(values_only=True); next(it); return list(it)
    P = linhas("parametros_mensais")
    tab, mag = {}, {}
    for r in linhas("competencias_servidor"):
        if r[1] not in ("ANALISTA JUDICIÁRIO", "TÉCNICO JUDICIÁRIO", "AUXILIAR JUDICIÁRIO"): continue
        if r[2] not in ("A", "B", "C") or not str(r[3]).isdigit() or int(r[3]) > 13 or r[0] < "2006-06": continue
        tab.setdefault(r[6], {}).setdefault(r[1], {})[f"{r[2]}{r[3]}"] = {"vb": r[7], "gaj": r[8]}
    for r in linhas("competencias_magistrado"):
        if r[4] and r[0] >= "2005-01": mag.setdefault(r[3], {})[r[1]] = r[4]
    (FONTES / "parametros_diprof.json").write_text(json.dumps({
        "fonte": f"TABELA_REMUNERAÇÃO.xlsx (DIPROF/TRT-17), via {pathlib.Path(caminho).name}. Valores nominais.",
        "teto_rgps": {r[0]: r[1] for r in P}, "salario_minimo": {r[0]: r[2] for r in P},
        "tabelas_servidor": dict(sorted(tab.items())), "subsidios_magistrado": dict(sorted(mag.items())),
        "competencia_final": max(r[0] for r in P)}, ensure_ascii=False, indent=0), encoding="utf-8")
    print("Parâmetros da DIPROF reextraídos.")


def validar(d):
    erros = []
    meses = sorted(d["inpc"]["serie"])
    if meses[0] != "1994-07": erros.append("INPC não começa em 1994-07")
    # sem buracos
    y, m = 1994, 7
    for k in meses:
        if k != f"{y}-{m:02d}": erros.append(f"INPC: lacuna antes de {k}"); break
        m += 1
        if m == 13: y, m = y + 1, 1
    if any(abs(v) > 60 for v in d["inpc"]["serie"].values()): erros.append("INPC com variação mensal implausível")
    t = d["teto_rgps"]
    if not all(t[a] <= t[b] for a, b in zip(sorted(t), sorted(t)[1:])): erros.append("teto do RGPS decresce em algum mês")
    for vig, cargos in d["tabelas"].items():
        for cargo, pad in cargos.items():
            if len(pad) != 13: erros.append(f"tabela {vig} {cargo}: {len(pad)} padrões (esperado 13)")
    return erros


def main():
    args = sys.argv[1:]
    if "--diprof" in args: extrair_diprof(args[args.index("--diprof") + 1])
    if "--offline" not in args:
        try: atualizar_inpc()
        except Exception as e: print("AVISO: INPC não atualizado (", e, ") — usando o armazenado.")
    inpc = json.loads((FONTES / "inpc_bcb188.json").read_text(encoding="utf-8"))
    dip = json.loads((FONTES / "parametros_diprof.json").read_text(encoding="utf-8"))
    d = {
        "meta": {"gerado_em": datetime.date.today().isoformat(),
                 "inpc_ate": max(inpc["serie"]), "tabelas_ate": dip["competencia_final"],
                 "fontes": [inpc["fonte"] + f", obtido em {inpc['obtido_em']}", dip["fonte"]],
                 "uso": "Parâmetros da calculadora de aposentadoria. Sem dados pessoais."},
        "inpc": {"serie": inpc["serie"]},
        "teto_rgps": dip["teto_rgps"], "salario_minimo": dip["salario_minimo"],
        "tabelas": dip["tabelas_servidor"], "subsidios": dip["subsidios_magistrado"],
    }
    erros = validar(d)
    if erros: sys.exit("ERRO na validação:\n  " + "\n  ".join(erros))
    SAIDA.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"OK → {SAIDA.name} (INPC até {d['meta']['inpc_ate']}, tabelas até {d['meta']['tabelas_ate']})")


if __name__ == "__main__":
    main()
