# Demandas_TRT17 — hub de painéis analíticos da SGP

Hub estático publicado em <https://f3rnich.github.io/Demandas_TRT17/>.
HTML/SVG/JS puro, sem framework nem build step.

Este README cobre o **pipeline de dados de força de trabalho** (painéis 6 a 12).
Os painéis colaborativos (1, 2, 3, 15) gravam direto no Firestore e não dependem
de nada aqui.

---

## Regra que não se negocia

A base de pessoal contém CPF, nome, nascimento, deficiência e doença grave.
**O repositório é público.** A base nunca entra no controle de versão — o
`.gitignore` bloqueia todas as extensões de planilha, mas a barreira real é o
procedimento: processar localmente e publicar apenas o JSON agregado, com
supressão k-anonimato k=5 aplicada na origem pelo `build_paineis_forca.py`.

---

## Configuração (uma vez só)

1. Clonar o repositório na pasta de trabalho:

   ```
   cd %USERPROFILE%\Downloads
   git clone https://github.com/F3rnich/Demandas_TRT17.git Build
   ```

2. Gravar o token na variável de ambiente do usuário (sem aspas):

   ```
   setx GITHUB_PAT <token>
   ```

   Fechar e abrir o CMD depois. O token nunca vai para arquivo.

3. Dependências:

   ```
   pip install pandas openpyxl odfpy numpy
   ```

   `odfpy` só é necessário para bases em `.ods`. Sem ele, o script converte via
   LibreOffice headless, o que funciona mas é mais lento.

---

## Atualização mensal

1. Copiar a base para a pasta `Build`.
2. Duplo clique em `ATUALIZAR PAINEIS.bat`.
3. Conferir o resumo na tela e responder `s` quando perguntar se publica.

O `.bat` roda `git pull` antes, então a pasta se mantém sincronizada com o repo
sozinha.

### A base precisa ser a acumulada, não o recorte do mês

Os painéis 6, 7 e 10 são séries temporais e são reconstruídos **do zero** a cada
execução, sobre as ~139 competências desde 2015-01. Não é possível anexar um mês
a um JSON pronto: o estimador Kaplan-Meier do painel 10 recalcula o conjunto em
risco sobre toda a história, e correções retroativas na origem só chegam aos
painéis por rebuild completo. O script aborta se detectar menos de 12
competências.

### Estrutura esperada

Aba `dados` com as colunas: `REFERENCIA`, `MATRICULA`, `TIPO_SERVIDOR`,
`SITUACAO_FUNCIONAL`, `CARGO`, `RAÇA`, `SEXO`, `IDADE`, `ESCOLARIDADE`, `AREA`,
`CODIGO_COMISSAO`, `NOME_COMISSAO`, `VALOR`, `UNIDADE_ADMINISTRATIVA`.

Aba `Base unidades` com `UNIDADE ADMINISTRATIVA` e `GRAU`, usada para mapear o
grau de jurisdição. A coluna `GRAU` da aba `dados` não é usada: fica sem match em
quase todo o histórico.

`IDADE` precisa ser calculada a partir de `REFERENCIA`, nunca de `TODAY()`.
`ESFERA`/`GRAU` devem vir de join contra `Base unidades` — `XLOOKUP` não
sobrevive ao LibreOffice.

---

## O que o `atualizar.py` bloqueia antes de publicar

| Verificação | Por quê |
|---|---|
| Abas que são link externo | Conteúdo em cache, procedência incerta |
| Menos de 12 competências | Recorte mensal em vez da base acumulada |
| Colunas faltando | O build quebraria no meio |
| `IDADE` constante no histórico | Ancorada em `TODAY()` — painel 8 sairia errado |
| `AREA` × `UNIDADE_ADMINISTRATIVA` divergentes na EJUD | Painéis 6 e 12 mostrariam números diferentes |
| Histórico retroativo alterado | Só a competência nova deveria mudar |
| Painéis 6 e 12 discordando | Erro de classificação na base |

A comparação retroativa baixa o JSON publicado e confere competência a
competência. Se não conseguir baixar, o deploy é bloqueado: sem essa conferência
não há como afirmar que o histórico permaneceu íntegro.

---

## Scripts

| Arquivo | Função |
|---|---|
| `ATUALIZAR PAINEIS.bat` | Ponto de entrada. `git pull` + `atualizar.py` |
| `atualizar.py` | Encadeia validação, build, comparação e deploy |
| `diagnostico.py` | Inspeção isolada da base, sem gerar nada |
| `build_paineis_forca.py` | Agrega a base e gera `dados_paineis_forca.json` (k=5) |
| `deploy.py` | Commit atômico multi-arquivo via Git Data API |
| `validate_checks.py` | Valida marcadores obrigatórios/proibidos por arquivo |
| `checks.json` | Manifesto de integridade |

### Convenções

`EJUD_RE` é definida **uma única vez**, em `build_paineis_forca.py`. Qualquer
script que precise identificar unidades da Escola Judicial deve importá-la, nunca
recopiar a expressão. A regex cobre a Escola Judicial e os núcleos de capacitação
de magistrados e de servidores; uma cópia desatualizada já produziu divergência
entre os painéis 6 e 12.

Painéis 1 a 5 podem mencionar "UAE" no título. Painéis 6 a 16 são exclusivamente
SGP.

---

## Deploy e verificação

`deploy.py` roda `validate_checks.py` antes e aborta se falhar (use `--force`
para ignorar). O commit é atômico via Git Data API.

Confirmação de publicação sempre pela Contents API com o SHA do commit:

```
https://api.github.com/repos/F3rnich/Demandas_TRT17/contents/<arquivo>?ref=<sha>
```

Nunca pelo CDN ou `raw.githubusercontent.com` — o cache atrasa e mostra estado
antigo. "Commit OK" não significa publicado.

Se o build do Pages travar com "Deployment failed, try again later", basta
reenviar com um commit vazio; o `deploy.py` já faz isso automaticamente. O PAT
não tem escopo `pages:write`, então `POST /pages/builds` retorna 403.

---

## Pendências conhecidas

- **Art. 6º da Res. CSJT 296/2021** usa denominador proxy (postos ocupados em vez
  de cargos efetivos autorizados, que incluem vagos), o que superestima a razão.
  O painel 12 não emite veredito de conformidade por isso. Substituir pelos
  "Cargos Efetivos Vagos" do portal de transparência (arquivos a partir de
  jan/2022, formato `.xlsx` apesar da extensão `.pdf`).
- **Painel 10**: a cauda da curva Kaplan-Meier chega a `n=5`, o limiar de
  supressão. Tratar com cautela em comunicação pública.
