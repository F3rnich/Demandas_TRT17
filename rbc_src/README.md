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

### Fase 15b (11/10/2026): teste com processo novo (RRC de 2019)

- CTC do SEI/SGP com fonte sem tabela de caracteres (texto "deslocado": `6(59,'25` = SERVIDOR; dígitos como caracteres de controle; tabela de funções em Calibri por número de glifo): `relatorios.js` → `decodificarFonte(pages)`, chamado ao abrir qualquer PDF (só age quando ≥ 10% dos trechos têm caracteres de controle).
- Relatório de remuneração de contribuição do SGRH (planilha .xlt: Mês, Classe, Vencimento, Função, GAJ, VPI, AQ, Remuneração, com o mês repetido = 13º) lido como ficha (`parseRelRemuneracao`), depois das fichas de verdade; o 13º vem da própria linha do relatório.
- Aceita .xlt, .xltx e .xlsm. RBC anterior em planilha: mês repetido = linha do 13º.
- Textos: servidor ou magistrado; magistrado desativa a especialidade; certidão de RBC com "NOME DO(A) MAGISTRADO(A)".
- Sem regressão completa (corpus apagado do computador de trabalho); as mudanças só agem nos formatos novos.
- VPI: a regra "VPI pela tabela" também completa o mês pago só em parte (07/2016, absorção indevida a partir de 21/07); devida até 31/12/2018 (STJ, AgInt no REsp 2.085.675, trânsito em 17/06/2024). VPI sem mês nesses meses fica em "Resolvidos pela calculadora".
- CTC da SEINFO (2019): nome e matrícula na linha abaixo de "SERVIDOR: SEXO: MATRÍCULA:"; número "N 21/2019" sem o "º".
- Certidão: chefe da DIPROF e secretária de Gestão de Pessoas preenchidos por padrão (o que o usuário digitar fica lembrado no navegador).

### Fase 15f (11/10/2026): declaração intrarregime de 2025 digitalizada pelo SEI

- PDF digitalizado com o carimbo de rodapé do SEI ("<título> SEI … / pg. N") conta como imagem (`charsTexto`); se o carimbo ou o nome do arquivo indica CTC/DTC, é lido por imagem **automaticamente mesmo com ficha**, quando não há CTC em texto (dados da certidão, funções, substituições e progressão).
- Modelo da Portaria MPS 2.010/2025 ("DADOS FUNCIONAIS 1º/2º PROVIMENTO"): início = 1º exercício; fim = fim do último período; cargo e especialidade do último provimento; progressão com o cargo de cada provimento; exoneração da certidão = "data de encerramento/afastamento" do último provimento.
- Funções na seção "N - FUNÇÕES" (ou, sem o título, linhas "NOME FC-04 (em substituição) dd/mm/aaaa a dd/mm/aaaa"); "(em substituição)" vai para Substituições.
- Esperada: substituição de quem é titular de função = diferença para a função substituída (Lei 8.112, art. 38, §1º); depois de `fcAte`, a substituição esperada vai para o mês seguinte (a folha paga após a frequência).
- Progressão da CTC lida por imagem (com classe/padrão) passa pela mesma conferência com o vencimento pago que o relatório em texto, com o cargo de cada linha. A referência do relatório é mantida quando o vencimento pago é o dela na tabela anterior (reajuste pago com atraso, ex.: Lei 12.774 em 2013) ou quando algum mês do período pagou o vencimento dela (progressão paga com atraso); só é "ajustada pelo vencimento pago" se a ficha nunca pagou aquela referência.
- Textos da entrada automática: rodapé da etapa 1 orienta pelo estado (sem arquivos / lendo / o que faltou deduzir) e o passo 1 só fica em alerta depois de haver arquivos; RBC anterior digitalizada é ignorada com motivo (antes ia para "ler por imagem", que a leria como progressão); CTC lida por imagem aparece como "CTC / relatório" na lista; nota de dois provimentos com cargos e datas da declaração.

### Fase 15g (11/10/2026): Big Grid de 2025 e CTC da SEINFO com rótulo centralizado

- Ficha "Big Grid" com cabeçalho " Valor " (espaços): chaves aparadas antes da leitura (antes, todos os valores saíam zerados).
- Funções da CTC com o rótulo no meio da lista de períodos ("FC-05 CHEFE DE SEÇÃO em Substituição" entre 20 datas): se há datas antes do primeiro código, cada linha vai para o rótulo mais próximo; senão, para o anterior.
- Substituição no mês seguinte só quando a ficha não traz competência própria (Big Grid tem "Ano/Mês" × "Ano/Mês Folha" e já põe o valor no mês do exercício).
- Filiação "PAI e MÃE" quebrada em linhas: o " e " decide; matrícula com espaço ("308.17. 1665") mantém os pontos; exoneração sem data legível = dia seguinte ao fim do período.
- AQ digitalizado (nome com AQ/AQP/qualificação) é ignorado com motivo, em vez de oferecer leitura como progressão.

### Fase 15h (11/10/2026): dois períodos na CTC, progressão retificada, planilha da DIPROF com ficha de terceiro

- **Intervalo sem contribuição:** CTC com dois períodos ("De 18/11/1999 a 27/07/2014 … De 20/12/2016 a 20/08/2024") → período do 1º início ao último fim, `lacunas` entre eles (`RBC.calcular(opts.lacunas)`, `esperada(dados.lacunas)`): meses inteiros no intervalo ficam fora; mês de borda é pro rata; 13º só com meses de 15+ dias.
- **Padrão devido** (regra `padraoDevido`, padrão ligado): progressão ou reajuste pago com atraso — vencimento pago é valor de tabela de outro padrão ou da tabela anterior, e a progressão vem de relatório/CTC conferida — a RBC usa vencimento e GAJ do padrão devido (planilha "Progressão real" da DIPROF; confirmado ao centavo em nov/2008–2012 deste caso). Com CTC que informa prescrição/efeito financeiro ("prescritos os direitos … anterior a 11/11/2008"), só a partir dessa data; antes, a esperada usa a progressão paga (da ficha).
- CTC: linhas "(REVOGADA)" marcadas como revogadas; duas CTCs na pasta → vale a mais recente (retificada, data ou número); VPNI "concedido judicialmente … efeitos financeiros a partir de janeiro de 2006" → judicial a partir do efeito; quintos sem tabela própria usam n/5 = 2n/10; data da certidão = última assinatura.
- Planilha de trabalho da DIPROF ("Relação de Remuneração de Contribuição", aba "Progressão real") é RBC anterior mesmo com aba de ficha (veio com a ficha de outra servidora).
- Ficha exportada com número redondo de linhas (3.000…) → aviso de exportação cortada.
- Rubrica "AQ-TS Ad Quali Técnico c/ curso superior" = AQ (a regra de "CURSO" a ignorava).
- Mês de início de período sem remuneração, pago na folha seguinte como D.E.A. com PSS → o valor (e o PSS) vão para o mês de origem. Início da opção pela FC integral (vencimento parcial, mês seguinte sem vencimento) → cargo efetivo pela tabela.
- Conferência por ano só com meses com ficha; ano sem ficha não é verificável. VPNI de mês sem ficha não duplica a VPNI judicial da esperada.

### Fase 15i (11/10/2026): RBC antiga (1996–2004), segurança, CTC com funções centralizadas

- Funções da CTC: rótulo sem datas na própria linha também indica leiaute centralizado; empate de distância vai para o rótulo sem datas; "FC-04 em" + "Substituição" na linha seguinte = substituição.
- "DEDUÇÃO VPI … (S. JUD. 13,23%)" com valor positivo na ficha entra como redução (a DIPROF tira a VPI nos meses com 13,23%).
- `limitarRetroativos`: retroativo distribuído que deixa as parcelas de tabela do cargo efetivo (VB, GAJ, APJ, DIF2886, GEXTRA, ATS) acima da tabela devida no mês volta à tabela, quando o padrão está confirmado (vencimento original ou final = tabela). Casos: GAJ de 07/2004 paga por 12 meses; reestruturação da Lei 10.475 (06/2002) com a estrutura antiga somada à nova.
- Modo tabela (`tabelaAte`): cargo efetivo, função, substituição e VPNI vêm só da tabela; parcelas antigas que só existem na ficha (gratificação extraordinária, representação, substituição paga no mês seguinte) não se somam.
- Comparação: mês até 2001 em que a RBC anterior é a remuneração pela tabela → causa "ajuste a regra Tabela até". No caso testado, "Tabela até" = 11/1999 reproduz 338/348 (padrão 06/1994: 301/348).

### Fase 15j (11/10/2026): anotações da DIPROF conferidas

| Anotação | Situação na calculadora |
|---|---|
| 1) PSS sobre função/substituição até 11/1998 | `fcAte` = 1998-11 |
| 2) PSS sobre anuênio/GATS desde 04/2002 | `atsDesde` = 2002-04 |
| 3) PSS sobre 13º desde 2003 | `gnDesde` = 2003 (antes: certidão complementar) |
| 4) VPI 59,87: 05/2003–12/2014 (a anotação diz 03/2003; a planilha da DIPROF começa em 05/2003, Lei 10.698); 01/2015–03/2016 sem VPI (13,23% e dedução 1330/1331); 04/2016–12/2018 pela tabela (passivo de 10/2024 fora); no 13º desde 2008 | base + `vpiTabela` + `gnSemVPIAte` = 2007; dedução positiva entra como redução |
| 5) VPNI Anajustra 15/12/1999–31/12/2005 sem PSS | esperada: `vpniJudSemPSS`; RBC segue a ficha nesse período (VPNI pela tabela suspensa) |
| 6) VPNI SINPOJUFES anterior a 15/12/1999 | **novo:** aviso na entrada para pedir a informação do processo |
| 7) Divisor = dias do mês desde 01/2018 | **corrigido:** era 12/2017 |
| 8) PSS sobre GAE desde 12/2008 | **novo:** regra `gaeDesde` = 2008-12 (antes, GAE incidia sempre) |
| 9) GAS com restituição 16/04/2014–30/10/2019 | GAS fora da RBC; **causa por ano** só conta PSS sobre GAS até 10/2019 e identifica a restituição |
| 10) AQ por VR desde 01/2026 | esperada usa VR desde 2026 |
| Folhas de URV com rubrica genérica de exercício anterior (2001.2.11, 2001.3.11, 2001.12.16, 2002.9.7, 2002.12.15) | **novo:** não são passivo (o 11,98% entra pelo ajuste mensal) |
| Tabela de nomes de função → FC | **novo:** CTC sem código usa a tabela (Assistente Secretário FC-5 … Auxiliar Especializado FC-1) |
- Comparação (Fase 15j): jan–out/2013 com a RBC anterior igual a nov/2012 → causa "a RBC anterior manteve os valores de 2012: a folha pagou a tabela da Lei 12.774 com atraso" (RRC de 2017, planilha "PAGO"; as RBCs de 2024–2025 usam o padrão devido).

### Fase 15k (11/10/2026): mapa "Mês a mês" para conferência

- Seletor de modo: **RBC anterior** (padrão quando há anterior), **Contribuição** (padrão sem anterior) e **Pago × esperado** (substitui o antigo pontinho de divergência).
- Cada célula mostra a RBC do mês em valor inteiro (oculto em telas < 1000 px); triângulo azul no canto = mês ajustado pela calculadora (ajuste, tabela, sem ficha, borda de período).
- Coluna do ano: resumo do modo (confere / diferença em R$ / meses iguais / 13º ≠) e Σ dos meses + 13º.
- Dica ao passar o mouse/foco: RBC, esperada, anterior e diferença com provável causa, PSS descontada × sobre a RBC, itens pago × esperado e ajustes. Clique abre o detalhe.

### Fase 15l (11/10/2026): causas da comparação e progressão confirmada pela planilha da DIPROF

- Causas: VPI tirada pelas RRCs antigas desde 21/07/2016 (absorvida pela Lei 13.317; jul/2016 com 20/30); mudança de tabela em 21/07/2016 dividida por 30 na RRC (sem ficha); pro rata do desligamento combinado com outra causa; 13º aponta o último mês cheio com causa.
- `lerRBCPlanilha` lê a coluna CLASSE/PADRÃO (`refs` por mês; "A-1 até 01/A-2" traz as duas).
- `confAnterior`: sem ficha, linha de progressão da CTC lida por imagem fica "confere com a planilha da DIPROF" (origem `anterior`) quando os meses inteiros do período trazem só aquela referência; senão continua incerta.

### Fase 15m (11/10/2026): regressão completa depois das Fases 15d–15l

Corpus remontado (3 pastas do processo SEI 0000775-34.2024: 76 casos com gabarito, 75 com cálculo; as pastas `RBC/` e `RRC/` da Fase 15 não vieram). Base: página de `ac367ce` (Fase 15, última regressão completa), mesma bateria.

| Rodada | Meses iguais | Certidão, com ficha | Certidão, sem ficha | 13º |
|---|---|---|---|---|
| `ac367ce` (base) | 3.410/5.209 | 2.621/3.543 (74,0%) | 368/638 (57,7%) | 237/377 |
| antes das correções abaixo | 3.589/5.209 | — | — | 260/377 |
| Fase 15m | **3.633/5.209** | **2.775/3.543 (78,3%)** | **423/638 (66,3%)** | **260/377** |

Entrada única (`--tudo`) = campos manuais nas duas versões. Itens para o usuário: valores sem mês 116 → 109; meses com pago ≠ esperado 3.913 → 2.830.

Correções de regressões (60 meses que batiam na base e deixaram de bater → 5):
- **Modo tabela (`aplicarTabelaAntiga`):** função/substituição/VPNI da ficha só saem quando a CTC/relatório registra a função ou VPNI naquele mês **e** a tabela tem o valor; senão fica a da ficha (casos de 1991–1994 sem tabela de FC).
- **`limitarRetroativos`:** não limita o retroativo que o motor distribuiu como diferença de nível (`fonteNivel`, progressão paga com atraso) quando o vencimento final fica acima da tabela do mês.
- **Exercício anterior com contribuição × padrão devido:** meses já postos no padrão devido não recebem de novo o vencimento/GAJ; a distribuição para no primeiro mês antes deles.
- **GAE antes de 12/2008 (`gaeIncidenciaFicha`):** entra quando a contribuição descontada no ano mostra PSS sobre ela (oficial com PSS sobre a GAE desde 02/2008); nota nas regras.

Regressões que ficam (5 meses, explicadas): pro rata com divisor 30 em RRC antiga sem ficha (2000-02, 2003-02; a calculadora usa os dias do mês — pergunta aberta à DIPROF); fim de período em 07/2012 com a DIPROF usando 22/31; 03/2009 com retroativo que a DIPROF manteve; 07/2016 com VPI 20/30 (os outros 6 casos do corpus usam a VPI cheia).

### Teste rápido (12/10/2026)

`node rbc_src/testes/smoke.js`: abre a página gerada, calcula um caso sintético (técnico 05/2013–03/2017, sem ficha, AQ e 13,23%), confere jun/2013, jan/2015 e jan/2017 com a RRC de 2017, usa o mapa (modos, dica, detalhe), baixa Excel, certidão .docx e escolhas salvas, verifica rolagem em 800 px e erros de JavaScript. Não precisa de corpus; rodar depois de cada `build_html.js`. Também testa o rótulo e o aviso de versão (página servida por http) e a leitura de uma ficha sintética em planilha longa (analista A-1, jan–jun/2012: cargo deduzido, R$ 6.611,39 por mês, contribuição confere). Também testa o ingresso deduzido da ficha (exercício em 18/01/2012, janeiro pago por 13/30). 28 verificações; sai com código 1 se alguma falhar.

### Versão e CI (12/10/2026)

- `build_html.js` grava a versão na página (hash de 8 caracteres do conteúdo + data do build; rebuild sem mudança mantém a data) e em `rbc_versao.json`, na raiz.
- A página mostra "versão de DD/MM/AAAA · id" no topo. Aberta pelo site, consulta `rbc_versao.json` na abertura e a cada 30 min; se o id mudou, mostra o aviso "Há uma versão mais nova" com botão que recarrega com `?v=<id>` (fura o cache).
- `.github/workflows/calculadora_rbc.yml`: a cada push que toque a calculadora, confere se a página publicada corresponde ao código-fonte e roda `smoke.js`. Falha = X vermelho no commit e e-mail do GitHub. A publicação do Pages é separada (pela branch): o teste avisa, não bloqueia. Para bloquear, mudar a fonte do Pages para "GitHub Actions" e publicar por workflow depois do teste.

### Ingresso deduzido da ficha e regressão em um comando (12/10/2026)

- **Ingresso sem CTC/declaração (`deduzirIngresso`):** quando a data de exercício não veio de documento, o dia sai do vencimento proporcional do primeiro mês da ficha comparado ao do mês seguinte (fração × divisor do mês = número inteiro de dias, tolerância 0,05). A data entra só no cálculo (`S.iniAuto`), não no campo, e a conferência mostra o aviso "Ingresso deduzido da ficha … confira". Efeito no corpus (12/10/2026, `--tudo`, 31 casos sem ingresso por documento): deduzido em 4, certo em 3; o errado era de 1994 (ficha começa depois do ingresso), daí a trava: só a partir de 1995. Placar mensal inalterado (3.633/5.209), porque a regressão preenche o ingresso do gabarito; o ganho é para o usuário, que deixa de digitar a data. `regressao.js` passou a registrar `auto.iniAuto`.
- **`pipeline/rodar_regressao.sh <pasta_com_o_corpus> [commit_base]`:** copia o corpus, converte .doc/.odt, roda o pipeline inteiro, a regressão da versão atual e, se pedido, a do commit base (worktree), e imprime o placar e os ganhos/regressões por caso. `TUDO=1` roda também pela entrada única. Os scripts do pipeline passaram a achar o repositório por `RBC_REPO` (padrão `/home/claude/demandas_trt17`) e criam `recs/` sozinhos.

### Guia de uso (12/10/2026)

- Fonte: `rbc_src/guia/guia_rbc.md`; página: `python3 rbc_src/guia/build_guia.py` → `guia_rbc.html` na raiz (precisa de pandoc). Link "Como usar" no topo da calculadora; registrado em `checks.json`; o teste rápido confere o link (29 verificações).
- Ao mudar a calculadora de modo que o usuário perceba (avisos, botões, mapa, regras), atualizar o guia no mesmo envio.
