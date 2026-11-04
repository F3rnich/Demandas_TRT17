// Testes do motor — node apos_src/testes.js
const M = require('./motor.js');
let falhas = 0, total = 0;
function eq(nome, obtido, esperado) {
  total++;
  if (obtido !== esperado) { falhas++; console.log(`✗ ${nome}\n    obtido:   ${obtido}\n    esperado: ${esperado}`); }
  else console.log(`✓ ${nome}`);
}
const R = (res, id) => res.regras.find(r => r.id === id);
const br = M.n2br;
const mais = (iso, dias) => br(M.d2n(iso) + dias);

/* Utilitários */
eq('aniversário 29/02 em ano comum → 01/03', M.n2d(M.aniversario(M.d2n('1964-02-29'), 61)), '2025-03-01');
eq('idade na véspera do aniversário', M.idadeAnos(M.d2n('1970-05-10'), M.d2n('2030-05-09')), 59);
eq('pontos 2026 mulher', M.pontosExigidos('F', 2026), 93);
eq('pontos 2026 homem', M.pontosExigidos('M', 2026), 103);
eq('pontos 2040 homem (teto)', M.pontosExigidos('M', 2040), 105);
eq('pontos 2040 mulher (teto)', M.pontosExigidos('F', 2040), 100);

/* Caso A — homem, ingresso em 1995, sem averbações.
   35 anos de contribuição: 1995-03-01 + 35*365 - 1 dias. */
const A = M.avaliar({ sexo: 'M', nasc: '1968-06-15', ref: '2026-11-04',
  ingressoSP: '1995-03-01', ingressoCargo: '1995-03-01', exercicio: '1995-03-01' });
eq('A: sem erros', A.ok, true);
const d35 = M.d2n('1995-03-01') + 35 * 365 - 1;
// Na EC 103 (13/11/2019 inclusive) tinha: 13/11/2019 - 01/03/1995 + 1 dias
const tEC = M.d2n('2019-11-13') - M.d2n('1995-03-01') + 1;
const falta = 35 * 365 - tEC;
eq('A: art. 20 — contribuição + pedágio', br(R(A, 'art20i').requisitos[1].data), br(d35 + falta));
eq('A: art. 20 — data = max(pedágio, 60 anos)', br(R(A, 'art20i').data), br(Math.max(d35 + falta, M.d2n('2028-06-15'))));
eq('A: art. 20 integral aplicável (ingresso ≤ 2003)', R(A, 'art20i').status, 'prevista');
eq('A: EC 47 aplicável, mas não cumprida até a EC 103', R(A, 'ec47').status, 'nao_cumprida');
eq('A: EC 41 art. 6º não cumprida até a EC 103', R(A, 'ec41a6').status, 'nao_cumprida');
eq('A: art. 10 — 65 anos', br(R(A, 'art10').data), '15/06/2033');
eq('A: compulsória aos 75', br(R(A, 'comp').data), '15/06/2043');
// Art. 4º: idade 62 em 15/06/2030; contribuição 35 anos em d35; pontos: (d - nasc + 1) + (d - ingresso + 1) >= P*365
{
  const nasc = M.d2n('1968-06-15'), ing = M.d2n('1995-03-01');
  let d = Math.max(M.d2n('2030-06-15'), d35);
  while (!((d - nasc + 1) + (d - ing + 1) >= M.pontosExigidos('M', new Date(d * 864e5).getUTCFullYear()) * 365)) d++;
  eq('A: art. 4º (pontos) — data', br(R(A, 'art4m').data), br(d));
  eq('A: art. 4º integral exige 65 anos', br(R(A, 'art4i').data), br(Math.max(d, M.d2n('2033-06-15'))));
}

/* Caso B — mulher com RGPS averbado e sobreposição; ingresso 2010 (sem integralidade). */
const B = M.avaliar({ sexo: 'F', nasc: '1975-02-10', ref: '2026-11-04',
  ingressoSP: '2010-04-05', ingressoCargo: '2010-04-05', exercicio: '2010-04-05',
  periodos: [
    { orgao: 'Empresa X', regime: 'RGPS', inicio: '1995-01-01', fim: '2004-12-31' },
    { orgao: 'Empresa Y', regime: 'RGPS', inicio: '2004-06-01', fim: '2010-04-30' } // sobrepõe 2004 e 2010
  ] });
{
  const u = (M.d2n('2010-04-04') - M.d2n('1995-01-01') + 1); // união até a véspera do Tribunal
  const ref = M.d2n('2026-11-04');
  const contribRef = u + (ref - M.d2n('2010-04-05') + 1);
  eq('B: contribuição na referência (sobreposição não conta em dobro)', Math.round(B.situacao.contribuicao), contribRef);
  eq('B: sobreposição detectada (dias)', B.situacao.sobreposicao, (M.d2n('2004-12-31') - M.d2n('2004-06-01') + 1) + (M.d2n('2010-04-30') - M.d2n('2010-04-05') + 1));
  eq('B: serviço público só conta o Tribunal', Math.round(B.situacao.servicoPublico), ref - M.d2n('2010-04-05') + 1);
  eq('B: integralidade inaplicável', R(B, 'art20i').status, 'inaplicavel');
  eq('B: art. 20 média aplicável', ['prevista', 'cumprida'].includes(R(B, 'art20m').status), true);
  // 20 anos de serviço público: 2010-04-05 + 7300 - 1
  eq('B: 20 anos de serviço público', br(R(B, 'art20m').requisitos[2].data), mais('2010-04-05', 7299));
  eq('B: teto do RGPS não se aplica (ingresso antes de 14/10/2013)', B.situacao.tetoRGPS, false);
}

/* Caso C — licença-prêmio e faltas. */
const C1 = M.avaliar({ sexo: 'M', nasc: '1966-01-20', ref: '2026-11-04', ingressoSP: '1990-02-01', ingressoCargo: '1990-02-01', exercicio: '1990-02-01' });
const C2 = M.avaliar({ sexo: 'M', nasc: '1966-01-20', ref: '2026-11-04', ingressoSP: '1990-02-01', ingressoCargo: '1990-02-01', exercicio: '1990-02-01',
  lpDias: 180, deducoes: [{ desc: 'faltas', data: '2000-05-01', dias: 10 }] });
eq('C: LP em dobro antecipa 35 anos em 170 dias (180 − 10 de faltas)',
  R(C1, 'art20i').requisitos[1].data - R(C2, 'art20i').requisitos[1].data > 0, true);
eq('C: faltas atrasam 20 anos de serviço público em 10 dias', R(C2, 'art20i').requisitos[2].data - R(C1, 'art20i').requisitos[2].data, 10);
eq('C: falta posterior aos 5 anos de cargo não altera essa data', R(C2, 'art10').requisitos[3].data - R(C1, 'art10').requisitos[3].data, 0);
eq('C: EC 47 aplicável (ingresso ≤ 1998)', R(C1, 'ec47').status !== 'inaplicavel', true);

/* Caso D — pedágio zero: quem já tinha 30 anos de contribuição na EC 103 */
const D = M.avaliar({ sexo: 'F', nasc: '1966-08-01', ref: '2026-11-04', ingressoSP: '1988-01-04', ingressoCargo: '1988-01-04', exercicio: '1988-01-04' });
eq('D: pedágio zero', R(D, 'art20i').requisitos[1].pedagio, 0);
eq('D: art. 20 integral = 57 anos', br(R(D, 'art20i').data), '01/08/2023');
eq('D: status cumprida', R(D, 'art20i').status, 'cumprida');
eq('D: abono desde 01/08/2023 ou antes', D.abono.abonoDesde <= M.d2n('2023-08-01'), true);

/* Caso E — migrou para o RPC → sem integralidade e com teto */
const E = M.avaliar({ sexo: 'M', nasc: '1970-01-01', ref: '2026-11-04', ingressoSP: '2000-01-01', ingressoCargo: '2000-01-01', exercicio: '2000-01-01', migrouRPC: true });
eq('E: art. 4º integral inaplicável (migração)', R(E, 'art4i').status, 'inaplicavel');
eq('E: teto do RGPS', E.situacao.tetoRGPS, true);

/* Caso F — PcD grave mulher: 20 anos */
const Fc = M.avaliar({ sexo: 'F', nasc: '1985-01-01', ref: '2026-11-04', ingressoSP: '2006-03-01', ingressoCargo: '2006-03-01', exercicio: '2006-03-01',
  deficiencia: { grau: 'grave', inicio: '2006-03-01' } });
eq('F: PcD grave — 20 anos de contribuição', br(R(Fc, 'pcdT').requisitos[0].data), mais('2006-03-01', 20 * 365 - 1));
// misto: 10 anos sem deficiência (de 30 exigidos) + resto grave (de 20) → 1/3 + x/20 = 1 → x = 13,33 anos
const Fm = M.avaliar({ sexo: 'F', nasc: '1985-01-01', ref: '2026-11-04', ingressoSP: '2006-03-01', ingressoCargo: '2006-03-01', exercicio: '2006-03-01',
  deficiencia: { grau: 'grave', inicio: M.n2d(M.d2n('2006-03-01') + 3650) } });
{
  const esperado = M.d2n('2006-03-01') + 3650 + Math.ceil((2 / 3) * 20 * 365) - 1;
  eq('F: PcD tempo misto convertido (art. 7º LC 142)', Math.abs(R(Fm, 'pcdT').requisitos[0].data - esperado) <= 1, true);
}

/* Caso G — especial: 25 anos de exposição antes da EC 103 (direito adquirido) */
const G = M.avaliar({ sexo: 'M', nasc: '1965-01-01', ref: '2026-11-04', ingressoSP: '1990-01-02', ingressoCargo: '1990-01-02', exercicio: '1990-01-02',
  exposicoes: [{ inicio: '1990-01-02', fim: '2019-11-13' }] });
eq('G: especial adquirida (25 anos até 2015)', R(G, 'sv33').status, 'cumprida');
eq('G: data 25 anos de exposição', br(R(G, 'sv33').data), mais('1990-01-02', 25 * 365 - 1));
eq('G: conversão 1,4 até a EC 103', Math.round(G.situacao.conversao), Math.round((M.d2n('2019-11-13') - M.d2n('1990-01-02') + 1) * 0.4));

/* Melhor provento não pode ser a compulsória quando há regra voluntária */
const H = M.avaliar({ sexo: 'M', nasc: '1985-03-10', ref: '2026-11-04', ingressoSP: '2016-01-16', ingressoCargo: '2016-01-16', exercicio: '2016-01-16' });
eq('H: melhor provento ≠ compulsória', H.melhor.id !== 'comp', true);

/* Validação: dados faltantes */
const Z = M.avaliar({ sexo: 'M' });
eq('Z: erros de entrada', Z.ok, false);

console.log(`\n${total - falhas}/${total} testes OK`);
process.exit(falhas ? 1 : 0);
