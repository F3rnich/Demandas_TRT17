#!/usr/bin/env python3
"""
build_atos_normativos.py — gera dados_atos_normativos.json a partir do PDF
"ATOS NORMATIVOS DO TRT DA 17ª REGIÃO" (compilação cronológica publicada pelo Tribunal).

Uso:
    pip install pdfplumber
    python build_atos_normativos.py "ATOS_NORMATIVOS_DO_TRT17_-_Atualizado_até_DD-MM-AAAA.pdf"
    python deploy.py "Atos normativos: atualização até DD/MM/AAAA" dados_atos_normativos.json

Como o PDF é lido:
  - Cada ato começa numa linha cujo primeiro caractere está em NEGRITO (cabeçalho).
    O cabeçalho continua enquanto os parênteses estiverem abertos.
  - Depois do cabeçalho: ementa (texto corrido) e notas (blocos entre parênteses,
    ex.: "(revogado pela ...)", "(alterado pelo ...)", "(normas correlatas: ...)").
  - Status é inferido das notas e, de forma complementar, das ementas de atos
    posteriores ("Revoga a Resolução Administrativa nº X"). Cada inferência guarda
    a origem, exibida no painel.
  - Citações a outros atos (nas notas e na ementa) são casadas com o índice por
    (família do tipo, número, ano) e desempatadas pela data de publicação citada
    e pela unidade emissora. O painel mostra a taxa de casamento.

Dados: o PDF é documento público (atos publicados no B.I./D.O./DEJT). Nada além
do conteúdo do próprio PDF entra no JSON.
"""
import sys, re, json, unicodedata, datetime, collections, os

try:
    import pdfplumber
except ImportError:
    sys.exit("Instale a dependência:  pip install pdfplumber")

SAIDA = "dados_atos_normativos.json"
SCHEMA = 1

# ---------------------------------------------------------------- utilidades
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm(s):
    return re.sub(r"\s+", " ", sem_acento(s).lower()).strip()

def ano4(a):
    a = int(a)
    if a < 100:
        a += 1900 if a >= 50 else 2000
    return a

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7,
         "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}

def primeira_data(s):
    """Primeira data dd/mm/aa(aa) ou mês/aa do texto -> 'AAAA-MM-DD' ou 'AAAA-MM'."""
    m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4}|\d{2})(?!\d)", s)
    if m:
        d, mo, a = int(m.group(1)), int(m.group(2)), ano4(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{a:04d}-{mo:02d}-{d:02d}"
    m = re.search(r"(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*(?:de\s*)?/?\s*(\d{2,4})", s, re.I)
    if m:
        return f"{ano4(m.group(2)):04d}-{MESES[norm(m.group(1))]:02d}"
    return None

# ---------------------------------------------------------------- tipos
# (rótulo exibido, regex sobre o cabeçalho normalizado, família p/ casamento de citações)
TIPOS = [
    ("Ato Conjunto",               r"^ato conjunto",                         "ATOCONJ"),
    ("Ato",                        r"^(atos?\b|a trt)",                     "ATO"),
    ("Resolução Administrativa",   r"^resolucao administrativa",             "RA"),
    ("Resolução",                  r"^resolucao",                            "RES"),
    ("Emenda Regimental",          r"^emenda regimental",                    "ER"),
    ("Portaria Conjunta",          r"^portaria conjunta",                    "PORTCONJ"),
    ("Portaria",                   r"^portaria",                             "PORT"),
    ("Provimento",                 r"^provimento",                           "PROV"),
    ("Instrução Normativa",        r"^instrucao normativa",                  "IN"),
    ("Ordem de Serviço",           r"^ordem de servico",                     "OS"),
    ("Recomendação",               r"^recomendac",                           "REC"),
    ("Nota Técnica",               r"^nota tecnica",                         "NT"),
    ("Edital",                     r"^edital",                               "EDITAL"),
    ("Despacho",                   r"^de?s?pacho",                          "DESP"),
    ("Acórdão",                    r"^acordao",                              "ACORD"),
    ("Comunicado",                 r"^comunicad",                            "COM"),
    ("Aviso",                      r"^aviso",                                "AVISO"),
    ("Termo",                      r"^termo",                                "TERMO"),
    ("Regimento / Regulamento",    r"^(regimento|regulamento)",              "REG"),
    ("Instrução de Serviço",       r"^instrucao de servico",                 "IS"),
    ("Apostila",                   r"^apostila",                             "APOST"),
    ("Ata",                        r"^ata\b",                               "ATA"),
    ("Extrato",                    r"^extrato",                              "EXTR"),
    ("Decisão administrativa",     r"^(decisao administrativa|pa n|sessao administrativa)", "DEC"),
    ("Escala / Lista / Resultado", r"^(escala|lista|resultado|homologacao)", "LISTA"),
    ("Precedentes",                r"^precedentes",                          "PREC"),
]

def classifica(cab):
    n = norm(cab)
    for rot, rx, fam in TIPOS:
        if re.search(rx, n):
            return rot, fam
    return "Outros", "OUTROS"

# palavras que, numa citação, indicam a família do ato citado
FAM_CITACAO = [
    (r"atos? conjuntos?", "ATOCONJ"),
    (r"resolu[cç](?:ao|oes|ões|ão) administrativas?|\bRA\b|resolu[cç](?:ao|ão) adm", "RA"),
    (r"emendas? regimenta(?:l|is)", "ER"),
    (r"portarias? conjuntas?", "PORTCONJ"),
    (r"portarias?", "PORT"),
    (r"provimentos?", "PROV"),
    (r"instru[cç](?:ao|ão|oes|ões) normativas?", "IN"),
    (r"ordens? de servi[cç]o", "OS"),
    (r"recomenda[cç](?:ao|ão|oes|ões)", "REC"),
    (r"notas? t[eé]cnicas?", "NT"),
    (r"editais|edital", "EDITAL"),
    (r"despachos?", "DESP"),
    (r"resolu[cç](?:ao|ão|oes|ões)", "RES"),
    (r"\batos?\b", "ATO"),
]
RX_FAM = re.compile("|".join(f"(?P<f{i}>{rx})" for i, (rx, _) in enumerate(FAM_CITACAO)), re.I)

# siglas de unidades emissoras (para desempate e filtro)
RX_SIGLA = re.compile(r"\b([A-Z]{2,}(?:\.[A-Z]{2,})*)\b")
SIGLAS_IGNORAR = {"TRT", "DEJT", "DO", "BI", "ES", "CNJ", "CSJT", "TST", "N", "NO", "NS", "ATO", "ATOS",
                  "NÚMERO", "DE", "DA", "DO", "ATOS", "EDITAL", "RA", "OAB", "PJE", "CPC", "CLT"}

def siglas(s):
    out = []
    if re.search(r"O\.?\s*C\.?\s*M\.?\s*J\.?\s*T", s): out.append("OCMJT")   # Ordem Capixaba do Mérito Judiciário do Trabalho
    for m in RX_SIGLA.finditer(s.replace("/", " ").replace("-", " ")):
        t = m.group(1)
        if t in SIGLAS_IGNORAR or len(t) > 12:
            continue
        for p in t.split("."):
            if p not in SIGLAS_IGNORAR and p not in out:
                out.append(p)
    return out

RX_NUM = re.compile(r"(?:n\s*[º°o]\.?\s*s?|n\.\s*[º°o]\.?\s*s?|N\s*[º°o]\.?\s*s?|N\.\s*[º°o]\.?\s*s?|n[º°]s|n\.ºs)?\s*(\d{1,4})\s*/\s*(\d{4}|\d{2})(?!\d|\s*/\s*\d)")

def numero_ano(cab):
    """Número e ano do ato a partir do trecho do cabeçalho antes dos parênteses."""
    base = cab.split("(")[0]
    m = re.search(r"n\s*\.?\s*[º°o]\.?\s*s?\s*\.?\s*(\d{1,4})\s*/\s*(\d{2,4})", base, re.I)
    if not m:
        m = re.search(r"(\d{1,4})\s*/\s*(\d{4}|\d{2})\b", base)
    if not m:
        return None, None
    return int(m.group(1)), ano4(m.group(2))

# ---------------------------------------------------------------- leitura do PDF
def linhas_pdf(caminho):
    with pdfplumber.open(caminho) as pdf:
        for pn, page in enumerate(pdf.pages, 1):
            altura = page.height
            for l in page.extract_text_lines(keep_blank_chars=False):
                txt = l["text"].strip()
                if not txt:
                    continue
                # número de página no rodapé
                if re.fullmatch(r"\d{1,3}", txt) and l["top"] > altura - 125:
                    continue
                chars = [c for c in l["chars"] if c["text"].strip()]
                negrito = bool(chars) and "Bold" in chars[0]["fontname"]
                yield pn, txt, negrito

def balanco(s):
    return s.count("(") - s.count(")")

def separa_blocos(resto):
    """Divide ementa/notas. Notas = blocos iniciados por '(' no início de linha
    (ou 'Revogado/Alterado...' solto, erro de digitação recorrente no PDF)."""
    ementa, notas, atual, prof = [], [], None, 0
    for ln in resto:
        inicio_nota = ln.startswith("(") or re.match(r"^(revogad|alterad|suprimid|cessad|retificad|republicad)", norm(ln))
        if atual is None and inicio_nota:
            atual, prof = [ln], balanco(ln)
            if prof <= 0:
                notas.append(" ".join(atual)); atual = None
            continue
        if atual is not None:
            atual.append(ln); prof += balanco(ln)
            if prof <= 0:
                notas.append(" ".join(atual)); atual = None
            continue
        if notas:  # texto corrido depois de nota: anexa à última nota (continuação)
            notas[-1] += " " + ln
        else:
            ementa.append(ln)
    if atual:
        notas.append(" ".join(atual))
    junta = lambda xs: re.sub(r"\s+", " ", re.sub(r"-\s+(?=[a-zà-ú])", "-", " ".join(xs))).strip()
    return junta(ementa), [re.sub(r"\s+", " ", n).strip() for n in notas]

NAO_CABECALHO = re.compile(r"^(\(|[A-ZÇÃÕÁÉÍÓÚ]{2,}(?:[ .][A-ZÇÃÕÁÉÍÓÚ]{2,})*$|(PRESI|SGP|SECOR|SEADM|DIGER)\b)")

def extrai_atos(caminho):
    """Agrupa linhas em atos. Cabeçalho = linha(s) iniciada(s) em negrito."""
    atos, cur, atualizado = [], None, None
    for pn, txt, negrito in linhas_pdf(caminho):
        if atualizado is None:
            m = re.search(r"atualizado at[eé]\s*(\d{2}/\d{2}/\d{4})", txt)
            if m:
                atualizado = m.group(1); continue
            if "ATOS NORMATIVOS DO TRT" in txt:
                continue
        if negrito:
            cab_atual = " ".join(cur["cab"]) if cur else ""
            fragmento = re.match(r"^(PRESI|SGP|SECOR|SEADM|DIGER)\b", txt) or txt[:1].islower()
            if cur is not None and (fragmento or (NAO_CABECALHO.match(txt) and not RX_NUM_CAB.search(txt.split("(")[0]) and not txt.startswith("PA "))):
                # fragmento em negrito que não abre ato (linha de tabela, "(TRT14/...)", trecho de nota)
                (cur["cab"] if not cur["resto"] and txt.startswith("(") else cur["resto"]).append(txt)
                continue
            if cur is not None and not cur["resto"] and "(" not in cab_atual and len(cur["cab"]) < 3:
                cur["cab"].append(txt)      # título longo em várias linhas
                continue
            if cur: atos.append(cur)
            cur = {"cab": [txt], "resto": [], "pg": pn}
            continue
        if cur is not None:
            cur["resto"].append(txt)
    if cur: atos.append(cur)
    # cabeçalho com parêntese aberto: puxa até 3 linhas seguintes SE elas o fecharem
    for a in atos:
        cab = " ".join(a["cab"])
        if balanco(cab) > 0 and a["resto"]:
            acc = cab
            for k in range(min(3, len(a["resto"]))):
                acc += " " + a["resto"][k]
                if balanco(acc) <= 0:
                    cab = acc; a["resto"] = a["resto"][k + 1:]; break
        a["cab"] = cab
    return atos, atualizado

RX_NUM_CAB = re.compile(r"n\s*\.?\s*[º°o]\.?\s*s?\s*\.?\s*\d{1,4}\s*/\s*\d{2,4}", re.I)

# ---------------------------------------------------------------- status
RX_REVOG = re.compile(r"revogad|suprimid|tornad[oa]s? sem efeito|sem efeito|cessad[oa]s? os? efeitos|cessa[cç][aã]o dos efeitos|cancelad|anulad|extint|insubsistente|exaurid", re.I)
RX_PARCIAL = re.compile(r"parcialmente|revogad[oa]s?\s+(?:o|os|a|as)?\s*(?:art|inc|§|par[aá]g|al[ií]nea|item|cap[ií]tulo|anexo)", re.I)
RX_ALTER = re.compile(r"alterad|altera[cç]|rerratificad|retificad|acrescid|complementad|modificad|revogad[oa]s? parcialmente|nova reda[cç]|atualizad|prorrogad|republicad", re.I)

def rel_da_nota(n):
    """Rótulo curto da relação expressa pela nota."""
    orig = re.sub(r"\s+", " ", n.strip("() "))
    t = norm(orig)
    m = re.match(r"([a-z\s,]+?)(?:\s+pel[oa]s?|\s+por|\s+atraves|\s*:|\s+em\s+\d|\s+a partir)", t)
    rot = (m.group(1) if m else " ".join(t.split()[:3])).strip(" ,")
    rot = rot[:40]
    # devolve com acentos (norm preserva o comprimento quando o espaçamento já é simples)
    return orig[:len(rot)].lower() if len(t) == len(orig) else rot

def status_por_notas(notas):
    rev = alt = False
    for n in notas:
        r = rel_da_nota(n)
        if r.startswith("normas correlatas") or r.startswith("norma correlata"):
            continue
        if RX_REVOG.search(r) or (RX_REVOG.search(n[:60]) and not RX_PARCIAL.search(n[:90])):
            if RX_PARCIAL.search(n[:90]):
                alt = True
            else:
                rev = True
        elif RX_ALTER.search(r) or RX_ALTER.search(n[:50]):
            alt = True
    return rev, alt

# ---------------------------------------------------------------- citações
RX_EXTERNO = re.compile(r"\b(CNJ|CSJT|TST|CJF|STF|STJ|TCU|Lei|Decreto|Conselho|Supremo|Superior|Receita|Minist[eé]rio|Corregedoria-Geral|Constitui[cç][aã]o|Emenda Constitucional|Medida Provis[oó]ria|TRT\s*(da\s*)?(?!17)\d{1,2}ª)")
RX_DATA_CIT = re.compile(r"(\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4})")

def citacoes(texto):
    """Lista de (familia, numero, ano, data_publicacao, siglas, inicio, fim).
    A família vale para todas as numerações seguintes até aparecer outra palavra de tipo."""
    out = []
    fam_pos = [(m.start(), FAM_CITACAO[int(next(k for k, v in m.groupdict().items() if v)[1:])][1]) for m in RX_FAM.finditer(texto)]
    for m in re.finditer(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{4}|\d{2})(?![\d])(?!\s*/\s*\d)", texto):
        ini = m.start()
        if 1950 <= int(m.group(1)) <= 2100 and len(m.group(2)) == 4:
            continue   # "biênio 2001/2003", "2015/2020": período, não número de ato
        if not 1991 <= ano4(m.group(2)) <= datetime.date.today().year:
            continue   # TRT-17 instalado em 1991; ano fora disso é erro de digitação na fonte
        # descarta datas (dd/mm/aaaa já filtrado pelo lookahead) e "nº 01/91" de B.I.
        antes = texto[max(0, ini - 22):ini]
        # número logo após "B.I./D.O." sem data no meio = número do boletim, não do ato
        # (após "DEJT dd/mm/aaaa e" o número seguinte é outro ato da enumeração)
        if re.search(r"(B\.\s*I\.|D\.\s*O\.|Boletim)[^,;)]*$", antes, re.I) and not RX_FAM.search(antes) \
                and not re.search(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{2,4}|/\d{2}\s*(e|,)\s*$", antes):
            continue
        if re.search(r"\d{1,2}\s*/\s*$", antes):
            continue
        fams = [f for p, f in fam_pos if p < ini]
        if not fams:
            continue
        # a palavra de tipo precisa estar razoavelmente perto (mesma enumeração)
        p_ult = max(p for p, f in fam_pos if p < ini)
        trecho = texto[p_ult:ini]
        if len(trecho) > 260 or re.search(r"\)\s*\(", trecho):
            continue
        # ato de outro órgão (CNJ, CSJT, TST, lei, decreto…): fora do escopo da compilação
        if RX_EXTERNO.search(trecho):
            continue
        # se entre a palavra de tipo e o número há "B.I./D.O. nº", ignora (é número do boletim)
        if re.search(r"(B\.\s*I\.|D\.\s*O\.)\s*(TRT\s*17\S*)?\s*n\S*\s*$", antes, re.I):
            continue
        depois = texto[m.end():m.end() + 45]
        dm = RX_DATA_CIT.search(depois)
        dpub = None
        if dm and re.search(r"D\.?\s*O\.?|DEJT|B\.?\s*I\.?|Di[aá]rio", depois[:dm.start()]):
            dpub = primeira_data(dm.group(1))
        elif not dm:
            dm2 = re.search(r"(?:B\.?\s*I\.?[^,;)]*?)(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s*/\s*(\d{2,4})", depois, re.I)
            if dm2:
                dpub = primeira_data(dm2.group(1) + "/" + dm2.group(2))
        sig = siglas(texto[p_ult:ini])
        out.append((fams[-1], int(m.group(1)), ano4(m.group(2)), dpub, sig, ini, m.end()))
    return out

# ---------------------------------------------------------------- atos citados sem verbete
# famílias com numeração única no Tribunal: divergência de data é erro de digitação, não outra série
SERIE_UNICA = {"RA", "RES", "PROV", "ER"}
FEMININO = ("Resolu", "Portaria", "Instru", "Ordem", "Recomenda", "Nota", "Emenda", "Ata", "Apostila", "Decis", "Escala")

FAM_ROT = {"ATO": "Ato", "ATOCONJ": "Ato Conjunto", "RA": "Resolução Administrativa", "RES": "Resolução",
           "ER": "Emenda Regimental", "PORTCONJ": "Portaria Conjunta", "PORT": "Portaria", "PROV": "Provimento",
           "IN": "Instrução Normativa", "OS": "Ordem de Serviço", "REC": "Recomendação", "NT": "Nota Técnica",
           "EDITAL": "Edital", "DESP": "Despacho"}
VERBO_ATIVO = [(r"^rerratificad", "Rerratifica"), (r"^revogad", "Revoga"), (r"^alterad", "Altera"),
               (r"^retificad", "Retifica"), (r"^referendad", "Referenda"), (r"^prorrogad", "Prorroga"),
               (r"^suprimid", "Suprime"), (r"^cessad", "Faz cessar os efeitos de"), (r"^republicad", "Republica"),
               (r"^complementad", "Complementa"), (r"^regulamentad", "Regulamenta"), (r"^suspens", "Suspende")]
EMENTA_PASSIVO = {"revoga": "Revogado por", "altera": "Alterado por", "regulamenta": "Regulamentado por",
                  "referenda": "Referendado por", "prorroga": "Prorrogado por", "republica": "Republicado por",
                  "retifica": "Retificado por", "suspende": "Suspenso por", "torna sem efeito": "Tornado sem efeito por",
                  "faz cessar": "Efeitos cessados por", "substitui": "Substituído por", "complementa": "Complementado por",
                  "acrescenta": "Complementado por", "homologa": "Homologado por"}

def constroi_citados(atos, faltantes):
    """Cria um registro por ato citado que não tem verbete na compilação.
    Chave: (família, número, ano, data citada); citações sem data juntam-se ao único registro datado, se houver."""
    grupos = collections.OrderedDict()
    for f in faltantes:
        cit = atos[f["cit"]]
        if (cit["fam"], cit["num"], cit["anum"]) == (f["fam"], f["num"], f["ano"]) or \
           (f["fam"] in SERIE_UNICA and any(a["fam"] == f["fam"] and a["num"] == f["num"] and a["anum"] == f["ano"] for a in (cit,))):
            continue   # autocitação (republicação, retificação do próprio ato)
        grupos.setdefault((f["fam"], f["num"], f["ano"], f["dpub"]), []).append(f)
    for chave in [k for k in grupos if k[3] is None]:
        irmaos = [k for k in grupos if k[:3] == chave[:3] and k[3] is not None]
        if len(irmaos) == 1:
            grupos[irmaos[0]].extend(grupos.pop(chave))
    citados, prox = [], len(atos)
    for (fam, num, ano, dpub), fs in grupos.items():
        sig = []
        for f in fs:
            for x in f["sig"]:
                if x not in sig: sig.append(x)
        rot = FAM_ROT.get(fam, "Ato")
        nome = f"{rot} {'/'.join(sig) + ' ' if sig else ''}nº {num}/{ano}"
        ementa, ent, vis = [], [], set()
        for f in sorted(fs, key=lambda f: f["cit"]):
            alvo = atos[f["cit"]]
            resumo = alvo["ementa"][:180] + ("…" if len(alvo["ementa"]) > 180 else "")
            if f["de"] == "nota":
                r = norm(f["rel"])
                verbo = next((v for rx, v in VERBO_ATIVO if re.search(rx, r)), None)
                if re.match(r"normas? correlatas?", r):
                    frase = f"Norma correlata de {alvo['nome']}"
                elif verbo:
                    art = "a" if alvo["tipo"].startswith(FEMININO) else "o"
                    frase = f"{verbo} {art} {alvo['nome']}"
                else:
                    frase = f"Citado em nota de {alvo['nome']} ({f['rel']})"
                rel_ent = f["rel"]
            else:
                passivo = EMENTA_PASSIVO.get(f["rel"])
                frase = f"{passivo} {alvo['nome']}" if passivo else f"Citado na ementa de {alvo['nome']}"
                rel_ent = f["rel"] + " (ementa)"
            frase += f" — {resumo}" if resumo else ""
            if frase not in vis:
                vis.add(frase); ementa.append(frase)
            if (rel_ent, f["cit"]) not in {(e["rel"], e["id"]) for e in ent}:
                ent.append({"rel": rel_ent, "id": f["cit"]})
            # liga a citação, no ato que cita, a este registro
            r_ = {"de": f["de"], "rel": f["rel"], "ids": [prox], "q": "citado", "s": f["s"], "e": f["e"], **({"dp": f["dpub"]} if f.get("dpub") else {})}
            if f["de"] == "nota": r_["k"] = f["k"]
            f["ref"].append(r_)
        citados.append({"id": prox, "tipo": rot, "nome": nome, "dpub": dpub,
                        "pub": f"publicação citada: {'/'.join(reversed(dpub.split('-')))}" if dpub else "data de publicação não citada",
                        "ano": int(dpub[:4]) if dpub else ano, "un": sig, "ementa": " · ".join(ementa), "ent": ent})
        prox += 1
    return citados

# ---------------------------------------------------------------- site do TRT-17 (seção Legislação)
SECAO_FAM = {"atos da presidencia": "ATO", "resolucoes administrativas": "RA", "portarias": "PORT",
             "provimentos": "PROV", "editais": "EDITAL", "recomendacoes": "REC", "ordens de servico": "OS",
             "instrucoes normativas": "IN"}
# série (unidade) dos Atos: pasta do site -> sigla canônica; siglas do PDF -> mesma sigla
PASTA_SERIE = {"presidencia": "PRESI", "gestao de pessoas": "SGP", "administracao": "SEADM", "diretoria-geral": "DIGER",
               "corregedoria": "SECOR", "escola judicial": "EJUD", "conciliacao": "NUPEMEC"}
SIGLA_SERIE = {"OCMJT": "OCMJT", "COGEP": "SGP", "SGP": "SGP", "SEGEP": "SGP", "SEREH": "SGP", "SGPE": "SGP", "SEDER": "SGP", "SECOR": "SECOR",
               "SEADM": "SEADM", "SADM": "SEADM", "DIGER": "DIGER", "DG": "DIGER", "EJUD": "EJUD", "EMATRA": "EJUD",
               "NUPEMEC": "NUPEMEC", "CEJUSC": "NUPEMEC"}
URL_SITE = "https://www.trt17.jus.br"

def serie_pdf(a):
    for s_ in a["un"]:
        if s_ in SIGLA_SERIE: return SIGLA_SERIE[s_]
    return "PRESI"

VAZIAS = {"para", "pelo", "pela", "sobre", "dispoe", "tribunal", "regiao", "trabalho", "presidencia", "presidente", "anexo", "republicacao", "retificacao", "retificado", "disponibilizado", "dejt"}

def palavras(t):
    """Radicais (5 letras) das palavras significativas — tolera plural e flexão."""
    return {w[:5] for w in re.findall(r"[a-z]{4,}", norm(t).replace("-", "")) if w not in VAZIAS}

def parse_doc_site(d):
    """-> (fam, num, ano, serie, nome, assunto)"""
    partes = [norm(x) for x in d["pasta"].split("/")]
    fam = SECAO_FAM.get(partes[0], "OUTROS")
    serie = PASTA_SERIE.get(partes[1]) if fam == "ATO" and len(partes) > 1 else None
    tit = re.sub(r"\s+", " ", d["titulo"] or "").strip()
    # "TIPO nº 12/2024 - assunto"  |  "RA 129/2012 - assunto"
    # número do ato: "12/2024", "84-2022" (Corregedoria) ou "21_2024"; o resto do título é o assunto
    m = (re.match(r"^(.*?(?<![\d/])\d{1,4}\s*/\s*\d{2,4})(?!\d)(?!\s*/\s*\d)\s*(.*)$", tit) or
         re.match(r"^(.*?\d{1,4}[-_](?:19|20)\d{2})(?!\d)\s*(.*)$", tit))
    nome, assunto = (m.group(1).strip(), re.sub(r"^[\s\-–—:]+", "", m.group(2) or "").strip()) if m else (tit, "")
    # "Ato ... N.º 18, de 10 de julho de 2019 - altera ..." : número + data por extenso, se vier antes de qualquer "nn/aaaa"
    md = re.search(r"n\.?\s*[º°o]?\.?\s*(\d{1,4})\s*,?\s*de\s+\d{1,2}\s*(?:º|o)?\s+de\s+(janeiro|fevereiro|mar[cç]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})", tit, re.I)
    mpos = re.search(r"(?<![\d/])\d{1,4}\s*[/_-]\s*\d{2,4}", tit)
    data_extenso = None
    if md and (not mpos or md.start() < mpos.start()):
        nome, assunto = tit[:md.end()].strip(), re.sub(r"^[\s\-–—:,]+", "", tit[md.end():]).strip()
        data_extenso = (int(md.group(1)), int(md.group(3)))
    mn = re.search(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{4}|\d{2})(?!\d)(?!\s*/\s*\d)", nome) or re.search(r"(\d{1,4})[-_]((?:19|20)\d{2})(?!\d)", nome)
    num, ano = (int(mn.group(1)), ano4(mn.group(2))) if mn else (None, None)
    if data_extenso:
        num, ano = data_extenso
    if num is not None and 1950 <= num <= 2100:     # "biênio 2003/2005" não é número de ato
        num, ano = None, None
    if ano is None:
        my = re.search(r"/((?:19|20)\d\d)(?:/|$)", "/" + d["pasta"] + "/")
        ano = int(my.group(1)) if my else None
    if num is None and ano is not None:
        # "Ato da Presidência - 52 - Designa ..." : número sem ano; o ano vem da pasta
        mx = re.match(r"^([^0-9]*?[-–]\s*(\d{1,4}))\s*[-–(]\s*(.*)$", tit)
        if mx and not 1950 <= int(mx.group(2)) <= 2100:
            num, nome, assunto = int(mx.group(2)), mx.group(1).strip(), mx.group(3).strip()
    # título com tipo diferente da pasta (ex.: Ato Conjunto dentro de Atos)
    rot, fam_t = classifica(nome)
    if fam_t not in ("OUTROS",) and fam_t != fam and not (fam == "ATO" and fam_t == "ATO"):
        fam = fam_t if fam_t in ("ATOCONJ", "RES", "PORTCONJ", "ER") else fam
    return fam, num, ano, serie, nome, assunto

# versão compilada/consolidada do próprio ato (não confundir com "Altera o Provimento Consolidado ...")
_CC = r"(?:compilad|consolidad)[oa]"
RX_COMPILADA = re.compile(
    r"\([^)]*\b" + _CC + r"\b[^)]*\)"                                   # (Compilada), (Compilada em 24/05/2023), (Republicado e consolidado)
    r"|\b(?:texto|reda[cç][aã]o|red\.|vers[aã]o)\s+(?:" + _CC + r"|atualizad[oa])\b"   # redação consolidada, versão atualizada
    r"|[-–]\s*" + _CC + r"\b(?!\s+n)"                                     # - Compilada -
    r"|\d{2,4}\s+" + _CC + r"\b"                                           # 65/2010 Consolidado
    r"|^\s*consolida[cç][aã]o\b|[-–]\s*ATUALIZAD[OA]\s*$", re.I)
RX_MODIFICADOR = re.compile(r"\b(alter\w*|inclui|insere|acresc\w*|suspende|revoga|d[aá] nova reda\w*|modifica)\b[^()]{0,90}\b" + _CC, re.I)
RX_DESATUALIZADO = re.compile(r"desatualizad", re.I)

def eh_compilada(t):
    t = t or ""
    return bool(RX_COMPILADA.search(t)) and not RX_MODIFICADOR.search(t)

def data_compilacao(t):
    """Data (ou ano) da versão compilada: 'Compilada 15/09/2021', 'versão 13/3/2024', 'redação consolidada 2026'."""
    m = re.search(r"(?:compilad|consolidad|atualizad|vers[aã]o)[^0-9()]{0,20}(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{2,4})", t or "", re.I)
    if m:
        return f"{ano4(m.group(3)):04d}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    m = re.search(r"(?:compilad|consolidad)[oa]\s+(?:em\s+)?((?:19|20)\d\d)\b", t or "", re.I)
    return f"{m.group(1)}-00-00" if m else ""

# marca de revogação no título do site: "(REVOGADA)" ou "- REVOGADA -"
RX_REV_SITE = re.compile(r"\(\s*(revogad[oa]s?|tornad[oa] sem efeito)\s*\)|[-–]\s*REVOGAD[OA]S?\s*(?:[-–]|$)", re.I)

def incorpora_site(atos, site):
    """Funde os documentos do site com os verbetes do PDF; cria atos 'só no site'."""
    grupos = collections.OrderedDict()
    for d in site["docs"]:
        if (d.get("ext") or "").lower() not in ("pdf", "doc", "docx", "odt", "htm", "html", ""):
            continue
        fam, num, ano, serie, nome, assunto = parse_doc_site(d)
        chave = (fam, num, ano, serie) if num is not None else ("SEMNUM", norm(d["titulo"]), ano)
        grupos.setdefault(chave, []).append((d, nome, assunto))
    idx = collections.defaultdict(list)
    for a in atos:
        if a["num"] is not None:
            idx[(a["fam"], a["num"], a["anum"])].append(a)
    st = collections.Counter()
    novos = []
    for chave, docs in grupos.items():
        # documento principal: o que não é anexo/errata
        compilada = lambda x: eh_compilada(x[0]["titulo"])
        # documento-base para nome/assunto: o original (não compilado, não anexo)
        docs.sort(key=lambda x: (compilada(x), bool(re.search(r"anexo|errata|retifica", norm(x[0]["titulo"]))), len(x[0]["titulo"])))
        d0, nome, assunto = docs[0]
        # arquivos: texto compilado primeiro (é o que traz o conteúdo em vigor)
        # versões compiladas: a mais recente não marcada como desatualizada é a vigente ("c"); as demais, histórico ("h")
        comp = [x for x in docs if compilada(x)]
        comp.sort(key=lambda x: (not RX_DESATUALIZADO.search(x[0]["titulo"] or ""), data_compilacao(x[0]["titulo"]) or "0000", x[0].get("modificado") or ""), reverse=True)
        vigente = comp[0] if comp and not RX_DESATUALIZADO.search(comp[0][0]["titulo"] or "") else None
        outros = sorted([x for x in docs if not compilada(x)], key=lambda x: (bool(re.search(r"anexo|errata", norm(x[0]["titulo"]))), len(x[0]["titulo"])))
        ordem = ([vigente] if vigente else []) + [x for x in comp if x is not vigente] + outros
        def marca(x):
            if x is vigente: return ["c", data_compilacao(x[0]["titulo"])]
            if compilada(x): return ["h", data_compilacao(x[0]["titulo"])]
            return []
        arquivos = [[URL_SITE + x[0]["url"], (x[0]["titulo"] or "")[:140]] + marca(x) for x in ordem if x[0].get("url")]
        texto_site = max([assunto, d0.get("descricao") or ""], key=len)
        rev_site = any(RX_REV_SITE.search(x[0]["titulo"] or "") for x in docs)
        alvo = None
        if chave[0] != "SEMNUM":
            fam, num, ano, serie = chave
            cands = [a for a in idx.get((fam, num, ano), []) if "site" not in a]
            if fam == "ATO" and serie:
                cands = [a for a in cands if serie_pdf(a) == serie]
            if len(cands) > 1:
                pw = palavras(texto_site)
                cands.sort(key=lambda a: -len(pw & palavras(a["ementa"])))
                st["desempate_texto"] += 1
            alvo = cands[0] if cands else None
            if alvo is not None:
                pw, pe = palavras(texto_site + " " + " ".join(x[0]["titulo"] or "" for x in docs)), palavras(alvo["ementa"])
                if len(pw) >= 3 and len(pe) >= 3 and not (pw & pe):
                    st["rejeitado_assunto"] += 1   # mesmo número, assuntos sem nada em comum: atos diferentes
                    alvo = None
        if alvo is not None:
            alvo["site"] = {"arq": arquivos, "txt": texto_site, "rev": rev_site}
            st["fundidos"] += 1
        else:
            fam = chave[0] if chave[0] != "SEMNUM" else classifica(nome)[1]
            rot = FAM_ROT.get(fam) or classifica(nome)[0]
            if chave[0] != "SEMNUM" and not re.search(r"[A-Za-zÀ-ú]", nome):
                nome = f"{rot}{' ' + chave[3] if chave[0] == 'ATO' and chave[3] else ''} nº {chave[1]}/{chave[2]}"
            if chave[0] != "SEMNUM" and re.match(r"^\s*consolida[cç][aã]o\b", nome, re.I):
                # "CONSOLIDAÇÃO - PROV. 01-2005 - ATUALIZADO": a própria norma consolidada
                nome = f"{rot} Consolidado nº {chave[1]:02d}/{chave[2]}"
                arq = re.sub(r"\.(pdf|docx?|odt)$", "", d0.get("arquivo") or "", flags=re.I)
                texto_site = "Texto consolidado e atualizado" + (f" ({arq})" if arq else "") + "."
            if chave[0] != "SEMNUM" and re.match(r"^(RA|R\.A\.)\s", nome):
                nome = f"Resolução Administrativa nº {chave[1]}/{chave[2]}"
            un = siglas(nome)
            if chave[0] == "ATO" and chave[3] and chave[3] not in un: un.append(chave[3])
            novos.append({"tipo": rot, "fam": fam, "nome": nome, "pub": "", "veic": "", "dpub": None,
                          "ano": chave[2], "num": chave[1] if chave[0] != "SEMNUM" else None,
                          "anum": chave[2] if chave[0] != "SEMNUM" else None, "un": un, "ementa": texto_site,
                          "notas": [], "pg": None, "site": {"arq": arquivos, "txt": texto_site, "rev": rev_site}, "pasta": d0["pasta"], "assunto": assunto})
            st["so_site"] += 1
        st["arquivos"] += len(docs)
    base = len(atos)
    for k, n in enumerate(sorted(novos, key=lambda a: (a["ano"] or 0, a["num"] or 0))):
        n["id"] = base + k
        atos.append(n)
    return st

# ---------------------------------------------------------------- natureza: norma geral × efeito concreto
# Efeito concreto = ato que se esgota num caso (designação, aposentadoria, escala, suspensão de prazo pontual, edital…).
# Na dúvida, norma geral: é melhor mostrar um ato a mais do que esconder uma norma.
RX_CONCRETO = re.compile(r"^\W*(?:"
    r"design\w*|dispens\w*|nome(?:ia|a[cç][aã]o)|exonera\w*|aposent\w*|pens[aã]o|concede\w*|concess[aã]o d[eao] (?:aposent|pens|licen|abono|f[eé]rias|di[aá]ria|ajuda)|"
    r"convoca\w*|remov\w*|remo[cç][aã]o|lota\w*|cede\b|cess[aã]o d[eao]|redistribu\w*|vincula\w*|desvincula\w*|reconduz\w*|substitui[cç][aã]o d[eoa]|"
    r"homologa\w*|torna p[uú]blic\w*|publica (?:a|o) (?:lista|resultado|rela[cç])|indica\w*|elege\w*|elei[cç][aã]o|escala\b|escala de|"
    r"suspen(?:de|s[aã]o)\b.{0,60}\b(?:prazo|expediente|atividade|distribui)|prorroga\w*\b.{0,60}\b(?:prazo|suspens|expediente)|"
    r"(?:decreta|declara)\b.{0,30}ponto facultativo|ponto facultativo|altera,?\s+excepcionalmente|altera a composi[cç][aã]o|comp[oõ]e\b|"
    r"referenda\w*|aceita\w*|averba\w*|declara\w* (?:vag|vac)|vac[aâ]ncia|promo(?:ve|[cç][aã]o)\b|abono|"
    r"gabarito|resultado|calend[aá]rio de correi|edital|lista d|rela[cç][aã]o d[oe]s|autoriza a elimina|aprova (?:a|o) (?:escala|relat[oó]rio|calend|lista)|"
    r"retifica\w*|republica\w*|torna sem efeito|faz cessar|cessa\w*|exclui\w*|inclui\w* (?:o|a|os|as)? ?(?:servidor|magistrad|ju[ií]z)|"
    r"determina\w*\s+(?:a\s+)?redistribui|participa\w*|estabelece\w*\s+a\s+escala|comunica\w*|aprova\w*\s+(?:a|as|o|os)\s+(?:remo[cç]|promo[cç]|lota[cç]|indica[cç]|designa)|lista tr[ií]plice|licen[cç]a (?:para|m[eé]dica|capacita)|afastamento d"
    r")", re.I)
# termos de norma geral (para descrições do portal, onde o verbo não abre o texto)
RX_GERAL = re.compile(r"\b(?:regulament\w*|institu\w*|disp[oõ]e(?:m)? sobre|disciplin\w*|normatiz\w*|estabelece\w*\s+(?:normas|crit[eé]rios|regras|diretrizes|procedimentos)|"
                      r"pol[ií]tica|regimento|norma de|cria\w*\b|fixa\w*\s+(?:o valor|crit|normas)|delega\w* compet|define\w*|aprova\w* (?:o regulamento|a pol[ií]tica|o plano|a norma))", re.I)
RX_CONCRETO_LIVRE = re.compile(r"\b(?:design\w*|aposent\w*|pens[aã]o|convoca\w*|redistribu\w*|remo[cç][aã]o|lista tr[ií]plice|elei[cç][aã]o|escala de f[eé]rias|"
                      r"suspen\w*\s+(?:dos\s+|os\s+)?prazos|prorroga\w*\s+(?:dos\s+|os\s+)?prazos|ponto facultativo|vincula\w*|homologa\w*|nomea\w*|exonera\w*|"
                      r"concede\w*|concess[aã]o de (?:aposent|pens|licen|abono)|vac[aâ]ncia|promo[cç][aã]o|participa[cç][aã]o (?:no|na|em)|recondu\w*|substitui[cç][aã]o d)", re.I)
TIPOS_CONCRETOS = {"Edital", "Apostila", "Escala / Lista / Resultado", "Despacho", "Ata", "Extrato", "Acórdão", "Decisão administrativa", "Aviso", "Comunicado"}

def natureza(tipo, texto, livre=False):
    """livre=True: descrição do portal ('O Tribunal publicou a RA nº X, que designa...'): vale o 1º termo encontrado."""
    if tipo in TIPOS_CONCRETOS:
        return "e"
    if livre:
        t = (texto or "")[:300]
        mc, mg = RX_CONCRETO_LIVRE.search(t), RX_GERAL.search(t)
        if mc and (not mg or mc.start() < mg.start()):
            return "e"
        return "g"
    t = re.sub(r"^\s*(?:o|a)\s+(?:presidente|desembargador\w*|tribunal)[^,]{0,120},\s*", "", texto or "", flags=re.I)  # "O Presidente..., no uso..., resolve"
    t = re.sub(r"^\s*(?:ad referendum[^,]*,\s*)", "", t, flags=re.I)
    t = re.sub(r"^\s*(?:republica[cç][aã]o|retifica[cç][aã]o|errata)\s*[-–:]\s*", "", t, flags=re.I)   # "Republicação - Altera o Ato..."
    return "e" if RX_CONCRETO.search(t[:220]) else "g"

# ---------------------------------------------------------------- temas (dicionário editável em temas_atos.json)
def carrega_temas(caminho="temas_atos.json"):
    if not os.path.exists(caminho):
        return [], []
    T = json.load(open(caminho, encoding="utf-8"))
    lista, regras = [], []
    def rx(xs):
        return re.compile("|".join(r"(?<![a-z0-9])" + re.escape(norm(x)) + (r"(?![a-z0-9])" if len(x) <= 5 else "") for x in xs)) if xs else None
    for g in T["grupos"]:
        for t in g["temas"]:
            pos = [x for x in t["termos"] if not x.startswith("!")]
            neg = [x[1:] for x in t["termos"] if x.startswith("!")]
            lista.append({"grupo": g["grupo"], "tema": t["tema"]})
            ign = re.compile("|".join(re.escape(norm(x)) for x in t.get("ignorar", []))) if t.get("ignorar") else None
            regras.append((rx(pos), rx(neg), ign))
    # características transversais (ex.: Colegiados): mesma regra, gravadas como marca do ato
    carac = []
    for c in T.get("caracteristicas", []):
        ign = re.compile("|".join(re.escape(norm(x)) for x in c.get("ignorar", []))) if c.get("ignorar") else None
        carac.append((c["nome"], rx(c["termos"]), ign))
    carrega_temas.caracteristicas = carac
    return lista, regras

def temas_do_texto(texto, regras):
    t = norm(texto)
    out = []
    for i, (pos, neg, ign) in enumerate(regras):
        tt = ign.sub(" ", t) if ign else t      # expressões que não contam para este tema
        if pos and pos.search(tt) and not (neg and neg.search(tt)):
            out.append(i)
    return out

# ---------------------------------------------------------------- principal
def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    caminho = sys.argv[1]
    site_path = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else None
    brutos, atualizado = extrai_atos(caminho)

    atos = []
    for i, b in enumerate(brutos):
        cab = re.sub(r"\s+", " ", b["cab"]).strip()
        ementa, notas = separa_blocos(b["resto"])
        tipo, fam = classifica(cab)
        num, ano = numero_ano(cab)
        pos_par = cab.find("(")
        nome = cab[:pos_par].strip(" -–") if pos_par > 0 else cab
        pub = cab[pos_par:].strip() if pos_par > 0 else ""
        dpub = primeira_data(pub) or None
        ano_ref = int(dpub[:4]) if dpub and int(dpub[:4]) >= 1990 else ano
        if dpub and int(dpub[:4]) < 1990:
            dpub = None
        if ano_ref is None and atos:
            ano_ref = atos[-1]["ano"]     # lista é cronológica: herda o ano do ato anterior
        veiculo = ("DEJT" if "DEJT" in pub else "D.O." if re.search(r"D\.\s*O", pub) else "B.I." if re.search(r"B\.\s*I", pub) else "")
        atos.append({
            "id": i, "tipo": tipo, "fam": fam, "nome": nome, "pub": pub.strip("() ") if pub else "",
            "veic": veiculo, "dpub": dpub, "ano": ano_ref, "num": num, "anum": ano,
            "un": siglas(nome), "ementa": ementa, "notas": notas, "pg": b["pg"],
        })

    n_compilacao = len(atos)
    st_site, site_meta = None, None
    if site_path:
        with open(site_path, encoding="utf-8") as f:
            site = json.load(f)
        st_site = incorpora_site(atos, site)
        site_meta = {"coletado_em": site.get("coletado_em"), "n_docs": len(site["docs"]), **st_site,
                     "parcial": bool(site.get("parcial")), "secoes_incompletas": site.get("secoes_incompletas") or {}}

    # índice para casamento
    idx = collections.defaultdict(list)
    for a in atos:
        if a["num"] is not None:
            idx[(a["fam"], a["num"], a["anum"])].append(a["id"])
            if a["fam"] == "ATOCONJ":
                idx[("ATO", a["num"], a["anum"])].append(a["id"])

    def casa(fam, num, ano, dpub, sig, origem_id):
        cands = [c for c in idx.get((fam, num, ano), []) if c != origem_id]
        if not cands and fam == "RES":
            cands = [c for c in idx.get(("RA", num, ano), []) if c != origem_id]
        if not cands and fam == "ATO":
            cands = [c for c in idx.get(("ATOCONJ", num, ano), []) if c != origem_id]
        if dpub and len(dpub) == 10 and fam not in SERIE_UNICA:
            # data citada diverge da data do candidato (> 10 dias): não é o mesmo ato
            dd_, mm_, aa_ = dpub[8:], dpub[5:7], dpub[:4]
            def perto(c):
                d = atos[c]["dpub"]
                if not d or len(d) != 10: return True
                # data citada aparece entre as (re)publicações do candidato
                if re.search(rf"{dd_}\s*/\s*{mm_}\s*/\s*({aa_}|{aa_[2:]})\b", atos[c]["pub"]): return True
                # data citada anterior ao ano do próprio ato: erro de digitação na fonte
                if atos[c]["anum"] and int(aa_) < atos[c]["anum"]: return True
                try:
                    return abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(dpub)).days) <= 10
                except ValueError:
                    return True
            cands = [c for c in cands if perto(c)]
        if fam == "ATO" and len(cands) == 1:
            explicita = next((SIGLA_SERIE[x] for x in sig if x in SIGLA_SERIE), None)
            if explicita and serie_pdf(atos[cands[0]]) != explicita:
                return [], "nao"   # citação de Ato da unidade X não pode casar com Ato de outra unidade
        if len(cands) <= 1:
            return cands, "unico" if cands else "nao"
        if dpub:
            f = [c for c in cands if atos[c]["dpub"] and (atos[c]["dpub"] == dpub or atos[c]["dpub"][:7] == dpub[:7] and len(dpub) == 7)]
            if len(f) == 1: return f, "data"
            if f: cands = f
        if fam == "ATO" and len(cands) > 1:
            # cada unidade numera seus Atos: a sigla citada indica a série (sem sigla além de PRESI = Presidência)
            # sem sigla de unidade na citação, vale a unidade do ato que cita ("revoga o Ato nº X" dentro de um Ato SGP = Ato SGP)
            orig = atos[origem_id] if origem_id is not None and origem_id < len(atos) else None
            padrao = serie_pdf(orig) if orig is not None and orig["fam"] == "ATO" else "PRESI"
            explicita = next((SIGLA_SERIE[x] for x in sig if x in SIGLA_SERIE), None)
            serie_cit = explicita or padrao
            f = [c for c in cands if serie_pdf(atos[c]) == serie_cit]
            if len(f) == 1: return f, "unidade"
            if f: cands = f
            elif explicita:
                return [], "nao"   # a citação nomeia a unidade e não há ato dela com esse número
        if sig:
            sc = [(len(set(sig) & set(atos[c]["un"])), c) for c in cands]
            best = max(s for s, _ in sc)
            f = [c for s, c in sc if s == best and best > 0]
            if len(f) == 1: return f, "unidade"
            if f: cands = f
        return cands, "ambiguo"

    stats = collections.Counter()
    saida_rel = collections.defaultdict(list)    # id -> [(rel, alvo_ids, qualidade, texto_citado)]
    entrada_rel = collections.defaultdict(list)  # alvo -> [(rel, origem)]
    revog_por_ementa = {}
    faltantes = []   # citações a atos sem verbete na compilação

    for a in atos:
        refs = []
        for k, n in enumerate(a["notas"]):
            rel = rel_da_nota(n)
            for fam, num, ano, dpub, sig, s, e in citacoes(n):
                ids, q = casa(fam, num, ano, dpub, sig, a["id"])
                stats["cit_" + ("ok" if q in ("unico", "data", "unidade") else q)] += 1
                if ids:
                    refs.append({"de": "nota", "k": k, "rel": rel, "ids": ids, "q": q, "s": s, "e": e, **({"dp": dpub} if dpub else {})})
                    for t in ids:
                        entrada_rel[t].append({"rel": rel, "id": a["id"], "inv": True})
                else:
                    faltantes.append({"fam": fam, "num": num, "ano": ano, "dpub": dpub, "sig": sig, "de": "nota",
                                      "k": k, "rel": rel, "cit": a["id"], "s": s, "e": e, "ref": refs})
        do_site = a["pg"] is None   # ementa = resumo do portal, não texto da compilação
        for fam, num, ano, dpub, sig, s, e in citacoes(a["ementa"]):
            if do_site and (fam, num, ano) == (a["fam"], a["num"], a["anum"]):
                continue   # o resumo do portal cita o próprio ato
            ids, q = casa(fam, num, ano, dpub, sig, a["id"])
            stats["cit_" + ("ok" if q in ("unico", "data", "unidade") else q)] += 1
            antes = norm(a["ementa"][max(0, s - 90):s])
            verbo = None
            mv = list(re.finditer(r"\b(revoga|altera|regulamenta|referenda|prorroga|republica|retifica|suspende|torna sem efeito|faz cessar|substitui|complementa|acrescenta|homologa)\b", antes))
            if mv and not do_site:   # verbos soltos nos resumos do portal não indicam relação confiável
                verbo = mv[-1].group(1)
            if not ids:
                faltantes.append({"fam": fam, "num": num, "ano": ano, "dpub": dpub, "sig": sig, "de": "ementa",
                                  "rel": verbo or "cita", "cit": a["id"], "s": s, "e": e, "ref": refs})
                continue
            refs.append({"de": "ementa", "rel": verbo or "cita", "ids": ids, "q": q, "s": s, "e": e})
            for t in ids:
                entrada_rel[t].append({"rel": (verbo or "cita") + " (ementa)", "id": a["id"], "inv": True})
                if verbo in ("revoga", "torna sem efeito", "faz cessar") and q != "ambiguo":
                    # só revoga atos anteriores (ordem da compilação; para atos do portal, pelo ano)
                    anterior = t < a["id"] if atos[t]["pg"] is not None else (atos[t]["ano"] or 0) <= (a["ano"] or 0)
                    if anterior:
                        trecho = norm(a["ementa"][s - 40:s])
                        if not re.search(r"\b(art|arts|inciso|incisos|§|paragrafo|alinea|item|anexo|dispositivo)", trecho):
                            revog_por_ementa.setdefault(t, a["id"])
        a["refs"] = refs

    # status
    for a in atos:
        rev, alt = status_por_notas(a["notas"])
        origem = "nota" if (rev or alt) else None
        if not rev and a["id"] in revog_por_ementa:
            rev, origem = True, "ementa"
            a["rev_por"] = revog_por_ementa[a["id"]]
        if not alt and any(x["rel"].startswith(("altera", "acrescenta", "complementa", "republica", "retifica", "prorroga")) for x in entrada_rel[a["id"]] if "(ementa)" in x["rel"]):
            alt = True
            origem = origem or "ementa"
        if "site" in a and a["site"]["rev"] and not rev:
            # o título no site do TRT marca o ato como revogado
            rev, origem = True, "site"
        a["st"] = "revogado" if rev else "alterado" if alt else ("site" if a["pg"] is None else "sem_registro")
        a["st_origem"] = origem
        # vínculos de entrada, sem duplicar
        vis, ent = set(), []
        for x in entrada_rel[a["id"]]:
            k = (x["rel"], x["id"])
            if k not in vis:
                vis.add(k); ent.append({"rel": x["rel"], "id": x["id"]})
        a["ent"] = ent
        stats["st_" + a["st"]] += 1

    citados = constroi_citados(atos, faltantes)
    stats["st_citado"] = len(citados)

    total_cit = stats["cit_ok"] + stats["cit_ambiguo"] + stats["cit_nao"]
    meta = {
        "schema": SCHEMA,
        "fonte": os.path.basename(caminho),
        "atualizado_ate": atualizado,
        "gerado_em": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_atos": n_compilacao,
        "n_so_site": len(atos) - n_compilacao,
        "n_citados": len(citados),
        "site": site_meta,
        "citacoes": {"total": total_cit, "casadas": stats["cit_ok"], "ambiguas": stats["cit_ambiguo"], "sem_par": stats["cit_nao"]},
        "status": {k[3:]: v for k, v in stats.items() if k.startswith("st_")},
    }
    # JSON compacto: chaves curtas
    enx = []
    for a in atos:
        o = {"i": a["id"], "t": a["tipo"], "n": a["nome"], "p": a["pub"], "v": a["veic"], "d": a["dpub"],
             "a": a["ano"], "u": a["un"], "e": a["ementa"], "o": a["notas"], "pg": a["pg"], "s": a["st"]}
        if a["st_origem"] in ("ementa", "site"): o["so"] = a["st_origem"]
        if len(a.get("assunto") or "") >= 8:
            o["k"] = natureza(a["tipo"], a["assunto"])                        # assunto do título no portal
        elif a["pg"] is not None:
            o["k"] = natureza(a["tipo"], a["ementa"] or a["nome"])           # ementa oficial da compilação
        else:
            o["k"] = natureza(a["tipo"], a["ementa"] or a["nome"], livre=True)  # descrição longa do portal
        o["f"] = ("cs" if a["pg"] is not None else "s") if "site" in a else "c"
        if "site" in a:
            o["pdf"] = a["site"]["arq"]
            if any(len(x) > 2 and x[2] == "c" for x in o["pdf"]): o["cp"] = 1
            if a["pg"] is not None and a["site"]["txt"] and norm(a["site"]["txt"])[:60] not in norm(a["ementa"]):
                o["ds"] = a["site"]["txt"]
            if a.get("pasta"): o["ps"] = a["pasta"]
        if a.get("rev_por") is not None: o["rp"] = a["rev_por"]
        if a["refs"]: o["r"] = [{k: v for k, v in r.items()} for r in a["refs"]]
        if a["ent"]: o["x"] = a["ent"]
        enx.append(o)
    for c in citados:
        o = {"i": c["id"], "t": c["tipo"], "n": c["nome"], "p": c["pub"], "v": "", "d": c["dpub"], "a": c["ano"],
             "u": c["un"], "e": c["ementa"], "o": [], "pg": None, "s": "citado", "x": c["ent"], "f": "x"}
        # citado: norma geral se modifica/complementa uma norma geral (ex.: altera o ato do teletrabalho)
        o["k"] = "g" if any(re.match(r"(alterad|revogad|altera|revoga|norma|regulament|complement|acrescent|retific|rerratific|referend|prorrog)", norm(x["rel"])) and enx[x["id"]].get("k") == "g" for x in c["ent"]) else "e"
        enx.append(o)
    # temas: nome + ementa (300 car.) + títulos dos arquivos no portal; sem tema próprio, herda do ato que revoga/altera
    temas_lista, temas_regras = carrega_temas(os.path.join(os.path.dirname(os.path.abspath(__file__)), "temas_atos.json"))
    if temas_regras:
        for o in enx:
            tx = o["n"] + " | " + (o["e"] or "")[:300] + " | " + " | ".join(x[1] for x in (o.get("pdf") or [])[:2])
            tm = temas_do_texto(tx, temas_regras)
            if tm: o["tm"] = tm
            t_ = norm(tx)
            for nome_c, rx_c, ign_c in getattr(carrega_temas, "caracteristicas", []):
                if nome_c == "Colegiados" and rx_c and rx_c.search(ign_c.sub(" ", t_) if ign_c else t_):
                    o["cl"] = 1
        for o in enx:
            if "tm" in o: continue
            herd = set()
            for r in o.get("r", []):
                if re.match(r"(revoga|altera|alterad|revogad|prorroga|regulament|complement|acrescent|norma)", norm(r["rel"])):
                    for i in r["ids"]:
                        herd.update(enx[i].get("tm", []))
            if herd: o["tm"] = sorted(herd); o["th"] = 1   # tema herdado
        meta["temas"] = temas_lista
        meta["temas_cobertura"] = {"normas_gerais": sum(1 for o in enx if o.get("k") == "g"),
                                   "com_tema": sum(1 for o in enx if o.get("k") == "g" and o.get("tm"))}
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "atos": enx}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{n_compilacao} atos da compilação · {len(atos) - n_compilacao} só no site · {len(citados)} citados sem verbete · atualizado até {atualizado}")
    if st_site: print(f"site: {dict(st_site)}")
    print(f"status: {meta['status']}")
    c = meta["citacoes"]
    if c["total"]:
        print(f"citações: {c['total']} · casadas {c['casadas']} ({100*c['casadas']/c['total']:.1f}%) · ambíguas {c['ambiguas']} · sem par {c['sem_par']}")
    print(f"-> {SAIDA} ({os.path.getsize(SAIDA)/1024:.0f} KB)")

if __name__ == "__main__":
    main()
