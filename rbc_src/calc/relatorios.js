/* Leitura dos relatórios do RH (PDF com texto) — TRT-17 / DIPROF
 * Entrada: páginas no formato [{items:[{str,x,y,w}]}] (pdf.js). Saída: registros para a tabela esperada.
 */
(function (root) {
  'use strict';
  const DT = /(\d{2})\/(\d{2})\/(\d{4})/g;
  const isoBR = s => { const m = /(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s); return m ? `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}` : null; };
  const datas = s => [...s.matchAll(DT)].map(m => `${m[3]}-${m[2]}-${m[1]}`).filter(d => d > '1902');

  function linhas(pages) {
    const out = [];
    for (const pg of pages) {
      const its = pg.items.filter(i => i.str && i.str.trim()).sort((a, b) => a.y - b.y || a.x - b.x);
      const ls = [];
      for (const it of its) { const l = ls[ls.length - 1]; if (l && Math.abs(l.y - it.y) <= 2.5) l.t.push(it); else ls.push({ y: it.y, t: [it] }); }
      for (const l of ls) out.push(l.t.sort((a, b) => a.x - b.x).map(i => i.str.trim()).join(' ').replace(/\s+/g, ' ').normalize('NFC'));
    }
    return out;
  }
  const textoDe = pages => linhas(pages).join('\n');

  // identifica o tipo de relatório pelo cabeçalho
  function tipoRelatorio(pages) {
    const t = textoDe(pages).toUpperCase();
    const tf = t.replace(/\s+/g, ' ');
    { const mc = /(CERTID[ÃA]O|DECLARA[ÇC][ÃA]O)( COMPLEMENTAR)?( DE| À| A)?( CERTID[ÃA]O DE)? (TEMPO DE CONTRIBUI|TEMPO DE SERVI)/.exec(tf), mr = /RELA[ÇC][ÃA]O DAS BASES/.exec(tf);
      if (mc && (!mr || mc.index < mr.index)) return 'CTC'; }
    if (/COMISS[ÃA]O/.test(t) && /DISPENSA/.test(t)) return /SUBSTITU/.test(t) ? 'SUBSTITUICOES' : 'FUNCOES';
    if (/SUBSTITU/.test(t)) return 'SUBSTITUICOES';
    if (/INCORPORA/.test(t)) return 'VPNI';
    if (/ANU[ÊE]NIO|PERCENTUAL ACUMULADO/.test(t)) return 'ATS';
    if (/QUALIFICA|T[ÍI]TULO/.test(t)) return 'AQ';
    if (/REFER[ÊE]NCIA|PADR[ÃA]O|CLASSE/.test(t)) return 'PROGRESSAO';
    return null;
  }

  function parseFuncoes(pages) {
    const out = [];
    for (const l of linhas(pages)) {
      const mc = /\b((?:FC|CJ|DAS)-\d+)\b/.exec(l); const ds = datas(l);
      if (!mc || !ds.length) continue;
      // nome: texto após o código até o primeiro número (nº de vaga, datas); o relatório repete "nome" e "nome atual"
      const meio = l.slice(mc.index + mc[1].length).split(/\s\d/)[0].trim();
      const pal = meio.split(' '), h = Math.floor(pal.length / 2);
      const nome = pal.length % 2 === 0 && pal.slice(0, h).join(' ') === pal.slice(h).join(' ') ? pal.slice(0, h).join(' ') : meio;
      out.push({ cod: mc[1], nome, ini: ds[0], fim: ds[1] || null });
    }
    return out;
  }
  function parseVPNI(pages) {
    const out = [];
    for (const l of linhas(pages)) {
      const mc = /\b((?:FC|CJ|DAS)-\d+)\b/.exec(l); const ds = datas(l);
      if (!mc || ds.length < 2 || !/INCORPORA/i.test(l)) continue;
      const iDt = l.lastIndexOf(mc[1]);
      const depois = datas(l.slice(iDt));
      out.push({ cod: mc[1], tipo: /QUINT/i.test(l) ? 'QUINTOS' : 'DECIMOS', natureza: /JUDICIAL/i.test(l) ? 'JUDICIAL' : 'ADMINISTRATIVA',
        ini: depois[0] || ds[ds.length - 1], fim: depois[1] || null, perda: /\bSim\s*$/i.test(l) });
    }
    return out.filter(v => !v.perda);
  }
  function parseATS(pages) {
    const out = [];
    for (const l of linhas(pages)) {
      if (!/ANU[ÊE]NIO|QUINQU|TRIÊNIO/i.test(l)) continue;
      const ds = datas(l); const conc = ds[ds.length - 1];
      const mm = /(\d+(?:,\d+)?)\s+(?:ANU[ÊE]NIO|QUINQU\S*|TRI[ÊE]NIO)\s+(\d+(?:,\d+)?)/i.exec(l);
      if (!conc || !mm) continue;
      out.push({ ini: conc, pct: +mm[2].replace(',', '.'), concedido: +mm[1].replace(',', '.') });
    }
    return out.sort((a, b) => a.ini < b.ini ? -1 : 1);
  }
  // progressão com texto: as colunas são identificadas pelo cabeçalho (posição x), porque o relatório traz várias datas
  // por linha (mudança, fim, publicação e alteração do ato). Formatos vistos:
  //  - "Dt. Mudança | Data Fim | Nº Ato Public. | Dt. Ato Public. | Nº do Ato Alteração | Dt. Ato Alteração | Nº de Protocolo | Classe | Padrão | Tipo | Situação"
  //  - "Data da Alteração | Data Fim Alteração | Data da Revogação | Classe | Padrão | Nível da Referência | Tipo do Documento | Nº Documento | Data Documento"
  function linhasItens(pages) {
    const out = [];
    for (const pg of pages) {
      const its = pg.items.filter(i => i.str && i.str.trim()).sort((a, b) => a.y - b.y || a.x - b.x);
      const ls = [];
      for (const it of its) { const l = ls[ls.length - 1]; if (l && Math.abs(l.y - it.y) <= 2.5) l.t.push(it); else ls.push({ y: it.y, t: [it] }); }
      for (const l of ls) { l.t.sort((a, b) => a.x - b.x); out.push(l.t.map(i => ({ s: i.str.trim(), x: i.x, c: i.x + (i.w || i.str.length * 4) / 2 }))); }
    }
    return out;
  }
  const DT1 = /^\d{1,2}\/\d{1,2}\/\d{4}$/;
  function colunaDe(txt) {
    const t = txt.toUpperCase();
    if (/REVOGA/.test(t)) return 'revog';
    if (/FIM/.test(t)) return 'fim';
    if (/\bATO\b|PROTOCOLO|PUBLIC|DOCUMENTO|N[ºO°]\.?\s/.test(t)) return 'outro';
    if (/MUDAN|ALTERA|IN[IÍ]CIO|VIG[EÊ]NCIA/.test(t)) return 'ini';
    if (/^CLASSE/.test(t)) return 'classe';
    if (/PADR/.test(t)) return 'padrao';
    if (/N[IÍ]VEL/.test(t)) return 'nivel';
    if (/^TIPO/.test(t)) return 'tipo';
    if (/SITUA/.test(t)) return 'situacao';
    return 'outro';
  }
  // divide um item de texto em palavras, estimando a posição x de cada uma (o PDF pode juntar células num item só)
  function tokens(l) {
    const out = [];
    for (const t of l) {
      const w = 2 * (t.c - t.x), n = t.s.length || 1;
      const re = /\S+/g; let m;
      while ((m = re.exec(t.s))) { const x = t.x + w * m.index / n, ww = w * m[0].length / n; out.push({ s: m[0], x, c: x + ww / 2 }); }
    }
    return out;
  }
  const temData = l => l.some(t => /\d{1,2}\/\d{1,2}\/\d{4}/.test(t.s));
  function parseProgressao(pages) {
    const L = linhasItens(pages);
    // cabeçalho: a linha que tem "Classe" e "Padrão" (e até duas linhas sem data logo acima ou abaixo, para rótulos em 2 linhas)
    const txt = l => l.map(t => t.s).join(' ').toUpperCase();
    // ignora linhas de identificação do tipo "Classe: C  Padrão: 13" (referência atual) e fica com o cabeçalho seguido de dados
    const ehCab = l => { const t = txt(l); return /CLASSE/.test(t) && /PADR/.test(t) && !/CLASSE\s*:|PADR[AÃ]O\s*:/.test(t) && !temData(l); };
    let iCab = -1;
    for (let i = 0; i < L.length; i++) if (ehCab(L[i]) && L.slice(i + 1, i + 4).some(l => temData(l) && DT1.test(tokens(l)[0].s))) { iCab = i; break; }
    if (iCab < 0) iCab = L.findIndex(ehCab);
    if (iCab < 0) return parseProgressaoRegex(pages);
    const cab = [...L[iCab]];
    for (const d of [-1, -2, 1]) { const l = L[iCab + d]; if (!l || temData(l) || !l.some(t => /[A-Za-zÀ-ú]/.test(t.s))) { if (d < 0) continue; else break; } cab.push(...l); }
    const grupos = [];
    for (const t of cab.sort((a, b) => a.c - b.c)) {
      const g = grupos.find(g => Math.abs(g.c - t.c) < 18 || (t.c >= g.x0 && t.c <= g.x1));
      if (g) { g.txt.push(t); g.x0 = Math.min(g.x0, t.x); g.x1 = Math.max(g.x1, t.x + 2 * (t.c - t.x)); g.c = (g.x0 + g.x1) / 2; }
      else grupos.push({ c: t.c, x0: t.x, x1: t.x + 2 * (t.c - t.x), txt: [t] });
    }
    for (const g of grupos) g.col = colunaDe(g.txt.sort((a, b) => a.x - b.x).map(t => t.s).join(' '));
    if (!grupos.some(g => g.col === 'classe')) return parseProgressaoRegex(pages);
    const out = [];
    for (let i = iCab + 1; i < L.length; i++) {
      const tk = tokens(L[i]); if (!tk.some(t => DT1.test(t.s))) continue;
      const v = {};
      for (const t of tk) {
        let best = null, bd = 1e9; for (const g of grupos) { const d = t.c < g.x0 ? g.x0 - t.c : t.c > g.x1 ? t.c - g.x1 : 0; const dd = d * 1000 + Math.abs(g.c - t.c); if (dd < bd) { bd = dd; best = g; } }
        (v[best.col] = v[best.col] || []).push(t.s);
      }
      const j = k => (v[k] || []).join(' ').trim();
      const dt = k => { const m = /\d{1,2}\/\d{1,2}\/\d{4}/.exec(j(k)); return m ? isoBR(m[0]) : null; };
      const ini = dt('ini') || isoBR(tk.find(t => DT1.test(t.s)).s), fim = dt('fim');
      let classe = j('classe'), padrao = j('padrao');
      if (!padrao && /\s/.test(classe)) { const m = /^(.*\S)\s+(\S+)$/.exec(classe); classe = m[1]; padrao = m[2]; }
      if (!classe && /\s/.test(padrao)) { const m = /^(\S+)\s+(.*)$/.exec(padrao); classe = m[1]; padrao = m[2]; }
      const sit = j('situacao').toUpperCase();
      const revogada = !!dt('revog') || /REVOG|CANCEL|INV[AÁ]LID|ANULAD|SEM EFEITO|TORNAD/.test(sit);
      if (!ini || !classe) continue;
      out.push({ ini, fim, revogada, classe: classe.toUpperCase().replace(/\s*-\s*/, '-'), padrao: padrao.toUpperCase(), tipo: j('tipo') });
    }
    return out.length ? out.sort((a, b) => a.ini < b.ini ? -1 : a.ini > b.ini ? 1 : 0) : parseProgressaoRegex(pages);
  }

  // ---------------------------------------------------------------- relatórios em planilha (CSV, XLS, XLSX)
  // rows: matriz de células (texto). Reconhece o cabeçalho pelos nomes das colunas e o tipo pelo cabeçalho e pelo nome do arquivo.
  const norm = s => String(s == null ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/\s+/g, ' ').trim();
  function dataCel(v) {
    const s = String(v == null ? '' : v).trim(); let m;
    if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/.exec(s))) { const y = m[3].length === 2 ? ((+m[3] < 50 ? '20' : '19') + m[3]) : m[3]; return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`; }
    if ((m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s))) return `${m[1]}-${m[2]}-${m[3]}`;
    if (/^\d{4,5}(\.\d+)?$/.test(s) && +s > 20000 && +s < 80000) { const d = new Date(Date.UTC(1899, 11, 30) + Math.round(+s) * 864e5); return d.toISOString().slice(0, 10); }
    return null;
  }
  function tabelaRelatorio(rows, nomeArq) {
    const nome = norm(nomeArq);
    let iH = -1, H = null;
    for (let i = 0; i < Math.min(rows.length, 30); i++) {
      const h = rows[i].map(norm); const t = h.join(' | ');
      const k = [/CLASSE/, /PADR/, /FUN[CÇ]/, /DESIGNA|NOMEA/, /DISPENSA|EXONERA/, /INCORPORA|QUINTOS|DECIMOS|FRACAO/, /ANUENIO|PERCENTUAL/, /SUBSTITU/, /MUDANCA|ALTERACAO|INICIO|VIGENCIA|CONCESSAO/, /FIM|TERMINO/].filter(r => r.test(t)).length;
      if (k >= 2) { iH = i; H = h; break; }
    }
    if (iH < 0) return { tipo: null, rows: [] };
    const ht = H.join(' | ');
    const tipo = (/CLASSE/.test(ht) && /PADR/.test(ht)) || /PROGRESS|ENQUADRA/.test(nome) ? 'PROGRESSAO'
      : /SUBSTITU/.test(ht) || /SUBSTITU/.test(nome) ? 'SUBSTITUICOES'
      : /INCORPORA|QUINTOS|DECIMOS|FRACAO|VPNI/.test(ht) || /VPNI|QUINTOS|DECIMOS/.test(nome) ? 'VPNI'
      : /ANUENIO|PERCENTUAL ACUM|ADICIONAL POR TEMPO/.test(ht) || /\bATS\b|ANUENIO/.test(nome) ? 'ATS'
      : /FUN[CÇ]|COMISS/.test(ht) || /FUNC/.test(nome) ? 'FUNCOES' : null;
    const col = (...res) => H.findIndex(h => h && res.some(r => r.test(h)));
    const cIni = col(/MUDANCA/, /DATA DA ALTERACAO|DT\.? ALTERACAO$/, /INICIO|INICIAL|DESIGNA|NOMEA|CONCESSAO|VIGENCIA|A PARTIR/, /^DATA$/);
    const cFim = col(/FIM|FINAL|TERMINO|DISPENSA|EXONERA/), cRev = col(/REVOGA/), cSit = col(/SITUA/);
    const cCl = col(/^CLASSE/), cPd = col(/PADR/), cPct = col(/PERCENTUAL ACUM|ACUMULADO/, /PERCENTUAL|%/);
    const out = [];
    for (const r of rows.slice(iH + 1)) {
      const cel = i => i >= 0 ? String(r[i] == null ? '' : r[i]).trim() : '';
      const linha = r.map(x => String(x == null ? '' : x)).join(' ');
      const ini = dataCel(cel(cIni)) || (r.map(dataCel).find(Boolean) || null); if (!ini) continue;
      const fim = dataCel(cel(cFim));
      if (tipo === 'PROGRESSAO') {
        let classe = cel(cCl), padrao = cel(cPd); if (!classe) continue;
        const revogada = !!dataCel(cel(cRev)) || /REVOG|CANCEL|INV[AÁ]LID|ANULAD|SEM EFEITO/i.test(cel(cSit));
        out.push({ ini, fim, revogada, classe: classe.toUpperCase().replace(/\s*-\s*/, '-'), padrao: padrao.toUpperCase() });
      } else if (tipo === 'FUNCOES' || tipo === 'SUBSTITUICOES') {
        const m = /\b((?:FC|CJ|DAS)\s*-?\s*\d+)\b/i.exec(linha); if (!m) continue;
        const cod = m[1].toUpperCase().replace(/\s+/g, '').replace(/^(FC|CJ|DAS)-?(\d)$/, '$1-0$2').replace(/^(FC|CJ|DAS)(\d)/, '$1-$2');
        const cNome = col(/DESCRI|DENOMINA|^FUNCAO$|NOME DA FUN/);
        out.push({ cod, nome: cNome >= 0 ? cel(cNome) : '', ini, fim });
      } else if (tipo === 'VPNI') {
        const m = /\b((?:FC|CJ|DAS)\s*-?\s*\d+)\b/i.exec(linha); if (!m) continue;
        if (/\bSIM\b/i.test(cel(col(/PERDA/)))) continue;
        out.push({ cod: m[1].toUpperCase().replace(/\s+/g, '').replace(/^(FC|CJ|DAS)(\d)/, '$1-$2'), tipo: /QUINT/i.test(linha) ? 'QUINTOS' : 'DECIMOS', natureza: /JUDIC/i.test(linha) ? 'JUDICIAL' : 'ADMINISTRATIVA', ini, fim });
      } else if (tipo === 'ATS') {
        const pct = parseFloat(String(cel(cPct)).replace('%', '').replace(',', '.')); if (!isFinite(pct)) continue;
        out.push({ ini, pct });
      }
    }
    return { tipo, rows: out.sort((a, b) => a.ini < b.ini ? -1 : 1) };
  }
  // CSV: separador detectado (; , tab) e aspas
  function lerCSV(texto) {
    const linha1 = texto.split(/\r?\n/).find(l => l.trim()) || '';
    const sep = [';', '\t', ','].sort((a, b) => linha1.split(b).length - linha1.split(a).length)[0];
    const rows = []; let row = [], cur = '', q = false;
    for (let i = 0; i < texto.length; i++) {
      const ch = texto[i];
      if (q) { if (ch === '"') { if (texto[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; continue; }
      if (ch === '"') q = true; else if (ch === sep) { row.push(cur); cur = ''; } else if (ch === '\n') { row.push(cur.replace(/\r$/, '')); rows.push(row); row = []; cur = ''; } else cur += ch;
    }
    if (cur || row.length) { row.push(cur); rows.push(row); }
    return rows;
  }

  // formato antigo, sem cabeçalho identificável
  function parseProgressaoRegex(pages) {
    const out = [];
    for (const l of linhas(pages)) {
      const m = /^\D{0,40}?(\d{1,2}\/\d{1,2}\/\d{4})(?:\s+(\d{1,2}\/\d{1,2}\/\d{4}))?/.exec(l); if (!m) continue;
      const resto = l.slice(m.index + m[0].length);
      const cp = /(?:^|\s)((?:N[ISA]\s*-\s*)?[A-D]|N[ASI])\s*-?\s*([IVX]{1,3}|\d{1,2})(?=\s|$)/.exec(resto); if (!cp) continue;
      out.push({ ini: isoBR(m[1]), fim: m[2] ? isoBR(m[2]) : null, revogada: /REVOG|CANCEL|INV[AÁ]LID/i.test(resto), classe: cp[1].replace(/\s/g, '').toUpperCase(), padrao: cp[2].toUpperCase() });
    }
    return out.sort((a, b) => a.ini < b.ini ? -1 : 1);
  }


  // progressão lida por OCR (relatório em imagem): datas confiáveis, classe/padrão só como pista
  function parseProgressaoTexto(texto) {
    const out = [];
    for (const raw of String(texto).split(/\n/)) {
      const l = raw.trim(); if (!/^\d{2}\/\d{1,3}\/\d{4}/.test(l)) continue;
      const ds = [], re = /(\d{2})\/(\d{1,3})\/(\d{4})/g; let m, fimDatas = 0;
      while ((m = re.exec(l)) && ds.length < 3) {
        const entre = l.slice(fimDatas, m.index).trim();
        if (ds.length && entre && !/^[\s—–\-|_.,:;'"]*$/.test(entre)) break;
        ds.push(`${m[3]}-${m[2].slice(-2).padStart(2, '0')}-${m[1]}`); fimDatas = re.lastIndex;
      }
      const resto = l.slice(fimDatas).split(/[NMH][ÍI]VEL/i)[0].trim();
      out.push({ ini: ds[0], fim: ds.length >= 2 ? ds[1] : null, revogada: ds.length >= 3, dica: resto });
    }
    return out;
  }

  // AQ: formato ainda não validado com relatório real — leitura por palavras-chave
  function parseAQ(pages) {
    const out = [];
    for (const l of linhas(pages)) {
      const ds = datas(l); if (!ds.length) continue;
      const u = l.toUpperCase();
      const tipo = /DOUTOR/.test(u) ? 'DOUTORADO' : /MESTR/.test(u) ? 'MESTRADO' : /ESPECIALIZ|P[ÓO]S-?GRAD/.test(u) ? 'ESPECIALIZACAO'
        : /TREINAM|CAPACIT|A[ÇC][ÕO]ES? DE/.test(u) ? 'TREINAMENTO' : /GRADUA/.test(u) ? 'GRADUACAO_TECNICO' : null;
      if (!tipo) continue;
      const pm = /(\d+(?:,\d+)?)\s*%/.exec(l);
      out.push({ tipo, ini: ds[0], fim: ds[1] || null, pct: pm ? +pm[1].replace(',', '.') : null });
    }
    return out;
  }
  // junta leituras de OCR feitas em resoluções diferentes (uma pode perder linhas que a outra pega)
  const dataOk = d => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || ''); return !!m && +m[1] >= 1950 && +m[1] <= 2100 && +m[2] >= 1 && +m[2] <= 12 && +m[3] >= 1 && +m[3] <= 31; };
  function juntarProgressoes(listas) {
    const out = new Map();
    for (const lst of listas) for (const p of lst) {
      if (!dataOk(p.ini) || (p.fim && !dataOk(p.fim))) continue;
      const k = p.ini + '|' + (p.revogada ? 1 : 0);
      if (!out.has(k)) out.set(k, Object.assign({}, p));
    }
    return [...out.values()].sort((a, b) => a.ini < b.ini ? -1 : a.ini > b.ini ? 1 : (a.revogada ? -1 : 1));
  }

  // dados do servidor no cabeçalho do relatório de progressão (Sistema de Gestão de RH)
  function dadosServidor(pages) {
    const t = linhas(pages).slice(0, 25).join('\n'), o = {};
    let m;
    if ((m = /Nome\s*:\s*([A-ZÀ-Ú][A-ZÀ-Ú .'-]+?)(?:\s{2,}|\s+Data|$)/m.exec(t))) o.nome = m[1].trim();
    if ((m = /Data de Exerc[ií]cio\s*:\s*(\d{1,2}\/\d{1,2}\/\d{4})/i.exec(t))) o.exercicio = isoBR(m[1]);
    if ((m = /Data (?:da )?Posse\s*:\s*(\d{1,2}\/\d{1,2}\/\d{4})/i.exec(t))) o.posse = isoBR(m[1]);
    if ((m = /Cargo\s*:\s*(T[ÉE]CNICO|ANALISTA|AUXILIAR)\s+JUDICI[ÁA]RIO/i.exec(t))) o.cargo = m[1].toUpperCase().replace('TECNICO', 'TÉCNICO') + ' JUDICIÁRIO';
    if ((m = /Espec[ií]?l?idade\s*:\s*([^\n]+)/i.exec(t))) { const e = m[1].toUpperCase(); o.especialidade = /SEGURAN|POL[IÍ]CIA/.test(e) ? 'SEGURANCA' : /MANDADO|OFICIAL/.test(e) ? 'OFICIAL' : ''; }
    return o;
  }

  // ------------------------------------------------------------------ CTC / declaração de tempo de contribuição (SEINFO)
  // A DIPROF nem sempre recebe os relatórios do RH: a CTC traz cargo, período, progressão, funções, anuênios, quintos,
  // afastamentos e se a contribuição foi limitada ao teto do RGPS. Formatos: CTC/DTC do SEI (texto) e CTC antiga digitalizada
  // (texto de OCR, com ruído — usa-se o que for legível).
  const ROM = { I: 1, II: 2, III: 3, IV: 4, V: 5, VI: 6, VII: 7, VIII: 8, IX: 9, X: 10 };
  const dBR = s => { const m = /(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{4})/.exec(s || ''); return m ? `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}` : null; };
  const RXD = /(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/g;
  function secao(ls, ini, fins) {
    const i = ls.findIndex(l => ini.test(l)); if (i < 0) return [];
    const out = [];
    for (let j = i + 1; j < ls.length; j++) { if (fins.some(f => f.test(ls[j]))) break; out.push(ls[j]); }
    return out;
  }
  const FIM_SEC = [/^\s*(\d+ ?- ?)?(FREQU[ÊE]NCIA|AVERBA|EXERC[ÍI]CIO DE CARGO|ANU[ÊE]NIOS|INCORPORA|OBSERVA[ÇC]|PROGRESS[ÃA]O FUNCIONAL|F[ÉE]RIAS|DESLIGAMENTO|CERTIFICO|VANTAGENS|INFORMA[ÇC][ÃA]O CESS)/i];
  function parseCTC(pages) {
    const ls = (typeof pages === 'string' ? pages.split('\n').map(l => l.replace(/\s+/g, ' ').trim().normalize('NFC')) : linhas(pages)).filter(l => !/^(Certid|Declara)\S* de Tempo de Contribui\S* \d+ .*SEI /i.test(l) && !/^id[ãa]o de Tempo/i.test(l));
    const t = ls.join('\n'), flat = t.replace(/\s+/g, ' '), up = flat.toUpperCase();
    const meta = {};
    // cargo (e especialidade)
    const mcg = /CARGO EFETIVO:?\s*(.{0,120})/i.exec(flat);
    if (mcg) {
      const c = mcg[1].toUpperCase();
      meta.cargo = /ANALISTA/.test(c) ? 'ANALISTA JUDICIÁRIO' : /T[ÉE]CNICO/.test(c) ? 'TÉCNICO JUDICIÁRIO' : /AUXILIAR/.test(c) ? 'AUXILIAR JUDICIÁRIO' : /JUIZ/.test(c) ? 'JUIZ' : '';
      meta.especialidade = /OFICIAL DE JUSTI/.test(c) ? 'OFICIAL' : /SEGURAN|POL[ÍI]CIA|AGENTE DE/.test(c) ? 'SEGURANCA' : '';
      meta.cargoTexto = mcg[1].replace(/\s*(REGIME JUR|ÓRG[ÃA]O DE LOTA).*$/i, '').trim();
    }
    const ex = /EFETIVO EXERC[ÍI]CIO:?\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/i.exec(flat) || /POSSE:?\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/i.exec(flat);
    if (ex) meta.exercicio = dBR(ex[1]);
    const per = /PER[ÍI]ODO DE CONTRIBUI\S*[^:]*:?\s*(?:DE\s+)?(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4})\s*(?:A|ATÉ|ATE)\s*(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4})/i.exec(flat);
    if (per) { meta.periodoIni = dBR(per[1]); meta.periodoFim = dBR(per[2]); }
    const vac = /(VAC[ÂA]NCIA|EXONERA\S*|DECLARADO VAGO A PARTIR DE|DESLIGAD\S* EM|APOSENTADORIA)\D{0,40}(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/i.exec(flat);
    if (vac) meta.vacancia = dBR(vac[2]);
    meta.inicio = meta.periodoIni || meta.exercicio || null;
    meta.fim = meta.periodoFim || null;
    // dados para o cabeçalho da RBC (ficam só no navegador)
    const tiraSexo = n => n && n.replace(/\s+(MASCULINO|FEMININO|[MF])$/, '').trim();
    let mm = /SERVIDOR(?:\(A\))?:?\s*([A-ZÀ-Ú][A-ZÀ-Ú .']{4,80}?)\s+(?:SEXO|MATR|CPF|CI\b|$)/.exec(flat) || /NOME(?: DO SERVIDOR)?:\s*([A-ZÀ-Ú][A-ZÀ-Ú .']{4,80}?)\s+(?:SEXO|MATR|CPF|$)/.exec(flat);
    if (mm) meta.nome = tiraSexo(mm[1].trim());
    mm = /MATR[ÍI]CULA:?\s*(\d[\d. ]{2,14}\d)/.exec(flat); if (mm) meta.matricula = mm[1].replace(/\s+/g, '');
    mm = /\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b/.exec(flat); if (mm) meta.cpf = mm[1];
    mm = /PIS\s*\/?\s*PASEP:?.{0,120}?\b(\d{1,3}\.\d{3}\.\d{3}\.\d{2,3}-?\d|\d{11})\b/i.exec(flat); if (mm) meta.pis = mm[1];
    mm = /NASCIMENTO:?.{0,160}?(\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4})/i.exec(flat); if (mm) meta.nascimento = (dBR(mm[1]) || '').split('-').reverse().join('/');
    mm = /NOME DA M[ÃA]E:?\s*([A-ZÀ-Úa-zà-ú][A-Za-zÀ-ú .']{4,80}?)\s+(?:DATA|NASC|CPF|PIS|$)/.exec(flat);
    if (mm) meta.mae = mm[1].trim();
    else {
      // "FILIAÇÃO: PAI e MÃE" (uma ou mais linhas, às vezes intercaladas com a data de nascimento): a mãe vem por último
      const i = ls.findIndex(l => /FILIA[ÇC][ÃA]O/i.test(l));
      if (i >= 0) {
        const partes = [];
        for (let j = i; j < Math.min(ls.length, i + 6); j++) {
          if (j > i && /ENDERE|CARGO|^RG\b|^CI\b|ADMISS|SEXO|LOTA|^\d+ ?-/i.test(ls[j])) break;
          const t = ls[j].replace(/FILIA[ÇC][ÃA]O:?|DATA DE NASCIMENTO:?|NASCIMENTO:?|\d{1,2}[\/.\-]\d{1,2}[\/.\-]\d{4}/gi, ' ').replace(/\s+/g, ' ').trim();
          if (t && /^[A-Za-zÀ-ú .']+$/.test(t)) partes.push(t);
        }
        const tudo = partes.join(' ').trim();
        const nomes = tudo.split(/\s+e\s+/i).map(x => x.trim()).filter(x => x.length > 3);
        meta.filiacao = nomes.length > 1 ? nomes : partes;
        if (meta.filiacao.length) meta.mae = meta.filiacao[meta.filiacao.length - 1];
      }
    }
    if (!meta.nome) {
      const i = ls.findIndex(l => /^\s*(SERVIDOR(?:\(A\))?|NOME):?\s*$/i.test(l) || /^\s*SERVIDOR(?:\(A\))?:?\s+SEXO/i.test(l));
      if (i >= 0 && ls[i + 1]) { const m2 = /^([A-ZÀ-Ú][A-ZÀ-Ú .']{4,80}?)(?:\s+[MF]\s|\s+\d|\s*$)/.exec(ls[i + 1].trim()); if (m2) meta.nome = tiraSexo(m2[1].trim()); }
    }
    if (meta.nome) meta.nome = tiraSexo(meta.nome);
    mm = /(CERTID[ÃA]O|DECLARA[ÇC][ÃA]O)(?: COMPLEMENTAR)? DE TEMPO DE (?:CONTRIBUI[ÇC][ÃA]O|SERVI[ÇC]O).{0,80}?N[º°o]\.?\s*(\d+\s*\/\s*\d{4})/i.exec(flat);
    const tipoDoc = /DECLARA[ÇC][ÃA]O(?: COMPLEMENTAR)? (?:DE|À) /i.test(flat.slice(0, 1500)) && !/CERTID[ÃA]O DE TEMPO/i.test(flat.slice(0, 600)) ? 'DECLARAÇÃO DE TEMPO DE CONTRIBUIÇÃO' : 'CERTIDÃO DE TEMPO DE CONTRIBUIÇÃO';
    if (mm) meta.ctcNumero = mm[2].replace(/\s+/g, '');
    const assin = [...flat.matchAll(/assinado eletronicamente por [^,]{3,80},[^,]{0,80}?,? em (\d{2}\/\d{2}\/\d{4})/gi)].map(x => x[1]);
    const vit = [...flat.matchAll(/Vit[óo]ria(?:-ES)?,?\s*(?:em\s*)?(\d{1,2})[-\/.](\d{1,2})[-\/.](\d{4})/gi)].map(x => x[1].padStart(2, '0') + '/' + x[2].padStart(2, '0') + '/' + x[3]);
    meta.ctcData = assin[0] || vit[vit.length - 1] || '';
    meta.tipoDoc = tipoDoc;
    meta.referencia = tipoDoc === 'DECLARAÇÃO DE TEMPO DE CONTRIBUIÇÃO' ? `${tipoDoc}${meta.ctcData ? ' DATADA DE ' + meta.ctcData : ''}` : `${tipoDoc}${meta.ctcNumero ? ' Nº ' + meta.ctcNumero : ''}${meta.ctcData ? ', de ' + meta.ctcData : ''}`;
    mm = /SEI\s+(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})/.exec(flat); if (mm) meta.processo = mm[1];
    // previdência complementar: teto do RGPS
    if (/LIMITAD\S* AO TETO DO (REGIME GERAL|RGPS)/.test(up)) meta.teto = 'sim';
    else if (/\bE ADERIU AO REGIME DE PREVID[ÊE]NCIA COMPLEMENTAR|\bE OPTOU PELA ADES[ÃA]O/.test(up) && !/N[ÃA]O OPTOU PELA ADES/.test(up)) meta.teto = 'migrou';
    else if (/N[ÃA]O ADERIU AO REGIME DE PREVID[ÊE]NCIA COMPLEMENTAR|N[ÃA]O OPTOU PELA ADES/.test(up)) meta.teto = 'nao';
    const mig = /(?:ADERIU|MIGRA\S*|OP[ÇC][ÃA]O)[^.]{0,160}?(?:EM|A PARTIR DE|DESDE)\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/i.exec(flat);
    if (meta.teto === 'migrou' && mig) meta.tetoDesde = dBR(mig[1]);
    // progressão: "Classe A, Padrão 1 = de 02/06/2023 a 01/06/2024 - ...", "Classe D, Padrão III = ...", "Classe A, Ref. NA-03 = ..."
    const PROGRESSAO = [];
    const rx = /CLASSE\s+([A-D])\s*,?\s*(?:PADR[ÃA]O|REF\.?|REFER[ÊE]NCIA)\s*([A-Z]{2}\s*-?\s*\d+|[IVX]+|\d+)\s*=?\s*(?:DE\s+)?(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})(?:\s*(?:A|ATÉ|ATE)\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4}))?/gi;
    for (const m of flat.matchAll(rx)) {
      let classe = m[1].toUpperCase(), padrao = m[2].toUpperCase().replace(/\s+/g, '');
      const nv = /^(N[AIS])-?(\d+)$/.exec(padrao); if (nv) { classe = nv[1]; padrao = String(+nv[2]); }
      else if (/^\d+$/.test(padrao)) padrao = String(+padrao);
      PROGRESSAO.push({ ini: dBR(m[3]), fim: dBR(m[4]) || '', classe, padrao, origem: 'relatorio', fonte: 'CTC' });
    }
    // CTC antiga: "Cargo efetivo: Técnico Judiciário, Classe C, Padrão 15" (referência na data da certidão)
    const atual = /CARGO EFETIVO:?[^,]{0,60},\s*CLASSE\s+([A-D])\s*,\s*PADR[ÃA]O\s+(\w+)/i.exec(flat);
    if (atual) meta.refFinal = atual[1].toUpperCase() + '-' + atual[2];
    // funções comissionadas
    const FUNCOES = [];
    let ult = null;
    for (const l of secao(ls, /CARGO EM COMISS[ÃA]O\s*\/\s*FUN[ÇC][ÃA]O COMISSIONADA|EXERC[ÍI]CIO DE CARGO EM COMISS/i, FIM_SEC)) {
      const mc = /\b((?:FC|CJ|DAS)\s*-?\s*0?(\d+))\b/i.exec(l);
      const ds = [...l.matchAll(RXD)].map(x => dBR(x[1]));
      if (mc) ult = { cod: mc[1].toUpperCase().replace(/\s+/g, '').replace(/^(FC|CJ|DAS)-?0?/, '$1-').replace(/-(\d)$/, '-0$1'), nome: l.slice(0, mc.index).replace(/[-–]\s*$/, '').trim() };
      if (!ult || !ds.length) continue;
      // "1 a 13-6-1991" (CTC antiga): mesmo mês
      for (let i = 0; i < ds.length; i += 2) FUNCOES.push({ cod: ult.cod, nome: ult.nome, ini: ds[i], fim: ds[i + 1] || null });
    }
    // anuênios: "1% a partir de 01/10/1995"
    const ATS = [];
    for (const l of secao(ls, /^\s*(\d+ ?- ?)?ANU[ÊE]NIOS/i, FIM_SEC)) {
      for (const m of l.matchAll(/(\d+(?:,\d+)?)\s*%\s*(?:A PARTIR DE|DESDE|EM)?\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})/gi)) ATS.push({ ini: dBR(m[2]), pct: +m[1].replace(',', '.'), fim: '' });
    }
    ATS.sort((a, b) => a.ini < b.ini ? -1 : 1);
    // quintos/décimos incorporados: "1/5 (um quinto) da função comissionada ... FC-3, com efeitos a partir de 17/07/1996 a 23/02/1997"
    const VPNI = [];
    const tq = secao(ls, /INCORPORA[ÇC][ÃA]O DE QUINTOS|INCORPORA[ÇC][ÕO]ES/i, FIM_SEC).join(' ').replace(/\s+/g, ' ');
    for (const m of tq.matchAll(/(\d+)\s*\/\s*(5|10)\b.{0,160}?((?:FC|CJ|DAS)\s*-?\s*\d+).{0,80}?A PARTIR DE\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4})(?:\s*A\s*(\d{1,2}[\/.]\d{1,2}[\/.]\d{4}))?/gi)) {
      const cod = m[3].toUpperCase().replace(/\s+/g, '').replace(/^(FC|CJ|DAS)-?0?/, '$1-').replace(/-(\d)$/, '-0$1');
      VPNI.push({ cod, tipo: m[2] === '5' ? 'QUINTOS' : 'DECIMOS', natureza: 'ADMINISTRATIVA', parcelas: +m[1], ini: dBR(m[4]), fim: dBR(m[5]) || '' });
    }
    // afastamentos e faltas (texto livre): só registro, a calculadora não desconta sem decisão
    const afast = [];
    for (const l of secao(ls, /^\s*(\d+ ?- ?)?OBSERVA[ÇC]/i, FIM_SEC)) { const ds = [...l.matchAll(RXD)].map(x => dBR(x[1])); if (ds.length) afast.push({ texto: l.trim(), ini: ds[0], fim: ds[1] || ds[0] }); }
    const freq = [];
    for (const l of secao(ls, /FREQU[ÊE]NCIA/i, [/^\s*(\d+ ?- ?)?(AVERBA|EXERC[ÍI]CIO DE CARGO|INFORMA[ÇC][ÃA]O CESS|DISCRIMINA)/i])) {
      const m = /^\s*((?:19|20)\d{2})\s+(\d+)\s+(.*)$/.exec(l); if (!m) continue;
      const nums = m[3].split(/\s+/).map(x => x === '-' ? 0 : +x).filter(x => !isNaN(x));
      freq.push({ ano: m[1], bruto: +m[2], liquido: nums.length ? nums[nums.length - 1] : +m[2], faltas: nums.length > 1 ? nums[0] : 0 });
    }
    return { meta, PROGRESSAO, FUNCOES, ATS, VPNI, afastamentos: afast, frequencia: freq };
  }

  const api = { parseCTC, dadosServidor, tabelaRelatorio, lerCSV, dataCel, parseAQ, juntarProgressoes, parseProgressaoTexto, linhas, tipoRelatorio, parseFuncoes, parseVPNI, parseATS, parseProgressao, isoBR };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.RBCRelatorios = api;
})(typeof self !== 'undefined' ? self : this);
