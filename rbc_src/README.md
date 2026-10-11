# Calculadora de RBC (DIPROF) — código-fonte

A página publicada no Hub (`../calculadora_rbc.html`) é gerada a partir desta pasta. **Não edite a página diretamente**: altere os fontes e gere de novo.

Sem dados pessoais. Fichas, relatórios do RH e RBCs da DIPROF ficam em `casos/`, que não é versionada.

## Estrutura

| Pasta/arquivo | Conteúdo |
|---|---|
| `calc/rbc_core.js` | Motor da ficha: classificação de rubricas, realocação de retroativos, 11,98%, GN, conferência de PSS |
| `calc/esperada.js` | Tabela esperada (base + relatórios), pesos por dia, AQ pela ficha, correção de classe/padrão |
| `calc/relatorios.js` | Leitores dos relatórios do RH (PDF de texto, CSV/XLSX; OCR da progressão em imagem fica em `ui.js`) |
| `calc/certidao.js` | Leitura de RBC já emitida (docx, PDF do SEI, planilha de trabalho) para comparação; geração da certidão de RBC e da certidão de 13º em .docx no modelo da DIPROF |
| `calc/ui.js` | Interface em 2 etapas (arquivos e servidor; conferência e emissão, com o quadro "A resolver" e os "Ajustes da RBC"), regras de cálculo (`REGRA_IDS`), modelo DIPROF (`aplicarTabelaAntiga`), exportação XLSX |
| `calc/rubricas_ref.json`, `calc/rubricas_cod.json` | Rubricas já classificadas (sugestão para rubrica nova) e descrição por código do sistema antigo (exportação "SQL Results" sem descrição); geradas por `pipeline/knn.py` e `pipeline/mk_codref.py`, sem dados pessoais |
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
- Gabarito alternativo: `"rbc": {"json": "gabarito.json"}` com `{"mensal": {"AAAA-MM": v}, "gn": {"AAAA": v}}`, extraído da certidão emitida (RBC em docx/PDF do SEI, tabela mês × ano). Compara também o 13º.
- `"gnCert": {"AAAA": v}` compara a aba "Certidão GN" (13º anterior à incidência de contribuição).
- Opções: `--par=8` (casos em paralelo), `--resumo`, `--sem-rel` (ignora CTC/relatórios, para medir o efeito deles), `--saida=arquivo.json`, `--pagina=outra.html`, `--tudo` (envia tudo pela entrada única, sem preencher campos; registra em `auto` o que a página deduziu — cargo, ingresso, desligamento, especialidade — e completa só o que ficou vazio).
- Antes de publicar: `python3 testes/varredura_nomes.py <nomes.txt>` (lista de nomes fora do repositório) procura nomes e CPFs na página e nos fontes.

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

## Situação em 10/10/2026 (calibração com 67 RBCs da DIPROF)

Corpus de 85 pastas de RBC (processo SEI 0000775-34.2024), 67 servidores com certidão legível, 4.119 competências no escopo (sem classistas e sem o caso "não fez"). Total mensal igual ao da certidão:

| Rodada | Meses com ficha | Meses sem ficha | 13º |
|---|---|---|---|
| Antes (commit e83c911) | 1.841/3.444 (53,5%) | 2/429 | 133/294 |
| Depois | 2.550/3.486 (73,1%) | 360/633 | 214/316 |

Mudanças: limite ao teto do RGPS (Funpresp/CTC), progressão deduzida da ficha quando não há relatório, leitor de CTC/declaração, meses sem ficha pela tabela, VPI pela tabela (ago/2016–dez/2018), regra "GAS até", fichas do FolhaWeb em planilha ("Big Grid") e em PDF "por folha", magistrado (subsídio + substituição; 13º pelo valor pago), certidão complementar de 13º, sugestão de categoria para rubrica não reconhecida. Detalhes, conflitos e pendências: documento da demanda no projeto.

## Fase 14 (10/10/2026): corpus ampliado (117 servidores) e entrada automática

- Entrada única: pasta, .zip ou arquivos soltos. A página separa ficha, CTC/relatório, RBC anterior, digitalizado e e-mail pelo conteúdo, lê tudo, deduz cargo (vencimento pago × tabela, todas as fichas), especialidade (GAE/GAS pagos), ingresso e desligamento (CTC/ficha) e vai direto à conferência quando nada falta. Só digitalizados → lê por imagem sem pedir.
- Ficha antiga do sistema anterior em PDF ("FICHA FINANCEIRA" com meses por extenso).
- Comparação mês a mês e do 13º com a RBC anterior (certidão ou planilha de trabalho).
- Certidão de RBC e certidão de 13º em .docx, com os dados do cabeçalho da CTC (nome, matrícula, CPF, PIS, nascimento, mãe, referência).
- Regressão (117 servidores; certidão como gabarito, planilha da DIPROF como gabarito secundário):

| Rodada | Certidão, meses com ficha | Planilha, meses com ficha | Planilha, sem ficha |
|---|---|---|---|
| ff8535c | 3.273/4.749 (68,9%) | 599/1.534 (39,0%) | 57/606 |
| Fase 14, campos manuais | 3.272/4.749 (68,9%) | 956/1.584 (60,4%) | 164/520 |
| Fase 14, entrada única | 3.272/4.749 (68,9%) | 956/1.584 (60,4%) | 164/520 |

Entrada única em 108 casos: cargo certo em 105, especialidade em 103, ingresso no mesmo mês em 72 (25 sem CTC/data na ficha).

### Fase 14b: interface em 2 etapas

As antigas etapas 2 (ficha e rubricas) e 3 (valores a distribuir) deixaram de ser paradas: no corpus, metade dos casos não tem nada a decidir nelas. O que exige decisão (rubrica não reconhecida, valor sem mês, devolução sem período, cargo ausente, progressão por imagem) vai para o quadro "A resolver" no topo da conferência; o resto (datas deduzidas, atrasados distribuídos, passivos, lançamentos manuais, classificação das rubricas) fica em "Ajustes da RBC", recolhido. Envios separados (CTC/relatórios e ficha) ficam em "Enviar por tipo". A entrada única abre a conferência sempre que há cálculo. `--tudo` registra em `uso` o que ficaria para o usuário em cada caso.

## Fase 15 (10/10/2026): menos itens para o usuário, dois vínculos, exercício anterior e novos formatos de ficha

- **Rubricas:** regras explícitas para as rubricas que ficavam sem categoria no corpus (restos a pagar, despesa de exercício anterior sem espaço, 13,23% sobre GN/proventos, complementação de salário-mínimo, vale-refeição, devolução de INSS, custeio, gratificação por deliberação coletiva de classista, cargo em comissão por opção). A sugestão kNN continua só como sugestão: aplicada automaticamente, acertaria 75–78% mesmo com similaridade ≥ 0,9 (erra justamente nas variantes "- CM", "- JR", "GN", "TREINAM.").
- **Valores sem mês:** pagamento e estorno do mesmo valor anulam-se; VPI de ago/2016–dez/2018 paga depois (passivo de 10/2024) fica fora quando a regra "VPI pela tabela" já pôs a VPI nesses meses; atalho "Incluir em <mês>" no próprio item. Resolvidos ficam listados em "Ajustes da RBC".
- **Devolução sem período:** só pede decisão quando marcada como integral (a da ficha sem período entra desmarcada).
- **Dois vínculos:** a progressão deduzida da ficha guarda o cargo de cada período (vencimento de outro cargo em ≥ 6 meses seguidos); a esperada e os meses sem vencimento usam a tabela do cargo do período; nota na conferência.
- **Exercício anterior com contribuição** (regra `passivoTabela`, padrão ligado): "D.E.A.RRA-ATIVOS"/"DESPESA EXERCICIO ANTERIOR" sem qualificador, quando a contribuição do mês do pagamento mostra PSS sobre o valor, é distribuído nos meses de origem pela diferença para o nível pago depois (até 3 meses antes do pagamento).
- **Fichas:** SGRH anual em PDF ("FICHA FINANCEIRA - AAAA", Telerik), CSJT "por folha" com ponto decimal (Jasper), exportação do banco antigo ("SQL Results", descrição pela tabela `rubricas_cod.json`); linhas de anotação no meio da planilha longa são ignoradas.
- Regressão (corpus remontado, 110 casos com cálculo): 4.761/7.624 → 4.841/7.657 meses iguais; 85 ganhos, 5 regressões explicadas no documento da fase (ficha nova lida onde a tabela acertava por acaso). Entrada única = campos manuais.
