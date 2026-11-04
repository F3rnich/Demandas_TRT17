/* ============================================================================
 * Motor de regras — Calculadora de aposentadoria (servidores e magistrados da União)
 * SGP · TRT-17. Processamento 100% local. Nenhum dado sai do navegador.
 *
 * Convenções
 *  - Tempo contado em dias; ano = 365 dias (Lei 8.112/1990, art. 101).
 *  - Todos os períodos são inclusivos (início e fim contam).
 *  - Idade: aniversário civil (29/02 → 01/03 em ano não bissexto).
 *  - Após a data de referência, presume-se exercício contínuo no Tribunal.
 * ==========================================================================*/
(function (raiz) {
'use strict';

const DIA = 86400000;
const ANO = 365;

/* ---------- datas como inteiros (dias desde 1970-01-01, UTC) ---------- */
function d2n(s) {
  if (s == null || s === '') return null;
  if (typeof s === 'number') return s;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s).trim());
  if (!m) return null;
  return Math.round(Date.UTC(+m[1], +m[2] - 1, +m[3]) / DIA);
}
function n2d(n) {
  if (n == null) return null;
  return new Date(n * DIA).toISOString().slice(0, 10);
}
function n2br(n) {
  if (n == null) return '—';
  const s = n2d(n); return s.slice(8, 10) + '/' + s.slice(5, 7) + '/' + s.slice(0, 4);
}
function anoDe(n) { return new Date(n * DIA).getUTCFullYear(); }
/** Data em que se completam `anos` de idade (aniversário civil). */
function aniversario(nasc, anos) {
  const dt = new Date(nasc * DIA);
  const y = dt.getUTCFullYear() + anos, m = dt.getUTCMonth(), d = dt.getUTCDate();
  if (m === 1 && d === 29) {
    const bis = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
    if (!bis) return Math.round(Date.UTC(y, 2, 1) / DIA);
  }
  return Math.round(Date.UTC(y, m, d) / DIA);
}
function idadeAnos(nasc, dia) {
  let a = anoDe(dia) - anoDe(nasc);
  if (aniversario(nasc, a) > dia) a--;
  return a;
}
/** "x anos, y meses e z dias" no padrão de 365/30 dias usado nos mapas de tempo. */
function fmtTempo(dias) {
  if (dias == null) return '—';
  const neg = dias < 0; let r = Math.round(Math.abs(dias));
  const a = Math.floor(r / ANO); r -= a * ANO;
  const m = Math.floor(r / 30); const d = r - m * 30;
  const p = [];
  if (a) p.push(a + (a === 1 ? ' ano' : ' anos'));
  if (m) p.push(m + (m === 1 ? ' mês' : ' meses'));
  if (d || !p.length) p.push(d + (d === 1 ? ' dia' : ' dias'));
  return (neg ? '−' : '') + p.join(', ');
}

/* ---------- parâmetros normativos ---------- */
const MARCOS = {
  EC20: d2n('1998-12-16'),   // publicação EC 20/1998
  EC41: d2n('2003-12-31'),   // publicação EC 41/2003
  RPC:  d2n('2013-10-14'),   // início do RPC no Judiciário da União (Funpresp-Jud)
  EC103: d2n('2019-11-13'),  // publicação/vigência EC 103/2019
  IDADE4: d2n('2022-01-01')  // art. 4º, §1º: idades mínimas sobem
};
const PADRAO_PARAM = {
  corteEC103: '2019-11-13',     // data-limite (inclusiva) para direito adquirido e pedágio
  lpNosPontos: true,            // licença-prêmio em dobro integra o tempo de contribuição dos pontos
  converteEspecial: true,       // conversão de tempo especial em comum até a EC 103 (STF Tema 942)
  acrescimoMulher15: false,     // 2% a partir de 15 anos (em vez de 20) para servidoras — tese em ADI
  idadeCompulsoria: 75          // LC 152/2015
};
function pontosExigidos(sexo, ano) {
  const inc = Math.max(0, ano - 2019);
  return sexo === 'F' ? Math.min(100, 86 + inc) : Math.min(105, 96 + inc);
}

/* ---------- leitura e validação da entrada ---------- */
function normalizar(e) {
  const p = Object.assign({}, PADRAO_PARAM, e.param || {});
  const x = {
    sexo: e.sexo === 'F' ? 'F' : 'M',
    nasc: d2n(e.nasc),
    ref: d2n(e.ref) ?? d2n(new Date().toISOString().slice(0, 10)),
    ingressoSP: d2n(e.ingressoSP),
    ingressoCarreira: d2n(e.ingressoCarreira) ?? d2n(e.ingressoCargo),
    ingressoCargo: d2n(e.ingressoCargo),
    exercicio: d2n(e.exercicio),
    migrouRPC: !!e.migrouRPC,
    magistrado: !!e.magistrado,
    policiaJudicial: !!e.policiaJudicial,
    periodos: (e.periodos || []).map((q, i) => ({
      i, orgao: q.orgao || '', regime: q.regime || 'RGPS',
      publico: q.publico != null ? !!q.publico : (q.regime === 'RPPS' || q.regime === 'MILITAR'),
      ini: d2n(q.inicio), fim: d2n(q.fim)
    })).filter(q => q.ini != null && q.fim != null),
    deducoes: (e.deducoes || []).map(q => ({
      desc: q.desc || '', data: d2n(q.data), dias: Math.max(0, +q.dias || 0),
      contrib: q.contrib !== false, sp: q.sp !== false, cargo: q.cargo !== false
    })).filter(q => q.dias > 0),
    lpDias: Math.max(0, +e.lpDias || 0),
    lpData: d2n(e.lpData) ?? MARCOS.EC20,
    exposicoes: (e.exposicoes || []).map(q => ({ ini: d2n(q.inicio), fim: d2n(q.fim) }))
      .filter(q => q.ini != null && q.fim != null),
    exposicaoContinua: !!e.exposicaoContinua,
    deficiencia: e.deficiencia && e.deficiencia.grau ? {
      grau: e.deficiencia.grau, ini: d2n(e.deficiencia.inicio), fim: d2n(e.deficiencia.fim)
    } : null,
    p, corte: d2n(p.corteEC103)
  };
  return x;
}
function validar(x) {
  const erros = [], avisos = [];
  if (x.nasc == null) erros.push('Informe a data de nascimento.');
  if (x.exercicio == null) erros.push('Informe a data de início de exercício no Tribunal.');
  if (x.ingressoCargo == null) erros.push('Informe a data de ingresso no cargo atual.');
  if (x.ingressoSP == null) erros.push('Informe a data mais remota de ingresso no serviço público sem interrupção.');
  if (erros.length) return { erros, avisos };
  if (x.ingressoCargo < x.exercicio && !x.periodos.some(q => q.publico && q.ini <= x.ingressoCargo))
    avisos.push('O ingresso no cargo é anterior ao exercício no Tribunal e não há período público averbado que o cubra. Confira se o cargo é o mesmo (ex.: redistribuição).');
  if (x.ingressoSP > x.exercicio)
    avisos.push('O ingresso no serviço público está depois do exercício no Tribunal. Ajuste: ele deve ser igual ou anterior.');
  if (x.ingressoCarreira != null && x.ingressoCarreira > x.ingressoCargo)
    avisos.push('O ingresso na carreira está depois do ingresso no cargo. Em regra, a carreira começa antes ou junto com o cargo.');
  x.periodos.forEach(q => {
    if (q.fim < q.ini) erros.push(`Período ${q.i + 1} (${q.orgao || 'sem nome'}): data final anterior à inicial.`);
    if (q.fim >= x.exercicio && q.ini <= x.exercicio) avisos.push(`Período ${q.i + 1} (${q.orgao || 'sem nome'}) termina depois do início no Tribunal. A sobreposição não é contada em dobro.`);
    if (q.fim > x.ref) avisos.push(`Período ${q.i + 1} (${q.orgao || 'sem nome'}) termina depois da data de referência.`);
  });
  if (x.nasc && aniversario(x.nasc, 18) > x.exercicio) avisos.push('Exercício no Tribunal antes dos 18 anos de idade: confira as datas.');
  // continuidade do serviço público: a partir de ingressoSP, deve haver vínculo público sem lacuna até o Tribunal
  const pub = x.periodos.filter(q => q.publico).map(q => [q.ini, q.fim]).concat([[x.exercicio, x.exercicio]]);
  pub.sort((a, b) => a[0] - b[0]);
  let cursor = x.ingressoSP - 1, lacuna = null;
  for (const [a, b] of pub) {
    if (b < x.ingressoSP) continue;
    if (a > cursor + 1) { lacuna = [cursor + 1, a - 1]; break; }
    cursor = Math.max(cursor, b);
    if (cursor >= x.exercicio) break;
  }
  if (lacuna) avisos.push(`Há intervalo sem vínculo público entre ${n2br(lacuna[0])} e ${n2br(lacuna[1])}. As datas-corte de ingresso (16/12/1998, 31/12/2003, 13/11/2019) dependem de vínculo sem interrupção — confira a data de ingresso informada.`);
  if (x.policiaJudicial) avisos.push('Agente/inspetor de polícia judicial: sem regra especial vigente (art. 5º da EC 103/2019 não inclui o cargo; MI 844/STF). Aplicadas as regras gerais.');
  return { erros, avisos };
}

/* ---------- linha do tempo diária ---------- */
function construirSeries(x) {
  const fimSim = aniversario(x.nasc, x.p.idadeCompulsoria) + 1;
  const ini0 = Math.min(x.exercicio, x.ingressoSP, x.ingressoCargo,
    ...x.periodos.map(q => q.ini), ...x.exposicoes.map(q => q.ini)) - 1;
  const N = fimSim - ini0 + 1;
  const idx = n => Math.min(N - 1, Math.max(0, n - ini0));
  const cont = new Int16Array(N + 1), pub = new Int16Array(N + 1), exp = new Int16Array(N + 1);
  const marca = (arr, a, b) => { if (b < ini0) return; arr[idx(a)]++; arr[idx(b) + 1]--; };
  for (const q of x.periodos) { marca(cont, q.ini, q.fim); if (q.publico) marca(pub, q.ini, q.fim); }
  marca(cont, x.exercicio, fimSim); marca(pub, x.exercicio, fimSim);
  for (const q of x.exposicoes) marca(exp, q.ini, Math.min(q.fim, x.exposicaoContinua ? fimSim : x.ref));
  if (x.exposicaoContinua) {
    const ult = x.exposicoes.reduce((m, q) => Math.max(m, q.fim), -Infinity);
    if (ult >= x.ref - 1) marca(exp, x.ref + 1, fimSim);
  }
  // deduções/acréscimos pontuais
  const dedC = new Float64Array(N), dedS = new Float64Array(N), dedG = new Float64Array(N);
  for (const d of x.deducoes) {
    const k = idx(d.data ?? x.exercicio);
    if (d.contrib) dedC[k] += d.dias; if (d.sp) dedS[k] += d.dias; if (d.cargo) dedG[k] += d.dias;
  }
  const lpK = idx(x.lpData);
  const fator = x.sexo === 'F' ? 1.2 : 1.4;     // atividade de 25 anos → comum (30 F / 35 M)
  const def = x.deficiencia;
  const reqDef = { grave: x.sexo === 'F' ? 20 : 25, moderada: x.sexo === 'F' ? 24 : 29, leve: x.sexo === 'F' ? 28 : 33 };
  const reqSem = x.sexo === 'F' ? 30 : 35;

  const S = {
    ini0, N, idx, dia: k => ini0 + k,
    C: new Float64Array(N),      // contribuição (com LP e conversão)
    Cp: new Float64Array(N),     // contribuição para pontos
    Cbruto: new Float64Array(N), // contribuição sem LP e sem conversão
    SP: new Float64Array(N), CG: new Float64Array(N), CR: new Float64Array(N),
    EXP: new Float64Array(N), CONV: new Float64Array(N),
    PCDf: new Float64Array(N),   // fração acumulada (LC 142, art. 7º)
    PCDd: new Float64Array(N),   // dias de contribuição na condição de PcD
    sobreposicao: 0
  };
  let c = 0, s = 0, e = 0, ac = 0, as = 0, ag = 0, ar = 0, ae = 0, conv = 0, lp = 0, pf = 0, pd = 0, dc = 0, ds = 0, dg = 0;
  let somaBruta = 0;
  for (let k = 0; k < N; k++) {
    c += cont[k]; s += pub[k]; e += exp[k];
    const d = ini0 + k;
    const ativo = c > 0;
    if (c > 1) S.sobreposicao += (d <= x.ref ? c - 1 : 0);
    if (ativo) {
      ac++;
      if (e > 0) { ae++; if (x.p.converteEspecial && d <= x.corte) conv += fator - 1; }
      if (def && def.ini != null && d >= def.ini && (def.fim == null || d <= def.fim)) { pd++; pf += 1 / (reqDef[def.grau] * ANO); }
      else pf += 1 / (reqSem * ANO);
    }
    if (s > 0) as++;
    if (d >= x.ingressoCargo) ag++;
    if (x.ingressoCarreira != null && d >= x.ingressoCarreira) ar++;
    if (k === lpK) lp = x.lpDias;
    dc += dedC[k]; ds += dedS[k]; dg += dedG[k];
    S.Cbruto[k] = ac - dc;
    S.C[k] = ac - dc + lp + conv;
    S.Cp[k] = ac - dc + (x.p.lpNosPontos ? lp : 0) + conv;
    S.SP[k] = as - ds; S.CG[k] = ag - dg; S.CR[k] = ar - dg;
    S.EXP[k] = ae; S.CONV[k] = conv;
    S.PCDf[k] = pf - (dc / ((reqSem) * ANO)); S.PCDd[k] = pd;
  }
  // mínimo do sufixo: primeiro dia a partir do qual a série não cai mais abaixo do limiar
  S.suf = {};
  S.primeiro = (nome, limiar, desde) => {
    let suf = S.suf[nome];
    if (!suf) {
      const a = S[nome]; suf = new Float64Array(N); let m = Infinity;
      for (let k = N - 1; k >= 0; k--) { m = Math.min(m, a[k]); suf[k] = m; }
      S.suf[nome] = suf;
    }
    let k0 = desde != null ? idx(desde) : 0;
    for (let k = k0; k < N; k++) if (suf[k] >= limiar - 1e-9) return ini0 + k;
    return null;
  };
  S.v = (nome, dia) => S[nome][idx(dia)];
  S.fim = fimSim;
  return S;
}

/* ---------- avaliação de regras ---------- */
function req(rotulo, exigido, data, extra) { return Object.assign({ rotulo, exigido, data }, extra || {}); }

/** Percentual da média — art. 26, §2º, EC 103 (60% + 2% por ano que exceder 20). */
function pctArt26(x, S, dia, base) {
  const anos = Math.floor(S.v('C', dia) / ANO);
  const lim = base != null ? base : (x.sexo === 'F' && x.p.acrescimoMulher15 ? 15 : 20);
  return Math.min(100, 60 + 2 * Math.max(0, anos - lim));
}

function avaliar(entrada) {
  const x = normalizar(entrada);
  const val = validar(x);
  if (val.erros.length) return { ok: false, erros: val.erros, avisos: val.avisos };
  const S = construirSeries(x);
  const F = x.sexo === 'F';
  const comp = aniversario(x.nasc, x.p.idadeCompulsoria);
  const idade = n => aniversario(x.nasc, n);
  const T = (anos) => anos * ANO;
  const tempo = (serie, anos, desde) => S.primeiro(serie, T(anos), desde);
  const max = (...ds) => ds.some(d => d == null) ? null : Math.max(...ds);
  const ingr2003 = x.ingressoSP != null && x.ingressoSP <= MARCOS.EC41 && !x.migrouRPC;
  const tetoRGPS = x.migrouRPC || x.ingressoSP >= MARCOS.RPC;
  const regras = [];
  const add = r => {
    r.data = r.aplicavel === false ? null : (r.data ?? max(...r.requisitos.map(q => q.data)));
    if (r.aplicavel === false) r.status = 'inaplicavel';
    else if (r.adquirido) r.status = (r.data != null && r.data <= x.corte) ? 'cumprida' : 'nao_cumprida';
    else if (r.data == null || r.data > comp) r.status = 'inalcancavel';
    else r.status = r.data <= x.ref ? 'cumprida' : 'prevista';
    if (r.status === 'cumprida' || r.status === 'prevista') {
      if (typeof r.provento === 'function') r.provento = r.provento(r.data);
    } else if (typeof r.provento === 'function') r.provento = r.provento(null);
    r.abonoDesde = (r.abono && (r.status === 'cumprida' || r.status === 'prevista')) ? r.data : null;
    regras.push(r);
  };
  const prov = (tipo, pct, extra) => Object.assign({ tipo, pct }, extra || {});
  const media = (d, pctF, extra) => prov('media', d != null ? pctF(d) : null, extra);

  const cargo5 = req('5 anos no cargo efetivo', '5 anos', tempo('CG', 5));
  const sp = n => req(`${n} anos de serviço público`, n + ' anos', tempo('SP', n));
  const contrib = n => req(`${n} anos de contribuição`, n + ' anos', tempo('C', n));
  const idd = n => req(`Idade de ${n} anos`, n + ' anos', idade(n));

  /* ===== 1. Direito adquirido até a EC 103 (art. 3º) ===== */
  // EC 47, art. 3º
  {
    const r = { id: 'ec47', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Integral com redução de idade',
      fund: 'Art. 3º da EC 47/2005', adquirido: true, abono: true,
      aplicavel: x.ingressoSP <= MARCOS.EC20,
      motivo: 'Exige ingresso no serviço público até 16/12/1998.' };
    const base = F ? 55 : 60, cmin = F ? 30 : 35;
    const rc = contrib(cmin), rs = sp(25), rcr = req('15 anos de carreira', '15 anos', tempo('CR', 15));
    // idade mínima reduzida em 1 ano para cada ano de contribuição acima do mínimo
    let dIdade = null;
    const d0 = max(rc.data, rs.data, rcr.data, cargo5.data);
    if (d0 != null) for (let d = d0; d <= Math.min(S.fim - 1, x.corte); d++) {
      const exc = Math.floor((S.v('C', d) - T(cmin)) / ANO);
      if (idadeAnos(x.nasc, d) >= base - Math.max(0, exc)) { dIdade = d; break; }
    }
    r.requisitos = [rc, rs, rcr, cargo5, req(`Idade de ${base} anos, reduzida 1 ano por ano de contribuição acima de ${cmin}`, `${base} − excedente`, dIdade)];
    r.data = dIdade;
    r.provento = () => prov('integral', 100, { paridade: true });
    add(r);
  }
  // EC 41, art. 6º
  add({ id: 'ec41a6', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Integral com paridade',
    fund: 'Art. 6º da EC 41/2003', adquirido: true, abono: true,
    aplicavel: x.ingressoSP <= MARCOS.EC41, motivo: 'Exige ingresso no serviço público até 31/12/2003.',
    requisitos: [idd(F ? 55 : 60), contrib(F ? 30 : 35), sp(20), req('10 anos de carreira', '10 anos', tempo('CR', 10)), cargo5],
    provento: () => prov('integral', 100, { paridade: true }) });
  // CF art. 40, §1º, III, a (redação EC 41)
  add({ id: 'cf40a', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Voluntária por idade e contribuição (regra anterior)',
    fund: 'Art. 40, §1º, III, "a", da CF (redação da EC 41/2003)', adquirido: true, abono: true,
    requisitos: [idd(F ? 55 : 60), contrib(F ? 30 : 35), sp(10), cargo5],
    provento: () => prov('media80', 100, { nota: 'Média das 80% maiores remunerações (Lei 10.887/2004)' }) });
  // CF art. 40, §1º, III, b
  add({ id: 'cf40b', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Voluntária por idade (regra anterior)',
    fund: 'Art. 40, §1º, III, "b", da CF (redação da EC 41/2003)', adquirido: true, abono: false,
    requisitos: [idd(F ? 60 : 65), sp(10), cargo5],
    provento: () => prov('media80', Math.min(100, Math.round(1000 * S.v('C', x.corte) / T(F ? 30 : 35)) / 10),
      { nota: 'Proporcional ao tempo de contribuição sobre a média das 80% maiores' }) });
  // EC 41, art. 2º (pedágio de 20% e redutor)
  {
    const cmin = F ? 30 : 35;
    const falta98 = Math.max(0, T(cmin) - S.v('C', MARCOS.EC20));
    const alvo = T(cmin) + 0.2 * falta98;
    const rc = req(`${cmin} anos de contribuição + pedágio de 20% (${fmtTempo(0.2 * falta98)})`, fmtTempo(alvo), S.primeiro('C', alvo));
    add({ id: 'ec41a2', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Antecipada com redutor',
      fund: 'Art. 2º da EC 41/2003', adquirido: true, abono: true,
      aplicavel: x.ingressoSP <= MARCOS.EC20, motivo: 'Exige ingresso em cargo efetivo até 16/12/1998.',
      requisitos: [idd(F ? 48 : 53), rc, cargo5],
      provento: d => {
        if (d == null) return prov('media80', null);
        const antecip = Math.max(0, (F ? 55 : 60) - idadeAnos(x.nasc, d));
        return prov('media80', Math.max(0, 100 - 5 * antecip), { nota: `Redutor de 5% por ano antecipado (${antecip} ano(s))` });
      } });
  }
  // Especial (SV 33) adquirida
  if (x.exposicoes.length) add({ id: 'sv33', grupo: 'Direito adquirido (antes da EC 103)', nome: 'Especial por agentes nocivos (regra anterior)',
    fund: 'Art. 40, §4º, III, da CF (redação anterior) c/c Súmula Vinculante 33 e art. 57 da Lei 8.213/1991', adquirido: true, abono: true,
    requisitos: [req('25 anos de efetiva exposição', '25 anos', tempo('EXP', 25)), sp(10), cargo5],
    provento: () => prov('media80', 100, { nota: 'Média, sem paridade' }) });

  /* ===== 2. Transição (EC 103) ===== */
  const ate103 = x.ingressoSP <= x.corte;
  const idade4 = d => (d < MARCOS.IDADE4 ? (F ? 56 : 61) : (F ? 57 : 62));
  // Art. 4º — pontos
  {
    const cmin = F ? 30 : 35;
    const base = [contrib(cmin), sp(20), cargo5];
    const dBase = max(...base.map(q => q.data));
    let dIdade = null, dPontos = null, dTudo = null;
    if (dBase != null) {
      const ini = Math.max(dBase, x.corte);
      for (let d = Math.max(x.corte, x.nasc); d < S.fim; d++) {
        const okI = idadeAnos(x.nasc, d) >= idade4(d);
        const pts = (d - x.nasc + 1) + S.v('Cp', d);
        const okP = pts >= pontosExigidos(x.sexo, anoDe(d)) * ANO;
        if (okI && dIdade == null) dIdade = d;
        if (okP && dPontos == null) dPontos = d;
        if (d >= ini && okI && okP) { dTudo = d; break; }
      }
    }
    const reqs = base.concat([
      req(`Idade mínima (${F ? '56/57' : '61/62'} anos)`, `${idade4(dTudo ?? x.ref)} anos`, dIdade),
      req('Pontos (idade + contribuição, em dias)', dTudo ? `${pontosExigidos(x.sexo, anoDe(dTudo))} pontos em ${anoDe(dTudo)}` : 'tabela anual', dPontos)
    ]);
    const intIdade = idade(F ? 62 : 65);
    add({ id: 'art4i', grupo: 'Transição da EC 103', nome: 'Pontos — integralidade e paridade',
      fund: 'Art. 4º, §6º, I, da EC 103/2019', abono: true,
      aplicavel: ate103 && ingr2003,
      motivo: x.migrouRPC ? 'Quem migrou para o regime complementar não tem integralidade.' : 'Exige ingresso no serviço público até 31/12/2003 (e ingresso até 13/11/2019).',
      requisitos: reqs.concat([req(`Idade de ${F ? 62 : 65} anos (para integralidade)`, `${F ? 62 : 65} anos`, intIdade)]),
      data: dTudo != null ? Math.max(dTudo, intIdade) : null,
      provento: () => prov('integral', 100, { paridade: true }) });
    add({ id: 'art4m', grupo: 'Transição da EC 103', nome: 'Pontos — média',
      fund: 'Art. 4º, §6º, II, da EC 103/2019 c/c art. 26', abono: true,
      aplicavel: ate103, motivo: 'Exige ingresso no serviço público até 13/11/2019.',
      requisitos: reqs, data: dTudo,
      provento: d => media(d, dd => pctArt26(x, S, dd), { teto: tetoRGPS }) });
  }
  // Art. 20 — pedágio de 100%
  {
    const cmin = F ? 30 : 35;
    const falta = Math.max(0, T(cmin) - S.v('C', x.corte));
    const alvo = T(cmin) + falta;
    const reqs = [idd(F ? 57 : 60),
      req(`${cmin} anos de contribuição + pedágio (${fmtTempo(falta)})`, fmtTempo(alvo), S.primeiro('C', alvo), { pedagio: falta }),
      sp(20), cargo5];
    add({ id: 'art20i', grupo: 'Transição da EC 103', nome: 'Pedágio — integralidade e paridade',
      fund: 'Art. 20, §2º, I, da EC 103/2019', abono: true,
      aplicavel: ate103 && ingr2003,
      motivo: x.migrouRPC ? 'Quem migrou para o regime complementar não tem integralidade.' : 'Exige ingresso no serviço público até 31/12/2003 (e ingresso até 13/11/2019).',
      requisitos: reqs, provento: () => prov('integral', 100, { paridade: true }) });
    add({ id: 'art20m', grupo: 'Transição da EC 103', nome: 'Pedágio — 100% da média',
      fund: 'Art. 20, §2º, II, da EC 103/2019', abono: true,
      aplicavel: ate103, motivo: 'Exige ingresso no serviço público até 13/11/2019.',
      requisitos: reqs, provento: d => media(d, () => 100, { teto: tetoRGPS }) });
  }
  // Art. 21 — especial (transição)
  if (x.exposicoes.length) {
    const opcoes = [[25, 86]];
    for (const [anosExp, pts] of opcoes) {
      let dP = null;
      const dExp = tempo('EXP', anosExp);
      for (let d = Math.max(x.corte, x.nasc); d < S.fim; d++) {
        if ((d - x.nasc + 1) + S.v('C', d) - S.v('CONV', d) >= pts * ANO) { dP = d; break; }
      }
      add({ id: 'art21_' + anosExp, grupo: 'Transição da EC 103', nome: `Especial por agentes nocivos — ${pts} pontos`,
        fund: `Art. 21, ${anosExp === 25 ? 'III' : anosExp === 20 ? 'II' : 'I'}, da EC 103/2019`, abono: true,
        aplicavel: ate103, motivo: 'Exige ingresso no serviço público até 13/11/2019.',
        requisitos: [req(`${anosExp} anos de efetiva exposição`, anosExp + ' anos', dExp),
          req(`${pts} pontos (idade + contribuição, sem conversão)`, pts + ' pontos', dP), sp(20), cargo5],
        provento: d => media(d, dd => pctArt26(x, S, dd), { teto: tetoRGPS }) });
    }
  }

  /* ===== 3. Regras permanentes (art. 10 da EC 103) ===== */
  add({ id: 'art10', grupo: 'Regra permanente (EC 103)', nome: 'Voluntária comum',
    fund: 'Art. 10, §1º, I, da EC 103/2019', abono: true,
    requisitos: [idd(F ? 62 : 65), contrib(25), sp(10), cargo5],
    provento: d => media(d, dd => pctArt26(x, S, dd), { teto: tetoRGPS }) });
  if (x.exposicoes.length) add({ id: 'art10esp', grupo: 'Regra permanente (EC 103)', nome: 'Especial por agentes nocivos',
    fund: 'Art. 10, §2º, II, da EC 103/2019', abono: false,
    notaAbono: 'O art. 10, §5º, prevê abono só para a regra do §1º, I; confirme o entendimento do órgão.',
    requisitos: [idd(60), req('25 anos de efetiva exposição', '25 anos', tempo('EXP', 25)), req('25 anos de contribuição (sem conversão)', '25 anos', S.primeiro('Cbruto', T(25))), sp(10), cargo5],
    provento: d => media(d, dd => pctArt26(x, S, dd), { teto: tetoRGPS }) });
  // PcD — art. 22 c/c LC 142
  if (x.deficiencia) {
    const g = x.deficiencia.grau;
    const anosG = { grave: F ? 20 : 25, moderada: F ? 24 : 29, leve: F ? 28 : 33 }[g];
    const inc = { grave: 'I', moderada: 'II', leve: 'III' }[g];
    add({ id: 'pcdT', grupo: 'Pessoa com deficiência (LC 142/2013)', nome: `Por tempo — deficiência ${g}`,
      fund: `Art. 22 da EC 103/2019 c/c art. 3º, ${inc}, da LC 142/2013`, abono: true,
      requisitos: [req(`${anosG} anos de contribuição como PcD (tempo misto convertido — art. 7º)`, anosG + ' anos', S.primeiro('PCDf', 1)), sp(10), cargo5],
      provento: () => prov('media', 100, { teto: tetoRGPS, nota: '100% da média (art. 8º, I, LC 142)' }) });
    add({ id: 'pcdI', grupo: 'Pessoa com deficiência (LC 142/2013)', nome: 'Por idade',
      fund: 'Art. 22 da EC 103/2019 c/c art. 3º, IV, da LC 142/2013', abono: true,
      requisitos: [idd(F ? 55 : 60), contrib(15), req('15 anos de contribuição na condição de PcD', '15 anos', tempo('PCDd', 15)), sp(10), cargo5],
      provento: d => media(d, dd => Math.min(100, 70 + Math.floor(S.v('C', dd) / ANO)), { teto: tetoRGPS, nota: '70% + 1% por ano de contribuição (art. 8º, IV, LC 142)' }) });
  }
  // Compulsória
  add({ id: 'comp', grupo: 'Regra permanente (EC 103)', nome: 'Compulsória',
    fund: 'Art. 40, §1º, II, da CF c/c LC 152/2015 e art. 26, §4º, da EC 103/2019', abono: false,
    requisitos: [idd(x.p.idadeCompulsoria)], data: comp,
    provento: d => media(d, dd => Math.round(Math.min(1, S.v('C', dd) / T(20)) * pctArt26(x, S, dd) * 10) / 10,
      { teto: tetoRGPS, nota: 'Tempo/20 anos (limitado a 1) × percentual do art. 26, §2º' }) });

  /* ---------- síntese ---------- */
  const validas = regras.filter(r => r.status === 'cumprida' || r.status === 'prevista');
  const ordemProv = r => r.provento && r.provento.tipo === 'integral' ? 300 : (r.provento && r.provento.pct != null ? 100 + r.provento.pct : 0);
  const primeira = validas.filter(r => r.id !== 'comp').sort((a, b) => a.data - b.data)[0] || null;
  const melhor = (validas.some(r => r.id !== 'comp') ? validas.filter(r => r.id !== 'comp') : validas).slice().sort((a, b) => ordemProv(b) - ordemProv(a) || a.data - b.data)[0] || null;
  const abonos = validas.filter(r => r.abonoDesde != null).sort((a, b) => a.abonoDesde - b.abonoDesde);
  const k = S.idx(x.ref);
  const situacao = {
    ref: x.ref, idadeAnos: idadeAnos(x.nasc, x.ref), idadeDias: x.ref - x.nasc + 1,
    contribuicao: S.C[k], contribuicaoBruta: S.Cbruto[k], lp: x.ref >= x.lpData ? x.lpDias : 0,
    conversao: S.CONV[k], servicoPublico: S.SP[k], cargo: S.CG[k], carreira: x.ingressoCarreira != null ? S.CR[k] : null,
    exposicao: S.EXP[k], pontos: (x.ref - x.nasc + 1 + S.Cp[k]) / ANO,
    pontosExigidos: pontosExigidos(x.sexo, anoDe(x.ref)),
    contribNoCorte: S.v('C', x.corte), sobreposicao: S.sobreposicao,
    compulsoria: comp, tetoRGPS, ingr2003, ate103,
    pcdFracao: x.deficiencia ? S.PCDf[k] : null
  };
  return { ok: true, avisos: val.avisos, regras, primeira, melhor, abono: abonos[0] || null, situacao, x };
}

const API = { avaliar, d2n, n2d, n2br, fmtTempo, aniversario, idadeAnos, pontosExigidos, PADRAO_PARAM, MARCOS, ANO };
if (typeof module !== 'undefined' && module.exports) module.exports = API;
else raiz.MotorApos = API;
})(typeof window !== 'undefined' ? window : globalThis);
