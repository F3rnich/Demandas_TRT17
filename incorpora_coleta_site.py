"""Atualização incremental da base do portal (seção Legislação do TRT-17) usada pelo painel de atos normativos.

Dois comandos, usados pela rotina de sábado (rotinas/atualizacao_atos_normativos.md):

  python incorpora_coleta_site.py alvos [--base B] [--hoje AAAA-MM-DD]
      Imprime o JSON de alvos para rotinas/coletor_semanal.js: pastas-mãe (para descobrir pastas novas),
      pastas cujos documentos serão listados (ano corrente + seções/unidades sem subpastas por ano),
      ids de documentos já conhecidos nessas pastas e ids de todas as pastas conhecidas.

  python incorpora_coleta_site.py incorpora resultado.json [--base B]
      Junta à base os documentos novos devolvidos pelo coletor; grava a base e imprime um resumo JSON
      (novos documentos, pastas novas, pendências). Não altera documentos já existentes.
"""
import argparse
import datetime as dt
import json
import re
import sys

BASE = "fontes/atos_normativos/legislacao_trt17_site.json"
RAIZ = 1015014
ANO = re.compile(r"^(19|20)\d\d$")


def carrega(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def alvos(base, hoje):
    pastas = base["pastas"]
    por_id = {p["id"]: p for p in pastas}
    filhos = {}
    for p in pastas:
        pai = p["caminho"].rsplit("/", 1)[0] if "/" in p["caminho"] else None
        filhos.setdefault(pai, []).append(p)
    anos = {str(hoje.year)} | ({str(hoje.year - 1)} if hoje.month == 1 else set())
    maes, docs = [], []
    for p in pastas:
        segs = p["caminho"].split("/")
        tem_ano = any(re.search(r"\b(19|20)\d\d\b", s) for s in segs)
        anteriores = any(re.match(r"(anos )?anteriores", s.lower()) for s in segs)
        fs = filhos.get(p["caminho"], [])
        if len(segs) == 1 or (not tem_ano and not anteriores and any(ANO.match(f["caminho"].split("/")[-1]) for f in fs)):
            maes.append(p["id"])                       # seção ou unidade organizada por ano
        if segs[-1] in anos:
            docs.append(p["id"])                       # pasta do ano corrente
        elif not tem_ano and not anteriores and p.get("n"):
            docs.append(p["id"])                       # seção/unidade com documentos soltos
    alvo_docs = set(docs)
    conhecidos = [d["id"] for d in base["docs"] if any(por_id.get(i, {}).get("caminho") == d["pasta"] for i in alvo_docs)]
    return {"url": "https://www.trt17.jus.br/web/legislacao", "maes": sorted(set(maes)), "docs": sorted(alvo_docs),
            "conhecidos": conhecidos, "pastas_conhecidas": sorted(por_id),
            "_rotulos": {str(i): por_id[i]["caminho"] for i in sorted(set(maes) | alvo_docs)}}


def incorpora(base, res):
    caminho = {RAIZ: ""}
    caminho.update({p["id"]: p["caminho"] for p in base["pastas"]})
    novas_pastas = []
    pend = list(res.get("pastas", []))
    for _ in range(5):                                 # pastas novas aninhadas: resolve em camadas
        resto = []
        for f in pend:
            if f["id"] in caminho:
                continue
            if f["paiId"] in caminho:
                c = (caminho[f["paiId"]] + "/" if caminho[f["paiId"]] else "") + f["nome"]
                caminho[f["id"]] = c
                base["pastas"].append({"id": f["id"], "caminho": c, "n": f.get("n")})
                novas_pastas.append(c)
            else:
                resto.append(f)
        pend = resto
    ids = {d["id"] for d in base["docs"]}
    novos, sem_pasta = [], []
    for d in res.get("novos", []):
        if d["id"] in ids:
            continue
        if d["pastaId"] not in caminho:
            sem_pasta.append(d["titulo"]); continue
        reg = {k: d.get(k) for k in ("id", "titulo", "descricao", "arquivo", "ext", "url", "bytes", "criado", "modificado", "kw", "cat")}
        reg["pasta"] = caminho[d["pastaId"]]
        base["docs"].append(reg); ids.add(d["id"]); novos.append(reg)
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if novos or novas_pastas:
        base["coletado_em"] = agora
    base["n_docs"], base["n_pastas"] = len(base["docs"]), len(base["pastas"])
    base.setdefault("incrementos", []).append({"em": agora, "novos": len(novos), "pastas_novas": novas_pastas,
                                               "bloqueado": res.get("bloqueado"), "incompletas": res.get("paginas_incompletas", [])})
    return {"novos": [{"pasta": d["pasta"], "titulo": d["titulo"], "criado": d["criado"]} for d in novos],
            "pastas_novas": novas_pastas, "sem_pasta": sem_pasta, "bloqueado": res.get("bloqueado"),
            "paginas_incompletas": res.get("paginas_incompletas", []), "n_docs": base["n_docs"]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("alvos"); a.add_argument("--base", default=BASE); a.add_argument("--hoje")
    b = sub.add_parser("incorpora"); b.add_argument("resultado"); b.add_argument("--base", default=BASE)
    b.add_argument("--simular", action="store_true", help="não grava a base")
    x = ap.parse_args()
    base = carrega(x.base)
    if x.cmd == "alvos":
        hoje = dt.date.fromisoformat(x.hoje) if x.hoje else dt.date.today()
        json.dump(alvos(base, hoje), sys.stdout, ensure_ascii=False)
    else:
        resumo = incorpora(base, carrega(x.resultado))
        if not x.simular:
            with open(x.base, "w", encoding="utf-8") as f:
                json.dump(base, f, ensure_ascii=False)
        json.dump(resumo, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
