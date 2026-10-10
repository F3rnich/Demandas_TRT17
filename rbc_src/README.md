# Calculadora de RBC (DIPROF) — código-fonte

A página publicada no Hub (`../calculadora_rbc.html`) é gerada a partir desta pasta. **Não edite a página diretamente**: altere os fontes e gere de novo.

Sem dados pessoais. Fichas, relatórios do RH e RBCs da DIPROF ficam em `casos/`, que não é versionada.

## Estrutura

| Pasta/arquivo | Conteúdo |
|---|---|
| `calc/rbc_core.js` | Motor da ficha: classificação de rubricas, realocação de retroativos, 11,98%, GN, conferência de PSS |
| `calc/esperada.js` | Tabela esperada (base + relatórios), pesos por dia, AQ pela ficha, correção de classe/padrão |
| `calc/relatorios.js` | Leitores dos relatórios do RH (PDF de texto, CSV/XLSX; OCR da progressão em imagem fica em `ui.js`) |
| `calc/ui.js` | Interface em 4 etapas, regras de cálculo (`REGRA_IDS`), modelo DIPROF (`aplicarTabelaAntiga`), exportação XLSX |
| `calc/template.html` | Leiaute; recebe os scripts e as bases embutidos |
| `calc/base_calc.json`, `calc/tabela.json` | Base de remuneração compacta e tabela de VB/GAJ (geradas de `base/final.json.gz`) |
| `calc/build_html.js` | Monta a página autocontida em `../calculadora_rbc.html` |
| `base/` | Extração da TABELA_REMUNERAÇÃO.xlsx (`extract.py` → `build.py` → `final.json`), planilha/CSVs da base (`write_out.py`), bases da calculadora (`mk_base_calc.py`, `mk_tabela.py`) e `guia_ia_rbc.md` |
| `testes/regressao.js` | Roda a página (Chromium/Playwright) em cada caso e compara o total mensal com a RBC da DIPROF |
| `casos/` | **Não versionada.** Um subdiretório por caso com os arquivos e um `caso.json` |

## Preparar o ambiente

```bash
cd rbc_src/calc
npm ci                      # playwright, xlsx, pdfjs-dist, exceljs, tesseract.js (OCR nos testes)
node build_html.js          # gera ../../calculadora_rbc.html
```

O Chromium do Playwright precisa estar instalado (no ambiente de nuvem do Claude já está).

## Regressão

```bash
cd rbc_src/calc
node ../testes/regressao.js                 # todos os casos de ../casos
node ../testes/regressao.js --so=caso_x     # só alguns
node ../testes/regressao.js --linha-base    # grava a linha de base atual
```

`casos/<id>/caso.json`:

```json
{
  "servidor": {"cargo": "TÉCNICO JUDICIÁRIO", "especialidade": "SEGURANCA", "espDesde": "", "inicio": "1995-01-09", "fim": "2012-06-24"},
  "relatorios": ["prog.pdf", "func.pdf", "vpni.pdf"],
  "fichas": ["ficha.xlsx"],
  "regras": {"vpniTabela": true},
  "rbc": {"arquivo": "dip.xlsx", "aba": "RBC", "colData": "A", "colTotal": "Q", "linhaIni": 10, "linhaFim": 240}
}
```

- Campos de `servidor` em branco são preenchidos pelo cabeçalho do relatório de progressão, como na página.
- `regras` usa os ids `r_*` da página (`ui.js`, `REGRA_IDS`). `aqTrein`: `"ficha"`, `"sim"` ou `"nao"`.
- `rbc.colTotal` é a coluna da remuneração total mensal na RBC da DIPROF. Linhas sem data (GN) ficam fora.
- A comparação usa a coluna X (total) da aba `RBC` exportada pela página, com tolerância de R$ 0,05.

Saída: meses iguais por caso, lista de divergências (mês, calculado, DIPROF, diferença, classe/padrão) e **regressões** — meses que batiam na linha de base e deixaram de bater (marcados com `!!`).

## Método de calibração

1. Cada RBC nova da DIPROF vira um caso em `casos/`.
2. Antes de mudar a lógica, rodar a regressão e gravar a linha de base.
3. Uma mudança só entra se melhora o caso-alvo **sem regressão** nos demais.
4. Se dois casos exigem regras opostas, a calculadora não decide: a diferença vira regra editável em "Regras de cálculo" e pergunta para a DIPROF no documento da demanda (projeto "Demandas aleatórias TRT-17", `claude/demanda-diprof-base-rbc-2026-10.md`, seção "Pendências para a DIPROF").
5. Na dúvida, prevalece a prática da RBC mais recente.

## Publicar

```bash
cd rbc_src/calc && node build_html.js && cd ../..
python3 validate_checks.py
git add calculadora_rbc.html rbc_src && git commit -m "..." && git push origin main
gh run list -R F3rnich/Demandas_TRT17 -L 2
```

O repositório é público: nunca versionar fichas, RBCs, relatórios, nomes ou CPFs. O `checks.json` bloqueia os nomes dos servidores de teste nos arquivos principais.

## Situação em 10/10/2026

Linha de base (caso de 1995–2012, RBC "considerando a FF"): 193/210 com as regras padrão; 172/210 com `vpniTabela` e `fcTabela` desligadas. Na rodada anterior, a RBC 3 (1994–2026) dava 326/384 com as regras padrão e 361/384 com as duas desligadas — conflito entre RBCs da DIPROF ainda sem decisão. Histórico completo por fase e pendências: documento da demanda no projeto.
