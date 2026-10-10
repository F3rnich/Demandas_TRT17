/* Tabela ESPERADA da RBC — TRT-17 / DIPROF
 * Remuneração e contribuição esperadas mês a mês, a partir dos dados do servidor,
 * dos relatórios do RH (progressão, funções, substituições, VPNI, ATS, AQ) e da base de remunerações.
 * Funções puras (sem DOM). Usa RBC (rbc_core.js) para pssDevida, addM, r2, diasMes.
 */
(function (root) {
  'use strict';
  const RBC = (typeof require !== 'undefined') ? require('./rbc_core.js') : root.RBC;
  const r2 = RBC.r2;
  const diasMes = k => new Date(+k.slice(0, 4), +k.slice(5, 7), 0).getDate();
  const iso = (k, d) => k + '-' + String(d).padStart(2, '0');
  const padN = p => { p = String(p == null ? '' : p).trim().toUpperCase(); return /^\d+$/.test(p) ? String(+p) : p; };

  // ------------------------------------------------------------------ índices da base
  function indexar(base) {
    const ix = { serv: new Map(), fc: new Map(), dec: new Map(), gab: new Map(), par: new Map(), v1323: new Map() };
    const push = (m, k, v) => { if (!m.has(k)) m.set(k, []); m.get(k).push(v); };
    for (const [i, f, cargo, cl, p, rub, v, id] of base.serv) push(ix.serv, cargo + '|' + cl + '|' + p, { i, f: f || '9999-12-31', rub, v, id });
    for (const [i, f, fun, mod, rub, v, id] of base.fc) push(ix.fc, fun, { i, f: f || '9999-12-31', mod, rub, v, id });
    for (const [i, f, fun, fr, rub, v, id, g] of base.dec) push(ix.dec, fun, { i, f: f || '9999-12-31', fr, rub, v, id, g });
    for (const [i, f, fun, mod, rub, v, id] of base.gab) push(ix.gab, fun, { i, f: f || '9999-12-31', mod, rub, v, id });
    for (const [i, f, cargo, cl, p, fun, rub, v, id] of (base.v1323 || [])) push(ix.v1323, fun ? 'F|' + fun : cargo + '|' + cl + '|' + p, { i, f: f || '9999-12-31', rub, v, id });
    for (const [n, i, f, v] of base.par) push(ix.par, n, { i, f: f || '9999-12-31', v });
    return ix;
  }
  const vig = (lst, d) => (lst || []).filter(x => x.i <= d && d <= x.f);
  const par = (ix, n, d) => { const h = vig(ix.par.get(n), d); return h.length ? h[h.length - 1].v : null; };

  // cargo da tabela na data (até 1994 a planilha usa "NÍVEL …")
  const NIVEL = { 'TÉCNICO JUDICIÁRIO': 'NÍVEL INTERMEDIÁRIO', 'ANALISTA JUDICIÁRIO': 'NÍVEL SUPERIOR', 'AUXILIAR JUDICIÁRIO': 'NÍVEL AUXILIAR' };
  function servNaData(ix, cargo, classe, padrao, d) {
    const cl = String(classe || '').toUpperCase().replace(/^N[ISA]\s*-?\s*/, '').trim();
    const p = padN(padrao);
    const cands = [cargo]; if (NIVEL[cargo]) cands.push(NIVEL[cargo]);
    for (const c of cands) {
      const h = vig(ix.serv.get(c + '|' + cl + '|' + p), d);
      if (h.length) { const o = {}; for (const x of h) o[x.rub] = x; return o; }
    }
    return null;
  }

  // peso de cada dia: a partir de 2018 = 1/dias do mês; antes, mês comercial de 30 dias, como na folha:
  // o dia 31 não conta e, em fevereiro, o último dia completa os 30 (quem muda em 21/07 fica 10/30 na situação nova).
  function pesos(k, desde, de30) {
    desde = desde || '2017-12'; de30 = de30 || '1994-07';
    const n = diasMes(k), w = [];
    for (let d = 1; d <= n; d++) w.push(k >= desde || k < de30 ? 1 / n : d < n ? (d <= 30 ? 1 / 30 : 0) : n === 31 ? 0 : (30 - (n - 1)) / 30);
    return w;
  }
  const naFaixa = (lst, d) => (lst || []).filter(x => x.ini <= d && (!x.fim || d <= x.fim));

  /**
   * dados: { cargo, especialidade: 'SEGURANCA'|'OFICIAL'|'', inicio, fim,
   *          progressoes:[{ini,fim,classe,padrao}], funcoes:[{ini,fim,cod,nome}], substituicoes:[{ini,fim,cod}],
   *          vpni:[{ini,fim,cod,tipo:'DECIMOS'|'QUINTOS',natureza:'ADMINISTRATIVA'|'JUDICIAL'}], ats:[{ini,pct}],
   *          aq:[{ini,fim,tipo:'DOUTORADO'|'MESTRADO'|'ESPECIALIZACAO'|'TREINAMENTO'|'GRADUACAO_TECNICO', pct?}],
   *          manual:[{cat, ini, fim, valor}] }   // parcelas sem relatório (13,23%, VPNI judicial informada etc.)
   * regras: as mesmas da calculadora (fcAte, atsDesde, gas, aqTrein, gnDesde, gnSemVPIAte, teto) +
   *         vpniJudSemPSS: ['1999-12-15','2005-12-31']
   */
  function calcularEsperada(base, dados, regrasIn) {
    const ix = base.__ix || (base.__ix = indexar(base));
    const regras = Object.assign({}, RBC.REGRAS_PADRAO, { vpniJudSemPSS: ['1999-12-15', '2005-12-31'] }, regrasIn || {});
    const ini = dados.inicio.slice(0, 7), fim = dados.fim.slice(0, 7);
    const linhas = [], avisos = new Map();
    const aviso = (k, t) => { const a = avisos.get(t) || { texto: t, meses: [] }; if (!a.meses.includes(k)) a.meses.push(k); avisos.set(t, a); };
    const prog = (dados.progressoes || []).filter(p => !p.revogada);
    const aqF = aqDaFicha(ix, dados.aqFicha, regras);

    for (let k = ini; k <= fim; k = RBC.addM(k, 1)) {
      const w = pesos(k, regras.divisorDiasDesde, regras.divisor30Desde), n = diasMes(k);
      const v = {}, info = { aq: [], ref: new Set(), refc: new Set(), funcao: new Set(), subst: new Set(), vpni: new Set(), ats: null };
      const add = (c, x) => { v[c] = (v[c] || 0) + x; };
      const fontes = new Set(), aqRel = {};
      for (let d = 1; d <= n; d++) {
        if (!w[d - 1]) continue;
        const dt = iso(k, d);
        if (dt < dados.inicio || dt > dados.fim) continue;
        const wd = w[d - 1];
        // cargo efetivo
        const pr = naFaixa(prog, dt).pop();
        if (!pr) { aviso(k, 'Sem progressão/enquadramento para a data'); continue; }
        info.ref.add(pr.classe + (/^\d+$/.test(pr.padrao) ? '-' : ' ') + pr.padrao); info.refc.add((String(pr.classe).toUpperCase().replace(/^N[ISA]\s*-?\s*/, '') || String(pr.classe).toUpperCase().replace(/-$/, '') + '-') + padN(pr.padrao));
        const t = servNaData(ix, dados.cargo, pr.classe, pr.padrao, dt);
        if (!t) { aviso(k, `Sem tabela para ${dados.cargo} ${pr.classe} ${pr.padrao}`); continue; }
        const vb = t.VB ? t.VB.v : 0;
        add('VB', vb * wd); if (t.VB) fontes.add(t.VB.id);
        for (const [rub, cat, sinal] of [['GAJ', 'GAJ', 1], ['GRAT_JUDICIARIA', 'GAJ', 1], ['APJ', 'APJ', 1], ['DIF_28_86', 'DIF2886', 1], ['GRAT_EXTRAORDINARIA', 'GEXTRA', 1], ['REDUTOR', 'REDUTOR', -1]])
          if (t[rub]) { add(cat, sinal * t[rub].v * wd); fontes.add(t[rub].id); }
        // ATS (anuênios) sobre o vencimento
        const at = naFaixa(dados.ats, dt).pop();
        if (at && at.pct) { add('ATS', vb * at.pct / 100 * wd); info.ats = at.pct / 100; }
        // VPI (Lei 10.698/2003)
        const vpi = par(ix, 'VPI_LEI_10698_2003', dt); if (vpi && dados.vpi !== false) add('VPI', vpi * wd);
        // GAS / GAE
        if (dados.especialidade && (!dados.espDesde || dt >= dados.espDesde)) {
          const cat = dados.especialidade === 'OFICIAL' ? 'GAE' : 'GAS';
          if (t[cat]) add(cat, t[cat].v * wd);
          else { const pc = par(ix, 'GAE_GAS_PERCENTUAL_IMPLANTACAO', dt); if (pc) add(cat, vb * pc * wd); }
        }
        // AQ
        for (const q of naFaixa(dados.aq, dt)) {
          aqRel[q.tipo === 'TREINAMENTO' ? 'AQ_TREIN' : 'AQ'] = true;
          let pc = q.pct != null ? q.pct / 100 : null;
          if (pc == null) {
            const nome = { DOUTORADO: 'AQ_PCT_DOUTORADO', MESTRADO: 'AQ_PCT_MESTRADO', ESPECIALIZACAO: 'AQ_PCT_ESPECIALIZACAO', TREINAMENTO: 'AQ_PCT_TREINAMENTO_POR_120H', GRADUACAO_TECNICO: 'AQ_PCT_GRADUACAO_TECNICO' }[q.tipo];
            pc = par(ix, nome, dt);
          }
          if (pc != null) add(q.tipo === 'TREINAMENTO' ? 'AQ_TREIN' : 'AQ', vb * pc * wd);
          else {
            const nomeVR = { DOUTORADO: 'AQ_DOUTORADO', MESTRADO: 'AQ_MESTRADO', ESPECIALIZACAO: 'AQ_POS_GRADUACAO_POR_CURSO', TREINAMENTO: 'AQ_CAPACITACAO_POR_120H' }[q.tipo];
            const vr = nomeVR && par(ix, nomeVR, dt);
            if (vr) add(q.tipo === 'TREINAMENTO' ? 'AQ_TREIN' : 'AQ', vr * wd); else aviso(k, 'AQ sem valor na base para ' + q.tipo);
          }
        }
        // função comissionada exercida (valor do servidor efetivo: opção)
        for (const f of naFaixa(dados.funcoes, dt)) {
          info.funcao.add(f.cod + (f.nome ? ' (' + f.nome + ')' : ''));
          const val = valorFuncao(ix, f.cod, dt);
          if (val == null) aviso(k, 'Sem tabela de função para ' + f.cod);
          else add('FC', val * wd);
        }
        for (const s of naFaixa(dados.substituicoes, dt)) {
          info.subst.add(s.cod);
          const val = valorFuncao(ix, s.cod, dt);
          if (val == null) aviso(k, 'Sem tabela de função para substituição ' + s.cod); else add('SUBST', val * wd);
        }
        // VPNI (quintos/décimos incorporados)
        const vp = naFaixa(dados.vpni, dt);
        if (vp.length) {
          const porCod = {};
          // enquanto o servidor ainda não exercia a função indicada no relatório de VPNI, a parcela é valorada pela função
          // que exercia na data (prática da DIPROF: "1/5 FC-3 até 23/02/97, após FC-4")
          const fNaData = naFaixa(dados.funcoes, dt).map(f => f.cod);
          const codEf = cod => (dados.funcoes || []).some(f => f.cod === cod) && !(dados.funcoes || []).some(f => f.cod === cod && f.ini <= dt) && fNaData.length ? fNaData[0] : cod;
          for (const p of vp) { const cd = codEf(p.cod); const c = porCod[cd] || (porCod[cd] = { adm: 0, jud: 0, tipo: p.tipo }); if (/JUD/i.test(p.natureza)) c.jud++; else c.adm++; }
          for (const cod in porCod) {
            const c = porCod[cod], den = /QUINT/i.test(c.tipo) ? 5 : 10;
            const vt = valorVPNI(ix, cod, c.adm + c.jud, den, dt), va = valorVPNI(ix, cod, c.adm, den, dt);
            if (vt == null) { aviso(k, `Sem tabela de VPNI para ${c.adm + c.jud}/${den} ${cod}`); continue; }
            info.vpni.add(`${c.adm + c.jud}/${den} ${cod}` + (c.jud ? ` (${c.jud}/${den} judicial)` : ''));
            add('VPNI', (va || 0) * wd);
            const jud = vt - (va || 0);
            if (jud) {
              const semPSS = regras.vpniJudSemPSS && dt >= regras.vpniJudSemPSS[0] && dt <= regras.vpniJudSemPSS[1];
              add(semPSS ? 'VPNI_JUD_SEM_PSS' : 'VPNI_JUD', jud * wd);
            }
          }
        }
        // 13,23% (decisão judicial) — tabela "VPI 12,23%" da base, nos períodos informados
        if (naFaixa(dados.v1323, dt).length) {
          const cl = String(pr.classe).toUpperCase().replace(/^N[ISA]\s*-?\s*/, ''), pp = padN(pr.padrao);
          const tv = vig(ix.v1323.get((NIVEL[dados.cargo] || dados.cargo) + '|' + cl + '|' + pp), dt);
          const by = {}; for (const x of tv) by[x.rub] = x.v;
          if (by.VPI_12_23 != null) {
            add('V1323_VB', by.VPI_12_23 * wd); add('V1323_GAJ', (by.GAJ_SOBRE_VPI || 0) * wd);
            if (at && at.pct) add('V1323_ATS', by.VPI_12_23 * at.pct / 100 * wd);
            if (vp.length && by.VB_REF_VPI) {
              // 13,23% sobre a VPNI: fração incorporada × VPNI de 10/10 da tabela de 2015 × (12,23%)
              const tx = by.VPI_12_23 / by.VB_REF_VPI;
              const pc = {}; for (const p of vp) pc[p.cod] = (pc[p.cod] || 0) + 1;
              for (const cod in pc) {
                const t10 = (ix.dec.get(cod) || []).find(x => x.g === 'VPNI_QUINTOS' && x.fr === '10/10' && x.i <= dt && dt <= x.f);
                if (t10) add('V1323_VPNI', t10.v * pc[cod] / 10 * tx * wd); else aviso(k, '13,23% sobre a VPNI sem tabela para ' + cod);
              }
            }
          } else aviso(k, 'Sem tabela de 13,23% para o padrão');
        }
        for (const m of naFaixa(dados.manual, dt)) add(m.cat, m.valor * wd);
      }
      // AQ pela ficha: se houve AQ pago no mês, o direito é presumido e o valor devido sai da tabela da carreira
      if (aqF[k]) for (const cat of ['AQ', 'AQ_TREIN']) {
        const a = aqF[k][cat]; if (!a || aqRel[cat]) continue;
        const val = a.nivel(v.VB || 0);
        if (val != null) { v[cat] = (v[cat] || 0) + val; info.aq.push(a.txt); }
        if (a.aviso) aviso(k, a.aviso);
      }
      for (const c in v) v[c] = r2(v[c]);
      linhas.push({ comp: k, v, ref: [...info.ref].join(' / '), refCurta: [...info.refc].join('/'), funcao: [...info.funcao].join(' / '), subst: [...info.subst].join(' / '), aq: info.aq.join(' / '), vpni: [...info.vpni].join(' / '), atsPct: info.ats, fontes: [...fontes] });
    }
    // incidência e contribuição
    const incide = (c, k) => {
      if (c === 'FC' || c === 'SUBST') return k <= regras.fcAte;
      if (c === 'ATS') return k >= regras.atsDesde;
      if (c === 'AQ_TREIN') return regras.aqTrein === 'ficha' ? !!(regras.aqTreinAnos && regras.aqTreinAnos[k.slice(0, 4)]) : !!regras.aqTrein;
      if (c === 'GAS') return !!regras.gas || (!!regras.gasAte && k <= regras.gasAte);
      if (c === 'VPNI_JUD_SEM_PSS') return false;
      return true;
    };
    for (const l of linhas) {
      l.inc = {}; let t = 0;
      for (const c in l.v) if (incide(c, l.comp)) { l.inc[c] = l.v[c]; t += l.v[c]; }
      l.total = r2(t);
      l.pss = RBC.pssDevida(l.total, l.comp, regras.teto);
    }
    // gratificação natalina (mesma regra da calculadora)
    const gns = [];
    const anos = [...new Set(linhas.map(l => l.comp.slice(0, 4)))];
    const dI = +dados.inicio.slice(8, 10), dF = +dados.fim.slice(8, 10);
    for (const y of anos) {
      if (regras.gnDesde && y < regras.gnDesde) continue;
      const ls = linhas.filter(l => l.comp.startsWith(y));
      const avos = ls.filter(l => { const pri = l.comp === ini, ult = l.comp === fim; if (!pri && !ult) return true; const a = pri ? dI : 1, b = ult ? dF : diasMes(l.comp); return b - a + 1 >= 15; }).length;
      const cheios = ls.filter(l => !(l.comp === fim && dF < diasMes(fim)) && !(l.comp === ini && dI > 1));
      const lb = cheios.length ? cheios[cheios.length - 1] : ls[ls.length - 1];
      let b = lb.total, obs = '';
      if (regras.gnSemVPIAte && y <= regras.gnSemVPIAte && lb.inc.VPI) { b = r2(b - lb.inc.VPI); obs = 'sem VPI'; }
      gns.push({ ano: y, depois: ls[ls.length - 1].comp, baseComp: lb.comp, avos, base: b, obs, valor: r2(b * avos / 12) });
    }
    return { linhas, gns, avisos: [...avisos.values()], regras };
  }

  // AQ / AQ-Treinamento a partir da ficha (decisão DIPROF, 09/10/2026): quem recebeu AQ no mês tinha direito a ele;
  // o nível (percentual até 2025, valores de referência desde 2026) é deduzido do valor pago e o valor devido vem da tabela.
  // Mês de mudança de nível: pro rata, com o dia de início deduzido do valor pago.
  function aqDaFicha(ix, fic, regras) {
    const out = {}; if (!fic) return out;
    const meses = Object.keys(fic).sort();
    for (const cat of ['AQ', 'AQ_TREIN']) {
      const info = {};
      for (const k of meses) {
        const f = fic[k], pago = f[cat]; if (!(pago > 0.005)) continue;
        const d = k + '-15', vr = k >= '2026-01';
        let cands = [];
        if (!vr) {
          if (!(f.VB > 0)) continue;
          const pcs = cat === 'AQ_TREIN' ? [1, 2, 3].map(n => [n * (par(ix, 'AQ_PCT_TREINAMENTO_POR_120H', d) || 0.01), n + '% (treinamento)'])
            : [['AQ_PCT_ESPECIALIZACAO', 'especialização'], ['AQ_PCT_MESTRADO', 'mestrado'], ['AQ_PCT_DOUTORADO', 'doutorado'], ['AQ_PCT_GRADUACAO_TECNICO', 'graduação']].map(([nm, t]) => { const x = par(ix, nm, d); return x ? [x, t + ' ' + (x * 100).toLocaleString('pt-BR') + '%'] : null; }).filter(Boolean);
          cands = pcs.map(([x, t]) => ({ x, t, val: vb => vb * x }));
          info[k] = { x: pago / f.VB, cands, tol: 0.0012 };
        } else {
          const lst = cat === 'AQ_TREIN' ? [1, 2, 3, 4, 5].map(n => [['AQ_CAPACITACAO_POR_120H', n]])
            : [[['AQ_DOUTORADO', 1]], [['AQ_MESTRADO', 1]]].concat([1, 2, 3, 4, 5].map(n => [['AQ_POS_GRADUACAO_POR_CURSO', n]]));
          const nomes = { AQ_CAPACITACAO_POR_120H: 'capacitação 120 h', AQ_DOUTORADO: 'doutorado', AQ_MESTRADO: 'mestrado', AQ_POS_GRADUACAO_POR_CURSO: 'pós-graduação' };
          cands = lst.map(l => { const x = l.reduce((s, [nm, n]) => s + (par(ix, nm, d) || 0) * n, 0); return { x, t: l.map(([nm, n]) => (n > 1 ? n + ' × ' : '') + nomes[nm]).join(' + '), val: () => x }; }).filter(c => c.x > 0);
          info[k] = { x: pago, cands, tol: 1 };
        }
      }
      // nível limpo de cada mês
      const ks = Object.keys(info).sort();
      for (const k of ks) { const I = info[k]; let best = null; for (const c of I.cands) if (!best || Math.abs(c.x - I.x) < Math.abs(best.x - I.x)) best = c; I.best = best; I.limpo = best && Math.abs(best.x - I.x) <= I.tol; }
      const regime = k => k >= '2026-01';
      for (let i = 0; i < ks.length; i++) {
        const k = ks[i], I = info[k];
        if (I.limpo) { (out[k] = out[k] || {})[cat] = { nivel: vb => I.best.val(vb), txt: I.best.t }; continue; }
        // mudança de nível no mês: anterior e seguinte no mesmo regime (0 se a sequência começa ou termina aqui)
        const kp = RBC.addM(k, -1), kn = RBC.addM(k, 1);
        const prev = info[kp] && info[kp].limpo && regime(kp) === regime(k) ? info[kp].best : null;
        const next = info[kn] && info[kn].limpo && regime(kn) === regime(k) ? info[kn].best : null;
        const xp = prev ? prev.x : 0, xn = next ? next.x : (prev ? prev.x : I.best.x);
        const div = k >= (regras.divisorDiasDesde || '2017-12') || k < (regras.divisor30Desde || '1994-07') ? diasMes(k) : 30;
        if ((I.x - xp) * (xn - I.x) > 0 && Math.abs(xn - xp) > 1e-9) {
          const dias = Math.max(1, Math.min(div - 1, Math.round((I.x - xp) / (xn - xp) * div)));
          const fr = dias / div, ini = div - dias + 1;
          (out[k] = out[k] || {})[cat] = { nivel: vb => (prev ? prev.val(vb) : 0) * (1 - fr) + (next ? next.val(vb) : 0) * fr,
            txt: (next ? next.t : '') + ' desde o dia ' + ini, aviso: `${cat === 'AQ' ? 'AQ' : 'AQ-Treinamento'} alterado no mês: início deduzido no dia ${ini} — confirmar` };
        } else (out[k] = out[k] || {})[cat] = { nivel: vb => I.best.val(vb), txt: I.best.t, aviso: `${cat === 'AQ' ? 'AQ' : 'AQ-Treinamento'} pago fora dos valores da tabela — conferir` };
      }
    }
    return out;
  }

  function valorFuncao(ix, cod, d) {
    const h = vig(ix.fc.get(cod), d);
    if (h.length) {
      const by = {}; for (const x of h) by[x.mod + '|' + x.rub] = x.v;
      // servidor efetivo: opção pelo cargo (valor líquido do redutor quando houver), FC de valor único, ou integral
      return by['OPTANTE|TOTAL'] ?? by['UNICO|FC_VALOR'] ?? by['OPTANTE|FC_OPCAO_65PCT'] ?? by['OPTANTE|FC_OPCAO_70PCT'] ?? by['INTEGRAL|TOTAL'] ?? by['INTEGRAL|FC_TOTAL'] ?? by['INTEGRAL|FC_INTEGRAL'] ?? null;
    }
    const g = vig(ix.gab.get(cod), d);   // antes de 1997: gratificação de gabinete
    if (g.length) { const by = {}; for (const x of g) by[x.mod + '|' + x.rub] = x.v; return by['COM VÍNCULO|TOTAL'] ?? by['COM VÍNCULO|SOMA'] ?? null; }
    return null;
  }
  // VPNI: tabela de décimos/quintos da época; depois da última tabela, vale a última (VPNI só muda por revisão geral)
  function valorVPNI(ix, cod, nParc, den, d) {
    if (!nParc) return 0;
    const fr = nParc + '/' + den;
    const lst = (ix.dec.get(cod) || []).filter(x => x.fr === fr && x.g === 'DECIMOS_QUINTOS');
    if (!lst.length) return null;
    let h = lst.filter(x => x.i <= d && d <= x.f);
    if (!h.length) { const ant = lst.filter(x => x.i <= d).sort((a, b) => a.i < b.i ? -1 : 1); if (!ant.length) return null; const ult = ant[ant.length - 1].i; h = ant.filter(x => x.i === ult); }
    const by = {}; for (const x of h) by[x.rub] = x.v;
    return by.DECIMOS_TOTAL ?? by.DECIMOS ?? by.DECIMOS_VALOR ?? null;
  }

  // ------------------------------------------------------------------ comparação esperada × recebida
  const GRUPO = { VPNI_JUD: 'VPNI', VPNI_JUD_SEM_PSS: 'VPNI', VPI_DED: 'VPI', ABONO: 'GAJ' };
  const gcat = c => GRUPO[c] || c;
  function comparar(esp, rec, opts) {
    const tol = (opts && opts.tol) || 0.05;
    const R = {}; for (const l of rec.linhas) R[l.comp] = l;
    const out = [];
    for (const e of esp.linhas) {
      const r = R[e.comp]; if (!r) continue;
      const ve = {}, vr = {};
      for (const c in e.v) ve[gcat(c)] = (ve[gcat(c)] || 0) + e.v[c];
      for (const c in (r.bruto || r.v)) vr[gcat(c)] = (vr[gcat(c)] || 0) + (r.bruto || r.v)[c];
      const itens = [];
      // antes de 07/1994 a ficha pode vir convertida (÷1.000, ÷2.750, ÷2.750.000) enquanto a tabela está na moeda da época
      if (e.comp < '1994-07' && r.fonte) {
        const se = Object.values(ve).reduce((a, b) => a + b, 0), sr = Object.values(vr).reduce((a, b) => a + b, 0);
        if (se > 0 && sr > 0 && [1000, 2750, 2750000, 2750 * 1000].some(f => Math.abs(sr * f / se - 1) < 0.2)) {
          out.push({ comp: e.comp, totalEsp: e.total, totalRec: r.total, pssEsp: e.pss, pssFicha: r.pssFicha, itens: [{ cat: 'TOTAL', esperado: r2(se), recebido: r2(sr), dif: r2(sr - se), sit: 'moeda diferente' }] });
          continue;
        }
      }
      for (const c of new Set([...Object.keys(ve), ...Object.keys(vr)])) {
        const a = r2(ve[c] || 0), b = r2(vr[c] || 0), d = r2(b - a);
        if (Math.abs(d) <= tol) continue;
        const sit = !r.fonte ? 'sem ficha' : !a ? 'pago sem previsão' : !b ? 'não pago' : d > 0 ? 'pago a maior' : 'pago a menor';
        itens.push({ cat: c, esperado: a, recebido: b, dif: d, sit });
      }
      out.push({ comp: e.comp, totalEsp: e.total, totalRec: r.total, pssEsp: e.pss, pssFicha: r.pssFicha, itens });
    }
    return out;
  }

  // sugere classe/padrão para uma data: pelo vencimento pago na ficha (quando houver) e pela pista do OCR
  const ROMANO = ['I', 'II', 'III', 'IV', 'V', 'VI'];
  function candidatos(base, cargo, d) {
    const ix = base.__ix || (base.__ix = indexar(base));
    const out = [];
    for (const [k, lst] of ix.serv) {
      const [cg, cl, p] = k.split('|');
      if (cg !== cargo && cg !== NIVEL[cargo]) continue;
      const vb = vig(lst, d).find(x => x.rub === 'VB'); if (!vb) continue;
      out.push({ classe: cg.startsWith('NÍVEL') ? 'N' + cg[6] + (cl ? '-' + cl : '') : cl, padrao: p, vb: vb.v, nivel: cg.startsWith('NÍVEL') });
    }
    return out;
  }
  function sugerirRef(base, cargo, d, dica, vbFicha) {
    const cs = candidatos(base, cargo, d); if (!cs.length) return null;
    if (vbFicha) {
      const fs = d < '1994-07' ? [1, 1.1198, 1000, 2750, 2750000] : [1, 1.1198];   // ficha antiga pode vir convertida
      // tenta cada fator em ordem (valor da ficha como está, depois os ajustes) e aceita o primeiro com um único candidato
      for (const f of fs) {
        const hit = cs.filter(c => Math.abs(c.vb - vbFicha * f) <= Math.max(0.05, c.vb * 0.0002, f * 0.006));
        if (hit.length === 1) return Object.assign({ origem: 'ficha' }, hit[0]);
      }
    }
    const norm = s => String(s || '').toUpperCase().replace(/[(\[{]=?/g, 'C').replace(/\bE\b/g, 'C').replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
    const h = norm(dica); let best = null, bs = -1;
    for (const c of cs) {
      const lab = norm(c.classe.replace('-', ' ') + ' ' + c.padrao);
      let sc = 0; const ht = h.split(' '), lt = lab.split(' ');
      for (const t of lt) if (ht.includes(t)) sc += 2; else if (ht.some(x => x && (x[0] === t[0] || x.endsWith(t)))) sc += 1;
      if (sc > bs) { bs = sc; best = c; }
    }
    return best ? Object.assign({ origem: bs >= 4 ? 'leitura' : 'incerta' }, best) : null;
  }

  const api = { sugerirRef, candidatos, comparar, calcularEsperada, indexar, pesos, valorFuncao, valorVPNI };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.RBCEsperada = api;
})(typeof self !== 'undefined' ? self : this);
