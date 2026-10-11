# Pipeline de calibração (corpus → casos de teste)

Scripts que transformam as pastas de RBC da DIPROF em casos para `testes/regressao.js`. Não contêm dados pessoais; o corpus e os casos ficam **fora** do repositório.

Caminhos fixos: corpus em `/home/claude/corpus`, trabalho em `/home/claude/work` (casos em `/home/claude/work/casos`). Rode a partir de `/home/claude/work`, com os scripts copiados para lá.

## Montar o corpus
1. Copiar as pastas do Downloads de Leo (pasta "RBC - 0000775-34.2024…" com 3 subpastas, mais `RBC/` e `RRC/`) para `/home/claude/corpus`.
2. Converter `.doc`/`.odt` para `.docx`: `soffice --headless --convert-to docx --outdir <pasta> <arquivo>`.
3. `cd rbc_src/calc && npm ci && node build_html.js`.

## Ordem
| # | Script | Faz |
|---|---|---|
| 1 | `gold.py` | Gabarito: última RBC certificada (docx/PDF do SEI) → grade mês × ano |
| 2 | `gold_js.js` | Refaz os PDFs com o leitor posicional de `calc/certidao.js` (mais preciso) |
| 3 | `gold_gn.py` | 13º e certidão complementar de GN |
| 4 | `gold_xls.py` | Reserva: planilha de trabalho da DIPROF (só se o título tiver o nome da pessoa) |
| 5 | `registry.py` | Registro de pessoas × pastas × documentos |
| 6 | `dump_recs.js` | Lê as fichas com o motor da página → `recs/` (planilha longa, Big Grid, exportação "SQL Results", PDF do FolhaWeb, do sistema antigo, do SGRH e do CSJT) |
| 7 | `learn.py` | Escolhe o gabarito de cada caso e mede regras |
| 8 | `mkcasos.py` | Cria `casos/<id>/caso.json` + cópias das fichas/CTCs |
| 9 | `infer_cargo.py` | Cargo pelo vencimento pago (magistrado pela tag) |
| 10 | `mkrel.py` | Liga CTCs/relatórios e `gnCert` aos casos |
| 11 | `post.py` | Metadados do gabarito |

Depois: `node ../testes/regressao.js /home/claude/work/casos --par=2 --resumo` (e `--tudo`), `python3 resumo2.py casos/_res_X.json rotulo …` para as métricas cert/planilha × com/sem ficha. Tabela de códigos do sistema antigo (para a exportação "SQL Results", que não traz a descrição): `python3 mk_codref.py` depois do passo 7 gera `calc/rubricas_cod.json`; se mudar, rode de novo a partir do passo 6.

Diagnóstico na regressão: `RBC_DUMP='<expressão JS>' node ../testes/regressao.js …` grava o resultado da expressão, avaliada na página, em `dump` de cada caso. O resultado também traz `uso.pendL` (valores sem mês), `uso.naoRecL` (rubricas não reconhecidas) e `uso.devolL` (devoluções).

Comparar duas rodadas (ganhos e regressões por caso): `python3 cmp2.py casos/_res_A.json casos/_res_B.json`. Valores sem mês contra o gabarito: `python3 pend_an.py casos/_res_X.json`.

Auxiliares: `diag.py`, `cmp.py`, `knn.py` (gera `rubricas_ref.json`), `inv_rub.js`.
