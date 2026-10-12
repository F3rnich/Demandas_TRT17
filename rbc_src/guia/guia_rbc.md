A calculadora monta a RBC a partir da pasta do processo e mostra onde ela pode estar errada; a decisão e a assinatura continuam com a DIPROF. Os arquivos são lidos no próprio computador e não saem dele.

[Abrir a calculadora](calculadora_rbc.html)

## Antes de começar: o que pôr na pasta

Junte numa pasta tudo o que veio no processo. A calculadora separa os arquivos sozinha pelo conteúdo, então não é preciso renomear nada.

| Documento | Formatos lidos | Para que serve |
|---|---|---|
| Ficha financeira | Planilha do sistema antigo (.xls), Big Grid do FolhaWeb, PDFs do FolhaWeb, do SGRH e do CSJT, ficha antiga em PDF, relatório de remuneração do SGRH (.xlt) | Valores pagos e contribuição descontada, mês a mês. É a base da RBC |
| CTC ou declaração de tempo | PDF em texto ou digitalizado pelo SEI (lido por imagem) | Nome, matrícula, períodos, progressões, funções, VPNI, teto |
| Relatórios do RH | Progressão, funções e substituições, VPNI (PDF) | Completam ou conferem o que a CTC traz |
| RBC anterior (se houver) | Certidão em .docx ou PDF em texto; planilha de trabalho da DIPROF (.xls) | Comparação mês a mês com a RBC nova |

- Pode arrastar a pasta inteira, um .zip ou arquivos soltos. E-mails e documentos sem relação com a RBC são ignorados e listados como "ignorados".
- Sem ficha financeira a calculadora ainda funciona: monta a RBC pela tabela de remuneração, com a classe e o padrão da CTC. Nesse caso o resultado depende do que você informar (veja "Quando desconfiar").
- CTC digitalizada leva alguns minutos para ser lida por imagem. A barra inferior mostra o andamento.

## Passo a passo

1. **Abra a página e confira a versão.** O topo mostra "versão de DD/MM/AAAA". Se aparecer a faixa "Há uma versão mais nova", clique em **Recarregar agora** antes de começar.
2. **Arraste a pasta do processo** para a página (ou use **Escolher uma pasta**). Na etapa 1 ("Arquivos e dados") a calculadora lê tudo e preenche cargo, especialidade, ingresso e desligamento. Se nada faltar, ela abre a conferência sozinha.
3. **Resolva o quadro "A resolver"**, no topo da etapa 2. São as únicas decisões que a calculadora não toma. Leia também o aviso "Antes de emitir, confira", quando houver.
4. **Confira o resultado** no mapa mês a mês e, se houver RBC anterior, na tabela de comparação com a provável causa de cada diferença.
5. **Emita.** Confira os campos da certidão (nome, matrícula, mãe, PIS, CPF, datas, assinantes), baixe a certidão (.docx) e a RBC em Excel, e salve as escolhas.

Duas áreas ficam recolhidas e normalmente não precisam ser abertas:

- **Ajustes da RBC:** tudo o que a calculadora deduziu ou distribuiu sozinha (datas, atrasados, exercício anterior, lançamentos). Abra quando quiser entender um mês.
- **Regras de cálculo (padrão DIPROF):** as regras das anotações da DIPROF (função até 11/1998, anuênio desde 04/2002, 13º desde 2003, divisor, teto etc.). Só altere com orientação da chefia; o que for alterado aparece nas notas da planilha.

## O quadro "A resolver" e os avisos

Enquanto houver item no quadro, a barra inferior mostra "Há pendências antes de gerar". Cada item tem um botão que leva ao lugar da correção.

| Item | O que significa | O que fazer |
|---|---|---|
| Cargo não informado | A calculadora não conseguiu deduzir o cargo pelo vencimento pago | Escolher o cargo na etapa 1 |
| Linhas da progressão com classe/padrão a conferir | Progressão lida por imagem que não pôde ser confirmada nem pelo vencimento pago nem pela planilha da DIPROF | Conferir classe e padrão na etapa 1, contra a CTC |
| Rubricas não reconhecidas | Rubrica da ficha sem regra conhecida | Escolher a categoria (vencimento, função, não entra etc.); a sugestão vem marcada |
| Valores pagos sem mês de referência | Atrasado ou exercício anterior sem competência de origem | Usar "Incluir em ‹mês›", distribuir por período ou desconsiderar |
| Devolução de contribuição sem período | Devolução marcada como integral sem dizer de quais meses | Informar o período ou desmarcar "integral" |

Avisos que não bloqueiam, mas pedem atenção:

- **Sem ficha: AQ e 13,23%.** A CTC não traz o adicional de qualificação nem o 13,23%. Se o servidor tinha direito, lance nas tabelas da etapa 1. Sem isso, um caso sem ficha pode dar quase todos os meses diferentes da RBC anterior.
- **Ingresso deduzido da ficha.** Sem CTC com a data de exercício, a calculadora deduz o dia pelo vencimento proporcional do primeiro mês. Confira com o processo; se for outro, informe na etapa 1.
- **Datas a confirmar.** Atrasados distribuídos por parte do mês (início ou fim de período). Confira com o processo.
- **CTC lida por imagem.** Confira nome, matrícula e períodos nos campos da certidão.
- **VPNI SINPOJUFES anterior a 15/12/1999.** Peça a informação do processo judicial.
- **Ficha cortada.** A ficha não cobre todo o período da CTC; os meses sem ficha saem da tabela.

## Conferência: o mapa mês a mês

Cada linha do mapa é um ano e cada quadrado, um mês, com a RBC do mês em reais (em telas estreitas só as cores). O último quadrado é o 13º, e a coluna da direita resume o ano e soma meses + 13º. Os botões acima do mapa trocam o que as cores mostram:

| Modo | Pergunta que responde | Cores |
|---|---|---|
| **RBC anterior** (abre por padrão quando há anterior) | A RBC nova bate com a certificada? | Verde = igual; tracejado = diferente, com causa provável identificada; laranja = diferente sem causa; cinza = mês fora da anterior |
| **Contribuição** | A contribuição descontada bate com a calculada sobre a RBC? A conferência vale para o ano, porque atrasados são descontados no mês em que são pagos | Verde = ano confere; laranja = ano com diferença; cinza = não verificado ou sem ficha |
| **Pago × esperado** | O que a ficha pagou é o que a CTC e as tabelas mandavam? | Verde = igual; laranja = parcela diferente do esperado |

- **Triângulo azul no canto** = mês que a calculadora ajustou (atrasado distribuído, valor pela tabela, mês sem ficha, início ou fim de período). Não é erro; é onde vale olhar primeiro.
- **Passe o mouse** num mês para ver RBC, esperada, RBC anterior e diferença com a provável causa, contribuição descontada × calculada e os ajustes. **Clique** para abrir a composição completa.

**Comparação com a RBC anterior.** Abaixo do mapa, a tabela lista só os meses diferentes, com a provável causa, e termina com um resumo por causa e o 13º. As causas mais comuns: AQ ou 13,23% não informados (casos sem ficha), VPI de 2016 a 2018 (a calculadora segue a decisão do STJ; RRCs antigas tiraram), pro rata com divisor 30 em RRCs antigas, padrão devido × valor pago. "Sem causa identificada" pede análise do mês.

## Quando desconfiar do resultado

Na última regressão (75 RBCs da DIPROF), a calculadora acertou 78% dos meses nos casos com ficha e 66% nos casos sem ficha, contra a certidão emitida. A maior parte das diferenças cai em pontos que dependem de decisão da DIPROF. Redobre a conferência nestes casos:

- **Sem ficha financeira.** A RBC sai toda da tabela; AQ, 13,23% e função só entram se informados. O mês incompleto usa os dias do mês; RRCs antigas usavam 30.
- **Períodos de 1991 a 1994.** A prática da DIPROF para a função variou de mês a mês; a calculadora acerta de 12 a 51 meses por caso.
- **Períodos de 1994 a 1999.** A RBC certificada pode ter usado a tabela, não o pago. Se a comparação apontar "ajuste a regra Tabela até", siga a orientação da chefia.
- **Progressão paga com atraso.** A calculadora usa o padrão devido; RRCs antigas usaram o pago.
- **CTC lida por imagem.** Confira períodos, progressões e funções com a CTC; a leitura por imagem pode errar um dígito.
- **Qualquer mês "sem causa identificada"** na comparação ou **ano laranja** no modo Contribuição.

Em caso de dúvida sobre um mês, abra a composição (clique no mês) e confira com a ficha. Se a calculadora estiver errada, anote o processo e o mês e envie a Leonardo, com a pasta, para correção.

## Emitir e guardar

| Botão | O que gera | Observação |
|---|---|---|
| Baixar certidão (.docx) | Relação das bases de cálculo no modelo da DIPROF, com os dados da CTC | Confira os campos antes; o documento é editável no Word |
| Baixar certidão de 13º (.docx) | Certidão complementar do 13º anterior à incidência (antes de 2003) | Aparece só quando há esse período |
| Baixar RBC em Excel | Planilha no modelo da DIPROF, com abas RBC, Conferência PSS, Esperada, Esperada × paga, Ajustes e Rubricas | Junte ao processo como memória de cálculo |
| Salvar escolhas para refazer depois | Arquivo .json com as decisões tomadas (rubricas, distribuições, regras, dados informados) | Guarde junto com a pasta; com "Abrir escolhas salvas" e a mesma pasta, o cálculo volta igual |
| Limpar dados | Apaga tudo da página | Use antes de começar outro processo |

- **Registre a versão.** Anote no processo a versão mostrada no topo ("versão de DD/MM/AAAA · código"). Se a calculadora for corrigida depois, dá para saber com qual versão a RBC foi feita.
- **O cálculo não fica salvo no navegador.** Ao fechar a página, ele se perde (só os nomes dos assinantes da certidão são lembrados); salve as escolhas antes de interromper o trabalho.
- **Dúvidas ou erros:** Leonardo Felipe Di Donato (SGP).
