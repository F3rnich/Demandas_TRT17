# -*- coding: utf-8 -*-
"""
ler_vagos.py — le os PDFs de "Cargos efetivos vagos" do portal de transparencia
do TRT-17 e devolve o denominador real do art. 6 da Res. CSJT 296/2021.

Por que existe: a base de pessoal so traz postos OCUPADOS. O art. 6 poe teto de
80% sobre (CJ + FC) / cargos efetivos AUTORIZADOS, que incluem os vagos. Sem
estes PDFs o painel 12 usa um proxy que superestima a razao e nao emite veredito.

Tres layouts convivem no acervo:
  1. duas colunas  (Cargo/Area/Especialidade | Quantitativo)          — 37 arquivos
  2. tres colunas  (+ "Dependentes de autorizacao para provimento")   —  7 (04-10/2025)
     Nestes o Quantitativo e a coluna do MEIO, nao o ultimo numero da linha.
  3. com "TOTAL :" impresso e nota de rodape de cargo em extincao     — 17

CARGO EM EXTINCAO: o Auxiliar Judiciario - Administrativa - Apoio de Servicos
Diversos esta em extincao (Res. CSJT 47/2008: "a medida que ficarem vagos, nao
deverao ser providos"). O TOTAL impresso pelo proprio tribunal exclui essas
vagas, e nos as excluimos tambem — inclusive nos 37 arquivos antigos que nao
trazem TOTAL, para a serie nao ganhar um degrau artificial em 04/2025.
Decisao de Leo em 01/09/2026.

TRAVA: nos arquivos com TOTAL impresso, o total calculado tem de bater
exatamente. Divergencia fora da lista DIVERGENCIA_NA_ORIGEM aborta — e o jeito
de nunca engolir em silencio um erro de parser.
"""
import re, subprocess, sys
from pathlib import Path

PASTA = Path("cargos_vagos")
EXTINCAO = re.compile(r"Auxiliar\s+Judici[áa]rio", re.I)
DATA = re.compile(r"Posi[çc][ãa]o\s+referente\s+ao\s+dia\s+(\d{2})[./-](\d{2})[./-](\d{4})", re.I)
TOTAL = re.compile(r"TOTAL\s*:\s*(\d+)", re.I)
# Divergencias CONHECIDAS entre o TOTAL impresso e a soma da propria coluna do
# documento — conferidas a mao, sao erro da ORIGEM e nao do parser. Prevalece a
# soma da coluna, que e auditavel linha a linha. Qualquer divergencia fora desta
# lista aborta.
DIVERGENCIA_NA_ORIGEM = {
    # A coluna Quantitativo soma 31 (fora o cargo em extincao), mas o TOTAL
    # impresso diz 30. A coluna vizinha "Dependentes de autorizacao" fecha em 27
    # com a leitura do mesmo parser, o que confirma que a extracao esta certa.
    "Cargos efetivos vagos - 01.10.2025.pdf": (30, 31),
}

L2 = re.compile(r"^(?P<d>\S.*?)\s{2,}(?P<q>\d+)\s*$")
L3 = re.compile(r"^(?P<d>\S.*?)\s{2,}(?P<q>\d+)\s{2,}(?P<a>[\d\-–—]+)\s*$")
LIXO = ("Quantitativo", "CARGOS EFETIVOS VAGOS", "Cargos efetivos vagos",
        "Cargo/", "Dependentes de", "autoriza", "provimento", "TOTAL", "extin")


def _texto(p):
    r = subprocess.run(["pdftotext", "-layout", str(p), "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ERRO: pdftotext falhou em %s: %s" % (p.name, r.stderr[:200]))
    return r.stdout


def _linhas(txt):
    tres = ("Dependentes de" in txt) or ("autorização para" in txt)
    out = []
    for l in txt.splitlines():
        l = l.rstrip()
        if not l.strip() or l.lstrip().startswith("*"):
            continue
        if any(k in l for k in LIXO):
            continue
        m = (L3.match(l) if tres else None) or L2.match(l)
        if not m:
            continue
        d = " ".join(m.group("d").split()).strip(" .-–—")
        if len(d) < 10 or not re.search(r"[A-Za-zÀ-ÿ]", d):
            continue          # marcador de nota de rodape solto
        out.append((d, int(m.group("q"))))
    return out, tres


def ler(pasta=PASTA, verboso=False):
    pasta = Path(pasta)
    if not pasta.is_dir():
        sys.exit("ERRO: pasta %s nao existe (ver LEIA-ME.md)." % pasta)
    reg = {}
    for p in sorted(pasta.glob("*.pdf")):
        txt = _texto(p)
        m = DATA.search(" ".join(txt.split()))
        if not m:
            sys.exit("ERRO: %s nao traz o rodape 'Posicao referente ao dia'." % p.name)
        data = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
        ref = data[:7]
        linhas, tres = _linhas(txt)
        if not linhas:
            sys.exit("ERRO: nenhuma linha extraida de %s." % p.name)
        uteis = [(d, q) for d, q in linhas if not EXTINCAO.search(d)]
        vagos = sum(q for _, q in uteis)
        mt = TOTAL.search(txt)
        divergente = False
        if mt and int(mt.group(1)) != vagos:
            esperado = DIVERGENCIA_NA_ORIGEM.get(p.name)
            if esperado != (int(mt.group(1)), vagos):
                sys.exit("ERRO: %s — TOTAL impresso %s, soma da coluna %d.\n"
                         "  Se a soma estiver certa e o documento errado, registre o par\n"
                         "  em DIVERGENCIA_NA_ORIGEM apos conferir a mao. Nao uso este acervo."
                         % (p.name, mt.group(1), vagos))
            divergente = True
            if verboso:
                print("  [aviso] %s: TOTAL impresso %d, soma da coluna %d — "
                      "erro conhecido da origem, prevalece a soma"
                      % (p.name, int(mt.group(1)), vagos))
        ent = {"arquivo": p.name, "data": data, "dia": int(m.group(1)), "colunas": 3 if tres else 2,
               "vagos": vagos, "bruto": sum(q for _, q in linhas), "n_linhas": len(linhas),
               "total_impresso": int(mt.group(1)) if mt else None,
               "retificado": bool(re.search(r"retific", p.name, re.I)),
               "divergente_na_origem": divergente}
        if ref in reg:
            v = reg[ref]
            fica = ent if (ent["retificado"] and not v["retificado"]) or \
                          (not v["retificado"] and ent["dia"] < v["dia"]) else v
            if verboso:
                print("  [aviso] duas fotos para %s (dias %d e %d) — uso a do dia %d"
                      % (ref, v["dia"], ent["dia"], fica["dia"]))
            reg[ref] = fica
        else:
            reg[ref] = ent
    return reg


if __name__ == "__main__":
    reg = ler(verboso=True)
    conf = sum(1 for v in reg.values() if v["total_impresso"] is not None)
    print("%d referencia(s) · %s a %s" % (len(reg), min(reg), max(reg)))
    print("%d com TOTAL impresso — todos conferidos contra o calculado" % conf)
    print("%d em layout de 3 colunas" % sum(1 for v in reg.values() if v["colunas"] == 3))
    print()
    print("ref      vagos  bruto   ref      vagos  bruto   ref      vagos  bruto")
    ks = sorted(reg)
    for i in range(0, len(ks), 3):
        print("  ".join("%s  %4d  %5d   " % (k, reg[k]["vagos"], reg[k]["bruto"]) for k in ks[i:i+3]))
    falt = sorted({"%d-%02d" % (a, m) for a in range(2022, 2027) for m in range(1, 13)
                   if min(ks) <= "%d-%02d" % (a, m) <= max(ks)} - set(ks))
    print("\nmeses sem arquivo: %s" % (", ".join(falt) or "nenhum"))
