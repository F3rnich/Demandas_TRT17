/* Certidão da RBC (modelo DIPROF) — leitura de RBC já emitida e geração do documento para assinatura
 * - lerRBCDocx / lerRBCPdf / lerRBCPlanilha: extraem a grade mês × ano (e o 13º) de uma RBC anterior, para comparar
 * - gerarCertidaoDocx: monta o .docx "RELAÇÃO DAS BASES DE CÁLCULO DE CONTRIBUIÇÃO" com os dados da CTC
 * - gerarCertidaoGNDocx: certidão complementar de gratificação natalina
 * Sem DOM: funciona no navegador e no Node (testes). JSZip é passado pelo chamador.
 */
(function (root) {
  'use strict';
  const MESES = ['JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO'];
  const ym = (y, m) => y + '-' + String(m).padStart(2, '0');
  const valBR = s => { const m = /-?\d{1,3}(?:\.\d{3})*,\d{1,2}/.exec(s || ''); return m ? +m[0].replace(/\./g, '').replace(',', '.') : null; };
  const moedaDe = s => { const m = /(CR\$|Cr\$|URV|R\$)/.exec(s || ''); return m ? m[1] : ''; };
  const xmlTxt = s => String(s).replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const mesIdx = l => { const u = String(l || '').toUpperCase().replace('MARCO', 'MARÇO').trim(); return MESES.indexOf(u); };

  // grade a partir de linhas de células (primeira célula = rótulo); células de "Ano: AAAA" abrem um bloco
  function grade(rows) {
    const mensal = {}, gn = {}, moeda = {}; let anos = [];
    for (const r of rows) {
      const ah = r.flatMap(c => [...String(c).matchAll(/Ano:\s*(\d{4})/g)].map(m => +m[1]));
      if (ah.length) { anos = ah; continue; }
      if (!anos.length || !r.length) continue;
      const lab = String(r[0] || '').replace(/\s+/g, ' ').toUpperCase().trim(), vals = r.slice(1);
      const mi = mesIdx(lab);
      if (mi >= 0) anos.forEach((a, i) => { const v = valBR(vals[i]); if (v != null) { mensal[ym(a, mi + 1)] = v; const mo = moedaDe(vals[i]); if (mo && mo !== 'R$') moeda[ym(a, mi + 1)] = mo; } });
      else if (/NATALINA|GRATIFICA|13/.test(lab)) anos.forEach((a, i) => { const v = valBR(vals[i]); if (v != null && gn[a] == null) gn[a] = v; });
    }
    return { mensal, gn, moeda };
  }
  // cabeçalho comum (texto corrido)
  function cabecalho(t) {
    const f = t.replace(/\s+/g, ' '), o = {};
    let m = /REFERENTE\s+[ÀA]\s+(.{5,140}?)(?:\.|ÓRG[ÃA]O|$)/i.exec(f); if (m) o.referencia = m[1].trim();
    m = /NOME DO SERVIDOR:?\s*([A-ZÀ-Ú][A-ZÀ-Ú .']{4,80}?)\s*(?:MATR|NOME DA|$)/.exec(f); if (m) o.nome = m[1].trim();
    const ds = [...f.matchAll(/Vit[óo]ria,\s*(\d{1,2})[º°]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})/gi)]; if (ds.length) o.emissao = ds[ds.length - 1].slice(1).join(' ');
    return o;
  }

  // ---------------------------------------------------------------- RBC em Word (.docx)
  async function lerRBCDocx(JSZip, buf) {
    const z = await JSZip.loadAsync(buf), x = await z.file('word/document.xml').async('string');
    const rows = [];
    for (const tr of x.match(/<w:tr[ >][\s\S]*?<\/w:tr>/g) || []) {
      const cells = (tr.match(/<w:tc>[\s\S]*?<\/w:tc>/g) || []).map(tc => xmlTxt((tc.match(/<w:t[^>]*>[^<]*<\/w:t>/g) || []).map(s => s.replace(/<[^>]+>/g, '')).join('')).trim());
      rows.push(cells);
    }
    const texto = xmlTxt((x.match(/<w:t[^>]*>[^<]*<\/w:t>/g) || []).map(s => s.replace(/<[^>]+>/g, '')).join(' '));
    return Object.assign(grade(rows), { cab: cabecalho(texto), fonte: 'docx' });
  }

  // ---------------------------------------------------------------- RBC em PDF (SEI): colunas pelos rótulos "Ano: AAAA", linhas pela faixa do mês
  function lerRBCPdf(pages) {
    const mensal = {}, gn = {}, moeda = {}; let texto = '', ultCols = null;
    for (const pg of pages) {
      const it = pg.items.filter(i => i.str && i.str.trim()).map(i => ({ s: i.str.trim(), x: i.x, y: i.y, w: i.w || 0 }));
      texto += it.map(i => i.s).join(' ') + '\n';
      const anos = [];
      for (let k = 0; k < it.length; k++) {
        const m = /^Ano:\s*(\d{4})?$/.exec(it[k].s); if (!m) continue;
        let y = m[1], x1 = it[k].x + it[k].w;
        if (!y) { const nx = it.find(j => Math.abs(j.y - it[k].y) < 2 && j.x > it[k].x && j.x - x1 < 25 && /^\d{4}$/.test(j.s)); if (!nx) continue; y = nx.s; x1 = nx.x + nx.w; }
        anos.push({ y: it[k].y, cx: (it[k].x + x1) / 2, ano: +y });
      }
      const tops = [...new Set(anos.map(a => Math.round(a.y)))].sort((a, b) => a - b);
      // bloco que continua da página anterior (quebra de página no meio dos meses): usa as colunas do último bloco
      const blocos = tops.map(tp => ({ tp, cols: anos.filter(a => Math.abs(a.y - tp) < 3).sort((a, b) => a.cx - b.cx) }));
      if (ultCols && (!tops.length || it.some(i => mesIdx(i.s) >= 0 && i.y < tops[0]))) blocos.unshift({ tp: -1, cols: ultCols });
      if (!blocos.length) continue;
      ultCols = blocos[blocos.length - 1].cols;
      blocos.forEach(({ tp, cols }, bi) => {
        const fimB = bi + 1 < blocos.length ? blocos[bi + 1].tp : 1e9;
        const xc0 = cols[0].cx;
        const labs = it.filter(i => i.y > tp && i.y < fimB && i.x < xc0 - 30 && (mesIdx(i.s) >= 0 || /^(13|GRATIFICA|NATALINA)/i.test(i.s))).sort((a, b) => a.y - b.y);
        const rows = []; for (const l of labs) { const mi = mesIdx(l.s); if (mi >= 0) rows.push({ y: l.y, m: mi + 1 }); else if (!rows.some(r => r.gn)) rows.push({ y: l.y, gn: true }); }
        rows.forEach((r, i) => {
          const a = i ? (rows[i - 1].y + r.y) / 2 : r.y - 8, b = i + 1 < rows.length ? (r.y + rows[i + 1].y) / 2 : r.y + (r.gn ? 30 : 14);
          const por = {};
          for (const t of it) { if (t.y < a || t.y >= b || t.x < xc0 - 70) continue; const cx = t.x + t.w / 2; const c = cols.reduce((p, q) => Math.abs(q.cx - cx) < Math.abs(p.cx - cx) ? q : p); (por[c.ano] = por[c.ano] || []).push(t.s); }
          for (const [ano, ts] of Object.entries(por)) { const s = ts.join(' '), v = valBR(s); if (v == null) continue; if (r.gn) gn[ano] = v; else { mensal[ym(ano, r.m)] = v; const mo = moedaDe(s); if (mo && mo !== 'R$') moeda[ym(ano, r.m)] = mo; } }
        });
      });
    }
    return { mensal, gn, moeda, cab: cabecalho(texto), fonte: 'pdf' };
  }

  // ---------------------------------------------------------------- planilha de trabalho da DIPROF (coluna "Remuneração")
  function lerRBCPlanilha(abas) {   // abas: [{nome, rows:[[...]]}] (sheet_to_json header:1, raw)
    let best = null;
    const mes = v => {
      if (typeof v === 'number' && v > 20000 && v < 60000) { const d = new Date(Date.UTC(1899, 11, 30) + v * 864e5); return ym(d.getUTCFullYear(), d.getUTCMonth() + 1); }
      if (v instanceof Date) return ym(v.getFullYear(), v.getMonth() + 1);
      const m = /^\s*(\d{1,2})\/(\d{4})\s*$/.exec(String(v || '')); return m ? ym(m[2], +m[1]) : null;
    };
    for (const a of abas) {
      const rows = a.rows;
      for (let i = 0; i < Math.min(rows.length, 40); i++) {
        const c = (rows[i] || []).map(x => String(x == null ? '' : x).trim().toLowerCase());
        if (!/^m[eê]s/.test(c[0] || '')) continue;
        const j = c.findIndex(x => /remunera|base de c/.test(x)); if (j < 0) continue;
        const mensal = {}, gn = {}; let ult = null;
        for (const r of rows.slice(i + 1)) {
          if (!r) continue; const k = mes(r[0]), v = r[j];
          if (k) { ult = k; if (typeof v === 'number' && v > 0) mensal[k] = Math.round(v * 100 + 1e-6) / 100; }
          else if (ult && /GN|13|NATAL/i.test(String(r[0] || '')) && typeof v === 'number' && v > 0) gn[ult.slice(0, 4)] = Math.round(v * 100 + 1e-6) / 100;
        }
        if (Object.keys(mensal).length && (!best || Object.keys(mensal).length > Object.keys(best.mensal).length)) best = { mensal, gn, moeda: {}, aba: a.nome, fonte: 'planilha' };
      }
    }
    return best;
  }
  // é RBC/certidão? (para separar de CTC e ficha na entrada única)
  const pareceRBC = texto => /RELA[ÇC][ÃA]O DAS (BASES DE C[ÁA]LCULO|REMUNERA[ÇC][ÕO]ES) DE CONTRIBUI/i.test(String(texto || '').replace(/\s+/g, ' ').slice(0, 4000));

  // ---------------------------------------------------------------- comparação com uma RBC anterior
  function comparar(linhas, gns, ant) {
    const calc = {}; for (const l of linhas) calc[l.comp] = l.total;
    const meses = [...new Set([...Object.keys(ant.mensal).filter(k => ant.mensal[k] > 0), ...linhas.filter(l => l.total > 0).map(l => l.comp)])].sort();
    const dif = [];
    let iguais = 0;
    for (const k of meses) { const a = ant.mensal[k] || 0, c = calc[k] || 0; if (Math.abs(a - c) <= 0.05) iguais++; else dif.push({ k, ant: a, calc: c, d: Math.round((c - a) * 100) / 100 }); }
    const gnDif = [];
    for (const g of gns) { const a = ant.gn[g.ano]; if (a != null && Math.abs(a - g.valor) > 0.05) gnDif.push({ ano: g.ano, ant: a, calc: g.valor }); }
    for (const [ano, a] of Object.entries(ant.gn)) if (a > 0 && !gns.some(g => g.ano === ano)) gnDif.push({ ano, ant: a, calc: null });
    return { total: meses.length, iguais, dif, gnDif };
  }

  // ---------------------------------------------------------------- geração do .docx
  const FONTE = 'Trebuchet MS';
  const run = (t, o = {}) => `<w:r><w:rPr><w:rFonts w:ascii="${FONTE}" w:hAnsi="${FONTE}" w:cs="${FONTE}"/>${o.b ? '<w:b/>' : ''}<w:sz w:val="${o.sz || 18}"/><w:szCs w:val="${o.sz || 18}"/></w:rPr><w:t xml:space="preserve">${esc(t)}</w:t></w:r>`;
  const par = (t, o = {}) => `<w:p><w:pPr><w:spacing w:before="${o.antes || 0}" w:after="${o.depois == null ? 60 : o.depois}"/>${o.al ? `<w:jc w:val="${o.al}"/>` : ''}</w:pPr>${(Array.isArray(t) ? t : [t]).map(x => typeof x === 'string' ? run(x, o) : run(x.t, Object.assign({}, o, x))).join('')}</w:p>`;
  const borda = '<w:tcBorders><w:top w:val="single" w:sz="6" w:color="000000"/><w:left w:val="single" w:sz="6" w:color="000000"/><w:bottom w:val="single" w:sz="6" w:color="000000"/><w:right w:val="single" w:sz="6" w:color="000000"/></w:tcBorders>';
  const cel = (conteudo, w, o = {}) => `<w:tc><w:tcPr><w:tcW w:w="${w}" w:type="dxa"/>${o.span ? `<w:gridSpan w:val="${o.span}"/>` : ''}${borda}${o.sombra ? '<w:shd w:val="clear" w:color="auto" w:fill="E7E6E6"/>' : ''}<w:vAlign w:val="center"/></w:tcPr>${conteudo}</w:tc>`;
  const tabela = (larg, linhas) => `<w:tbl><w:tblPr><w:tblW w:w="${larg.reduce((a, b) => a + b, 0)}" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="51" w:type="dxa"/><w:right w:w="51" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>${larg.map(w => `<w:gridCol w:w="${w}"/>`).join('')}</w:tblGrid>${linhas.map(l => `<w:tr><w:trPr><w:cantSplit/></w:trPr>${l}</w:tr>`).join('')}</w:tbl>`;
  const fmt = v => v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const moedaMes = k => k < '1986-03' ? 'Cr$' : k < '1989-02' ? 'Cz$' : k < '1990-04' ? 'NCz$' : k < '1993-08' ? 'Cr$' : k < '1994-07' ? 'CR$' : 'R$';
  const ROT_MOEDA = { 'Cr$': 'Cr$', 'CR$': 'CR$', 'R$': 'R$', 'Cz$': 'Cz$', 'NCz$': 'NCz$' };

  function documento(corpo, paisagem) {
    const sect = paisagem ? '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>' : '<w:pgSz w:w="11906" w:h="16838"/>';
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${corpo}<w:sectPr>${sect}<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>`;
  }
  async function pacote(JSZip, docXml) {
    const z = new JSZip();
    z.file('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
    z.file('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
    z.file('word/document.xml', docXml);
    return z.generateAsync({ type: 'blob', mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
  }
  const cabInst = () => ['PODER JUDICIÁRIO FEDERAL', 'JUSTIÇA DO TRABALHO', 'TRIBUNAL REGIONAL DO TRABALHO DA 17ª REGIÃO', 'Secretaria de Gestão de Pessoas',
    'Endereço: Av. Nossa Senhora dos Navegantes, 1245, Enseada do Suá, Vitória-ES, 29050-335', 'Tel.: (27) 3321-2473 - diprof@trt17.jus.br']
    .map((t, i) => par(t, { al: 'center', b: i < 3, sz: i < 4 ? 20 : 16, depois: 0 })).join('');

  /** d: {nome, mae, nascimento, matricula, pis, cpf, inicio, fim, referencia, local, dataEmissao, chefe, cargoChefe, secretario, cargoSecretario,
   *      linhas:[{comp,total}], gns:[{ano,valor}], porBloco} */
  async function gerarCertidaoDocx(JSZip, d) {
    const anosSet = new Set(); for (const l of d.linhas) anosSet.add(l.comp.slice(0, 4));
    const anos = [...anosSet].sort(); const porBloco = d.porBloco || 6;
    const val = {}; for (const l of d.linhas) val[l.comp] = l.total;
    const gn = {}; for (const g of d.gns || []) gn[g.ano] = g.valor;
    const LR = 1700, LC = Math.floor((9354 - LR) / porBloco), larg = [LR].concat(Array(porBloco).fill(LC)), W = LR + LC * porBloco;
    const txt = (t, o) => par(t, Object.assign({ depois: 0 }, o));
    const fmtV = (k, v) => v == null ? 'X' : (moedaMes(k) + ' ' + fmt(v));
    const cab = [
      cel(txt([{ t: 'ÓRGÃO EXPEDIDOR: ', b: true }, 'TRIBUNAL REGIONAL DO TRABALHO DA 17ª REGIÃO']), W - 2600, { span: 1 }) + cel(txt([{ t: 'CNPJ: ', b: true }, '02.488.507/0001-61']), 2600),
      cel(txt([{ t: 'NOME DO SERVIDOR: ', b: true }, d.nome || '']), W - 2600) + cel(txt([{ t: 'MATRÍCULA: ', b: true }, d.matricula || '']), 2600),
      cel(txt([{ t: 'NOME DA MÃE: ', b: true }, d.mae || '']), W - 2600) + cel(txt([{ t: 'DATA DE NASCIMENTO: ', b: true }, d.nascimento || '']), 2600),
      cel(txt([{ t: 'DATA DE INÍCIO DA CONTRIBUIÇÃO/ADMISSÃO: ', b: true }, d.inicio || '']), Math.floor((W - 2600) / 2)) + cel(txt([{ t: 'DATA DA EXONERAÇÃO: ', b: true }, d.fim || '']), Math.ceil((W - 2600) / 2)) + cel(txt([{ t: 'PIS/PASEP: ', b: true }, d.pis || '']) + txt([{ t: 'CPF: ', b: true }, d.cpf || '']), 2600),
    ];
    const tabCab = cab.map(l => `<w:tbl><w:tblPr><w:tblW w:w="${W}" w:type="dxa"/><w:tblLayout w:type="fixed"/></w:tblPr><w:tblGrid><w:gridCol w:w="${W}"/></w:tblGrid><w:tr>${l}</w:tr></w:tbl>`).join('');
    let blocos = '';
    for (let i = 0; i < anos.length; i += porBloco) {
      const bl = anos.slice(i, i + porBloco); while (bl.length < porBloco) bl.push(null);
      const linhas = [];
      linhas.push(cel(txt({ t: 'Mês', b: true }, { al: 'center' }), LR, { sombra: true }) + bl.map(a => cel(txt(a ? { t: 'Ano: ' + a, b: true } : '', { al: 'center' }), LC, { sombra: true })).join(''));
      linhas.push(cel(txt(''), LR, { sombra: true }) + bl.map(a => cel(txt(a ? { t: 'Valor', b: true } : '', { al: 'center' }), LC, { sombra: true })).join(''));
      MESES.forEach((m, mi) => linhas.push(cel(txt({ t: m, b: true }), LR) + bl.map(a => { if (!a) return cel(txt(''), LC); const k = a + '-' + String(mi + 1).padStart(2, '0'); return cel(txt(fmtV(k, val[k] > 0 ? val[k] : null), { al: 'right' }), LC); }).join('')));
      linhas.push(cel(txt({ t: '13º SALÁRIO OU GRATIFICAÇÃO NATALINA', b: true }), LR) + bl.map(a => cel(txt(a ? (gn[a] > 0 ? fmtV(a + '-12', gn[a]) : 'X') : '', { al: 'right' }), LC)).join(''));
      blocos += tabela(larg, linhas) + par('', { depois: 120 });
    }
    const assin = (n, c) => par(n || '[nome]', { al: 'center', b: true, depois: 0 }) + par(c, { al: 'center', depois: 200 });
    const corpo = cabInst() + par('', { depois: 120 }) +
      par('RELAÇÃO DAS BASES DE CÁLCULO DE CONTRIBUIÇÃO', { al: 'center', b: true, sz: 22, depois: 0 }) +
      par('REFERENTE À ' + (d.referencia || '[CERTIDÃO DE TEMPO DE CONTRIBUIÇÃO Nº __/____, de __/__/____]').toUpperCase() + '.', { al: 'center', b: true, depois: 160 }) +
      tabCab + par('', { depois: 120 }) + blocos +
      par((d.local || 'Vitória') + ', ' + (d.dataEmissao || '[data]') + '.', { antes: 120, depois: 240 }) +
      assin(d.chefe, d.cargoChefe || 'Chefe da Divisão de Processamento de Folha de Pagamento') +
      par('UNIDADE GESTORA DO RPPS', { b: true, antes: 120 }) +
      par('Homologo, diante da inexistência de unidade gestora do RPPS, o presente documento e declaro que as informações nele constantes correspondem à verdade. ' + (d.local || 'Vitória') + ', ' + (d.dataEmissao || '[data]') + '.', { al: 'both', depois: 240 }) +
      assin(d.secretario, d.cargoSecretario || 'Secretária de Gestão de Pessoas');
    return pacote(JSZip, documento(corpo));
  }
  async function gerarCertidaoGNDocx(JSZip, d) {   // d: {texto, local, dataEmissao, assinante, cargoAssinante}
    const corpo = cabInst() + par('', { depois: 200 }) + par('CERTIDÃO', { al: 'center', b: true, sz: 22, depois: 240 }) +
      par(d.texto, { al: 'both', sz: 22, depois: 240 }) + par((d.local || 'Vitória') + ', ' + (d.dataEmissao || '[data]') + '.', { sz: 22, depois: 480 }) +
      par(d.assinante || '[nome]', { al: 'center', b: true, sz: 22, depois: 0 }) + par(d.cargoAssinante || '[cargo]', { al: 'center', sz: 22 });
    return pacote(JSZip, documento(corpo));
  }
  const dataExtenso = (dt) => { const M = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']; return dt.getDate() + ' de ' + M[dt.getMonth()] + ' de ' + dt.getFullYear(); };

  const api = { lerRBCDocx, lerRBCPdf, lerRBCPlanilha, pareceRBC, comparar, gerarCertidaoDocx, gerarCertidaoGNDocx, dataExtenso, grade };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.RBCCert = api;
})(typeof self !== 'undefined' ? self : this);
