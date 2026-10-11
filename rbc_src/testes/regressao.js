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
const PAGINA = (process.argv.find(a => a.startsWith('--pagina=')) || '').slice(9) || path.resolve(CALC, '..', '..', 'calculadora_rbc.html');

const args = process.argv.slice(2);
const DIR = path.resolve(args.find(a => !a.startsWith('--')) || path.resolve(__dirname, '..', 'casos'));
const SO = (args.find(a => a.startsWith('--so=')) || '').slice(5).split(',').filter(Boolean);
const LB = args.includes('--linha-base');
const SEM_REL = args.includes('--sem-rel');
const TUDO = args.includes('--tudo');   // usa a entrada única (pasta inteira) em vez dos campos e envios separados   // ignora os relatórios/CTC do caso (mede o efeito deles)
const DUMP = process.env.RBC_DUMP;   // expressão JS avaliada na página (diagnóstico); vai em "dump" no resultado
const SAIDA = (args.find(a => a.startsWith('--saida=')) || '--saida=_resultado.json').slice(8);

const MAP = { 'jszip.min.js': 'jszip/dist/jszip.min.js', 'xlsx.full.min.js': 'xlsx/dist/xlsx.full.min.js', 'pdf.min.js': 'pdfjs-dist/build/pdf.min.js', 'pdf.worker.min.js': 'pdfjs-dist/build/pdf.worker.min.js', 'exceljs.min.js': 'exceljs/dist/exceljs.min.js' };
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
  let auto = null;
  if (TUDO) {
    // entrada única: todos os arquivos de uma vez, sem preencher nada; o que a página não deduzir vem do caso
    const todos = (c.fichas || []).concat(SEM_REL ? [] : (c.relatorios || [])).concat(c.extras || []).map(f);
    await p.setInputFiles('#fileTudo', todos);
    await p.waitForFunction(() => /ignorado/.test(document.getElementById('tudoSt').textContent), null, { timeout: 300000 });
    auto = await p.evaluate(() => ({ cargo: document.getElementById('cargo').value, inicio: document.getElementById('inicio').value, fim: document.getElementById('fim').value, esp: document.getElementById('especialidade').value }));
    auto.ok = { cargo: auto.cargo === (s.cargo || ''), inicio: auto.inicio === s.inicio, fim: !auto.fim || auto.fim === s.fim, esp: auto.esp === (s.especialidade || '') };
    // período do gabarito sempre (a CTC pode cobrir outro período que o da RBC comparada)
    await p.evaluate(sv => { const $ = id => document.getElementById(id);
      if (sv.cargo && !$('cargo').value) $('cargo').value = sv.cargo;
      if (sv.especialidade && !$('especialidade').value) { $('especialidade').value = sv.especialidade; $('espDesde').disabled = false; if (sv.espDesde) $('espDesde').value = sv.espDesde; }
      if (sv.inicio) $('inicio').value = sv.inicio; if (sv.fim) $('fim').value = sv.fim; }, s);
    await p.evaluate(() => window.__RBC_CALC());
    await p.waitForFunction(() => window.__RBC_STATE.res, null, { timeout: 120000 });
  } else {
  if (s.cargo) await p.selectOption('#cargo', s.cargo);
  if (s.especialidade) await p.selectOption('#especialidade', s.especialidade);
  for (const [sel, v] of [['#espDesde', s.espDesde], ['#inicio', s.inicio], ['#fim', s.fim], ['#nome', s.nome]])
    if (v) { await p.fill(sel, v); await p.dispatchEvent(sel, 'change'); }
  const rel = SEM_REL ? [] : (c.relatorios || []);
  if (rel.length) {
    await p.setInputFiles('#fileRel', rel.map(f));
    // os arquivos são lidos em sequência; relatório repetido do mesmo tipo substitui o anterior
    await p.waitForFunction(() => window.__RBC_STATE.relArqs.length && window.__RBC_STATE.relArqs.every(a => a.st === 'ok'), null, { timeout: 180000 });
    await p.waitForTimeout(300);
  }
  await p.click('#avancar');
  const nf = (c.fichas || []).length;
  if (nf) await p.setInputFiles('#file', c.fichas.map(f));
  else await p.evaluate(() => window.__RBC_CALC());   // só CTC/relatórios: RBC pela tabela
  // com CTC a página já calcula pela tabela antes da ficha: espera a leitura de todas as fichas
  await p.waitForFunction(n => window.__RBC_STATE.arquivos.length >= n && window.__RBC_STATE.res, nf, { timeout: 120000 });
  await p.waitForTimeout(200);
  }
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
  // o que ficaria para o usuário decidir (etapas 2 e 3): rubricas sem categoria, valores sem mês, datas a confirmar
  const uso = await p.evaluate(() => { const C = window.__RBC_CONT && window.__RBC_CONT(); if (!C) return null; const R = window.__RBC_STATE.res;
    const sm = l => Math.round(l.reduce((a, x) => a + Math.abs(x.valor || x.total || 0), 0));
    return { naoRec: C.naoRec.length, naoRecV: sm(C.naoRec), pend: C.pend.length, pendV: sm(C.pend), parc: C.parc.length, passivos: R.passivos.length, retro: R.log.filter(l => l.tipo === 'retroativo').length,
      devol: window.__RBC_STATE.devol.length, devolSemPer: window.__RBC_STATE.devol.filter(d => !(d.ini && d.fim)).length, anosAtt: C.att, divMes: C.divMes.size,
      pendL: C.pend.map(x => [x.comp, x.cat, x.valor, x.motivo]), naoRecL: C.naoRec.map(x => [x.cod, x.desc, x.primeiro, x.ultimo, x.total]), devolL: window.__RBC_STATE.devol.map(d => [d.ini, d.fim, d.origem, d.obs]) }; });
  const dump = DUMP ? await p.evaluate(DUMP).catch(e => 'erro: ' + e.message) : undefined;
  await p.evaluate(() => window.__RBC_IR(2)); await p.waitForTimeout(300);
  const [dl] = await Promise.all([p.waitForEvent('download', { timeout: 60000 }), p.click('#x_rbc', { timeout: 30000 })])
    .catch(async e => { throw new Error('exportação: ' + e.message.split('\n')[0] + (erros.length ? ' | erros da página: ' + erros.join(' / ') : '') + ' | ' + await p.evaluate(() => document.getElementById('x_msg').textContent).catch(() => '')); });
  const saida = f(SEM_REL ? '_saida_semrel.xlsx' : '_saida_calculadora.xlsx'); await dl.saveAs(saida);
  await ctx.close();

  const ws = XLSX.readFile(saida).Sheets.RBC;
  const calc = coluna(ws, 'A', 'X', 1, 2000), ref = {};
  for (let r = 1; r <= 2000; r++) { const a = ws['A' + r], x = ws['B' + r]; const k = a && mesDe(a.v); if (k && x) ref[k] = x.v; }
  const R = c.rbc; let dip, gnDip = null;
  if (R.json) {  // gabarito extraído da certidão (RBC emitida): {mensal:{'AAAA-MM':v}, gn:{'AAAA':v}}
    const gj = JSON.parse(fs.readFileSync(f(R.json), 'utf8')); dip = {};
    for (const [k, v] of Object.entries(gj.mensal)) if (v > 0) dip[k] = v;
    gnDip = gj.gn || {};
  } else {
    const wb = XLSX.readFile(f(R.arquivo));
    const wd = wb.Sheets[R.aba || wb.SheetNames[0]]; if (!wd) throw new Error('aba não encontrada: ' + R.aba);
    dip = coluna(wd, R.colData || 'A', R.colTotal, R.linhaIni || 1, R.linhaFim || 2000);
  }
  const meses = Object.keys(dip).sort(), iguais = [], div = [];
  for (const k of meses) {
    const v = calc[k];
    if (v != null && Math.abs(v - dip[k]) <= 0.05) iguais.push(k);
    else div.push({ mes: k, calc: v == null ? null : +v.toFixed(2), dip: +dip[k].toFixed(2), dif: v == null ? null : +(v - dip[k]).toFixed(2), ref: ref[k] || '' });
  }
  // gratificação natalina: linhas da planilha sem data cujo rótulo é GN (coluna A) — total na coluna X
  let gn = null;
  if (gnDip) {
    const calcGN = {};
    let ultAno = null;
    for (let r = 1; r <= 2000; r++) { const a = ws['A' + r], x = ws['X' + r]; const k = a && mesDe(a.v); if (k) { ultAno = k.slice(0, 4); continue; }
      if (a && /^GN$/i.test(String(a.v).trim()) && ultAno && x && typeof x.v === 'number') calcGN[ultAno] = (calcGN[ultAno] || 0) + x.v; }
    gn = { total: 0, iguais: 0, div: [] };
    for (const [y, v] of Object.entries(gnDip)) { if (!(v > 0)) continue; gn.total++; const cv = calcGN[y]; if (cv != null && Math.abs(cv - v) <= 0.05) gn.iguais++; else gn.div.push({ ano: y, calc: cv == null ? null : +cv.toFixed(2), dip: v }); }
  }
  // certidão complementar de GN (anos fora da RBC): aba "Certidão GN"
  let gnCert = null;
  if (c.gnCert) {
    const wg = XLSX.readFile(saida).Sheets['Certidão GN'], calcC = {};
    if (wg) for (let r = 2; r <= 200; r++) { const a = wg['A' + r], e = wg['E' + r]; if (a && typeof a.v === 'number' && e && typeof e.v === 'number') calcC[String(a.v)] = e.v; }
    gnCert = { total: 0, iguais: 0, div: [] };
    for (const [y, v] of Object.entries(c.gnCert)) { gnCert.total++; const cv = calcC[y]; if (cv != null && Math.abs(cv - v) <= 0.05) gnCert.iguais++; else gnCert.div.push({ ano: y, calc: cv == null ? null : cv, dip: v }); }
  }
  return { id, auto, uso, dump, total: meses.length, iguais: iguais.length, mesesIguais: iguais, divergencias: div, gn, gnCert, erros, leitura };
}

(async () => {
  if (!fs.existsSync(PAGINA)) throw new Error('Página não encontrada. Rode antes: node build_html.js');
  const ids = fs.readdirSync(DIR).filter(n => fs.existsSync(path.join(DIR, n, 'caso.json')) && (!SO.length || SO.includes(n))).sort();
  if (!ids.length) throw new Error('Nenhum caso em ' + DIR);
  const base = fs.existsSync(path.join(DIR, '_linha_base.json')) ? JSON.parse(fs.readFileSync(path.join(DIR, '_linha_base.json'))) : {};
  const b = await chromium.launch(); const out = {};
  const PAR = +((args.find(a => a.startsWith('--par=')) || '--par=1').slice(6));
  const QUIET = args.includes('--resumo');
  const fila = ids.slice();
  await Promise.all(Array.from({ length: PAR }, async () => { while (fila.length) { const id = fila.shift();
    const c = JSON.parse(fs.readFileSync(path.join(DIR, id, 'caso.json'), 'utf8'));
    try { out[id] = await Promise.race([rodar(b, id, c), new Promise((_, rj) => setTimeout(() => rj(new Error('tempo esgotado')), 300000).unref())]); } catch (e) { out[id] = { id, falha: String(e).slice(0, 300) }; }
  } }));
  for (const id of ids) {
    const r = out[id];
    if (r.falha) { console.log(`\n## ${id}: FALHA — ${r.falha}`); continue; }
    const ant = base[id] ? new Set(base[id].mesesIguais) : null;
    const regr = ant ? r.divergencias.filter(x => ant.has(x.mes)) : [];
    console.log(`\n## ${id}: ${r.iguais}/${r.total} meses iguais` + (r.gn ? ` · GN ${r.gn.iguais}/${r.gn.total}` : '') + (r.gnCert ? ` · certidão GN ${r.gnCert.iguais}/${r.gnCert.total}` : '') + (ant ? ` (linha de base ${base[id].iguais}/${base[id].total}; regressões: ${regr.length})` : ''));
    if (QUIET) continue;
    if (r.erros.length) console.log('  erros na página:', r.erros.join(' | '));
    console.log('  relatórios:', r.leitura.rel.join('; ') || '—');
    for (const x of r.divergencias) console.log(`  ${regr.includes(x) ? '!! ' : '   '}${x.mes}  calc ${x.calc}  dip ${x.dip}  dif ${x.dif}  ${x.ref}`);
  }
  await b.close();
  const resumo = Object.values(out).filter(r => !r.falha);
  console.log('\nTOTAL:', resumo.reduce((a, r) => a + r.iguais, 0) + '/' + resumo.reduce((a, r) => a + r.total, 0), 'meses iguais em', resumo.length, 'caso(s)' +
    ' · GN ' + resumo.reduce((a, r) => a + (r.gn ? r.gn.iguais : 0), 0) + '/' + resumo.reduce((a, r) => a + (r.gn ? r.gn.total : 0), 0));
  fs.writeFileSync(path.join(DIR, SAIDA), JSON.stringify(out, null, 1));
  if (LB) { fs.writeFileSync(path.join(DIR, '_linha_base.json'), JSON.stringify(Object.assign(base, out), null, 1)); console.log('Linha de base gravada.'); }
})().catch(e => { console.error(e); process.exit(1); });
