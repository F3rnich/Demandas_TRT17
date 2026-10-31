# Rotina semanal — atualização dos atos normativos (modo assistido, sábados)

> **Desde 31/10/2026 a coleta é ASSISTIDA.** Na execução automática de 31/10 o firewall do portal bloqueou o 1º pedido (HTTP 202).
> A tarefa agendada (sábados ~9h53) agora só manda um lembrete ao Leo; ela não acessa o portal.
> A coleta acontece numa conversa com o Leo presente: ele navega pelas pastas no Chrome dele, no ritmo de uma pessoa, e o Claude
> lê o que já está carregado na aba (texto da página, DOM, respostas que a própria página buscou), **sem disparar pedidos próprios ao portal**
> (nada de `coletor_semanal.js` em série nem `fetch` à API). Se o portal mostrar desafio/CAPTCHA, quem resolve é o Leo; o Claude não.
> Roteiro do modo assistido: passo 1 e 2 abaixo; passo 3 para saber quais pastas abrir (`_rotulos` de `/tmp/alvos.json`: as pastas de 2026
> e as seções sem subpasta por ano, e as pastas-mãe para ver se surgiu pasta nova); o Leo abre uma por vez e avisa; o Claude extrai os
> documentos novos da aba e monta `/tmp/resultado.json` no formato do coletor (`pastas`, `novos`, `paginas_incompletas`, `bloqueado`);
> depois seguem os passos 5 a 8. O jeito exato de extrair da aba (DOM ou respostas de rede) fica registrado aqui após a 1ª execução.

Objetivo: trazer para o painel `dashboard_atos_normativos.html` os atos publicados na seção Legislação do portal do TRT-17
na última semana e, quando o Leo tiver baixado um PDF novo da compilação oficial, reprocessar a compilação.
Publicação é direta (decisão do Leo, 31/10/2026) quando a validação passa. Execute sem pedir confirmação, exceto nos casos de parada abaixo.

## Regras que não mudam
- O portal fica atrás de um firewall (AWS WAF). Se o coletor devolver `bloqueado` (HTTP 202, resposta vazia ou não-JSON),
  **pare a coleta**: não repita o pedido, não recarregue a página em série, não renove token, não troque de rede, não resolva CAPTCHA.
  Isso é contorno de proteção e está vedado. Só registre e avise o Leo.
- Nunca grave tokens/credenciais no repositório (ele é público).
- Mexa só nos arquivos desta ferramenta: `dados_atos_normativos.json`, `fontes/atos_normativos/*`.
- Em caso de erro no build ou na validação, **não publique**: avise o Leo com o erro.

## Passos
1. **Repositório.** `add_repo` (owner `F3rnich`, repo `Demandas_TRT17`, access `push`), clone e `cd` para ele. `pip install pdfplumber --break-system-packages` se faltar.
2. **PDF novo da compilação (opcional).** Pelo computador do Leo (ferramentas `mcp__remote-devices__*`), liste `C:\Users\leofe\Downloads`.
   Procure PDFs cujo nome case com `/atos.?normativos.*trt.?17/i`. Para cada candidato modificado depois de `meta.gerado_em` de
   `dados_atos_normativos.json`, traga-o para a nuvem (`device_stage_files`), leia a data "atualizado até dd/mm/aaaa" da 1ª página e,
   se for **posterior** a `meta.atualizado_ate`, copie para `fontes/atos_normativos/compilacao.pdf`. Se o computador não responder, siga sem PDF.
3. **Alvos da coleta.** `python3 -I incorpora_coleta_site.py alvos > /tmp/alvos.json` (≈30 pedidos, ~4 min).
4. **Coleta no Chrome do Leo** (Claude in Chrome; carregue as ferramentas numa única ToolSearch):
   - `tabs_context_mcp` → `tabs_create_mcp` → `navigate` para `https://www.trt17.jus.br/web/legislacao`.
   - `javascript_tool`: o conteúdo de `rotinas/coletor_semanal.js` seguido de `__coletaSemanal(<conteúdo de /tmp/alvos.json>)`.
   - A cada ~45 s: `javascript_tool` com `await new Promise(r=>setTimeout(r,40000)); ({fim: __coleta.fim, pedidos: __coleta.pedidos, bloqueado: __coleta.bloqueado})`.
   - Quando `fim`: `JSON.stringify(__coleta.resultado)` → grave em `/tmp/resultado.json`. Feche a aba.
   - Se o Chrome não estiver disponível (computador desligado, extensão fechada), pule para o passo 6 só com o PDF, se houver.
5. **Incorporar.** `python3 -I incorpora_coleta_site.py incorpora /tmp/resultado.json` (grava a base e imprime o resumo).
6. **Reprocessar** se houver documento novo, pasta nova ou PDF novo:
   `python3 -I build_atos_normativos.py fontes/atos_normativos/compilacao.pdf --site fontes/atos_normativos/legislacao_trt17_site.json`
   Confira: `meta.n_atos` não pode cair em relação ao valor anterior (salvo PDF novo com explicação); total de atos não pode cair.
   `python3 validate_checks.py` tem que terminar em "Tudo integro".
7. **Publicar.** `git add dados_atos_normativos.json fontes/atos_normativos/` → commit "Atos normativos: atualização semanal de DD/MM/AAAA (N novos)"
   (com as linhas de atribuição do sistema) → `git push origin main`. Confira em
   `https://api.github.com/repos/F3rnich/Demandas_TRT17/actions/runs?head_sha=<sha>` que "Validar integridade dos paineis" e
   "pages build and deployment" terminaram em `success`.
   Sem novidades e sem bloqueio: só registre o incremento (commit da base com `incrementos` atualizado é opcional; não publique se nada mudou).
8. **Relatório** (mensagem final, 3–8 linhas, português): atos novos por pasta (título curto), pastas novas, PDF novo (data), situação da coleta
   (completa / bloqueada pelo firewall / Chrome indisponível), páginas incompletas (pasta com mais de 200 documentos), commit publicado.
   Se houve bloqueio, diga ao Leo que basta abrir a página Legislação no Chrome dele em outro dia; nada a fazer agora.

## Limites conhecidos
- A coleta semanal olha só as pastas do ano corrente (e do ano anterior em janeiro) e as seções sem subpastas por ano.
  Documento novo enfiado numa pasta antiga não é visto — para isso, rodar o coletor completo (`coletor_legislacao.html`) de vez em quando.
- Alterações em documentos já existentes (novo título, arquivo trocado) não são atualizadas pelo incremento.
