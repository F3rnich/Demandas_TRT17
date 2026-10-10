# Guia para a IA — cálculo de RBC (TRT-17 / DIPROF)

Este guia acompanha a base `Base_Remuneracao_RBC_TRT17.xlsx` (ou os CSVs equivalentes, separador `;`, UTF-8). Ele diz à IA o que há na base, como consultá-la e o que **não** fazer. Carregue os CSVs e este arquivo como conhecimento do Projeto.

## 1. O que é a RBC aqui

RBC = Relação das Remunerações de Contribuição que acompanha a Certidão de Tempo de Contribuição (CTC). A Portaria MPS 154/2008 (art. 6º, X, e Anexo II) exige a relação **mês a mês, desde a competência julho/1994** (ou desde o início da contribuição, se posterior), e define remuneração de contribuição como o valor usado como base de cálculo da contribuição do servidor ao RPPS naquela competência (art. 13, parágrafo único), observada a legislação de cada época. A norma de regência atual dos RPPS deve ser conferida pela DIPROF antes do uso (a Portaria MTP 1.467/2022 consolidou as regras).

Consequência prática (correção da DIPROF, 09/10/2026): a **RBC cobre todo o período**, inclusive antes de 07/1994. Nesses meses usa a **moeda da época, sem conversão** (Cr$, CR$, URV), e as colunas de fator de conversão e remuneração em real ficam em branco. O **cálculo da média** da aposentadoria usa os dados da RBC, mas **só de 07/1994 em diante**. As tabelas da base começam em 1990.

## 2. Arquivos

| Arquivo | Para quê |
|---|---|
| `valores` | Fonte de verdade. 1 linha = 1 valor: vigência × cargo/função × referência × rubrica, com aba e célula de origem. |
| `competencias_servidor` | Mesma informação, expandida por mês (01/1990–12/2026) para cargos efetivos. **Use esta para a RBC de servidor.** |
| `competencias_magistrado` | Idem para magistrados (subsídio e parcelas). |
| `competencias_funcao` | Valores de FC/CJ por mês. Meses sem tabela aparecem como `SEM_DADO_NA_PLANILHA`. |
| `parametros_mensais` | Teto do RGPS, salário mínimo, fator da GAJ, fator de implantação GAE/GAS, VPI (R$ 59,87), VR do AQ e contribuição limitada ao teto, por mês. |
| `parametros` | Os mesmos parâmetros com vigência e base legal (inclui deduções do IR e valores do AQ). |
| `tabela_ir` | Faixas do IRRF (não entra na RBC; útil para conferências de folha). |
| `regras_incidencia` | Anotações da DIPROF sobre incidência de PSS (aba ANOTAÇÕES da planilha original). |
| `alertas` | Inconsistências da planilha original. **Consulte antes de usar qualquer competência citada ali.** |
| `rubricas`, `dicionario` | Significado dos códigos e colunas. |

## 3. Como consultar

1. Localize a linha em `competencias_servidor` por `competencia` (AAAA-MM), `cargo`, `classe` e `padrao`.
   - Até 06/1994 o cargo aparece como `NÍVEL AUXILIAR/INTERMEDIÁRIO/SUPERIOR`; de 1995 em diante, `ANALISTA/TÉCNICO/AUXILIAR JUDICIÁRIO`.
   - A numeração de padrões mudou ao longo do tempo (ex.: A-21…C-35 em 1997–2001; A-01…C-15 em 2002–2012; 01…13 a partir de 31/12/2012). **Não converta padrões entre estruturas por conta própria**: peça ao usuário o enquadramento vigente em cada período.
2. `situacao`:
   - `OK` — tabela única no mês.
   - `MUDANCA_NO_MES` — outra tabela começa no meio do mês (`nova_tabela_em`). Calcule pro rata pelos dias de cada tabela. Divisor: dias do mês do fato gerador (28 a 31) a partir de dez/2017, conforme a Res. CSJT 211/2017, art. 1º (DEJT 30/11/2017, vigência na publicação); antes, 30 dias (anotação 7 da DIPROF).
   - `VERIFICAR_VALOR` — algum valor da linha falhou na validação; mostre o alerta correspondente ao usuário e peça confirmação.
3. Ignore registros com `status = nao_usar` (ex.: "FC integral" das abas 2025/2026, calculada como FC ÷ 0,65 sem base legal).
4. Colunas de total (`TOTAL`, `TOTAL_BRUTO`, `SOMA`, `e_total = VERDADEIRO`) são subtotais da planilha. Não as some com as parcelas.
5. Sempre cite o `id`/`ids_origem` dos valores usados, para rastreio até a célula original.

## 4. Montagem da remuneração de contribuição de um servidor (por competência)

A base traz as **tabelas**. Os dados **individuais** precisam vir do usuário (assentamentos/folha):

- cargo, classe e padrão em cada período (progressões/promoções);
- adicional por tempo de serviço (anuênios/ATS, % sobre o VB);
- VPNI/quintos/décimos incorporados (função e fração);
- adicional de qualificação (títulos, cursos);
- função comissionada/cargo em comissão exercido e se houve opção pela inclusão na base;
- GAS/GAE (se Agente de Polícia Judicial / Oficial de Justiça);
- afastamentos, licenças sem remuneração, faltas, ingresso e vacância no mês;
- regime previdenciário (sujeito ou não ao teto do RGPS / previdência complementar).

Roteiro:

1. **Parcelas do cargo efetivo** — pegue na `competencias_servidor` as parcelas da época (VB, GAJ, APJ, DIF_28_86, GRAT_EXTRAORDINARIA etc.).
2. **Vantagens individuais** — calcule a partir dos dados do usuário e das tabelas (`valores` com grupo `DECIMOS_QUINTOS`, `VPNI_QUINTOS`, `VPI_13_23`; `parametros` para VPI e AQ).
3. **Regras de incidência** — aplique as anotações de `regras_incidencia`, entre elas: PSS sobre função/substituição até nov/1998; PSS sobre anuênio/GATS a partir de abr/2002; PSS sobre GAE a partir de 1º/12/2008; VPNI paga judicialmente (ANAJUSTRA, 15/12/1999 a 31/12/2005) não teve contribuição; VPI de R$ 59,87 de mar/2003 a dez/2014 e abr/2016 a dez/2018 para alguns servidores (jan/2015–mar/2016 não recebida). Para o período após a Lei 10.887/2004, a base é a do art. 4º dessa lei (vencimento do cargo efetivo e vantagens permanentes, com as exclusões ali listadas; FC/CJ só com opção do servidor). **Se uma parcela não estiver coberta por regra explícita, pergunte — não presuma incidência.**
4. **Teto** — para servidor sujeito ao teto do RGPS, a base de contribuição ao RPPS é limitada a `parametros_mensais.teto_rgps`.
5. **Proporcionalidade** — mudança de tabela, ingresso, vacância, afastamento: pro rata conforme item 3.2.
6. **Arredondamento** — 2 casas decimais por parcela e no total. Alguns valores da planilha têm mais casas (fórmulas sem arredondamento; ver alertas); arredonde e informe.
7. **Saída** — tabela mês a mês (jan–dez por ano), no formato do Anexo II, com memória de cálculo por competência: parcelas, valores, `ids` de origem, regra de incidência aplicada e pendências.

## 5. Lacunas e decisões da DIPROF (09/10/2026)

A aba `alertas` traz a coluna `situacao` (`resolvido`, `aceito`, `tratado`, `a_confirmar`) e a coluna `decisao_diprof`. Os `a_confirmar` são das tabelas de 1990–1994 e trazem uma proposta já aplicada ou uma pergunta à DIPROF; ao usar esses valores, avise.

- **Escopo:** a RBC cobre todo o período de contribuição, na moeda da época antes de 07/1994 (sem conversão). A média só considera de 07/1994 em diante.
- **Antes de 07/1994 (modelo da DIPROF, RBC de servidor com período em Cr$):** a RBC usa os valores das **tabelas** da época (classe/padrão do relatório de progressão), não os da ficha. Os reajustes eram mensais e os atrasados, frequentes, então a ficha não espelha a competência. Parcelas sem tabela na base (funções de 1991–1993, substituições) vêm da ficha ou do processo. Pro rata pelos **dias do mês** (ex.: ingresso em 12/03/1991 = 20/31). Coluna de moeda: Cr$ até 07/1993; CR$ de 08/1993 a 06/1994 (de 03 a 06/1994 os valores estão em URV, rotulados CR$ como no modelo); R$ depois. O adiantamento da Lei 8.272/91 e o abono de Cr$ 102.000 (Lei 8.622/93) entram no vencimento. A diferença de URV e o abono da MP 433/94 ficam fora.
- **Correções propostas nas tabelas antigas (a confirmar):** 1992 G30 = 261.818,12 (a fórmula somava 7.878,77 no lugar de 67.878,77); 1992 G63 = 430.567,66 (a GE da mesma linha, 731.965,02, é esse valor × 1,7); 1994 G119 = 111,49 (faltava um dígito); totais e parcelas derivadas recalculados. A aba 1990 passou a ter moeda Cr$ (NCz$ até 15/03/1990, paridade 1:1).
- **FC/CJ de 2009 a 2022:** não houve reajuste de FC. FC usa a tabela de dez/2008 até 20/07/2016; CJ usa dez/2008 até 31/12/2015 e a tabela de 01/01/2016 até 20/07/2016; a tabela da Lei 13.317/16 (21/07/2016) vale até 31/01/2023.
- **FC/CJ de 2006 a 2008 e décimos de 2006:** a tabela de funções vale o ano todo; o valor integral das FC e os décimos de 2006 valem de janeiro a dezembro.
- **Magistrados 2017–2018:** vale a tabela de 2016 (mesmos valores da Lei 13.091/2015) até 31/12/2018.
- **FC "integral" de 2025/2026:** a FC tem valor único; use a coluna de valor. A coluna "integral" (FC ÷ 0,65) tem `status = nao_usar`.
- **DAS de 1995:** o 1º bloco vale para jan–fev/1995 (valores anteriores à Lei 9.030/95); o 2º, para mar–dez/1995 (Lei 9.030/95). Ambos com 11,98%.
- **AQ:** até dez/2025, percentual sobre o vencimento (Lei 11.416/2006, art. 15): doutorado 12,5%, mestrado 10%, especialização 7,5% (não se acumulam), treinamento 1% por 120 h até 3% (cada conjunto vale 4 anos) e 5% para técnico com graduação de 21/07/2016 a 19/09/2023. A partir de 2026, Valor de Referência. Percentuais em `parametros` e `parametros_mensais`. O AQ é devido a partir da apresentação do título.
- **GAS:** criada pela Lei 11.416/2006; **não é base de contribuição** e não entra na RBC em nenhum período, inclusive de 06/2009 a 15/04/2014, quando houve desconto de PSS sobre ela. A GAE é base.
- **AQ e AQ-Treinamento na prática da calculadora:** se a ficha mostra AQ pago numa competência, o servidor tinha direito a ele; o valor devido é o da tabela da carreira (percentual sobre o vencimento até 2025; valores de referência a partir de 2026), com o nível deduzido do valor pago. O AQ-Treinamento é conferido do mesmo modo pela ficha, mas **não integra a base** (decisão da DIPROF de 09/10/2026); só o AQ de títulos entra.
- **GAJ de 12%** de jun/2002 a jun/2004: confirmada.
- **VPI (R$ 59,87):** mai/2003 a dez/2014 e abr/2016 a dez/2018; sem pagamento de jan/2015 a mar/2016. Houve outros períodos sem pagamento para alguns servidores: conferir a ficha.
- **VPI de 2015:** 12,23%, conforme a tabela.
- **2003, D102:** total corrigido para R$ 2.358,42. **Vencimentos de 2025 sem arredondamento:** aceitos.

## 6. Comportamento esperado da IA

- Responder com a competência, os valores, os `ids` e a regra aplicada. Nunca devolver só um número.
- Não estimar valores ausentes nem converter moedas por conta própria.
- Quando a pergunta depender de dado individual não informado, perguntar antes de calcular.
- Ao encontrar uma competência citada em `alertas`, reproduzir o alerta na resposta.

## 7. Modelo de pedido à IA

> Monte a RBC de [nome/matrícula], [cargo], de [MM/AAAA] a [MM/AAAA]. Enquadramentos: [classe/padrão e datas]. ATS: [% e datas]. Quintos/VPNI: [função, fração, datas]. AQ: [títulos e datas]. FC/CJ: [função, datas, opção pela inclusão na base S/N]. Afastamentos: [períodos]. Regime: [sujeito ou não ao teto do RGPS]. Use apenas a base anexada, aplique as regras de incidência e liste as pendências.
