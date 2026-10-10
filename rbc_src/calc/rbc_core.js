/* Motor da Calculadora de RBC — TRT-17 / DIPROF
 * Funções puras (sem DOM). Usado pela página HTML e pelos testes em Node.
 */
(function (root) {
  'use strict';
  const MES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
  const NUM = /^-?[\d.]*\d,\d{2}$|^0$/;
  const brNum = s => parseFloat(String(s).replace(/\./g, '').replace(',', '.'));
  const r2 = v => Math.round((v + Number.EPSILON) * 100) / 100;
  const ym = (y, m) => `${y}-${String(m).padStart(2, '0')}`;
  const addM = (k, n) => { let y = +k.slice(0, 4), m = +k.slice(5, 7) + n; while (m > 12) { m -= 12; y++; } while (m < 1) { m += 12; y--; } return ym(y, m); };
  const diasMes = k => new Date(+k.slice(0, 4), +k.slice(5, 7), 0).getDate();
  // divisor do pro rata: mês comercial de 30 dias até a competência anterior a DIV.desde; depois, dias do mês
  // antes de 07/1994 a DIPROF usa os dias do mês (prática da RBC de servidor com período em Cr$); de 07/1994 a 11/2017, 30 dias
  const DIV = { desde: '2017-12', de30: '1994-07' };
  const divisor = k => (k >= DIV.desde || k < DIV.de30 ? diasMes(k) : 30);

  // ------------------------------------------------------------------ LEITURA DE FICHAS
  /** Planilha longa do sistema antigo (Ano, Mês, Tipo, Código Rubrica, Descrição Rubrica, Tipo Rubrica, Sequencial Rubrica, Valor Rubrica) */
  function parseLongRows(rows) {
    const out = [];
    for (const r of rows) {
      const ano = +r['Ano'], mes = +r['Mês'];
      if (!ano || !mes) continue;
      const nat = String(r['Tipo Rubrica'] || '').trim().toUpperCase();
      const v = +r['Valor Rubrica'] || 0;
      const tipo = +r['Tipo'] || 0;
      out.push({
        ano, mes, comp: ym(ano, mes), fonte: 'planilha',
        folha: tipo === 0 ? 'N' : (tipo === 13 ? 'G' : 'S'), tipoFolha: tipo,
        cod: String(r['Código Rubrica']).trim(), desc: String(r['Descrição Rubrica'] || '').trim(),
        seq: +r['Sequencial Rubrica'] || 0, v: nat === 'R' ? v : -v,
      });
    }
    return out;
  }

  /** Ficha do FolhaWeb exportada em planilha ("Big Grid": Relacionamento, Ano Folha, Mês Folha, Tipo Cálculo, Ano, Mês, Tipo Rubrica,
   *  Cód. Rubrica, Rubrica, Valor, Tipo Valor). Ano/Mês = competência; Ano/Mês Folha = mês do pagamento.
   *  Retroativo já vem na competência de origem. Linhas "Somente Cálculo" (bases) não entram como rubrica; a base de PSO
   *  calculada pela folha volta em basePSO[comp] para conferência. */
  function isBigGrid(rows) { return !!(rows && rows.length && ('Relacionamento' in rows[0] || 'Cód. Rubrica' in rows[0]) && 'Tipo Valor' in rows[0]); }
  function parseBigGrid(rows) {
    const recs = [], basePSO = {}, baseGN = {}, info = {};
    for (const r of rows) {
      const ano = +r['Ano'], mes = +r['Mês']; if (!ano || !mes) continue;
      const comp = ym(ano, mes), pago = ym(+r['Ano Folha'] || ano, +r['Mês Folha'] || mes);
      const tr = String(r['Tipo Rubrica'] || '').trim(), desc = String(r['Rubrica'] || '').trim(), cod = String(r['Cód. Rubrica'] || '').trim();
      const v = +r['Valor'] || 0, rec = /^Receita/i.test(String(r['Tipo Valor'] || ''));
      if (!info.cargo && r['Cargo']) Object.assign(info, { cargo: String(r['Cargo']).trim(), espec: String(r['Espec.'] || '').trim(), exercicio: String(r['Data de Exercício'] || '').trim(), nome: String(r['Relacionamento'] || '').trim() });
      if (/^Somente C/i.test(tr)) {
        if (/^BASE C[AÁ]LCULO PSO - MENSAL$/i.test(desc)) basePSO[comp] = r2((basePSO[comp] || 0) + v);
        if (/^BASE C[AÁ]LCULO PSO - GN$/i.test(desc)) baseGN[comp] = r2((baseGN[comp] || 0) + v);
        continue;
      }
      if (/^(Patronal|Consigna|Benef[ií]cio|Juros|Corre[cç])/i.test(tr)) continue;
      const retro = /Retroativo/i.test(String(r['Tipo Cálculo'] || ''));
      recs.push({ ano, mes, comp, pago, fonte: 'biggrid', folha: /^F[ée]rias/i.test(tr) ? 'F' : 'N', tipoFolha: 0, retro, tipoRub: tr,
        cod, desc, seq: 0, v: rec ? v : -v });
    }
    return { recs, basePSO, baseGN, info };
  }

  function groupLines(items) {
    const its = items.filter(i => i.str && i.str.trim()).sort((a, b) => a.y - b.y || a.x - b.x);
    const lines = [];
    for (const it of its) {
      const ln = lines.length ? lines[lines.length - 1] : null;
      if (ln && Math.abs(ln.y - it.y) <= 2.5) ln.items.push(it); else lines.push({ y: it.y, items: [it] });
    }
    return lines.map(l => l.items.sort((a, b) => a.x - b.x));
  }

  /** Ficha do FolhaWeb em PDF. pages = [{items:[{str,x,y,w}]}], y crescendo para baixo. */
  function parseFolhaWebPages(pages) {
    const recs = [], refs = {};
    let ano = null, centers = null, cur = null;
    for (const pg of pages) {
      for (const ln of groupLines(pg.items)) {
        const texts = ln.map(i => i.str.trim());
        const joined = texts.join(' ');
        const mp = joined.match(/Período:\s*\d{2}\/(\d{4})/);
        if (mp) { ano = +mp[1]; centers = null; cur = null; continue; }
        if (ln.filter(i => MES.includes(i.str.trim())).length >= 12) {
          centers = {};
          for (const i of ln) { const s = i.str.trim(); if (MES.includes(s) || s === 'TOTAL') centers[s] = i.x + i.w / 2; }
          cur = null; continue;
        }
        if (!centers || ano == null) continue;
        if (/^(Emissão|Anotações|Folha\s|FOLHA\s)/.test(joined)) { if (/^Anotações/.test(joined)) centers = null; continue; }
        const xJan = centers.JAN;
        const label = ln.filter(i => i.x < xJan - 60 && !NUM.test(i.str.trim())).map(i => i.str.trim()).join(' ').trim();
        const vals = {};
        for (const i of ln) {
          const s = i.str.trim();
          if (NUM.test(s) && i.x > xJan - 60) {
            const cx = i.x + i.w / 2; let best = null, bd = 1e9;
            for (const k in centers) { const d = Math.abs(centers[k] - cx); if (d < bd) { bd = d; best = k; } }
            vals[best] = brNum(s);
          }
        }
        const nv = Object.keys(vals).length;
        const mc = label.match(/^(\d{7}) - (.*)$/);
        if (/^Referência Salarial/.test(label)) {
          for (const i of ln) {
            const s = i.str.trim();
            if (/^[A-C]\d{1,2}$/.test(s)) { const cx = i.x + i.w / 2; let best = null, bd = 1e9; for (const k in centers) { const d = Math.abs(centers[k] - cx); if (d < bd) { bd = d; best = k; } } if (best !== 'TOTAL') refs[ym(ano, MES.indexOf(best) + 1)] = s; }
          }
          cur = null; continue;
        }
        if (mc) cur = { cod: mc[1], desc: mc[2], got: false };
        else if (['BRUTO', 'DESCONTOS', 'LÍQUIDO'].includes(label)) cur = { cod: label, desc: label, got: false };
        else if (label && cur && !cur.got) { cur.desc += ' ' + label; }
        else if (label && cur && cur.got && !nv) { cur.desc += ' ' + label; continue; }
        else if (label) { cur = null; continue; }
        if (nv && cur && !cur.got) {
          for (const k in vals) if (k !== 'TOTAL' && vals[k] !== 0) {  // meses futuros vêm zerados no PDF
            const mes = MES.indexOf(k) + 1;
            recs.push({ ano, mes, comp: ym(ano, mes), fonte: 'pdf', folha: 'N', tipoFolha: 0, cod: cur.cod, desc: cur.desc, seq: 0, v: vals[k], _h: cur });
          }
          cur.got = true;
        }
      }
    }
    // descrições completas (linhas de continuação chegam depois dos valores)
    for (const r of recs) { r.desc = r._h.desc.replace(/\s+/g, ' ').trim(); delete r._h; }
    return { recs, refs };
  }

  /** Ficha do FolhaWeb em PDF no leiaute "por folha" (colunas MM/AAAA-seq; seções Pagamentos Mensais, Pagamentos em
   *  suplementares, Pagamentos - Passivos). A coluna é o mês do PAGAMENTO; comp = mês da folha. seq 0 = folha normal,
   *  13 = gratificação natalina, demais = suplementar. Rubricas depois de "Total Receitas" são descontos. */
  const VAL = /^(?:R\$\s*)?-?[\d.]*\d,\d{2}$/;
  function isFolhaWebPorFolha(pages) {
    if (pages.some(pg => groupLines(pg.items).some(ln => ln.filter(i => MES.includes(i.str.trim())).length >= 12))) return false;
    return pages.some(pg => pg.items.some(i => /^\d{1,2}\/\d{4}-\d{1,2}$/.test(i.str.trim())));
  }
  function parseFolhaWebPorFolha(pages) {
    const recs = [], info = {};
    let cols = null, secao = 'N', desconto = false, cur = null;
    const all = [];
    for (const pg of pages) for (const ln of groupLines(pg.items)) all.push(ln);
    for (let li = 0; li < all.length; li++) {
      const ln = all[li];
      const joined = ln.map(i => i.str.trim()).filter(Boolean).join(' ');
      if (/^Pagamentos Mensais/.test(joined)) { secao = 'N'; cols = null; desconto = false; cur = null; continue; }
      if (/^Pagamentos em suplementares/.test(joined)) { secao = 'S'; cols = null; desconto = false; cur = null; continue; }
      if (/^Pagamentos - Passivos/.test(joined)) { secao = 'P'; cols = null; desconto = false; cur = null; continue; }
      if (!info.cargo) { const ix = all.findIndex(l => l.some(i => i.str.trim() === 'Cargo')); if (ix >= 0 && all[ix + 1]) { const c = all[ix + 1].map(i => i.str.trim()).filter(Boolean); info.cargo = c[c.length - 1]; } }
      const hs = ln.filter(i => /^\d{1,2}\/\d{4}-\d{1,2}$/.test(i.str.trim()));
      if (hs.length) {
        cols = hs.map(i => { const m = i.str.trim().match(/^(\d{1,2})\/(\d{4})-(\d{1,2})$/); return { x: i.x + i.w / 2, comp: ym(+m[2], +m[1]), seq: +m[3] }; });
        const tot = ln.find(i => /^Total Rubricas/.test(i.str.trim())); if (tot) cols.push({ x: tot.x + tot.w / 2, total: true });
        desconto = false; cur = null; continue;
      }
      if (!cols) continue;
      if (/^Total Receitas/.test(joined)) { desconto = true; cur = null; continue; }
      if (/^(Total Descontos|Valor L[ií]quido)/.test(joined)) { cur = null; continue; }
      const xMin = Math.min(...cols.map(c => c.x)) - 70;
      const label = ln.filter(i => i.x + i.w < xMin + 40 && !VAL.test(i.str.trim()) && i.str.trim() !== 'R$').map(i => i.str.trim()).join(' ').trim();
      const vals = [];
      for (const i of ln) {
        const s = i.str.trim(); if (!VAL.test(s) || i.x < xMin) continue;
        const cx = i.x + i.w / 2; let best = null, bd = 1e9;
        for (const c of cols) { const d = Math.abs(c.x - cx); if (d < bd) { bd = d; best = c; } }
        if (best && !best.total) vals.push({ col: best, v: brNum(s.replace(/^R\$\s*/, '')) });
      }
      const mc = label.match(/^(\d{7}) - ?(.*)$/);
      if (mc) cur = { cod: mc[1], desc: mc[2], got: false };
      else if (label && cur && !vals.length) { cur.desc += ' ' + label; continue; }
      else if (label) { cur = null; continue; }
      if (vals.length && cur && !cur.got) {
        for (const { col, v } of vals) if (v !== 0) {
          const folha = secao === 'P' ? 'P' : col.seq === 0 ? 'N' : col.seq === 13 ? 'G' : 'S';
          recs.push({ ano: +col.comp.slice(0, 4), mes: +col.comp.slice(5, 7), comp: col.comp, fonte: 'pdf', folha, tipoFolha: col.seq, cod: cur.cod, desc: cur.desc, seq: 0, v: desconto ? -v : v, _h: cur });
        }
        cur.got = true;
      }
    }
    for (const r of recs) { r.desc = r._h.desc.replace(/\s+/g, ' ').trim(); delete r._h; }
    return { recs, refs: {}, info };
  }

  // ------------------------------------------------------------------ CLASSIFICAÇÃO DE RUBRICAS
  const CAT = {
    VB: 'Vencimento', DIF2886: 'Dif. Lei 8622/8627', GEXTRA: 'Grat. Extraordinária 170%', GAJ: 'GAJ / Abono', APJ: 'APJ',
    REDUTOR: 'Redutor', ATS: 'ATS', VPI: 'VPI', VPNI: 'VPNI', VPNI_JUD: 'VPNI Judicial', FC: 'Função comissionada', SUBST: 'Substituição',
    V1323_VB: '13,23% Vencimento', V1323_GAJ: '13,23% GAJ', V1323_ATS: '13,23% ATS', V1323_VPNI: '13,23% VPNI', V1323_FC: '13,23% FC',
    VPI_DED: 'Dedução de VPI (13,23%)', AQ: 'AQ', AQ_TREIN: 'AQ Treinamento', GAE: 'GAE', GAS: 'GAS', FALTAS: 'Faltas', V1198: '11,98% (rubrica própria)',
    SUBSIDIO: 'Subsídio (magistrado)', FC_PREV: 'Função com opção de contribuição',
    PSS: 'Contribuição RPPS', GN: 'Gratificação natalina', PASSIVO: 'Passivo / exercício anterior', IGNORAR: 'Não remuneratória / não entra', CLASSIFICAR: 'A classificar',
  };
  const REMUN = ['SUBSIDIO', 'FC_PREV', 'VB', 'DIF2886', 'GEXTRA', 'GAJ', 'APJ', 'REDUTOR', 'ATS', 'VPI', 'VPI_DED', 'VPNI', 'VPNI_JUD', 'FC', 'SUBST', 'V1323_VB', 'V1323_GAJ', 'V1323_ATS', 'V1323_VPNI', 'V1323_FC', 'AQ', 'AQ_TREIN', 'GAE', 'GAS', 'FALTAS', 'V1198'];
  const NIVEL = ['VB', 'DIF2886', 'GEXTRA', 'GAJ', 'APJ', 'REDUTOR', 'ATS', 'VPI', 'VPI_DED', 'VPNI', 'VPNI_JUD', 'V1323_VB', 'V1323_GAJ', 'V1323_ATS', 'V1323_VPNI', 'V1323_FC', 'AQ', 'AQ_TREIN', 'GAE', 'GAS', 'V1198'];

  function classify(cod, desc) {
    const d = (desc || '').toUpperCase();
    const c = String(cod);
    if (/ISEN/.test(d) && /(D\.E\.A|DEA|EXERC|RRA|JUROS|CORR|S\.JUD|SENT)/.test(d)) return 'PASSIVO';
    if (/(- CM|- JR|- SELIC|CORRE[CÇ][AÃ]O MONET|CORR\. MONET|C\. ?MONET|JUROS)/.test(d)) return 'IGNORAR';
    if (['BRUTO', 'DESCONTOS', 'LÍQUIDO'].includes(c)) return 'IGNORAR';
    if (/NATALINA|\(13O?\.?\)|GN \(13|13[°º]/.test(d)) return /PREVID|RPPS|PSS|IMPOSTO/.test(d) ? 'IGNORAR' : 'GN';
    if (/RESTITUI/.test(d) && /PSS/.test(d)) return 'IGNORAR';
    if (/^(0099504|0099404|98002|98003|98004)$/.test(c) || (/(PREVID[EÊ]NCIA SOCIAL|CONTRIBUI[CÇ][AÃ]O RPPS|^PSS)/.test(d) && !/ISENT|DEVOLU/.test(d))) return 'PSS';
    if (/(D\.E\.A|\bDEA\b|DESPESA EXERC|DESP\.? EX\.? ANT|EXERC[IÍ]CIO ANTERIOR|\bRRA\b|PASSIVO|DEC\.? JUDICIAL|S(ENT)?\.? ?JUD\.? ?10,87)/.test(d)) return 'PASSIVO';
    if (/(DEVOLU[CÇ][AÃ]O PSS|HONOR[AÁ]RIOS|IND\. FAZENDA|AJUDA DE CUSTO|ASSOJAFES)/.test(d)) return 'IGNORAR';
    // até 1994: adiantamento da Lei 8.272/91 e abono de Cr$ 102.000 (Lei 8.622/93) integram o vencimento; a diferença de URV fica fora (RBCs da DIPROF)
    if (/ADIANT.*8\.?272|^ABONO$/.test(d)) return 'VB';
    if (/DIFEREN[CÇ]A DE URV/.test(d)) return 'IGNORAR';
    if (/F[EÉ]RIAS|1\/3|ADIANTAMENTO|ANTECIPA/.test(d)) return 'IGNORAR';
    if (/(AUX[IÍ]LIO|AUX\.|ASSIST|ALIMENTA|SA[UÚ]DE|PR[EÉ]-ESCOLAR|NATALIDADE|TRANSPORTE|DI[AÁ]RIA|INDENIZ|PERMAN[EÊ]NCIA|UNIMED|CONSIGNA|AJUSTE|EMPR[EÉ]STIMO|SINPOJUFES|ANAJUSTRA|ANASTRA|IMPOSTO|PENS[AÃ]O|ABONO PECUNI|SAL[AÁ]RIO-FAM|SAL[AÁ]RIO FAM|GOLDEN|PLANO DE SA)/.test(d)) return 'IGNORAR';
    if (/(SERVI[CÇ]O EXTRAORD|HORA EXTRA|CURSO|CONCURSO|GECC|ADICIONAL NOTURNO|^GRU$|RESTITUI[CÇ][AÃ]O OUTROS|FUNPRESP|PREV\. SOCIAL - (INSS|FMP)|PREV\. SOCIAL-GRAT|AGEPOLJUS|ASSOJAF|AJUCLA|ANAMATRA|AMATRA|ASSOCIACAO MAGISTRADOS|FINANCIAMENTO|ALUGUEL|A B S P|DEP[OÓ]SITO EM JU[IÍ]ZO)/.test(d)) return 'IGNORAR';
    // magistrados: subsídio (Lei 11.143/2005 e seguintes) é a base de contribuição
    if (/SUBS[IÍ]DIO/.test(d) && /MAGISTR|JUIZ|LEI 11\.?143|LEI 1[2-4]\./.test(d)) return 'SUBSIDIO';
    // diferença de subsídio por substituição de magistrado (Lei 10.474/2002): integra o subsídio (RBC de juiz, 2006–2010)
    if (/SUBSTITUI\S* MAGISTRAD/.test(d)) return 'SUBSIDIO';
    // função comissionada com opção pela contribuição (Lei 10.887/2004, art. 4º, § 2º): entra na base
    if (/FUN[CÇ][AÃ]O.*C\/ ?PREVID/.test(d)) return 'FC_PREV';
    if (/11,98/.test(d)) return 'V1198';
    if (/13,23/.test(d)) {
      if (/DEDU/.test(d) && /VPI/.test(d)) return 'VPI_DED';
      if (/VENC/.test(d)) return 'V1323_VB';
      if (/G\.?A\.?J/.test(d)) return 'V1323_GAJ';
      if (/ATS|ANU[EÊ]NIO/.test(d)) return 'V1323_ATS';
      if (/VPNI/.test(d)) return 'V1323_VPNI';
      if (/FC|FUN[CÇ]/.test(d)) return 'V1323_FC';
      if (/SUBST/.test(d)) return 'SUBST';
      return 'CLASSIFICAR';
    }
    if (/(GABINETE|FUN[CÇ][AÃ]O GAB|-GAB\.?$)/.test(d)) return 'FC';
    if (/FALTA/.test(d)) return 'FALTAS';
    if (/SUBSTITUI/.test(d)) return 'SUBST';
    if (/(FUN[CÇ][AÃ]O COMISS|FUNC\. COMISS|F\.C\. |CARGO EM COMISS|GRATIFICA[CÇ][AÃ]O DE GABINETE|^DAS)/.test(d)) return 'FC';
    if (/(QUALIF.*TREIN|AQ-AT|QUALIFICA[CÇ][AÃ]O - TREINAMENTO|QUALIFICA[CÇ][AÃ]O TREINAMENTO|AQ.*TREINAMENTO)/.test(d)) return 'AQ_TREIN';
    if (/(ADIC\.? ?QUALIF|AQ-PG|ADICIONAL DE QUALIFICA|AQ - )/.test(d)) return 'AQ';
    if (/(GAS\b|ATIV\.? ?SEGURAN|ATIVIDADE DE SEGURAN)/.test(d)) return /SEM PREVID/.test(d) ? 'IGNORAR' : 'GAS';
    if (/(GAE\b|ATIV\.? ?EXTERNA|ATIVIDADE EXTERNA)/.test(d)) return 'GAE';
    if (/(V\.?P\.?N\.?I|VPNI|D[EÉ]CIMOS|QUINTOS)/.test(d)) return /JUDIC/.test(d) ? 'VPNI_JUD' : 'VPNI';
    if (/(VANTAGEM PECUNI|V\.P\.I|\bVPI\b)/.test(d)) return 'VPI';
    if (/(ANU[EÊ]NIO|GATS|\bATS\b|TEMPO DE SERVI)/.test(d)) return 'ATS';
    if (/(28,86|8622|8627|DIF\. ?LEI)/.test(d)) return 'DIF2886';
    if (/GRAT.*EXTRAORD/.test(d)) return 'GEXTRA';
    if (/(PADR[AÃ]O JUDICI|\bAPJ\b)/.test(d)) return 'APJ';
    if (/REDUTOR.*(FUN|F\.?C\.?\b|COMISS)/.test(d)) return 'FC';   // redutor sobre a função acompanha a função
    if (/(REDUTOR)/.test(d)) return 'REDUTOR';
    if (/^GRAT\.? ?JUDICI[AÁ]RIA/.test(d)) return 'GAJ';   // gratificação judiciária (80%), 1993
    if (/(GRAT\.? ?ATIV\.? ?JUDIC|GRATIFICA[CÇ][AÃ]O ATIV\.? JUDICI|ATIVIDADE JUDICI|^GAJ\b|\bGAJ\b)/.test(d)) return 'GAJ';
    if (/^VENCIMENTO|VENCIMENTO (LEI|-)|^VENCIMENTO$/.test(d)) return 'VB';
    return 'CLASSIFICAR';
  }

  /** Inventário de rubricas encontradas, com categoria sugerida */
  function inventario(recs, overrides) {
    const m = new Map();
    for (const r of recs) {
      const k = r.cod + '|' + r.desc;
      let e = m.get(k);
      if (!e) { e = { cod: r.cod, desc: r.desc, n: 0, total: 0, primeiro: r.comp, ultimo: r.comp, cat: classify(r.cod, r.desc) }; m.set(k, e); }
      e.n++; e.total += r.v; if (r.comp < e.primeiro) e.primeiro = r.comp; if (r.comp > e.ultimo) e.ultimo = r.comp;
    }
    const out = [...m.values()];
    for (const e of out) { const o = (overrides || {})[e.cod + '|' + e.desc]; if (o) e.cat = o; e.total = r2(e.total); }
    return out.sort((a, b) => a.cat.localeCompare(b.cat) || a.cod.localeCompare(b.cod));
  }

  // ------------------------------------------------------------------ PSS
  const FX = {
    2020: [1045, 2089.60, 3134.40, 6101.06, 10448.00, 20896.00, 40747.20], 2021: [1100, 2203.48, 3305.22, 6433.57, 11017.42, 22034.83, 42967.92],
    2022: [1212, 2427.35, 3641.03, 7087.22, 12136.79, 24273.57, 47333.46], 2023: [1302, 2571.29, 3856.94, 7507.49, 12856.50, 25712.99, 50140.33],
    2024: [1412, 2666.68, 4000.03, 7786.02, 13333.48, 26666.94, 52000.54], 2025: [1518, 2793.88, 4190.83, 8157.41, 13969.49, 27938.95, 54480.97],
    2026: [1621, 2902.84, 4354.27, 8475.55, 14514.26, 29028.52, 56605.61],
  };
  const AL = [0.075, 0.09, 0.12, 0.14, 0.145, 0.165, 0.19, 0.22];
  function pssDevida(base, comp, tetoRGPS) {
    const y = +comp.slice(0, 4), m = +comp.slice(5, 7);
    if (comp < '2020-03') {
      let b = base; if (tetoRGPS && tetoRGPS[comp]) b = Math.min(b, tetoRGPS[comp]);
      return r2(b * 0.11);
    }
    const fx = (FX[y] || FX[2026]).slice(); if (y === 2023 && m >= 5) fx[0] = 1320;
    let b = base; if (tetoRGPS) b = Math.min(b, fx[3]);
    let t = 0, prev = 0;
    for (let i = 0; i < AL.length; i++) { const lim = i < fx.length ? fx[i] : 1e12; if (b > prev) t += (Math.min(b, lim) - prev) * AL[i]; prev = lim; }
    return r2(t);
  }

  // ------------------------------------------------------------------ MOTOR
  /**
   * opts: { inicio:'YYYY-MM-DD', fim:'YYYY-MM-DD', cats:{'cod|desc':cat}, refs:{comp:ref}, tabela:[{i,f,c,r,v}],
   *         regras:{fcAte:'1998-11', atsDesde:'2002-04', gas:true, aqTrein:false, conferirDesde:'2002-01', teto:false},
   *         manual:[{id, cat, ini, fim}]  // alocação manual de passivos / pagamentos sem competência
   *         ignorarAloc:{id:true} }
   */
  const AJ1198 = ['VB', 'GAJ', 'GEXTRA', 'DIF2886', 'APJ', 'FC', 'VPNI', 'REDUTOR'];
  // Padrões = prática observada da DIPROF nas RBCs analisadas (cada item é decisão a confirmar)
  const REGRAS_PADRAO = { fcAte: '1998-11', atsDesde: '2002-04', gas: false, aqTrein: false, conferirDesde: '2002-01', teto: false,
    ajuste1198Desde: '1994-04', ajuste1198Ate: '2001-01', descontarFaltas: false, gnDesde: '2003', gnSemVPIAte: '2007', divisorDiasDesde: '2017-12', divisor30Desde: '1994-07', tabelaAte: '1994-06', vpniTabela: true, fcTabela: true, tetoDesde: '', tetoAuto: true, semFichaTabela: true, gasAte: '', vpiTabela: true, gnFicha: false };
  const TABCAT = ['VB', 'GAJ', 'ATS', 'GEXTRA', 'DIF2886', 'APJ'];
  function calcular(recs, opts) {
    const regras = Object.assign({}, REGRAS_PADRAO, opts.regras || {});
    if (regras.divisorDiasDesde) DIV.desde = regras.divisorDiasDesde;
    DIV.de30 = regras.divisor30Desde || '1994-07';
    const ini = opts.inicio.slice(0, 7), fim = opts.fim.slice(0, 7);
    const meses = []; for (let k = ini; k <= fim; k = addM(k, 1)) meses.push(k);
    const catOf = r => (opts.cats && opts.cats[r.cod + '|' + r.desc]) || classify(r.cod, r.desc);
    const fontes = {};
    const cur = {}, extra = {}, supl = {}, pss = {}, passivos = [], semComp = [];
    for (const k of meses) { cur[k] = {}; extra[k] = {}; pss[k] = 0; }
    for (const r of recs) {
      if (r.comp < addM(ini, -1) || r.comp > addM(fim, 24)) continue;
      const cat = catOf(r);
      fontes[r.comp] = r.fonte;
      if (cat === 'PSS') { if (pss[r.comp] !== undefined && r.folha !== 'G') pss[r.comp] += -r.v; continue; }
      if (cat === 'PASSIVO') { if (r.v > 0 && r.comp >= ini) passivos.push({ id: 'P' + r.comp + r.cod + r.seq + passivos.length, comp: r.comp, cod: r.cod, desc: r.desc, valor: r2(r.v) }); continue; }
      if (!REMUN.includes(cat)) continue;
      if (!(r.comp in cur)) continue;
      if (r.folha === 'N' && r.seq === 0) cur[r.comp][cat] = (cur[r.comp][cat] || 0) + r.v;
      else if (r.folha !== 'G') { extra[r.comp][cat] = (extra[r.comp][cat] || 0) + r.v; if (r.folha === 'S') { supl[r.comp] = supl[r.comp] || {}; supl[r.comp][cat] = (supl[r.comp][cat] || 0) + r.v; } }
    }
    const val = {}; for (const k of meses) val[k] = Object.assign({}, cur[k]);
    const log = [];
    const g = (k, c) => (val[k] && val[k][c]) || 0;

    // 1) picos (retroativo embutido no valor do mês — fichas em PDF)
    for (const c of NIVEL) {
      for (let i = 1; i < meses.length - 1; i++) {
        const k = meses[i], a = g(meses[i - 1], c), x = g(k, c), b = g(meses[i + 1], c);
        const b2 = i + 2 < meses.length ? g(meses[i + 2], c) : b;
        if (Math.abs(x - a) < 0.005 || Math.abs(x - b) < 0.005) continue;
        if (Math.abs(b - b2) > 0.005) continue;               // nível seguinte instável
        const excesso = x - b;
        if (Math.abs(b - a) < 0.005) {                         // pagamento avulso sobre nível inalterado
          if (excesso > 0.005) { val[k][c] = b; extra[k][c] = (extra[k][c] || 0) + excesso; log.push({ tipo: 'pico', cat: c, comp: k, valor: r2(excesso) }); }
          continue;
        }
        if (Math.sign(excesso) === Math.sign(b - a)) { val[k][c] = b; extra[k][c] = (extra[k][c] || 0) + excesso; log.push({ tipo: 'pico', cat: c, comp: k, valor: r2(excesso) }); }
      }
    }
    // 2) realocação de retroativos para a competência de origem
    const pend = [];
    // valor esperado pela tabela (cargo/ref identificados pelo VB de um mês de referência)
    const tabHit = (k, vb) => (opts.tabela || []).filter(t => t.i <= k + '-15' && (!t.f || t.f >= k + '-15') && Math.abs(t.v - vb) < 0.015);
    const tabGet = (k, cr, cat) => { const t = (opts.tabela || []).find(t => t.c === cr.c && t.r === cr.r && t.i <= k + '-15' && (!t.f || t.f >= k + '-15')); if (!t) return undefined; return cat === 'VB' ? t.v : t[cat]; };
    function tabAlloc(i, c, rest) {
      // mês de referência: o seguinte (nível já atualizado) ou o próprio
      for (const ir of [i + 1, i]) {
        const kr = meses[ir]; if (!kr) continue;
        const hits = tabHit(kr, g(kr, 'VB')); const u = new Set(hits.map(h => h.c + '|' + h.r));
        if (u.size !== 1) continue;
        const cr = hits[0];
        const pct = c === 'ATS' && g(kr, 'VB') ? Math.round(g(kr, 'ATS') / g(kr, 'VB') * 1000) / 1000 : null;
        const esp = kk => { if (c === 'ATS') { const vb = tabGet(kk, cr, 'VB'); return pct && vb !== undefined ? r2(vb * pct) : undefined; } return tabGet(kk, cr, c); };
        let r = rest; const aloc = [];
        for (let j = i; j >= 0 && j >= i - 36 && Math.abs(r) > 0.005; j--) {
          const kk = meses[j], e = esp(kk); if (e === undefined) break;
          const gap = r2(e - g(kk, c));
          if (Math.abs(gap) < 0.005) { if (j === i) continue; break; }
          if (Math.sign(gap) !== Math.sign(r)) break;
          if (Math.abs(r) >= Math.abs(gap) - 0.02) { aloc.push({ comp: kk, valor: gap, fracao: 1, fonteNivel: 'tabela ' + cr.r }); r -= gap; }
          else { const f = r / gap, dv = divisor(kk); aloc.push({ comp: kk, valor: r2(r), fracao: f, dias: Math.round(f * dv), diaInicio: dv - Math.round(f * dv) + 1, fonteNivel: 'tabela ' + cr.r }); r = 0; }
        }
        if (aloc.length && Math.abs(r) <= 0.05 * aloc.length) { aloc[0].valor = r2(aloc[0].valor + r); return { aloc, rest: 0 }; }
      }
      return null;
    }
    for (let i = 0; i < meses.length; i++) {
      const k = meses[i];
      for (const c of Object.keys(extra[k])) {
        let rest = extra[k][c]; if (Math.abs(rest) < 0.005) continue;
        if (opts.ignorarAloc && opts.ignorarAloc[k + '|' + c]) continue;
        const aloc = [];
        const nx = meses[i + 1] ? g(meses[i + 1], c) : g(k, c);
        // (a) rubrica sem valor corrente no mês (paga só em folha suplementar): alocar em unidades mensais
        if (Math.abs(g(k, c)) < 0.005) {
          const cands = [];
          if (i > 0 && Math.abs(g(meses[i - 1], c)) > 0.005) cands.push(g(meses[i - 1], c));
          for (let j = i + 1; j < Math.min(meses.length, i + 4); j++) { const u = (extra[meses[j]] && extra[meses[j]][c]) || g(meses[j], c); if (Math.abs(u) > 0.005) { cands.push(u); break; } }
          for (const u of cands) {
            const n = rest / u, nr = Math.round(n);
            if (nr >= 1 && Math.abs(n - nr) < 0.02 && i - nr + 1 >= 0) {
              for (let j = i; j > i - nr; j--) { const kk = meses[j]; val[kk][c] = g(kk, c) + u; aloc.push({ comp: kk, valor: r2(u), fracao: 1 }); }
              rest = 0; break;
            }
          }
        }
        // (t) diferença para a tabela da época (reajustes escalonados pagos de uma vez)
        if (Math.abs(rest) > 0.005 && opts.tabela && TABCAT.includes(c)) {
          const r0 = tabAlloc(i, c, rest);
          if (r0) { for (const a of r0.aloc) { val[a.comp][c] = g(a.comp, c) + a.valor; aloc.push(a); } rest = r0.rest; }
        }
        // (b) diferença de nível: começa no próprio mês (se o nível sobe no mês seguinte) e recua
        if (Math.abs(rest) > 0.005) {
          // só folha suplementar pode referir-se ao próprio mês; retroativo na folha normal ou embutido refere-se a meses anteriores
          const soSupl = supl[k] && supl[k][c] && Math.abs(supl[k][c] - extra[k][c]) < 0.005;
          const nivel = (soSupl && Math.abs(nx - g(k, c)) > 0.005 && Math.sign(nx - g(k, c)) === Math.sign(rest)) ? nx : (g(k, c) || nx);
          let j = i; if (!soSupl || Math.abs(nivel - g(k, c)) < 0.005) j = i - 1;
          for (; j >= 0 && j >= i - 36 && Math.abs(rest) > 0.005; j--) {
            const kk = meses[j]; const gap = nivel - g(kk, c);
            // folha suplementar paga meses depois: pula até 3 meses já no nível novo antes de começar a distribuir
            if (Math.abs(gap) < 0.005 && !aloc.length && j > i - 3) continue;
            if (Math.abs(gap) < 0.005 || Math.sign(gap) !== Math.sign(rest)) break;
            if (Math.abs(rest) >= Math.abs(gap) - 0.02) { val[kk][c] = g(kk, c) + gap; aloc.push({ comp: kk, valor: r2(gap), fracao: 1 }); rest -= gap; }
            else if (Math.abs(rest) < 0.05 && aloc.length) { const u = aloc[aloc.length - 1]; val[u.comp][c] = g(u.comp, c) + rest; u.valor = r2(u.valor + rest); rest = 0; }
            else { const f = rest / gap; val[kk][c] = g(kk, c) + rest; const dv = divisor(kk); aloc.push({ comp: kk, valor: r2(rest), fracao: f, dias: Math.round(f * dv), diaInicio: dv - Math.round(f * dv) + 1 }); rest = 0; }
          }
        }
        if (Math.abs(rest) > 0.05) {
          if (k === meses[i] && i === 0) { /* primeiro mês: retroativo de período anterior ao início */ }
          pend.push({ id: k + '|' + c, comp: k, cat: c, valor: r2(rest), motivo: aloc.length ? 'Sobra após alocar retroativo' : 'Pagamento sem competência identificável' });
        }
        if (aloc.length) log.push({ tipo: 'retroativo', cat: c, pagoEm: k, valor: r2(extra[k][c] - rest), aloc });
      }
    }
    // 3) alocações manuais (passivos e pendências)
    for (const ma of (opts.manual || [])) {
      const alvo = meses.filter(k => k >= ma.ini.slice(0, 7) && k <= ma.fim.slice(0, 7)); if (!alvo.length) continue;
      const aloc = [];
      if (ma.modo === 'percentualVB' && ma.pct) {
        // ex.: AQ pago em passivo — pct × VB de cada competência; diferença para o valor pago fica registrada
        let soma = 0;
        const dI = ma.ini.length >= 10 ? +ma.ini.slice(8, 10) : 1, dF = ma.fim.length >= 10 ? +ma.fim.slice(8, 10) : 31;
        for (const k of alvo) { let fr = 1; if (k === ma.ini.slice(0, 7) && dI > 1) fr = (divisor(k) - dI + 1) / divisor(k); if (k === ma.fim.slice(0, 7) && dF < diasMes(k)) fr = Math.min(fr, Math.min(dF, divisor(k)) / divisor(k)); const p = r2(ma.pct * g(k, 'VB') * fr); val[k][ma.cat] = g(k, ma.cat) + p; soma += p; aloc.push({ comp: k, valor: p, fracao: fr }); }
        log.push({ tipo: 'manual', modo: ma.modo, cat: ma.cat, pagoEm: ma.origem, valor: r2(ma.valor || 0), alocado: r2(soma), diferenca: r2((ma.valor || 0) - soma), aloc });
        continue;
      } else if (ma.modo === 'unidade' && ma.unidade) {
        let rest = ma.valor;
        for (let j = alvo.length - 1; j >= 0 && Math.abs(rest) > 0.005; j--) {
          const k = alvo[j]; const p = Math.abs(rest) >= Math.abs(ma.unidade) - 0.005 ? ma.unidade : rest;
          val[k][ma.cat] = g(k, ma.cat) + p; aloc.push({ comp: k, valor: r2(p), fracao: p === ma.unidade ? 1 : p / ma.unidade }); rest -= p;
        }
      } else {
        const parte = ma.valor / alvo.length;
        for (const k of alvo) { val[k][ma.cat] = g(k, ma.cat) + parte; aloc.push({ comp: k, valor: r2(parte), fracao: 1 }); }
      }
      log.push({ tipo: 'manual', cat: ma.cat, pagoEm: ma.origem, valor: r2(ma.valor), aloc });
    }
    // 4) período parcial (início/fim no meio do mês)
    const parcial = (k, dias) => {
      const ref = meses[meses.indexOf(k) + (k === ini ? 1 : -1)];
      for (const c of Object.keys(val[k])) {
        const cheio = ref ? g(ref, c) : g(k, c);
        if (Math.abs(g(k, c) - cheio) < 0.005 && cheio) val[k][c] = cheio * dias / divisor(k);
      }
    };
    const dIni = +opts.inicio.slice(8, 10), dFim = +opts.fim.slice(8, 10);
    if (dIni > 1) parcial(ini, divisor(ini) - dIni + 1);
    if (dFim < diasMes(fim)) parcial(fim, Math.min(dFim, divisor(fim)));

    // 4b) 11,98% (conversão URV, reconhecida judicialmente) sobre parcelas de tabela até 12/2001 — opcional
    const em1198 = k => !!regras.ajuste1198Ate && k <= regras.ajuste1198Ate && k >= (regras.ajuste1198Desde || '1994-04');
    if (regras.ajuste1198Ate) for (const k of meses) if (em1198(k)) for (const c of AJ1198) if (val[k][c]) val[k][c] = val[k][c] * 1.1198;
    // 5) incidência e linhas da RBC
    const incide = (c, k) => {
      if (c === 'FC' || c === 'SUBST' || c === 'V1323_FC') return k <= regras.fcAte;
      if (c === 'ATS' || c === 'V1323_ATS') return k >= regras.atsDesde;
      if (c === 'AQ_TREIN') return regras.aqTrein === 'ficha' ? 'ficha' : !!regras.aqTrein;
      if (c === 'GAS') return !!regras.gas || (!!regras.gasAte && k <= regras.gasAte);
      if (c === 'FALTAS') return regras.descontarFaltas !== false;
      if (c === 'V1198') return !em1198(k);
      return REMUN.includes(c);
    };
    const linhas = [];
    for (const k of meses) {
      const v = {}; let tot = 0;
      for (const c of REMUN) { const x = r2(g(k, c)); if (Math.abs(x) >= 0.005 && incide(c, k) === true) { v[c] = x; tot += x; } }
      const atsPct = v.ATS && v.VB ? Math.round(v.ATS / v.VB * 1000) / 1000 : null;
      const ref = (opts.refs && opts.refs[k]) || inferirRef(opts.tabela, k, g(k, 'VB'));
      const alocs = log.filter(l => l.aloc && l.aloc.some(a => a.comp === k && a.fracao < 1));
      const bruto = {}; for (const c of REMUN) { const x = r2(g(k, c)); if (Math.abs(x) >= 0.005) bruto[c] = x; }
      linhas.push({ comp: k, ref, v, bruto, atsPct, total: r2(tot), pssFicha: r2(pss[k] || 0), fonte: fontes[k] || '', parcialInferido: alocs.map(l => ({ cat: l.cat, ...l.aloc.find(a => a.comp === k) })) });
    }
    // 5b) AQ-Treinamento "pela ficha" (decisão DIPROF, 09/10/2026): entra na base no ano em que a contribuição descontada
    // mostra que houve desconto sobre ele (ano a ano, para absorver atrasados); sem ficha conferível, fica fora
    const aqTreinAnos = {};
    if (regras.aqTrein === 'ficha') {
      for (const y of [...new Set(meses.map(k => k.slice(0, 4)))]) {
        const ls = linhas.filter(l => l.comp.startsWith(y) && l.fonte && l.comp >= regras.conferirDesde);
        const at = ls.filter(l => Math.abs(g(l.comp, 'AQ_TREIN')) >= 0.005); if (!at.length) continue;
        const f = ls.reduce((a, l) => a + l.pssFicha, 0);
        const sem = ls.reduce((a, l) => a + pssDevida(l.total, l.comp, regras.teto), 0);
        const com = ls.reduce((a, l) => a + pssDevida(l.total + r2(g(l.comp, 'AQ_TREIN')), l.comp, regras.teto), 0);
        // entra se, com ele, a diferença do ano diminui e o resíduo fica abaixo de metade da contribuição sobre o AQ-Treinamento
        // (ou de R$ 5); na dúvida, fica fora
        aqTreinAnos[y] = Math.abs(f - com) < Math.abs(f - sem) && Math.abs(f - com) <= Math.max(5, 0.5 * (com - sem));
      }
      for (const l of linhas) if (aqTreinAnos[l.comp.slice(0, 4)]) { const x = r2(g(l.comp, 'AQ_TREIN')); if (Math.abs(x) >= 0.005) { l.v.AQ_TREIN = x; l.total = r2(l.total + x); } }
    }
    // 6) gratificação natalina
    const gns = [];
    const anos = [...new Set(meses.map(k => k.slice(0, 4)))];
    for (const y of anos) {
      const ms = meses.filter(k => k.startsWith(y));
      const avos = ms.filter(k => { const di = k === ini ? divisor(k) - dIni + 1 : divisor(k); const df = k === fim ? Math.min(dFim, divisor(k)) : divisor(k); return Math.min(di, df) >= 15 || (k !== ini && k !== fim); }).length;
      const cheios = ms.filter(k => !(k === fim && dFim < diasMes(fim)) && !(k === ini && dIni > 1));
      const baseK = cheios.length ? cheios[cheios.length - 1] : ms[ms.length - 1];
      // antes de gnDesde a GN não teve contribuição: fica fora da RBC, mas é calculada para a certidão complementar
      const fora = !!(regras.gnDesde && y < regras.gnDesde);
      const lb = linhas.find(l => l.comp === baseK);
      let base = lb.total, obs = '';
      if (regras.gnSemVPIAte && y <= regras.gnSemVPIAte && (lb.v.VPI || lb.v.VPI_DED)) { base = r2(base - (lb.v.VPI || 0) - (lb.v.VPI_DED || 0)); obs = 'sem VPI'; }
      gns.push({ ano: y, depois: ms[ms.length - 1], baseComp: baseK, avos, base, obs, valor: r2(base * avos / 12), fora });
    }
    // 6b) 13º pelo valor pago (prática da DIPROF nas RBCs de magistrado: rubrica "gratificação natalina" do ano, sem o adiantamento)
    if (regras.gnFicha) {
      const pago = {};
      for (const r of recs) {
        if (catOf(r) !== 'GN' || !(r.v > 0)) continue;
        const d = String(r.desc || '').toUpperCase(); if (/ADIANT|PREVID|RPPS|IMPOSTO|FUNPRESP|DEVOL/.test(d)) continue;
        pago[r.comp.slice(0, 4)] = r2((pago[r.comp.slice(0, 4)] || 0) + r.v);
      }
      for (const g of gns) if (pago[g.ano] != null) { g.valor = pago[g.ano]; g.base = pago[g.ano]; g.avos = 12; g.obs = 'valor pago na ficha'; g.daFicha = true; }
    }
    // 7) conferência pela contribuição
    let acF = 0, acC = 0;
    for (const l of linhas) {
      l.pssCalc = pssDevida(l.total, l.comp, regras.teto);
      l.conferir = l.comp >= regras.conferirDesde;
      l.dif = r2(l.pssFicha - l.pssCalc);
      if (l.conferir) { acF += l.pssFicha; acC += l.pssCalc; }
      l.acumDif = l.conferir ? r2(acF - acC) : null;
    }
    const porAno = anos.map(y => {
      const ls = linhas.filter(l => l.comp.startsWith(y));
      const f = r2(ls.reduce((s, l) => s + l.pssFicha, 0)), c = r2(ls.reduce((s, l) => s + l.pssCalc, 0));
      return { ano: y, conferir: ls.some(l => l.conferir), pssFicha: f, pssCalc: c, dif: r2(f - c), mesesSemFicha: ls.filter(l => !l.fonte).length };
    });
    const tratados = new Set((opts.manual || []).map(m => m.id).filter(Boolean));
    const ehTratado = p => tratados.has(p.id) || (opts.manual || []).some(m => m.cat === p.cat && m.valor && Math.abs(m.valor - p.valor) < 0.01);
    const pendInc = pend.filter(p => incide(p.cat, p.comp) && !ehTratado(p));
    const logInc = log.filter(l => l.aloc && l.aloc.some(a => incide(l.cat, a.comp)));
    return { aqTreinAnos, meses, linhas, gns, log: logInc, pend: pendInc, pendNaoIncidentes: pend.filter(p => !incide(p.cat, p.comp)), passivos, porAno, resumo: { pssFicha: r2(acF), pssCalc: r2(acC), dif: r2(acF - acC) }, regras };
  }

  /** Regime de previdência complementar (Lei 12.618/2012): base limitada ao teto do RGPS.
   *  Indícios: ingresso a partir de 14/10/2013 (início do Funpresp-Jud) ou, na ficha, PSS "TETO RGPS" / Funpresp patrocinada
   *  (servidor antigo que migrou). Devolve o primeiro mês limitado e o motivo. */
  const FUNPRESP_JUD = '2013-10-14';
  function detectarTeto(recs, inicio) {
    let k = null, mot = '';
    for (const r of recs || []) {
      const d = String(r.desc || '').toUpperCase();
      if (/^(98001|98096|98097)$/.test(String(r.cod)) || /TETO RGPS/.test(d) || /FUNPRESP.*PATROCINADA/.test(d)) {
        if (!k || r.comp < k) { k = r.comp; mot = 'ficha: ' + String(r.desc).trim(); }
      }
    }
    // ingresso no TRT depois de 14/10/2013 não basta: quem vem de outro cargo público federal sem quebra de vínculo mantém o
    // regime anterior (casos da DIPROF sem limitação). Sem indício na ficha, só fica o alerta.
    if (k && inicio && inicio.slice(0, 7) > k) k = inicio.slice(0, 7);
    // indício já no primeiro mês de ficha enviado e ingresso desde 14/10/2013: limitado desde o ingresso
    const primeira = (recs || []).reduce((m, r) => (!m || r.comp < m ? r.comp : m), null);
    if (k && primeira && k === primeira && inicio && inicio >= FUNPRESP_JUD && inicio.slice(0, 7) < k) { k = inicio.slice(0, 7); mot += ' (desde o ingresso: indício já no primeiro mês de ficha)'; }
    if (k) return { desde: k, motivo: mot };
    if (inicio && inicio >= FUNPRESP_JUD) return { desde: '', motivo: 'ingresso a partir de 14/10/2013, sem contribuição ao Funpresp na ficha: confirme se o servidor está sujeito ao teto' };
    return null;
  }

  function inferirRef(tabela, k, vb) {
    if (!tabela || !vb) return '';
    const d = k + '-15';
    const hits = tabela.filter(t => t.i <= d && (!t.f || t.f >= d) && Math.abs(t.v - vb) < 0.015);
    if (!hits.length) return '';
    const u = [...new Set(hits.map(h => h.r))];
    return u.length === 1 ? u[0] + ' (inferido)' : '';
  }

  const api = { MES, CAT, REMUN, REGRAS_PADRAO, parseLongRows, parseFolhaWebPages, parseBigGrid, isBigGrid, parseFolhaWebPorFolha, isFolhaWebPorFolha, classify, inventario, calcular, detectarTeto, FUNPRESP_JUD, pssDevida, addM, divisor, r2, DIV };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.RBC = api;
})(typeof self !== 'undefined' ? self : this);
