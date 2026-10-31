"""Atualização incremental da base do portal (seção Legislação do TRT-17) usada pelo painel de atos normativos.

Dois comandos, usados pela rotina de sábado (rotinas/atualizacao_atos_normativos.md):

  python incorpora_coleta_site.py alvos [--base B] [--hoje AAAA-MM-DD]
      Imprime o JSON de alvos para rotinas/coletor_semanal.js: pastas-mãe (para descobrir pastas novas),
      pastas cujos documentos serão listados (ano corrente + seções/unidades sem subpastas por ano),
      ids de documentos já conhecidos nessas pastas e ids de todas as pastas conhecidas.
      Inclui também pastas de ANOS ANTERIORES ("antigas"), por dois gatilhos (ver ACOMP):
        - pendência: um ato novo altera/revoga um ato antigo -> a pasta do original é revista toda semana até
          aparecer o compilado/consolidado/marcação de revogada, ou por até 365 dias;
        - rodízio: RODIZIO pastas antigas por semana, priorizando as que mais recebem documentos tardios e as
          visitadas há mais tempo.

  python incorpora_coleta_site.py incorpora resultado.json [--base B]
      Junta à base os documentos novos devolvidos pelo coletor; grava a base e imprime um resumo JSON
      (novos documentos, pastas novas, pendências). Não altera documentos já existentes.
      resultado.json pode trazer "visitadas": [ids de pastas abertas] (o rodízio usa a data da visita).

  python incorpora_coleta_site.py pendencias [--hoje AAAA-MM-DD]
      Recalcula as pendências a partir da base inteira (útil após coleta completa) e imprime o estado.
"""
import argparse
import datetime as dt
import json
import re
import sys

BASE = "fontes/atos_normativos/legislacao_trt17_site.json"
ACOMP = "fontes/atos_normativos/acompanhamento_pastas_antigas.json"
RODIZIO = 3            # pastas antigas "ativas" (já receberam documento tardio desde 2026) por semana no rodízio
RODIZIO_QUIETAS = 1    # e pastas antigas sem histórico de documento tardio
MAX_PEND = 6           # teto de pastas pendentes por semana (as menos visitadas e de pendência mais recente primeiro)
PRAZO_PEND = 365       # dias que uma pendência fica aberta sem compilado
RAIZ = 1015014
ANO = re.compile(r"^(19|20)\d\d$")


def carrega(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


# ---------- pastas de anos anteriores: pendências por alteração + rodízio ----------
TIPOS = [("RA", r"resolu[çc][ãa]o\s+administrativa|\bRA\b"), ("ATO", r"\bato\b"), ("PORTARIA", r"portaria"),
         ("PROVIMENTO", r"provimento"), ("IN", r"instru[çc][ãa]o\s+normativa"), ("OS", r"ordem\s+de\s+servi[çc]o"),
         ("RECOMENDACAO", r"recomenda[çc][ãa]o")]
GATILHO = re.compile(r"\b(alter|acrescent|revog|d[áa] nova reda|republica|modific|inclui)", re.I)
REF = re.compile(r"(resolu[çc][ãa]o\s+administrativa|\bRA\b|\bato\b|portaria|provimento|instru[çc][ãa]o\s+normativa|"
                 r"ordem\s+de\s+servi[çc]o|recomenda[çc][ãa]o)(?:[^\d]|17\s*\.?\s*[ªa°º]){0,60}?(?<!\d)0*(\d{1,4})\s*[-/.]\s*((?:19|20)\d\d)(?!\d)", re.I)
MARCA = re.compile(r"compilad|consolidad|atualizad|revogad|republica", re.I)


UNIDADES = [("Gestão de Pessoas", r"\b(SGP|COGEP|SEGEP)\b"), ("Diretoria-Geral", r"\bDIGER\b"), ("Administração", r"\bSEADM\b"),
            ("Corregedoria", r"\b(SECOR|CORREG\w*)\b"), ("Escola Judicial", r"\bEJUD\b"), ("Conciliação", r"\bNUPEMEC|CEJUSC\b")]


def unidades_de(txt):
    """Unidades (nome da pasta de Atos/Portarias) citadas no trecho; PRESI sozinho = Presidência."""
    u = {nome for nome, rx in UNIDADES if re.search(rx, txt, re.I)}
    if not u and re.search(r"\bPRESI", txt, re.I):
        u = {"Presidência"}
    return u


def tipo_de(txt):
    for t, rx in TIPOS:
        if re.search(rx, txt, re.I):
            return t
    return None


def ano_pasta(caminho):
    m = re.search(r"/((?:19|20)\d\d)$", caminho)
    return int(m.group(1)) if m else None


def num_ano(titulo):
    m = REF.search(titulo)
    return (tipo_de(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (None, None, None)


def refs_alteradas(d):
    """Atos mais antigos citados como alterados/revogados por d: [(tipo, numero, ano)]."""
    txt = (d.get("titulo") or "") + " | " + (d.get("descricao") or "")
    if not GATILHO.search(txt):
        return []
    _, n0, a0 = num_ano(d.get("titulo") or "")
    out = []
    for m in REF.finditer(txt):
        t, n, a = tipo_de(m.group(1)), int(m.group(2)), int(m.group(3))
        if (n, a) != (n0, a0) and (t, n, a) not in [o[:3] for o in out]:
            out.append((t, n, a, frozenset(unidades_de(m.group(0)))))
    return out


def indice_originais(base):
    """(tipo, numero, ano) -> pastas de anos anteriores onde o ato aparece."""
    idx = {}
    for d in base["docs"]:
        if ano_pasta(d["pasta"]) is None:
            continue
        t, n, a = num_ano(d["titulo"])
        if n is not None and a == ano_pasta(d["pasta"]):
            idx.setdefault((t, n, a), set()).add(d["pasta"])
    return idx


def calcula_pendencias(base, hoje, acomp=None):
    """Recalcula as pendências a partir da base inteira. Mantém as já resolvidas fora."""
    idx = indice_originais(base)
    marcados = {}                                     # (tipo, n, ano) -> [datas de compilados/revogadas]
    for d in base["docs"]:
        if MARCA.search(d["titulo"]):
            t, n, a = num_ano(d["titulo"])
            marcados.setdefault((t, n, a), []).append((d.get("criado") or "")[:10])
    pend = []
    limite = (hoje - dt.timedelta(days=PRAZO_PEND)).isoformat()
    for d in base["docs"]:
        desde = (d.get("criado") or "")[:10]
        if desde < limite:
            continue
        for t, n, a, unid in refs_alteradas(d):
            ref = (t, n, a)
            if a >= hoje.year and ano_pasta(d["pasta"]) in (None, hoje.year):
                continue                              # alterado do próprio ano: pasta já está no alvo
            pastas = sorted(p for p in idx.get(ref, ()) if ano_pasta(p) and ano_pasta(p) < hoje.year)
            if unid and t in ("ATO", "PORTARIA"):
                filtradas = [p for p in pastas if any("/" + u + "/" in p for u in unid)]
                pastas = filtradas or pastas
            if not pastas:
                continue
            if any(x >= desde for x in marcados.get(ref, [])):
                continue                              # compilado/marcação já publicado depois da alteração
            pend.append({"ref": f"{t} {n}/{a}", "pastas": pastas, "por": d["titulo"][:120], "por_id": d["id"],
                         "desde": desde, "ate": (dt.date.fromisoformat(desde) + dt.timedelta(days=PRAZO_PEND)).isoformat()})
    pend.sort(key=lambda p: p["desde"])
    return pend


def prioridade_rodizio(base, hoje):
    """Pastas de anos anteriores ordenadas por atividade tardia nos últimos 2 anos (docs criados depois do ano da pasta)."""
    corte = (hoje - dt.timedelta(days=730)).isoformat()
    cont = {}
    for p in base["pastas"]:
        a = ano_pasta(p["caminho"])
        if a and a < hoje.year:
            cont[p["caminho"]] = 0
    for d in base["docs"]:
        a = ano_pasta(d["pasta"]); c = (d.get("criado") or "")[:10]
        # ignora a carga inicial do portal (2025) em pastas antigas: só conta o que entrou de 2026 em diante
        if a and d["pasta"] in cont and c >= max(corte, "2026-01-01") and int(c[:4]) > a:
            cont[d["pasta"]] += 1
    return cont


def carrega_acomp(caminho=ACOMP):
    try:
        return carrega(caminho)
    except FileNotFoundError:
        return {"pendencias": [], "visitas": {}}


def escolhe_antigas(base, acomp, hoje, ja):
    por_caminho = {p["caminho"]: p["id"] for p in base["pastas"]}
    vis = acomp.get("visitas", {})
    cand = {}
    for pe in acomp.get("pendencias", []):
        if pe["ate"] < hoje.isoformat():
            continue
        for c in pe["pastas"]:
            if c in por_caminho and por_caminho[c] not in ja:
                x = cand.setdefault(c, {"caminho": c, "motivo": [], "recente": ""})
                x["motivo"].append(f"pendência: {pe['ref']} alterado por {pe['por'][:60]} ({pe['desde']})")
                x["recente"] = max(x["recente"], pe["desde"])
    ordem = sorted(cand, key=lambda c: (vis.get(c, "0000"), [-ord(ch) for ch in cand[c]["recente"]]))
    out = {}
    for c in ordem[:MAX_PEND]:
        x = cand[c]; x.pop("recente")
        out[por_caminho[c]] = x
    cont = prioridade_rodizio(base, hoje)
    livres = [c for c in cont if por_caminho.get(c) not in ja and por_caminho.get(c) not in out]
    chave = lambda c: (vis.get(c, "0000"), -cont[c], c)
    escolhidas = sorted((c for c in livres if cont[c] > 0), key=chave)[:RODIZIO] + \
        sorted((c for c in livres if cont[c] == 0), key=chave)[:RODIZIO_QUIETAS]
    for c in escolhidas:
        out[por_caminho[c]] = {"caminho": c, "motivo": [f"rodízio (última visita: {vis.get(c, 'nunca')}; "
                                                         f"{cont[c]} docs tardios desde 2026)"]}
    return out


def alvos(base, hoje, acomp=None):
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
    antigas = escolhe_antigas(base, acomp or carrega_acomp(), hoje, alvo_docs)
    alvo_docs |= set(antigas)
    conhecidos = [d["id"] for d in base["docs"] if any(por_id.get(i, {}).get("caminho") == d["pasta"] for i in alvo_docs)]
    return {"url": "https://www.trt17.jus.br/web/legislacao", "maes": sorted(set(maes)), "docs": sorted(alvo_docs),
            "conhecidos": conhecidos, "pastas_conhecidas": sorted(por_id),
            "antigas": [{"id": i, **v} for i, v in antigas.items()],
            "_rotulos": {str(i): por_id[i]["caminho"] for i in sorted(set(maes) | alvo_docs)}}


def atualiza_acomp(base, res, acomp, hoje):
    caminho = {p["id"]: p["caminho"] for p in base["pastas"]}
    for i in res.get("visitadas", []):
        if i in caminho and ano_pasta(caminho[i]):
            acomp.setdefault("visitas", {})[caminho[i]] = hoje.isoformat()
    antes = {(p["ref"], p["por_id"]) for p in acomp.get("pendencias", [])}
    acomp["pendencias"] = calcula_pendencias(base, hoje)
    depois = {(p["ref"], p["por_id"]) for p in acomp["pendencias"]}
    acomp["atualizado_em"] = hoje.isoformat()
    return {"pendencias_novas": sorted(r for r, _ in depois - antes), "pendencias_resolvidas": sorted(r for r, _ in antes - depois),
            "pendencias_abertas": len(depois)}


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
    b.add_argument("--hoje")
    c = sub.add_parser("pendencias"); c.add_argument("--base", default=BASE); c.add_argument("--hoje")
    x = ap.parse_args()
    base = carrega(x.base)
    hoje = dt.date.fromisoformat(x.hoje) if x.hoje else dt.date.today()
    acomp = carrega_acomp()
    if x.cmd == "alvos":
        json.dump(alvos(base, hoje, acomp), sys.stdout, ensure_ascii=False)
        return
    if x.cmd == "pendencias":
        resumo = atualiza_acomp(base, {}, acomp, hoje)
    else:
        resumo = incorpora(base, carrega(x.resultado))
        resumo.update(atualiza_acomp(base, carrega(x.resultado), acomp, hoje))
        if not x.simular:
            with open(x.base, "w", encoding="utf-8") as f:
                json.dump(base, f, ensure_ascii=False)
    if not getattr(x, "simular", False):
        with open(ACOMP, "w", encoding="utf-8") as f:
            json.dump(acomp, f, ensure_ascii=False, indent=1)
    json.dump(resumo, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
