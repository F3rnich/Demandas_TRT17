#!/usr/bin/env bash
# Regressão completa em um comando (corpus fora do repositório; nada aqui contém dados pessoais).
#
# uso:  bash rbc_src/pipeline/rodar_regressao.sh <pasta_com_o_corpus> [commit_base]
#   <pasta_com_o_corpus>  pasta com as pastas do processo SEI 0000775-34.2024 (as 3 subpastas e, se houver, RBC/ e RRC/)
#   [commit_base]         opcional: commit com que comparar (ex.: ac367ce). Sem ele, só a versão atual.
#   TUDO=1                também roda pela entrada única (--tudo)
#   PAR=2                 casos em paralelo
#
# Faz: copia o corpus para /home/claude/corpus, converte .doc/.odt, roda o pipeline em /home/claude/work
# (gabarito → fichas → casos), roda a regressão na página atual e, se pedido, na do commit base, e imprime o placar
# (certidão/planilha × com/sem ficha) e os ganhos e regressões por caso. Ao fim, lembra de apagar as cópias.
set -euo pipefail
ORIG="${1:?informe a pasta com o corpus}"; BASE="${2:-}"; PAR="${PAR:-2}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"; export RBC_REPO="$REPO"
CORPUS=/home/claude/corpus; WORK=/home/claude/work; CALC="$REPO/rbc_src/calc"
log(){ printf '\n== %s\n' "$*"; }

log "corpus: $ORIG → $CORPUS"
[ -e "$CORPUS" ] && { echo "Já existe $CORPUS (cópia anterior?). Apague antes: rm -r $CORPUS $WORK"; exit 1; }
mkdir -p "$CORPUS" "$WORK"; cp -r "$ORIG"/. "$CORPUS"/
find "$CORPUS" \( -iname '*.doc' -o -iname '*.odt' \) -print0 | while IFS= read -r -d '' f; do
  soffice --headless --convert-to docx --outdir "$(dirname "$f")" "$f" >/dev/null 2>&1 || echo "não converteu: $f"; done
echo "$(find "$CORPUS" -type f | wc -l) arquivos"

log "dependências"
python3 -c "import docx, openpyxl, pdfplumber, xlrd" 2>/dev/null || pip install -q --break-system-packages python-docx openpyxl pdfplumber xlrd
[ -d "$CALC/node_modules" ] || (cd "$CALC" && npm ci --silent)
(cd "$CALC" && node build_html.js)

log "pipeline (gabarito, fichas, casos)"
cp "$REPO"/rbc_src/pipeline/*.py "$REPO"/rbc_src/pipeline/*.js "$WORK"/; cd "$WORK"
q(){ local o; o=$("$@" 2>&1) || { echo "$o" | tail -20; echo "FALHOU: $*"; exit 1; }; echo "$o" | { grep -v -e polyfill -e 'Require stack' -e '^- /' -e canvas || true; } | tail -1; }
q python3 gold.py; q node gold_js.js; q python3 gold_gn.py; q python3 gold_xls.py; q python3 registry.py
q node dump_recs.js; q python3 learn.py; q python3 mkcasos.py; q python3 infer_cargo.py; q python3 mkrel.py; q python3 post.py
echo "$(ls -d casos/*/ | wc -l) casos"

cd "$CALC"
log "regressão: versão atual"
node ../testes/regressao.js "$WORK/casos" --par="$PAR" --resumo --saida=_res_atual.json > "$WORK/log_atual.txt" 2>&1; tail -1 "$WORK/log_atual.txt"
[ -n "${TUDO:-}" ] && { node ../testes/regressao.js "$WORK/casos" --par="$PAR" --resumo --tudo --saida=_res_atual_tudo.json > "$WORK/log_atual_tudo.txt" 2>&1; echo "--tudo: $(tail -1 "$WORK/log_atual_tudo.txt")"; }

if [ -n "$BASE" ]; then
  log "regressão: base $BASE"
  WT=/home/claude/rbc_base_$BASE; git -C "$REPO" worktree add -q "$WT" "$BASE"
  ln -s "$CALC/node_modules" "$WT/rbc_src/calc/node_modules"; (cd "$WT/rbc_src/calc" && node build_html.js >/dev/null)
  node ../testes/regressao.js "$WORK/casos" --par="$PAR" --resumo --pagina="$WT/calculadora_rbc.html" --saida=_res_base.json > "$WORK/log_base.txt" 2>&1; tail -1 "$WORK/log_base.txt"
  git -C "$REPO" worktree remove --force "$WT"
fi

cd "$WORK"
log "placar"
if [ -n "$BASE" ]; then python3 resumo2.py casos/_res_base.json base casos/_res_atual.json atual; python3 cmp2.py casos/_res_base.json casos/_res_atual.json | tail -25
else python3 resumo2.py casos/_res_atual.json atual; fi
log "detalhe por caso: $WORK/log_atual.txt e $WORK/casos/_res_*.json"
echo "Ao terminar a análise, apague as cópias (dados pessoais):  rm -r $CORPUS $WORK"
