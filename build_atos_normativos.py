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
            r_ = {"de": f["de"], "rel": f["rel"], "ids": [prox], "q": "citado", "s": f["s"], "e": f["e"]}
            if f["de"] == "nota": r_["k"] = f["k"]
            f["ref"].append(r_)
        citados.append({"id": prox, "tipo": rot, "nome": nome, "dpub": dpub,
                        "pub": f"publicação citada: {'/'.join(reversed(dpub.split('-')))}" if dpub else "data de publicação não citada",
                        "ano": int(dpub[:4]) if dpub else ano, "un": sig, "ementa": " · ".join(ementa), "ent": ent})
        prox += 1
    return citados

# ---------------------------------------------------------------- principal
def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    caminho = sys.argv[1]
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
        if len(cands) <= 1:
            return cands, "unico" if cands else "nao"
        if dpub:
            f = [c for c in cands if atos[c]["dpub"] and (atos[c]["dpub"] == dpub or atos[c]["dpub"][:7] == dpub[:7] and len(dpub) == 7)]
            if len(f) == 1: return f, "data"
            if f: cands = f
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
                    refs.append({"de": "nota", "k": k, "rel": rel, "ids": ids, "q": q, "s": s, "e": e})
                    for t in ids:
                        entrada_rel[t].append({"rel": rel, "id": a["id"], "inv": True})
                else:
                    faltantes.append({"fam": fam, "num": num, "ano": ano, "dpub": dpub, "sig": sig, "de": "nota",
                                      "k": k, "rel": rel, "cit": a["id"], "s": s, "e": e, "ref": refs})
        for fam, num, ano, dpub, sig, s, e in citacoes(a["ementa"]):
            ids, q = casa(fam, num, ano, dpub, sig, a["id"])
            stats["cit_" + ("ok" if q in ("unico", "data", "unidade") else q)] += 1
            antes = norm(a["ementa"][max(0, s - 90):s])
            verbo = None
            mv = list(re.finditer(r"\b(revoga|altera|regulamenta|referenda|prorroga|republica|retifica|suspende|torna sem efeito|faz cessar|substitui|complementa|acrescenta|homologa)\b", antes))
            if mv:
                verbo = mv[-1].group(1)
            if not ids:
                faltantes.append({"fam": fam, "num": num, "ano": ano, "dpub": dpub, "sig": sig, "de": "ementa",
                                  "rel": verbo or "cita", "cit": a["id"], "s": s, "e": e, "ref": refs})
                continue
            refs.append({"de": "ementa", "rel": verbo or "cita", "ids": ids, "q": q, "s": s, "e": e})
            for t in ids:
                entrada_rel[t].append({"rel": (verbo or "cita") + " (ementa)", "id": a["id"], "inv": True})
                if verbo in ("revoga", "torna sem efeito", "faz cessar") and q != "ambiguo" and atos[t]["id"] < a["id"] + 50:
                    # só revoga atos anteriores (lista é cronológica)
                    if t < a["id"]:
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
        a["st"] = "revogado" if rev else "alterado" if alt else "sem_registro"
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
        "n_atos": len(atos),
        "n_citados": len(citados),
        "citacoes": {"total": total_cit, "casadas": stats["cit_ok"], "ambiguas": stats["cit_ambiguo"], "sem_par": stats["cit_nao"]},
        "status": {k[3:]: v for k, v in stats.items() if k.startswith("st_")},
    }
    # JSON compacto: chaves curtas
    enx = []
    for a in atos:
        o = {"i": a["id"], "t": a["tipo"], "n": a["nome"], "p": a["pub"], "v": a["veic"], "d": a["dpub"],
             "a": a["ano"], "u": a["un"], "e": a["ementa"], "o": a["notas"], "pg": a["pg"], "s": a["st"]}
        if a["st_origem"] == "ementa": o["so"] = "ementa"
        if a.get("rev_por") is not None: o["rp"] = a["rev_por"]
        if a["refs"]: o["r"] = [{k: v for k, v in r.items()} for r in a["refs"]]
        if a["ent"]: o["x"] = a["ent"]
        enx.append(o)
    for c in citados:
        o = {"i": c["id"], "t": c["tipo"], "n": c["nome"], "p": c["pub"], "v": "", "d": c["dpub"], "a": c["ano"],
             "u": c["un"], "e": c["ementa"], "o": [], "pg": None, "s": "citado", "x": c["ent"]}
        enx.append(o)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "atos": enx}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(atos)} atos · {len(citados)} atos citados sem verbete · atualizado até {atualizado}")
    print(f"status: {meta['status']}")
    c = meta["citacoes"]
    if c["total"]:
        print(f"citações: {c['total']} · casadas {c['casadas']} ({100*c['casadas']/c['total']:.1f}%) · ambíguas {c['ambiguas']} · sem par {c['sem_par']}")
    print(f"-> {SAIDA} ({os.path.getsize(SAIDA)/1024:.0f} KB)")

if __name__ == "__main__":
    main()
