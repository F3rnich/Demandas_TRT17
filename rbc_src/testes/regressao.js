// Regressão da calculadora de RBC contra RBCs prontas da DIPROF.
//
// Uso (a partir de rbc_src/calc, depois de `npm ci` e `node build_html.js`):
//   node ../testes/regressao.js [pasta_dos_casos] [--so=caso1,caso2] [--linha-base]
//
// Cada caso fica em <pasta_dos_casos>/<id>/ com os arquivos (ficha, relatórios, RBC da DIPROF)
// e um caso.json. A pasta de casos tem dados pessoais e NÃO é versionada (rbc_src/casos/ no .gitignore).
//
// caso.json:
// {
//   "servidor": {"cargo":"TÉCNICO JUDICIÁRIO","especialidade":"SEGURANCA","espDesde":"","inicio":"1995-01-09","fim":"2012-06-24"},
//   "relatorios": ["prog.pdf","func.pdf","vpni.pdf"],
//   "fichas": ["ficha.xlsx"],
//   "regras": {"vpniTabela": true},                      // opcional: sobrepõe as regras padrão (ids r_* da página)
//   "rbc": {"arquivo":"dip.xlsx","aba":"RBC - considerando a FF","colData":"A","colTotal":"Q","linhaIni":1,"linhaFim":600}
// }
//
// Saída: meses iguais (tolerância R$ 0,05) por caso e lista de divergências.
// Grava <pasta>/_resultado.json. Com --linha-base, grava também _linha_base.json; nas rodadas seguintes
// aponta REGRESSÕES (mês que batia na linha de base e deixou de bater).
const path = require('path'), fs = require('fs');
const CALC = path.resolve(__dirname, '..', 'calc');
const req = require('module').createRequire(path.join(CALC, 'package.json'));
const { chromium } = req('playwright'); const XLSX = req('xlsx');
const NM = path.join(CALC, 'node_modules');
const PAGINA = path.resolve(CALC, '..', '..', 'calculadora_rbc.html');

const args = process.argv.slice(2);
const DIR = path.resolve(args.find(a => !a.startsWith('--')) || path.resolve(__dirname, '..', 'casos'));
const SO = (args.find(a => a.startsWith('--so=')) || '').slice(5).split(',').filter(Boolean);
const LB = args.includes('--linha-base');

const MAP = { 'xlsx.full.min.js': 'xlsx/dist/xlsx.full.min.js', 'pdf.min.js': 'pdfjs-dist/build/pdf.min.js', 'pdf.worker.min.js': 'pdfjs-dist/build/pdf.worker.min.js', 'exceljs.min.js': 'exceljs/dist/exceljs.min.js' };
const mesDe = v => {
  if (v == null || v === '') return null;
  if (typeof v === 'number') { const d = XLSX.SSF.parse_date_code(v); return d ? d.y + '-' + String(d.m).padStart(2, '0') : null; }
  if (v instanceof Date) return v.getFullYear() + '-' + String(v.getMonth() + 1).padStart(2, '0');
  const s = String(v).trim(); let m;
  if ((m = s.match(/^(\d{1,2})\/(\d{4})$/))) return m[2] + '-' + m[1].padStart(2, '0');
  if ((m = s.match(/^\d{1,2}\/(\d{1,2})\/(\d{4})$/))) return m[2] + '-' + m[1].padStart(2, '0');
  if ((m = s.match(/^(\d{4})-(\d{2})/))) return m[1] + '-' + m[2];
  return null;
};
function coluna(ws, colData, colVal, r0, r1) {
  const o = {};
  for (let r = r0; r <= r1; r++) {
    const a = ws[colData + r], x = ws[colVal + r]; const k = a && mesDe(a.v);
    if (k && x && typeof x.v === 'number') o[k] = (o[k] || 0) + x.v; // soma linhas repetidas do mesmo mês (ex.: GN fica fora por não ter data)
  }
  return o;
}

async function rodar(b, id, c) {
  const d = path.join(DIR, id), f = n => path.join(d, n);
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const p = await ctx.newPage(); const erros = [];
  p.on('pageerror', e => erros.push(String(e)));
  await ctx.route(/cdnjs/, r => r.fulfill({ path: NM + '/' + MAP[r.request().url().split('/').pop()], contentType: 'application/javascript' }));
  await ctx.route(/jsdelivr/, r => {
    const u = r.request().url(); let q;
    if (/tesseract\.js@5\.1\.1\/dist\/(.+)$/.test(u)) q = 'tesseract.js/dist/' + RegExp.$1;
    else if (/tesseract\.js-core@5\.1\.1\/(.+)$/.test(u)) q = 'tesseract.js-core/' + RegExp.$1;
    else if (/@tesseract\.js-data\/por@1\.0\.0\/(.+)$/.test(u)) q = '@tesseract.js-data/por/' + RegExp.$1;
    if (!q || !fs.existsSync(NM + '/' + q)) return r.fulfill({ status: 404 });
    r.fulfill({ path: NM + '/' + q, contentType: /\.wasm$/.test(q) ? 'application/wasm' : /\.js$/.test(q) ? 'application/javascript' : 'application/octet-stream' });
  });
  await ctx.route(/fonts\.(googleapis|gstatic)/, r => r.fulfill({ body: '', contentType: 'text/css' }));
  await p.goto('file://' + PAGINA);
  const s = c.servidor || {};
  if (s.cargo) await p.selectOption('#cargo', s.cargo);
  if (s.especialidade) await p.selectOption('#especialidade', s.especialidade);
  for (const [sel, v] of [['#espDesde', s.espDesde], ['#inicio', s.inicio], ['#fim', s.fim], ['#nome', s.nome]])
    if (v) { await p.fill(sel, v); await p.dispatchEvent(sel, 'change'); }
  const rel = c.relatorios || [];
  if (rel.length) {
    await p.setInputFiles('#fileRel', rel.map(f));
    // os arquivos são lidos em sequência; relatório repetido do mesmo tipo substitui o anterior
    await p.waitForFunction(() => window.__RBC_STATE.relArqs.length && window.__RBC_STATE.relArqs.every(a => a.st === 'ok'), null, { timeout: 180000 });
    await p.waitForTimeout(300);
  }
  await p.click('#avancar');
  await p.setInputFiles('#file', (c.fichas || []).map(f));
  await p.waitForFunction(() => window.__RBC_STATE.res, null, { timeout: 120000 });
  if (c.regras) {
    await p.evaluate(rg => {
      for (const [k, v] of Object.entries(rg)) {
        const el = document.getElementById('r_' + k); if (!el) throw new Error('regra desconhecida: ' + k);
        if (el.type === 'checkbox') el.checked = !!v; else el.value = v === true ? 'sim' : v === false ? 'nao' : v;
      }
      window.__RBC_CALC();
    }, c.regras);
  }
  const leitura = await p.evaluate(() => ({
    rel: window.__RBC_STATE.relArqs.map(a => a.nome + ': ' + (a.erro ? 'ERRO ' + a.erro : (a.tipo || '?') + ' ' + a.n + ' linha(s)')),
    prog: ((window.__RBC_STATE.rel || {}).PROGRESSAO || []).map(r => [r.ini, r.classe + '-' + r.padrao, r.origem].join(' ')),
  }));
  await p.click('#avancar'); await p.click('#avancar'); await p.waitForTimeout(300);
  const [dl] = await Promise.all([p.waitForEvent('download'), p.click('#avancar')]);
  const saida = f('_saida_calculadora.xlsx'); await dl.saveAs(saida);
  await ctx.close();

  const ws = XLSX.readFile(saida).Sheets.RBC;
  const calc = coluna(ws, 'A', 'X', 1, 2000), ref = {};
  for (let r = 1; r <= 2000; r++) { const a = ws['A' + r], x = ws['B' + r]; const k = a && mesDe(a.v); if (k && x) ref[k] = x.v; }
  const R = c.rbc, wb = XLSX.readFile(f(R.arquivo));
  const wd = wb.Sheets[R.aba || wb.SheetNames[0]]; if (!wd) throw new Error('aba não encontrada: ' + R.aba);
  const dip = coluna(wd, R.colData || 'A', R.colTotal, R.linhaIni || 1, R.linhaFim || 2000);
  const meses = Object.keys(dip).sort(), iguais = [], div = [];
  for (const k of meses) {
    const v = calc[k];
    if (v != null && Math.abs(v - dip[k]) <= 0.05) iguais.push(k);
    else div.push({ mes: k, calc: v == null ? null : +v.toFixed(2), dip: +dip[k].toFixed(2), dif: v == null ? null : +(v - dip[k]).toFixed(2), ref: ref[k] || '' });
  }
  return { id, total: meses.length, iguais: iguais.length, mesesIguais: iguais, divergencias: div, erros, leitura };
}

(async () => {
  if (!fs.existsSync(PAGINA)) throw new Error('Página não encontrada. Rode antes: node build_html.js');
  const ids = fs.readdirSync(DIR).filter(n => fs.existsSync(path.join(DIR, n, 'caso.json')) && (!SO.length || SO.includes(n))).sort();
  if (!ids.length) throw new Error('Nenhum caso em ' + DIR);
  const base = fs.existsSync(path.join(DIR, '_linha_base.json')) ? JSON.parse(fs.readFileSync(path.join(DIR, '_linha_base.json'))) : {};
  const b = await chromium.launch(); const out = {};
  for (const id of ids) {
    const c = JSON.parse(fs.readFileSync(path.join(DIR, id, 'caso.json'), 'utf8'));
    try { out[id] = await rodar(b, id, c); } catch (e) { out[id] = { id, falha: String(e) }; }
    const r = out[id];
    if (r.falha) { console.log(`\n## ${id}: FALHA — ${r.falha}`); continue; }
    const ant = base[id] ? new Set(base[id].mesesIguais) : null;
    const regr = ant ? r.divergencias.filter(x => ant.has(x.mes)) : [];
    console.log(`\n## ${id}: ${r.iguais}/${r.total} meses iguais` + (ant ? ` (linha de base ${base[id].iguais}/${base[id].total}; regressões: ${regr.length})` : ''));
    if (r.erros.length) console.log('  erros na página:', r.erros.join(' | '));
    console.log('  relatórios:', r.leitura.rel.join('; ') || '—');
    for (const x of r.divergencias) console.log(`  ${regr.includes(x) ? '!! ' : '   '}${x.mes}  calc ${x.calc}  dip ${x.dip}  dif ${x.dif}  ${x.ref}`);
  }
  await b.close();
  const resumo = Object.values(out).filter(r => !r.falha);
  console.log('\nTOTAL:', resumo.reduce((a, r) => a + r.iguais, 0) + '/' + resumo.reduce((a, r) => a + r.total, 0), 'meses iguais em', resumo.length, 'caso(s)');
  fs.writeFileSync(path.join(DIR, '_resultado.json'), JSON.stringify(out, null, 1));
  if (LB) { fs.writeFileSync(path.join(DIR, '_linha_base.json'), JSON.stringify(Object.assign(base, out), null, 1)); console.log('Linha de base gravada.'); }
})().catch(e => { console.error(e); process.exit(1); });
