(function(){
'use strict';
const $ = id => document.getElementById(id);
const E = window.RBCEsperada, RR = window.RBCRelatorios;
const fmt = new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2});
const f2 = v => (v===null||v===undefined||v==='') ? '' : fmt.format(v);
const rs = v => 'R$ '+f2(v);
const esc = s => String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const MESES=['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
const mesTxt = k => MESES[+k.slice(5,7)-1]+'/'+k.slice(0,4);
const dataBr = d => d ? d.split('-').reverse().join('/') : '';
const ultimoDia = k => k+'-'+String(new Date(+k.slice(0,4),+k.slice(5,7),0).getDate()).padStart(2,'0');
if (window.pdfjsLib) pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

const TIPOS_REL = ['PROGRESSAO','FUNCOES','SUBSTITUICOES','VPNI','ATS','V1323'];   // AQ e AQ-Treinamento: sem relatório, conferidos pela ficha
const S = { devol:[], arquivos:[], recs:[], refs:{}, basePSO:{}, fichaInfo:{}, cats:{}, manual:[], res:null, etapa:1, abertos:{}, sel:null,
  rel:Object.fromEntries(TIPOS_REL.map(t=>[t,[]])), relArqs:[], esp:null, espBy:{}, cmp:null, ignorar:{}, ack:{} };
const REGRA_IDS = ['vpniTabela','fcTabela','tabelaAte','divisor30Desde','fcAte','atsDesde','conferirDesde','ajuste1198Desde','ajuste1198Ate','gnDesde','gnSemVPIAte','divisorDiasDesde','gas','aqTrein','descontarFaltas','teto','tetoDesde','tetoAuto','semFichaTabela','gasAte','vpiTabela','gnFicha'];
const NOME = { SUBSIDIO:'Subsídio (magistrado)', FC_PREV:'Função com opção de contribuição', VB:'Vencimento', DIF2886:'Diferença Leis 8.622/8.627', GEXTRA:'Gratificação extraordinária', GAJ:'GAJ', APJ:'Adicional padrão judiciário', REDUTOR:'Redutor', ATS:'Adicional por tempo de serviço', VPI:'VPI', VPI_DED:'Dedução de VPI', VPNI:'VPNI (quintos/décimos)', VPNI_JUD:'VPNI judicial', VPNI_JUD_SEM_PSS:'VPNI judicial (sem contribuição)', FC:'Função comissionada', SUBST:'Substituição', V1323_VB:'13,23% s/ vencimento', V1323_GAJ:'13,23% s/ GAJ', V1323_ATS:'13,23% s/ ATS', V1323_VPNI:'13,23% s/ VPNI', V1323_FC:'13,23% s/ função', AQ:'Adicional de qualificação', AQ_TREIN:'AQ-Treinamento', GAE:'GAE', GAS:'GAS', FALTAS:'Faltas', V1198:'11,98%', PSS:'Contribuição previdenciária (PSS)', GN:'Gratificação natalina (13º)', PASSIVO:'Passivo / exercício anterior', IGNORAR:'Não entra na RBC', CLASSIFICAR:'Não reconhecida' };
const CURTO = { SUBSIDIO:'Subsídio', FC_PREV:'Função c/ PSS', VB:'Venc.', DIF2886:'Dif. 8622', GEXTRA:'Grat. extr.', GAJ:'GAJ', APJ:'APJ', REDUTOR:'Redutor', ATS:'ATS', VPI:'VPI', VPI_DED:'Ded. VPI', VPNI:'VPNI', VPNI_JUD:'VPNI jud.', FC:'Função', SUBST:'Subst.', V1323_VB:'13,23% VB', V1323_GAJ:'13,23% GAJ', V1323_ATS:'13,23% ATS', V1323_VPNI:'13,23% VPNI', V1323_FC:'13,23% FC', AQ:'AQ', AQ_TREIN:'AQ-Trein.', GAE:'GAE', GAS:'GAS', FALTAS:'Faltas', V1198:'11,98%' };
const nome = c => NOME[c] || RBC.CAT[c] || c;

// ------------------------------------------------------------ regras
function setRegras(r){ for (const k of REGRA_IDS){ const el=$('r_'+k); if(el.type==='checkbox') el.checked=!!r[k]; else if(k==='aqTrein') el.value = r[k]==='ficha'?'ficha':r[k]?'sim':'nao'; else el.value = r[k]==null?'':r[k]; } }
function getRegras(){
  const r={}; for (const k of REGRA_IDS){ const el=$('r_'+k); r[k] = el.type==='checkbox' ? el.checked : (el.value||''); }
  r.aqTrein = r.aqTrein==='sim' ? true : r.aqTrein==='nao' ? false : 'ficha';
  for (const k of ['ajuste1198Ate','gnDesde','gnSemVPIAte']) if(!r[k]) r[k]=null;
  if(!r.gasAte) r.gasAte='';
  if(!r.ajuste1198Desde) r.ajuste1198Desde=RBC.REGRAS_PADRAO.ajuste1198Desde;
  if(!r.divisorDiasDesde) r.divisorDiasDesde=RBC.REGRAS_PADRAO.divisorDiasDesde;
  if(!r.divisor30Desde) r.divisor30Desde=RBC.REGRAS_PADRAO.divisor30Desde;
  if(!r.tabelaAte) r.tabelaAte=null;
  r.tetoDesde = r.tetoDesde || (r.tetoAuto && S.tetoAuto && S.tetoAuto.desde ? S.tetoAuto.desde : '');
  return r;
}
function regrasAlteradas(){ const a=Object.assign(getRegras(),{tetoDesde:$('r_tetoDesde').value||''}), p=RBC.REGRAS_PADRAO; return REGRA_IDS.filter(k=>String(a[k]==null?'':a[k])!==String(p[k]==null?'':p[k])); }
setRegras(RBC.REGRAS_PADRAO);
$('r_reset').onclick=e=>{ e.preventDefault(); setRegras(RBC.REGRAS_PADRAO); calc(); };
for (const k of REGRA_IDS) $('r_'+k).addEventListener('change', calc);
for (const id of ['inicio','fim','cargo','espDesde']) $(id).addEventListener('change', calc);
$('especialidade').addEventListener('change',()=>{ calc(); });

// período efetivo: a RBC cobre todo o período de contribuição; desligamento em branco = último mês da ficha
function iniEf(){ let v=$('inicio').value; if(!v && S.recs.length) v=S.recs.map(r=>r.comp).sort()[0]+'-01'; return v; }
// moeda de cada competência: a RBC usa a moeda da época, sem conversão; a média da aposentadoria só usa de 07/1994 em diante
// 03–06/1994: valores em URV, rotulados CR$ como no modelo da DIPROF (a moeda corrente era o cruzeiro real)
function moedaDe(k){ return k<'1986-03'?'Cr$':k<'1989-02'?'Cz$':k<'1990-04'?'NCz$':k<'1993-08'?'Cr$':k<'1994-07'?'CR$':'R$'; }
const naMedia = k => k>='1994-07';
function fimEf(){ let v=$('fim').value; if(!v && S.recs.length){ const c=S.recs.map(r=>r.comp).sort(); v=ultimoDia(c[c.length-1]); } return v; }

// ------------------------------------------------------------ PDFs
async function pdfDoc(buf){
  const doc=await pdfjsLib.getDocument({data:new Uint8Array(buf)}).promise; const pages=[];
  for(let n=1;n<=doc.numPages;n++){
    const p=await doc.getPage(n); const vp=p.getViewport({scale:1}); const tc=await p.getTextContent();
    pages.push({items:tc.items.map(it=>{const t=pdfjsLib.Util.transform(vp.transform,it.transform);return {str:it.str,x:t[4],y:t[5],w:it.width};})});
  }
  return {doc,pages};
}
function ligarDrop(dropId,fileId,fn){
  const d=$(dropId), f=$(fileId);
  d.onclick=()=>f.click();
  d.onkeydown=e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); f.click(); } };
  d.ondragover=e=>{e.preventDefault();d.classList.add('over');};
  d.ondragleave=()=>d.classList.remove('over');
  d.ondrop=e=>{e.preventDefault();d.classList.remove('over');fn(e.dataTransfer.files);};
  f.onchange=e=>{ fn(e.target.files); e.target.value=''; };
}
ligarDrop('drop','file',lerArquivos);
ligarDrop('dropRel','fileRel',lerRelatorios);

// ------------------------------------------------------------ etapa 1: relatórios do RH
const OPC = {
  tipoVPNI:[['DECIMOS','Décimos'],['QUINTOS','Quintos']],
  natureza:[['ADMINISTRATIVA','Administrativa'],['JUDICIAL','Judicial']],
  tipoAQ:[['ESPECIALIZACAO','Especialização'],['MESTRADO','Mestrado'],['DOUTORADO','Doutorado'],['TREINAMENTO','Treinamento (120 h)'],['GRADUACAO_TECNICO','Graduação (técnico)']]
};
const cIni=['ini','date','Início'], cFim=['fim','date','Fim'], cCod=['cod','text','Código'];
const REL = {
  PROGRESSAO:{titulo:'Progressão e enquadramento', cols:[cIni,cFim,['classe','text','Classe'],['padrao','text','Padrão'],['revogada','chk','Revogada']], novo:{origem:'manual'},
    dica:'Cada linha é um período em uma classe e padrão. Linhas revogadas não entram no cálculo.'},
  FUNCOES:{titulo:'Funções comissionadas', cols:[cIni,cFim,['cod','text','Código (ex.: FC-03)'],['nome','text','Função']]},
  SUBSTITUICOES:{titulo:'Substituições', cols:[cIni,cFim,['cod','text','Função substituída (ex.: FC-05)']]},
  VPNI:{titulo:'VPNI (quintos e décimos)', cols:[cIni,cFim,cCod,['tipo','sel','Tipo',OPC.tipoVPNI],['natureza','sel','Natureza',OPC.natureza]], novo:{tipo:'DECIMOS',natureza:'ADMINISTRATIVA'},
    dica:'Uma linha por parcela incorporada, a partir da data em que passou a ser paga.'},
  ATS:{titulo:'Adicional por tempo de serviço', cols:[['ini','date','A partir de'],['pct','num','Percentual acumulado (%)']]},
  AQ:{titulo:'Adicional de qualificação', cols:[cIni,cFim,['tipo','sel','Título',OPC.tipoAQ],['pct','num','% (se diferente da lei)']], novo:{tipo:'ESPECIALIZACAO'},
    dica:'Opcional. Sem relatório, vale a ficha: se houve AQ pago no mês, o direito é presumido e o valor devido é calculado pela tabela (até 2025, % do vencimento da Lei 11.416; desde 2026, valores de referência). O nível é deduzido do valor pago. Linhas preenchidas aqui têm prioridade sobre a ficha.'},
  V1323:{titulo:'13,23% (decisão judicial)', cols:[cIni,cFim], dica:'Períodos em que o 13,23% foi devido. Não vem de relatório: informe se houver.'}
};
const ORIGEM = { ficha:['ok','confere com o vencimento pago'], relatorio:['ok','do relatório'], relatorioOk:['ok','do relatório; confere com o vencimento pago'], corrigido:['att','ajustado pelo vencimento pago — confira'], leitura:['info','lido da imagem — confira'], incerta:['att','incerto — confira'], manual:['info','informado por você'] };
function tagOrigem(r){ const o=ORIGEM[r.origem]; return o?`<span class="tag ${o[0]}"${r.dica?` title="Texto lido: ${esc(r.dica)}"`:''}>${o[1]}${r.origem==='corrigido'&&r.relOrig?' (relatório: '+esc(r.relOrig)+')':''}</span>`:''; }

function celula(t,i,c,r){
  const [k,tp,lab,opc]=c, v=r[k], a=`data-t="${t}" data-i="${i}" data-c="${k}" aria-label="${esc(lab)}, linha ${i+1}"`;
  if(tp==='date') return `<input type="date" ${a} value="${esc(v||'')}">`;
  if(tp==='num') return `<input type="number" step="0.01" ${a} value="${v==null?'':esc(v)}">`;
  if(tp==='chk') return `<input type="checkbox" ${a}${v?' checked':''}>`;
  if(tp==='sel') return `<select ${a}>${opc.map(([x,l])=>`<option value="${x}"${x===v?' selected':''}>${esc(l)}</option>`).join('')}</select>`;
  return `<input type="text" ${a} value="${esc(v||'')}" autocomplete="off">`;
}
function renderRelTabelas(){
  const el=$('relTabelas'); const foco=document.activeElement&&el.contains(document.activeElement)?document.activeElement.dataset:null;
  el.innerHTML=TIPOS_REL.map(t=>{
    const R=REL[t], rows=S.rel[t], arq=S.relArqs.find(a=>a.tipo===t&&!a.erro);
    const nInc=t==='PROGRESSAO'?rows.filter(r=>r.origem==='incerta'&&!r.revogada).length:0;
    const aberto = rows.length && (t==='PROGRESSAO' || S.abertos['rel'+t]);
    return `<details class="relbox" data-rel="${t}"${aberto||S.abertos['rel'+t]?' open':''}><summary>${esc(R.titulo)} <span class="muted small" style="font-weight:400">${rows.length?rows.length+' linha(s)':'vazio'}${arq?' · '+esc(arq.nome):''}</span>${nInc?` <span class="tag att">${nInc} a conferir</span>`:''}</summary>
      ${R.dica?`<p class="muted small" style="margin:6px 0 8px">${esc(R.dica)}</p>`:''}
      ${t==='PROGRESSAO'&&rows.some(r=>r.ocr)&&!S.res?'<div class="aviso info" style="margin:0 0 10px"><span class="ic">i</span><div>A progressão veio como imagem. A classe e o padrão serão conferidos com o vencimento pago assim que você enviar a ficha (etapa 2).</div></div>':''}
      ${rows.length?`<div class="tw" style="max-height:none"><table class="ed"><thead><tr>${R.cols.map(c=>`<th class="l">${esc(c[2])}</th>`).join('')}${t==='PROGRESSAO'?'<th class="l">Conferência</th>':''}<th></th></tr></thead><tbody>${rows.map((r,i)=>`<tr>${R.cols.map(c=>`<td>${celula(t,i,c,r)}</td>`).join('')}${t==='PROGRESSAO'?`<td data-tag="${i}">${tagOrigem(r)}</td>`:''}<td><button class="btn link" data-rm-rel="${t}|${i}" aria-label="Remover linha ${i+1}">Remover</button></td></tr>`).join('')}</tbody></table></div>`:''}
      <button class="btn sec peq" data-add-rel="${t}" style="margin-top:10px">Adicionar linha</button>
    </details>`; }).join('');
  if(foco&&foco.t){ const x=el.querySelector(`[data-t="${foco.t}"][data-i="${foco.i}"][data-c="${foco.c}"]`); if(x) x.focus(); }
}
$('relTabelas').addEventListener('toggle',e=>{ const d=e.target; if(d.dataset&&d.dataset.rel) S.abertos['rel'+d.dataset.rel]=d.open; },true);
$('relTabelas').addEventListener('change',e=>{
  const x=e.target, d=x.dataset; if(!d.t) return;
  const r=S.rel[d.t][+d.i]; if(!r) return;
  let v = x.type==='checkbox'?x.checked : x.type==='number'?(x.value===''?null:parseFloat(x.value.replace(',','.'))) : x.value;
  if(x.type==='text' && d.c!=='nome') v=v.trim().toUpperCase();
  r[d.c]=v;
  if(d.t==='PROGRESSAO' && (d.c==='classe'||d.c==='padrao')){ r.origem='manual'; const td=document.querySelector(`[data-tag="${d.i}"]`); if(td) td.innerHTML=tagOrigem(r); }
  calc();
});
$('relTabelas').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b) return;
  if(b.dataset.addRel){ const t=b.dataset.addRel; S.rel[t].push(Object.assign({ini:'',fim:''},REL[t].novo||{})); S.abertos['rel'+t]=true; renderRelTabelas(); const l=document.querySelectorAll(`[data-t="${t}"][data-c="ini"]`); if(l.length) l[l.length-1].focus(); calc(); }
  if(b.dataset.rmRel){ const [t,i]=b.dataset.rmRel.split('|'); S.rel[t].splice(+i,1); renderRelTabelas(); calc(); }
});
function renderArqRel(){
  const TIT={PROGRESSAO:'progressão',FUNCOES:'funções',SUBSTITUICOES:'substituições',VPNI:'VPNI',ATS:'ATS',AQ:'adicional de qualificação'};
  $('filesRel').innerHTML=S.relArqs.map(a=>`<li><span class="sit ${a.erro?'att':a.st==='ok'?'ok':'none'}">${esc(a.nome)}</span><span class="q">${a.erro?esc(a.erro):a.st!=='ok'?esc(a.msg||'Lendo…'):`${TIT[a.tipo]||a.tipo}: ${a.n} linha(s)${a.ocr?' (lida da imagem)':''}${a.msgFim?' — '+esc(a.msgFim):''}`}</span></li>`).join('');
}
const TESS='https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/';
function carregarScript(src){ return new Promise((ok,err)=>{ const s=document.createElement('script'); s.src=src; s.onload=ok; s.onerror=()=>err(new Error('não foi possível carregar o leitor de imagem; verifique a conexão')); document.head.appendChild(s); }); }
async function ocrProgressao(doc,msg){
  if(!window.Tesseract){ msg('Carregando o leitor de imagem…'); await carregarScript(TESS+'tesseract.min.js'); }
  msg('Preparando o leitor de imagem…');
  const w=await Tesseract.createWorker('por',1,{workerPath:TESS+'worker.min.js',corePath:'https://cdn.jsdelivr.net/npm/tesseract.js-core@5.1.1',langPath:'https://cdn.jsdelivr.net/npm/@tesseract.js-data/por@1.0.0/4.0.0_best_int'});
  const listas=[];
  try{
    for(let n=1;n<=doc.numPages;n++){
      const pg=await doc.getPage(n);
      // duas resoluções: cada leitura pode perder uma linha que a outra pega
      for(const [j,dpi] of [[1,300],[2,200]]){
        msg(`Lendo a imagem (página ${n} de ${doc.numPages}, leitura ${j} de 2)…`);
        const vp=pg.getViewport({scale:dpi/72}); const cv=document.createElement('canvas'); cv.width=Math.ceil(vp.width); cv.height=Math.ceil(vp.height);
        const ctx=cv.getContext('2d'); ctx.fillStyle='#fff'; ctx.fillRect(0,0,cv.width,cv.height);
        await pg.render({canvasContext:ctx,viewport:vp}).promise;
        const {data}=await w.recognize(cv); listas.push(RR.parseProgressaoTexto(data.text)); if(j===1) (ocrProgressao.textos=ocrProgressao.textos||[]).push(data.text);
      }
    }
  } finally { await w.terminate(); }
  return RR.juntarProgressoes(listas);
}
// CTC / declaração de tempo de contribuição: preenche os dados do servidor e as tabelas (progressão, funções, anuênios,
// quintos) que ainda não vieram de relatório do RH. Relatório do RH, quando enviado, prevalece.
function aplicarCTC(r,info,ocr){
  const m=r.meta||{}, pre=[];
  if(m.cargo&&m.cargo!=='JUIZ'&&!$('cargo').value){ $('cargo').value=m.cargo; pre.push('cargo'); }
  if(m.especialidade&&!$('especialidade').value){ $('especialidade').value=m.especialidade; $('espDesde').disabled=false; pre.push('especialidade'); }
  if(m.inicio&&!$('inicio').value){ $('inicio').value=m.inicio; pre.push('início do período'); }
  if(m.fim&&!$('fim').value){ $('fim').value=m.fim; pre.push('fim do período'); }
  S.ctc=m;
  const usados=[];
  const por={PROGRESSAO:r.PROGRESSAO, FUNCOES:r.FUNCOES, ATS:r.ATS, VPNI:[].concat(...(r.VPNI||[]).map(v=>Array.from({length:v.parcelas||1},()=>({cod:v.cod,tipo:v.tipo,natureza:v.natureza,ini:v.ini,fim:v.fim||''}))))};
  for(const [t,rows] of Object.entries(por)){
    if(!rows||!rows.length) continue;
    const doRH=S.relArqs.some(a=>a.tipo===t&&a!==info);
    if(doRH) continue;
    S.rel[t]=rows.map(o=>Object.assign({},o,{fim:o.fim||'',fonte:'CTC'},t==='PROGRESSAO'?{origem:ocr?'incerta':'relatorio'}:{})); usados.push(t);
  }
  info.tipo='CTC'; info.n=usados.reduce((a,t)=>a+S.rel[t].length,0);
  const nomes={PROGRESSAO:'progressão',FUNCOES:'funções',ATS:'anuênios',VPNI:'quintos/décimos'};
  const tt=m.teto==='sim'?'contribuição limitada ao teto do RGPS':m.teto==='migrou'?'migrou para a previdência complementar'+(m.tetoDesde?' em '+m.tetoDesde.split('-').reverse().join('/'):''):m.teto==='nao'?'sem limitação ao teto':'';
  info.msgFim=[usados.length?'tabelas: '+usados.map(t=>nomes[t]).join(', '):'nenhuma tabela legível', pre.length?'preenchido: '+pre.join(', '):'', tt, ocr?'lida por imagem — confira':''].filter(Boolean).join(' · ');
  if(r.frequencia&&r.frequencia.some(f=>f.faltas>0)) info.msgFim+=' · faltas na CTC: '+r.frequencia.filter(f=>f.faltas>0).map(f=>f.ano+' ('+f.faltas+')').join(', ');
  info.st='ok'; renderArqRel();
}
async function lerRelatorios(list){
  const fila=[...list]; if(!fila.length) return;
  for(const f of fila){
    const info={nome:f.name,tipo:null,n:0,erro:'',st:'lendo',msg:'Lendo…'}; S.relArqs.push(info); renderArqRel();
    try{
      let tipo, rows;
      if(/\.(csv|txt|xlsx?|ods)$/i.test(f.name)){
        // planilha ou CSV exportado do sistema de RH: colunas reconhecidas pelo cabeçalho
        const buf=await f.arrayBuffer(); let m2;
        if(/\.(csv|txt)$/i.test(f.name)){ let t=new TextDecoder('utf-8').decode(buf); if(t.includes('\uFFFD')) t=new TextDecoder('windows-1252').decode(buf); m2=RR.lerCSV(t); }
        else { const wb=XLSX.read(buf,{type:'array',cellDates:false}); m2=[]; for(const n of wb.SheetNames){ m2=m2.concat(XLSX.utils.sheet_to_json(wb.Sheets[n],{header:1,raw:false,dateNF:'dd/mm/yyyy',defval:''})); } }
        const r=RR.tabelaRelatorio(m2,f.name); tipo=r.tipo;
        if(!tipo) throw new Error('Planilha não reconhecida: confira se a primeira linha tem os nomes das colunas (ex.: Dt. Mudança, Data Fim, Classe, Padrão).');
        rows=r.rows.map(o=>Object.assign({},o,{fim:o.fim||''},tipo==='PROGRESSAO'?{origem:'relatorio'}:{}));
      } else {
      if(!/\.pdf$/i.test(f.name)) throw new Error('Formato não aceito. Envie PDF, CSV, XLS ou XLSX.');
      const {doc,pages}=await pdfDoc(await f.arrayBuffer());
      const chars=pages.reduce((s,p)=>s+p.items.reduce((a,i)=>a+i.str.trim().length,0),0);
      if(chars<30){
        tipo='PROGRESSAO'; info.ocr=true; ocrProgressao.textos=[];
        rows=(await ocrProgressao(doc,m=>{info.msg=m;renderArqRel();})).map(r=>({ini:r.ini,fim:r.fim||'',classe:'',padrao:'',revogada:r.revogada,dica:r.dica,origem:'incerta',ocr:true}));
        const txt=(ocrProgressao.textos||[]).join('\n');
        // CTC digitalizada: lida pelo mesmo reconhecimento de texto; o que vier é conferido pela ficha e pelo usuário
        if(/TEMPO\s+DE\s+(CONTRIBUI|SERVI)/i.test(txt) && !/RELA..O\s+DAS\s+BASES/i.test(txt)){ aplicarCTC(RR.parseCTC(txt),info,true); continue; }
      } else {
        tipo=RR.tipoRelatorio(pages);
        if(tipo==='CTC'){ aplicarCTC(RR.parseCTC(pages),info,false); continue; }
        if(!tipo) throw new Error('Documento não reconhecido. Os aceitos são: CTC ou declaração de tempo de contribuição, progressão, funções, substituições, VPNI e ATS.');
        if(tipo==='AQ') throw new Error('Não há relatório de AQ: o AQ e o AQ-Treinamento são conferidos pela ficha.');
        if(tipo==='PROGRESSAO'){ // preenche os dados do servidor que estiverem em branco
          const d=RR.dadosServidor(pages), pre=[];
          if(d.nome&&!$('nome').value){ $('nome').value=d.nome; pre.push('nome'); }
          if(d.cargo&&!$('cargo').value){ $('cargo').value=d.cargo; pre.push('cargo'); }
          if(d.especialidade!==undefined&&!$('especialidade').value&&d.especialidade){ $('especialidade').value=d.especialidade; pre.push('especialidade'); }
          if(d.exercicio&&!$('inicio').value){ $('inicio').value=d.exercicio; pre.push('ingresso (data de exercício)'); }
          if(pre.length) info.msgFim='preenchido a partir do relatório: '+pre.join(', ')+' — confira';
        }
        const fn={FUNCOES:RR.parseFuncoes,SUBSTITUICOES:RR.parseFuncoes,VPNI:RR.parseVPNI,ATS:RR.parseATS,PROGRESSAO:RR.parseProgressao}[tipo];
        rows=fn(pages).map(r=>{ const o=Object.assign({},r); delete o.perda; delete o.concedido; if(!o.fim) o.fim=''; if(tipo==='PROGRESSAO') o.origem='relatorio'; if(tipo==='SUBSTITUICOES') delete o.nome; return o; });
      }
      }
      S.relArqs=S.relArqs.filter(a=>a===info||a.tipo!==tipo);
      info.tipo=tipo; info.n=rows.length; S.rel[tipo]=rows;
      if(!rows.length) info.erro='Nenhuma linha encontrada. Preencha a tabela abaixo ou envie o mesmo relatório em CSV/XLSX.';
      if(tipo==='SUBSTITUICOES') info.msgFim='formato ainda não testado: confira as linhas';
    }catch(e){ console.error(e); info.erro=e.message||String(e); }
    info.st='ok'; renderArqRel();
  }
  renderRelTabelas(); calc();
}
// classe/padrão lidos da imagem: confirmados pelo vencimento pago na ficha
function vbFichaPara(ini,fim){
  if(!S.res) return null;
  const k=ini.slice(8,10)==='01'?ini.slice(0,7):RBC.addM(ini.slice(0,7),1);
  const kf=fim?(fim===ultimoDia(fim.slice(0,7))?fim.slice(0,7):RBC.addM(fim.slice(0,7),-1)):'9999-12';
  // prefere um mês já em real (fichas antigas podem trazer valores anteriores a 07/1994 convertidos)
  const ok=S.res.linhas.filter(l=>l.comp>=k&&l.comp<=kf&&l.fonte&&l.bruto&&l.bruto.VB>0);
  const l=ok.find(x=>x.comp>='1994-07'&&x.comp<=RBC.addM(k>'1994-07'?k:'1994-07',3))||ok.find(x=>x.comp<=RBC.addM(k,3));
  return l?{k:l.comp,vb:l.bruto.VB}:null;
}
function aplicarSugestoes(){
  const cargo=$('cargo').value; if(!cargo) return false; let mud=false;
  const nrm=x=>String(x||'').toUpperCase().replace(/\s|-/g,'').replace(/^N[ISA](?=[A-D])/,'');
  const npd=x=>{ x=String(x||'').trim().toUpperCase(); return /^\d+$/.test(x)?String(+x):x; };
  for(const r of S.rel.PROGRESSAO){
    // linha de relatório em texto: confere com o vencimento pago; se a ficha indicar outra referência, ajusta e avisa
    if(!r.ocr&&(r.origem==='relatorio'||r.origem==='relatorioOk'||r.origem==='corrigido')&&r.ini&&!r.revogada){
      const ref=vbFichaPara(r.ini,r.fim); if(!ref) continue;
      const d=ref.k+'-01'>r.ini?ref.k+'-01':r.ini;
      const sg=E.sugerirRef(BASE,cargo,d,'',ref.vb);
      const orig=r.relOrig?r.relOrig.split(' '):[r.classe,r.padrao];
      if(!sg||sg.origem!=='ficha') continue;
      const igual=nrm(sg.classe)===nrm(orig[0])&&npd(sg.padrao)===npd(orig[1]);
      const n=igual?{classe:orig[0],padrao:orig[1],origem:'relatorioOk',relOrig:undefined}:{classe:sg.classe,padrao:sg.padrao,origem:'corrigido',relOrig:orig.join(' ')};
      if(n.classe!==r.classe||n.padrao!==r.padrao||n.origem!==r.origem){ Object.assign(r,n); if(!n.relOrig) delete r.relOrig; mud=true; }
      continue;
    }
    if(!r.ocr||r.origem==='manual'||!r.ini) continue;
    const ref=vbFichaPara(r.ini,r.fim);
    const d=ref?(ref.k+'-01'>r.ini?ref.k+'-01':r.ini):r.ini;
    const s=E.sugerirRef(BASE,cargo,d,r.dica,ref&&ref.vb);
    const n=s?{classe:s.classe,padrao:s.padrao,origem:s.origem}:{classe:'',padrao:'',origem:'incerta'};
    if(n.classe!==r.classe||n.padrao!==r.padrao||n.origem!==r.origem){ Object.assign(r,n); mud=true; }
  }
  return mud;
}
function dadosServidor(){
  const cargo=$('cargo').value, ini=iniEf(), fim=fimEf();
  if(!cargo||!ini||!fim||ini>fim) return null;
  const ord=l=>l.slice().sort((a,b)=>a.ini<b.ini?-1:a.ini>b.ini?1:0);
  let prog=ord(S.rel.PROGRESSAO.filter(p=>p.ini&&p.classe&&p.padrao));
  // sem relatório de progressão (caso comum: a DIPROF trabalha com a ficha e a CTC), a classe/padrão vem do vencimento pago
  if(!prog.length) prog=progDaFicha(cargo,ini,fim);
  else if(prog[0].ini>ini){
    // relatório/CTC começa depois do ingresso (ex.: CTC sem as referências anteriores a 1992): o início vem da ficha
    const p0=prog[0].ini, vesp=new Date(Date.UTC(+p0.slice(0,4),+p0.slice(5,7)-1,+p0.slice(8,10)-1)).toISOString().slice(0,10);
    const antes=progDaFicha(cargo,ini,fim).filter(p=>p.ini<p0).map(p=>Object.assign({},p,{fim:(!p.fim||p.fim>=p0)?vesp:p.fim}));
    prog=antes.concat(prog);
  }
  if(!prog.length) return null;
  const per=l=>ord(l.filter(r=>r.ini)).map(r=>Object.assign({},r,{fim:r.fim||null}));
  const atsRel=per(S.rel.ATS).filter(r=>r.pct!=null);
  return { cargo, especialidade:$('especialidade').value, espDesde:$('especialidade').value&&$('espDesde').value||null, inicio:ini, fim,
    progressoes:prog.map(p=>({ini:p.ini,fim:p.fim||null,classe:p.classe,padrao:p.padrao,revogada:!!p.revogada})),
    funcoes:per(S.rel.FUNCOES).filter(r=>r.cod), substituicoes:per(S.rel.SUBSTITUICOES).filter(r=>r.cod),
    vpni:per(S.rel.VPNI).filter(r=>r.cod), ats:atsRel.length?atsRel:atsDaFicha(), aq:[], v1323:per(S.rel.V1323), aqFicha:aqDaFicha() };
}
// Progressão inferida da ficha: classe/padrão de cada mês pelo vencimento pago (mês cheio, folha normal). Meses sem ficha:
// carreira da Lei 11.416/2006 (A1–A5, B6–B10, C11–C13) avança um padrão a cada 12 meses a partir da última mudança vista
// e recua da mesma forma antes da primeira; nas demais tabelas mantém a referência mais próxima. Tudo marcado "inferido".
const SEQ11416=['A-1','A-2','A-3','A-4','A-5','B-6','B-7','B-8','B-9','B-10','C-11','C-12','C-13'];
function progDaFicha(cargo,ini,fim){
  if(!S.res) return [];
  const pts=[];
  for(const l of S.res.linhas){
    if(!l.fonte||!l.bruto||!(l.bruto.VB>0)||l.comp===ini.slice(0,7)||l.comp===fim.slice(0,7)) continue;
    const sg=E.sugerirRef(BASE,cargo,l.comp+'-15','',l.bruto.VB); if(!sg||sg.origem!=='ficha') continue;
    pts.push({k:l.comp,classe:sg.classe,padrao:String(sg.padrao)});
  }
  if(!pts.length) return [];
  const ref=p=>p.classe+'-'+(/^\d+$/.test(p.padrao)?+p.padrao:p.padrao);
  const out=[]; let cur=null;
  for(const p of pts){ if(cur&&ref(cur)===ref(p)){ cur.ult=p.k; continue; } cur={ini:p.k+'-01',ult:p.k,classe:p.classe,padrao:p.padrao,origem:'ficha'}; out.push(cur); }
  const passo=(r,n)=>{ const i=SEQ11416.indexOf(ref(r)); if(i<0) return null; const j=Math.min(SEQ11416.length-1,Math.max(0,i+n)); const [c,pd]=SEQ11416[j].split('-'); return {classe:c,padrao:pd}; };
  const res=[];
  // antes da primeira referência vista
  const f0=out[0]; if(ini.slice(0,7)<f0.ini.slice(0,7)){
    let k=f0.ini.slice(0,7), n=0; const ant=[];
    while(k>ini.slice(0,7)){ const k2=RBC.addM(k,-12); n--; const st=k>='2007-01'?passo(f0,n):null; const iniP=k2<ini.slice(0,7)?ini:k2+'-01';
      ant.unshift(Object.assign({ini:iniP,fim:ultimoDia(RBC.addM(k,-1)),origem:'inferida'},st||{classe:f0.classe,padrao:f0.padrao})); k=k2; }
    res.push(...ant);
  }
  out.forEach((o,i)=>{ const nx=out[i+1]; res.push({ini:o.ini,fim:nx?ultimoDia(RBC.addM(nx.ini.slice(0,7),-1)):null,classe:o.classe,padrao:o.padrao,origem:'ficha'}); });
  // depois da última referência vista: progressão anual presumida (só na carreira da Lei 11.416)
  const ul=out[out.length-1], last=res[res.length-1];
  if(ul.ult<fim.slice(0,7)&&SEQ11416.includes(ref(ul))){
    last.fim=ultimoDia(ul.ult); let k=RBC.addM(ul.ult,1), base=ul.ini.slice(0,7), n=0;
    while(k<=fim.slice(0,7)){ let prox=RBC.addM(base,12*(n+1)); while(prox<=ul.ult){ n++; prox=RBC.addM(base,12*(n+1)); }
      const st=passo(ul,n); const ate=prox>fim.slice(0,7)?null:ultimoDia(RBC.addM(prox,-1));
      res.push(Object.assign({ini:k+'-01',fim:ate,origem:'inferida'},st)); if(!ate) break; k=prox; n++; }
  }
  return res;
}
// ATS sem relatório: percentual pago na ficha (ATS ÷ vencimento), por período
function atsDaFicha(){
  if(!S.res) return []; const out=[]; let cur=null;
  for(const l of S.res.linhas){ if(!l.fonte||!l.bruto||!(l.bruto.VB>0)) continue; const p=l.bruto.ATS?Math.round(l.bruto.ATS/l.bruto.VB*100):0;
    if(cur&&cur.pct===p){ cur.fim=ultimoDia(l.comp); continue; } cur={ini:l.comp+'-01',fim:ultimoDia(l.comp),pct:p}; out.push(cur); }
  if(out.length) out[out.length-1].fim=null;
  return out.filter(o=>o.pct>0);
}
// AQ e AQ-Treinamento: havendo pagamento no mês, presume-se o direito; o valor devido é calculado pela tabela da carreira
function aqDaFicha(){
  if(!S.res) return null; const o={};
  for(const l of S.res.linhas){ const b=l.bruto||{}; if(b.AQ>0.005||b.AQ_TREIN>0.005) o[l.comp]={VB:b.VB||0,AQ:b.AQ||0,AQ_TREIN:b.AQ_TREIN||0}; }
  return o;
}

// dados do cabeçalho da ficha do FolhaWeb (cargo, data de exercício): só preenchem campos vazios
function infoFicha(inf){
  if(!inf) return; Object.assign(S.fichaInfo, inf);
  const c=String(inf.cargo||'').toUpperCase();
  const cg=/ANALISTA/.test(c)?'ANALISTA JUDICIÁRIO':/T[ÉE]CNICO/.test(c)?'TÉCNICO JUDICIÁRIO':/AUXILIAR/.test(c)?'AUXILIAR JUDICIÁRIO':'';
  if(cg&&!$('cargo').value){ $('cargo').value=cg; }
  const m=String(inf.exercicio||'').match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(m&&!$('inicio').value){ $('inicio').value=m[3]+'-'+m[2]+'-'+m[1]; }
}
// ------------------------------------------------------------ etapa 2: ficha
async function lerArquivos(list){
  const fila=[...list]; if(!fila.length) return;
  $('barraSt').textContent='Lendo '+fila.length+' arquivo(s)…';
  for (const f of fila){
    const info={nome:f.name, anos:'', erro:'', dup:0};
    try{
      const buf=await f.arrayBuffer(); let recs=[], refs={};
      if (/\.pdf$/i.test(f.name)){ const pg=(await pdfDoc(buf)).pages; const r=RBC.isFolhaWebPorFolha(pg)?RBC.parseFolhaWebPorFolha(pg):RBC.parseFolhaWebPages(pg); recs=r.recs; refs=r.refs||{}; if(r.info) infoFicha(r.info); }
      else if (/\.xlsx?$/i.test(f.name)){ const wb=XLSX.read(buf,{type:'array'});
        // sistema antigo (planilha longa) ou FolhaWeb exportado em planilha (Big Grid). Usa a primeira aba reconhecida: as
        // seguintes costumam ser cópias de trabalho (conferências, ajustes) e duplicariam lançamentos
        for(const n of wb.SheetNames){ const rows=XLSX.utils.sheet_to_json(wb.Sheets[n]); let r=null;
          if(RBC.isBigGrid(rows)){ const b=RBC.parseBigGrid(rows); r=b.recs; if(r.length){ Object.assign(S.basePSO,b.basePSO); infoFicha(b.info); } }
          else if(rows.length&&('Código Rubrica' in rows[0])) r=RBC.parseLongRows(rows);
          if(r&&r.length){ recs=r; break; } } }
      else info.erro='Formato não aceito. Envie .xls, .xlsx ou .pdf.';
      if(!info.erro && !recs.length) info.erro='Nenhum lançamento encontrado. Confira se é a ficha financeira exportada do sistema.';
      const ja=new Set(S.recs.map(r=>r.comp+'|'+r.fonte));
      const novos=recs.filter(r=>!ja.has(r.comp+'|'+r.fonte));
      info.dup=recs.length-novos.length;
      const anos=[...new Set(novos.map(r=>r.ano))].sort(); info.anos=anos.length?(anos.length>1?anos[0]+' a '+anos[anos.length-1]:String(anos[0])):'';
      S.recs=S.recs.concat(novos); Object.assign(S.refs,refs);
      for(const p of devolDaFicha(novos)) if(!S.devol.some(q=>q.obs===p.obs)) S.devol.push(p);
    }catch(e){ info.erro='Não foi possível ler o arquivo ('+(e.message||e)+').'; }
    S.arquivos.push(info);
  }
  calc();
  if(S.relArqs.length||S.rel.PROGRESSAO.length) renderRelTabelas();
}

// ------------------------------------------------------------ cálculo
function ignMap(){ const o={}; for(const k in S.ignorar) o[k]=true; return o; }
function calc(){
  const ini=iniEf(), fim=fimEf();
  S.res=null;
  S.tetoAuto=RBC.detectarTeto(S.recs, ini);
  if(S.ctc&&S.ctc.teto==='sim') S.tetoAuto={desde:(S.ctc.inicio||ini||'').slice(0,7), motivo:'CTC: contribuição limitada ao teto do RGPS'};
  else if(S.ctc&&S.ctc.teto==='migrou'&&S.ctc.tetoDesde) S.tetoAuto={desde:S.ctc.tetoDesde.slice(0,7), motivo:'CTC: migração para a previdência complementar'};
  else if(S.ctc&&S.ctc.teto==='nao') S.tetoAuto=S.tetoAuto&&S.tetoAuto.desde?Object.assign({},S.tetoAuto,{motivo:S.tetoAuto.motivo+' — atenção: a CTC diz que não houve adesão'}):{desde:'',motivo:'CTC: sem limitação ao teto do RGPS'};
  { const t=S.tetoAuto, el=$('tetoDica'); if(el) el.textContent = t&&t.desde ? `Detectado: desde ${t.desde.slice(5,7)}/${t.desde.slice(0,4)} (${t.motivo})` : t ? t.motivo : 'Sem contribuição ao Funpresp na ficha'; }
  // sem ficha, mas com progressão (CTC ou relatório): a RBC sai inteira da tabela (meses marcados "sem ficha")
  if((S.recs.length || S.rel.PROGRESSAO.length) && ini && fim && ini<=fim){
    try{ const rg=getRegras(); if($('cargo').value==='MAGISTRADO') rg.gnFicha=true;
      S.res = RBC.calcular(S.recs,{inicio:ini, fim, cats:S.cats, refs:S.refs, tabela:TABELA, regras:rg, manual:S.manual, ignorarAloc:ignMap()}); }
    catch(e){ console.error(e); S.res=null; }
  }
  if(aplicarSugestoes()) renderRelTabelas();
  S.esp=null; S.cmp=null; S.espBy={};
  const d=dadosServidor();
  if(d){ try{ S.esp=E.calcularEsperada(BASE,d,Object.assign(getRegras(),{aqTreinAnos:S.res?S.res.aqTreinAnos:{}})); for(const l of S.esp.linhas) S.espBy[l.comp]=l; if(S.res) S.cmp=E.comparar(S.esp,S.res); }catch(e){ console.error(e); S.esp=null; } }
  aplicarTabelaAntiga();
  aplicarSemFicha();
  aplicarTeto();
  // 13º anterior a gnDesde: fora da RBC; vai para a certidão complementar de gratificação natalina
  if(S.res){ S.gnCert=S.res.gns.filter(g=>g.fora); S.res.gns=S.res.gns.filter(g=>!g.fora); } else S.gnCert=[];
  renderTudo();
}
// Antes de 07/1994 (regra tabelaAte), a RBC usa a remuneração da tabela (prática da DIPROF): com os reajustes mensais e os
// atrasados da época, a ficha não espelha o mês de competência. Parcelas sem tabela (função, substituição, lançamentos manuais) vêm da ficha.
function aplicarTabelaAntiga(){
  const ate=getRegras().tabelaAte; if(!ate||!S.esp||!S.res) return;
  for(const l of S.res.linhas){
    if(l.comp>ate) continue; const e=S.espBy[l.comp]; if(!e) continue;
    const v=Object.assign({},e.inc); for(const c in l.v) if(!(c in e.v)) v[c]=l.v[c];
    l.vFicha=l.v; l.v=v; l.total=RBC.r2(Object.values(v).reduce((a,b)=>a+b,0)); l.daTabela=true;
    l.pssCalc=RBC.pssDevida(l.total,l.comp); if(l.fonte) l.dif=RBC.r2(l.pssFicha-l.pssCalc);
  }
  // Modelo da DIPROF (RBCs conferidas): mesmo com a ficha como base, algumas parcelas saem da tabela
  //  - VPNI (quintos/décimos): pela tabela, conforme o relatório de VPNI; no período da VPNI judicial sem contribuição
  //    (dez/1999 a dez/2005, ação da ANAJUSTRA) segue a ficha
  //  - função e redutor até a data em que a função integrava a base (nov/1998): pela tabela
  //  - mês sem vencimento na ficha (opção pela FC integral, por exemplo): parcelas do cargo efetivo pela tabela
  const rg=getRegras();
  for(const l of S.res.linhas){
    if(l.daTabela||!l.fonte) continue; const e=S.espBy[l.comp]; if(!e) continue;
    const v=Object.assign({},l.v), aj=[];
    const set=(cats)=>{ for(const c of cats){ if(e.inc[c]!=null) v[c]=e.inc[c]; else delete v[c]; } };
    // (VPNI e função pela tabela só com relatório do RH: as tabelas lidas da CTC servem à conferência, não substituem a ficha)
    if(rg.vpniTabela!==false && S.rel.VPNI.some(r=>r.fonte!=='CTC') && !(l.comp>='1999-12'&&l.comp<='2005-12') && (e.v.VPNI||e.v.VPNI_JUD)){ set(['VPNI','VPNI_JUD']); aj.push('VPNI pela tabela'); }
    if(rg.fcTabela!==false && l.comp<=rg.fcAte && (e.v.FC!=null||e.v.SUBST!=null) && [...S.rel.FUNCOES,...S.rel.SUBSTITUICOES].some(r=>r.fonte!=='CTC')){ set(['FC','SUBST','REDUTOR']); aj.push('função e redutor pela tabela'); }
    if(!(l.bruto&&l.bruto.VB>0) && e.v.VB){ set(['VB','GAJ','APJ','DIF2886','GEXTRA','REDUTOR']); aj.push('sem vencimento na ficha: cargo efetivo pela tabela'); }
    // VPI (Lei 10.698/2003) devida de abr/2016 a dez/2018 e não paga na folha a partir de ago/2016: as RBCs da DIPROF
    // emitidas desde 2025 incluem o valor da tabela (6 casos; as de 2024 não incluíam)
    if(rg.vpiTabela!==false && l.comp>='2016-04' && l.comp<='2018-12' && !(l.v.VPI>0) && e.inc.VPI>0){ v.VPI=e.inc.VPI; aj.push('VPI pela tabela'); }
    if(!aj.length) continue;
    const tot=RBC.r2(Object.values(v).reduce((a,b)=>a+b,0)); if(Math.abs(tot-l.total)<0.005){ continue; }
    l.vFicha=l.v; l.v=v; l.total=tot; l.ajustes=aj; l.pssCalc=RBC.pssDevida(l.total,l.comp,rg.teto); l.dif=RBC.r2(l.pssFicha-l.pssCalc);
  }
  // 13º recalculado sobre a remuneração final do mês-base
  for(const g of S.res.gns){ if(g.daFicha) continue; const lb=S.res.linhas.find(x=>x.comp===g.baseComp); if(!lb) continue;
    let b=lb.total; if(g.obs==='sem VPI') b=RBC.r2(b-(lb.v.VPI||0)-(lb.v.VPI_DED||0)); g.base=b; g.valor=RBC.r2(b*g.avos/12); }
  // mês de ingresso ou de desligamento sem ficha (ex.: posse em 30/06, primeira ficha em julho): o proporcional costuma vir
  // na folha seguinte; se nada foi ligado ao mês, a RBC usa a tabela pelos dias de exercício
  const ls=S.res.linhas, bordas=[ls[0],ls[ls.length-1]];
  for(const l of bordas){
    if(!l||l.fonte||l.daTabela||Math.abs(l.total)>0.005) continue; const e=S.espBy[l.comp]; if(!e) continue;
    l.v=Object.assign({},e.inc); l.total=RBC.r2(Object.values(l.v).reduce((a,b)=>a+b,0)); l.daTabela=true; l.borda=true;
    l.pssCalc=RBC.pssDevida(l.total,l.comp);
  }
}
// Meses do período sem ficha enviada: a RBC usa a remuneração esperada pela tabela (marcada na planilha). Regra editável.
function vizinhoComFicha(k){
  const ls=S.res.linhas.filter(l=>l.fonte&&l.bruto&&l.bruto.VB>0); let best=null, bd=1e9;
  const n=x=>+x.slice(0,4)*12+ +x.slice(5,7);
  for(const l of ls){ const d=Math.abs(n(l.comp)-n(k)); if(d<bd){ bd=d; best=l; } }
  return best;
}
function aplicarSemFicha(){
  if(!S.res||!S.esp||!getRegras().semFichaTabela) return;
  for(const l of S.res.linhas){
    if(l.fonte||l.daTabela||Math.abs(l.total)>0.005) continue; const e=S.espBy[l.comp]; if(!e) continue;
    l.v=Object.assign({},e.inc);
    // parcelas sem tabela (AQ, VPNI): repete o mês com ficha mais próximo (AQ como percentual do vencimento)
    const viz=vizinhoComFicha(l.comp);
    if(viz){ const b=viz.bruto||{}; if(b.AQ>0&&b.VB>0&&l.v.VB&&!l.v.AQ) l.v.AQ=RBC.r2(l.v.VB*b.AQ/b.VB);
      for(const c of ['VPNI','VPNI_JUD']) if(viz.v[c]&&!l.v[c]) l.v[c]=viz.v[c]; }
    l.total=RBC.r2(Object.values(l.v).reduce((a,b)=>a+b,0)); l.daTabela=true; l.semFicha=true;
    l.pssCalc=RBC.pssDevida(l.total,l.comp);
  }
  for(const g of S.res.gns){ if(g.daFicha) continue; const lb=S.res.linhas.find(x=>x.comp===g.baseComp); if(!lb||!lb.semFicha) continue;
    let b=lb.total; if(g.obs==='sem VPI') b=RBC.r2(b-(lb.v.VPI||0)-(lb.v.VPI_DED||0)); g.base=b; g.valor=RBC.r2(b*g.avos/12); }
}
// Regime de previdência complementar (Funpresp): a base de contribuição ao RPPS é limitada ao teto do RGPS
// (Lei 12.618/2012, art. 3º). A RBC registra o menor valor entre a remuneração e o teto, inclusive no 13º.
function tetoRGPS(k){ const d=k+'-15'; const p=(BASE.par||[]).find(x=>x[0]==='TETO_RGPS'&&x[1]<=d&&x[2]>=d); return p?p[3]:null; }
function aplicarTeto(){
  const desde=getRegras().tetoDesde; if(!S.res||!desde) return;
  for(const l of S.res.linhas){
    if(l.comp<desde) continue; const t=tetoRGPS(l.comp); if(t==null) continue;
    l.tetoRGPS=t; if(l.total>t){ l.totalSemTeto=l.total; l.total=t; }
    l.pssCalc=RBC.pssDevida(l.total,l.comp,true); if(l.fonte) l.dif=RBC.r2(l.pssFicha-l.pssCalc);
  }
  for(const g of S.res.gns){ if(g.depois<desde) continue; const t=tetoRGPS(g.depois); if(t==null) continue; g.tetoRGPS=t; if(g.valor>t){ g.valorSemTeto=g.valor; g.valor=t; } }
}
// ------------------------------------------------------------ certidão complementar de gratificação natalina
// Modelo da DIPROF: "Certifico, em complementação à Relação das Remunerações de Contribuições emitida em …, que o(a)
// servidor(a) …, CPF …, recebeu por este Tribunal, a título de Gratificação Natalina (considerando-se apenas as parcelas
// que compunham a base do recolhimento previdenciário mensal), os seguintes valores: …. Certifico ainda que não houve
// recolhimento de contribuição previdenciária sobre esses valores."
const UN=['','um','dois','três','quatro','cinco','seis','sete','oito','nove','dez','onze','doze','treze','quatorze','quinze','dezesseis','dezessete','dezoito','dezenove'];
const DZ=['','','vinte','trinta','quarenta','cinquenta','sessenta','setenta','oitenta','noventa'];
const CT=['','cento','duzentos','trezentos','quatrocentos','quinhentos','seiscentos','setecentos','oitocentos','novecentos'];
function ext999(n){ if(n===100) return 'cem'; const c=Math.floor(n/100), r=n%100, p=[]; if(c) p.push(CT[c]); if(r<20){ if(r) p.push(UN[r]); } else { p.push(DZ[Math.floor(r/10)]+(r%10?' e '+UN[r%10]:'')); } return p.join(' e '); }
function extInt(n){
  if(n===0) return 'zero';
  const g=[]; let x=n; while(x>0){ g.push(x%1000); x=Math.floor(x/1000); }
  const nomes=[['',''],['mil','mil'],['milhão','milhões'],['bilhão','bilhões']], partes=[];
  for(let i=g.length-1;i>=0;i--){ const v=g[i]; if(!v) continue; let t=i===1&&v===1?'mil':ext999(v)+(i?' '+nomes[i][v>1?1:0]:''); partes.push({t,v,i}); }
  return partes.map((p,j)=>{ if(j===0) return p.t; const ult=j===partes.length-1; return ((ult&&(p.v<100||p.v%100===0))?' e ':' ')+p.t; }).join('');
}
const MOEDAS={'Cr$':['cruzeiro','cruzeiros'],'CR$':['cruzeiro real','cruzeiros reais'],'R$':['real','reais'],'Cz$':['cruzado','cruzados'],'NCz$':['cruzado novo','cruzados novos']};
function porExtenso(v,moeda){
  const [s1,sp]=MOEDAS[moeda]||MOEDAS['R$']; const n=Math.floor(Math.round(v*100)/100+1e-9), c=Math.round((v-n)*100);
  let t='';
  if(n){ t=extInt(n); t+=(n%1000000===0?' de ':' ')+(n===1?s1:sp); }
  if(c){ t+=(n?' e ':'')+extInt(c)+' '+(c===1?'centavo':'centavos')+(n?'':' de '+s1); }
  return t||'zero '+sp;
}
const moedaAno = y => moedaDe(y+'-12');
function textoCertidaoGN(){
  const g=(S.gnCert||[]).filter(x=>x.valor>0); if(!g.length) return '';
  const nome=$('nome').value.trim()||'[nome do servidor]';
  const itens=g.map(x=>{ const m=moedaAno(x.ano); return `${m} ${fmt.format(x.valor)} (${porExtenso(x.valor,m)}) em ${x.ano}`; });
  const lista=itens.length>1?itens.slice(0,-1).join('; ')+' e '+itens[itens.length-1]:itens[0];
  return `Certifico, em complementação à Relação das Remunerações de Contribuições emitida em [data], referente à Certidão de Tempo de Contribuição nº [número], que o(a) servidor(a) ${nome}, CPF [CPF], recebeu por este Tribunal Regional do Trabalho, a título de Gratificação Natalina (considerando-se apenas as parcelas que compunham a base do recolhimento previdenciário mensal), os seguintes valores: ${lista}. Certifico ainda que não houve recolhimento de contribuição previdenciária sobre esses valores. Nada mais.`;
}
// ------------------------------------------------------------ benefício especial (Lei 12.618/2012, art. 3º, § 2º)
// Base = remuneração que serviu de base a contribuição efetivamente mantida, desde 07/1994. Períodos com contribuição
// devolvida ao servidor contam para a RBC e a média, mas não para o benefício especial (prática da DIPROF).
const ano4 = y => y.length===4 ? y : (+y < 50 ? '20' : '19') + y;
function devolDaFicha(recs){
  const out=[];
  for(const r of recs){
    const d=String(r.desc||'').toUpperCase();
    if(!/DEVOLU|RESTITU/.test(d) || !/PSS|PREVID|CONTRIB|RPPS/.test(d)) continue;
    const m=/(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\s*(?:-|A|ATÉ|ATE)\s*(\d{1,2})\/(\d{1,2})\/(\d{2,4})/.exec(d);
    const MS=['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ'], p2=x=>String(x).padStart(2,'0');
    const mm=/\b(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\/(\d{2,4})\s*(?:-|A|ATÉ|ATE)\s*(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\/(\d{2,4})/.exec(d);
    let ini='', fim='';
    if(m){ const yf=ano4(m[6]), yi=m[3]?ano4(m[3]):yf; ini=`${yi}-${p2(m[2])}-${p2(m[1])}`; fim=`${yf}-${p2(m[5])}-${p2(m[4])}`; }
    else if(mm){ const ki=ano4(mm[2])+'-'+p2(MS.indexOf(mm[1])+1), kf=ano4(mm[4])+'-'+p2(MS.indexOf(mm[3])+1); ini=ki+'-01'; fim=ultimoDia(kf); }
    // só a devolução de 01/07 a 24/10/1994 é integral pela prática da DIPROF; as demais (ex.: dez/1998–jan/2000, ações judiciais)
    // podem ser parciais e entram desmarcadas, para a DIPROF decidir
    const integral = ini==='1994-07-01' && fim==='1994-10-24';
    out.push({ini, fim, obs:`${r.desc} (pago em ${mesTxt(r.comp)}, ${rs(Math.abs(r.v))})`, origem:'ficha', semPeriodo:!ini, aplicar:integral});
  }
  return out;
}
function fracDevolvida(k){
  const n=new Date(+k.slice(0,4),+k.slice(5,7),0).getDate(); let dias=0;
  for(let d=1; d<=n; d++){ const dt=k+'-'+String(d).padStart(2,'0'); if(S.devol.some(p=>p.aplicar!==false&&p.ini&&p.fim&&p.ini<=dt&&dt<=p.fim)) dias++; }
  return {dias, n};
}
// dias do mês corrido, como na RBC da DIPROF (out/1994: 7/31)
function baseBE(l){ if(!naMedia(l.comp)) return null; const {dias,n}=fracDevolvida(l.comp); return RBC.r2(l.total*(n-dias)/n); }

// leitura por ano: a contribuição é descontada no mês do pagamento, então atrasados deslocam valores entre meses;
// o ano é a unidade de conferência e o mês só aponta onde olhar.
function anosConf(R){
  const out={}; const catOf=r=>(S.cats[r.cod+'|'+r.desc])||RBC.classify(r.cod,r.desc);
  for(const l of R.linhas){ const y=l.comp.slice(0,4); const a=out[y]||(out[y]={ano:y,dif:0,calc:0,ficha:0,nConf:0,semFicha:0,causas:[]});
    if(!l.fonte){ a.semFicha++; continue; } if(!l.conferir) continue; a.nConf++; a.dif+=l.dif; a.calc+=l.pssCalc; a.ficha+=l.pssFicha; }
  const soma={}, rest={}; const add=(y,k,v)=>{ (soma[y]=soma[y]||{})[k]=((soma[y]||{})[k]||0)+v; };
  for(const r of S.recs){ if(r.folha==='G') continue; const c=catOf(r); const y=String(r.ano); if(!out[y]) continue;
    if(c==='GAS' && !R.regras.gas) add(y,'GAS',r.v); if(c==='AQ_TREIN' && (R.regras.aqTrein===false || (R.regras.aqTrein==='ficha' && !(R.aqTreinAnos||{})[y]))) add(y,'AQ_TREIN',r.v); if(c==='CLASSIFICAR') add(y,'CLASSIFICAR',r.v); if(c==='PSS' && r.v>0.005){ add(y,'REST',r.v); (rest[y]=rest[y]||new Set()).add(mesTxt(r.comp)); } }
  for(const y in out){ const a=out[y]; a.dif=RBC.r2(a.dif); a.verif=a.nConf>0; a.ok=!a.verif || Math.abs(a.dif)<=Math.max(5,0.01*a.calc);
    const sy=soma[y]||{};
    if(sy.GAS>0.005) a.causas.push(`houve contribuição sobre ${rs(sy.GAS)} de GAS, que a regra atual deixa fora da RBC (cerca de ${rs(sy.GAS*0.11)} de contribuição)`);
    if(sy.AQ_TREIN>0.005) a.causas.push(`houve ${rs(sy.AQ_TREIN)} de AQ-Treinamento, fora da RBC pela regra atual`);
    if(sy.REST) a.causas.push(`houve devolução de ${rs(sy.REST)} de contribuição ao servidor (${[...rest[y]].join(', ')})`);
    if(sy.CLASSIFICAR) a.causas.push(`há ${rs(sy.CLASSIFICAR)} em rubricas não reconhecidas`);
    const pas=R.passivos.filter(p=>p.comp.startsWith(y) && !/ISEN/i.test(p.desc));
    if(pas.length){ const t=pas.reduce((s,p)=>s+p.valor,0); a.causas.push(`houve ${rs(t)} em passivos/exercícios anteriores sem isenção de PSS (${[...new Set(pas.map(p=>mesTxt(p.comp)))].join(', ')}), cuja contribuição não corresponde a meses da RBC`); }
    for(const p of R.pend) if(p.comp.startsWith(y)) a.causas.push(`${rs(p.valor)} de ${nome(p.cat).toLowerCase()} pago em ${mesTxt(p.comp)} ${S.ack[p.id]?'desconsiderado':'ainda sem mês de referência'}`);
    for(const k in S.ignorar) if(k.startsWith(y)) a.causas.push(`${rs(S.ignorar[k].valor)} de ${nome(S.ignorar[k].cat).toLowerCase()} pago em ${mesTxt(S.ignorar[k].comp)} foi desconsiderado`);
    if(a.semFicha) a.causas.push(`${a.semFicha} mês(es) sem ficha`);
  }
  return out;
}
function contagens(){
  const R=S.res; if(!R) return null;
  const inv=RBC.inventario(S.recs,S.cats);
  // antes do corte da tabela, atrasados e pendências não afetam a RBC (os valores saem da tabela)
  const ate=S.esp?(getRegras().tabelaAte||''):''; const vale=k=>!ate||k>ate;
  const parc=[]; for(const l of R.log) if(l.tipo==='retroativo') for(const a of l.aloc) if(a.fracao<1&&vale(a.comp)) parc.push({cat:l.cat,pagoEm:l.pagoEm,...a});
  const anos=anosConf(R); const sit={};
  for(const l of R.linhas){ const a=anos[l.comp.slice(0,4)];
    sit[l.comp]= (!l.fonte&&(l===R.linhas[0]||l===R.linhas[R.linhas.length-1]))?'nv' : !l.fonte?'none' : !l.conferir?'nv' : Math.abs(l.dif)<=0.5?'ok' : (a.ok?'comp':'att'); }
  const lv=Object.values(anos).filter(a=>a.verif);
  const cmp=S.cmp||[]; const divMes=new Set(cmp.filter(m=>m.itens.length).map(m=>m.comp));
  return { naoRec:inv.filter(e=>e.cat==='CLASSIFICAR'), inv, pend:R.pend.filter(p=>!S.ack[p.id]&&vale(p.comp)), pendTodos:R.pend, parc, sit, anos, divMes,
    anosVerif:lv.length, anosOk:lv.filter(a=>a.ok).length, anosAtt:lv.filter(a=>!a.ok),
    none:Object.values(sit).filter(x=>x==='none').length, nv:Object.values(sit).filter(x=>x==='nv').length, att:lv.filter(a=>!a.ok).length };
}

// ------------------------------------------------------------ navegação
function irPara(n){
  if(n>2 && !S.res) return;
  S.etapa=n;
  document.querySelectorAll('.etapa').forEach(s=>s.classList.toggle('on', s.id==='e'+n));
  window.scrollTo({top:0});
  renderTudo();
  const h=document.querySelector('#e'+n+' h2'); if(h){ h.setAttribute('tabindex','-1'); h.focus({preventScroll:true}); }
}
document.querySelectorAll('#trilho li').forEach(li=>li.querySelector('button').onclick=()=>irPara(+li.dataset.e));
$('voltar').onclick=()=>irPara(Math.max(1,S.etapa-1));
$('avancar').onclick=()=>{ if(S.etapa<4) irPara(S.etapa+1); else $('x_rbc').click(); };

function etapa1Status(){
  const nInc=S.rel.PROGRESSAO.filter(r=>r.origem==='incerta'&&!r.revogada).length;
  if(!$('cargo').value) return 'Escolha o cargo do servidor.';
  if(!S.rel.PROGRESSAO.length&&!S.esp) return 'Envie a ficha financeira (a progressão é deduzida do vencimento pago) ou os relatórios do RH.';
  if(nInc) return `${nInc} linha(s) da progressão com classe/padrão a conferir${S.res?'':' (a ficha, na etapa 2, ajuda a confirmar)'}.`;
  return S.esp?`Remuneração esperada calculada para ${S.esp.linhas.length} meses.`:'Informe o ingresso ou envie a ficha.';
}
function renderGNCert(){
  const box=$('gnCertBox'); if(!box) return; const g=(S.gnCert||[]).filter(x=>x.valor>0);
  box.hidden=!g.length; if(!g.length) return;
  $('gnCertTab').innerHTML=`<div class="tw"><table><thead><tr><th class="l">Ano</th><th>Avos</th><th>Base (mês)</th><th>Valor</th></tr></thead><tbody>${g.map(x=>`<tr><td class="l">${x.ano}</td><td>${x.avos}/12</td><td>${mesTxt(x.baseComp)}</td><td>${moedaAno(x.ano)} ${fmt.format(x.valor)}</td></tr>`).join('')}</tbody></table></div>`;
  const t=textoCertidaoGN(); if(!$('gnCertTxt').dataset.editado) $('gnCertTxt').value=t;
}
$('gnCertTxt').addEventListener('input',()=>{ $('gnCertTxt').dataset.editado='1'; });
$('gnCertCopiar').onclick=async()=>{ try{ await navigator.clipboard.writeText($('gnCertTxt').value); $('gnCertMsg').textContent='Copiado.'; }catch(e){ $('gnCertTxt').select(); $('gnCertMsg').textContent='Selecione e copie (Ctrl+C).'; } };
function renderTudo(){
  renderGNCert();
  const C=contagens();
  const nInc=S.rel.PROGRESSAO.filter(r=>r.origem==='incerta'&&!r.revogada).length;
  document.querySelectorAll('#trilho li').forEach(li=>{
    const n=+li.dataset.e; li.classList.toggle('atual', n===S.etapa); li.classList.toggle('feito', n<S.etapa);
    const b=li.querySelector('button'); b.disabled = n>2 && !S.res;
    if(n===S.etapa) b.setAttribute('aria-current','step'); else b.removeAttribute('aria-current');
    li.classList.toggle('alerta', !!((n===1 && (nInc || (S.esp&&S.esp.avisos.length))) || (C && ((n===2 && C.naoRec.length) || (n===3 && (C.pend.length || C.parc.length)) || (n===4 && (C.att || C.divMes.size))))));
  });
  $('voltar').hidden = S.etapa===1;
  $('avancar').disabled = S.etapa>=2 && !S.res;
  $('avancar').textContent = S.etapa===4 ? 'Baixar RBC em Excel' : 'Continuar';
  let st='';
  if(S.etapa===1) st=etapa1Status();
  else if(!S.recs.length) st='Envie a ficha financeira.';
  else if(!S.res) st='Confira as datas de ingresso e desligamento na etapa 1.';
  else if(S.etapa===2) st=C.naoRec.length?`${C.naoRec.length} rubrica(s) sem categoria.`:`${S.res.linhas.length} meses; todas as rubricas reconhecidas.`;
  else if(S.etapa===3) st=(C.pend.length||C.parc.length)?`${C.pend.length} valor(es) sem mês, ${C.parc.length} data(s) a confirmar.`:'Nada pendente.';
  else st=(C.att?`${C.att} ano(s) com diferença na contribuição. `:'Contribuição conferida. ')+(S.cmp?`${C.divMes.size} mês(es) com pagamento diferente do esperado.`:'');
  $('barraSt').textContent=st;
  { const temEsp=!!$('especialidade').value; $('espDesde').disabled=!temEsp; if(!temEsp) $('espDesde').value=''; $('espAjuda').textContent=temEsp?'Em branco = data de posse':'Escolha a especialidade para informar'; }
  $('inicioDica').textContent=$('inicio').value&&$('inicio').value<'1994-07-01'?'Antes de 07/1994: moeda da época, fora da média':'Data de posse';
  renderArquivos(); renderCobertura(); renderPrevia();
  if(S.etapa===2) renderRubricas(C);
  if(S.etapa===3) renderPend(C);
  if(S.etapa===4) renderConferencia(C);
  $('x_rbc').disabled=!S.res;
}
function renderPrevia(){
  const el=$('previa'); if(!el) return;
  if(!S.esp){ el.innerHTML=''; return; }
  const av=S.esp.avisos;
  el.innerHTML=`<div class="aviso ${av.length?'att':'ok'}"><span class="ic">${av.length?'!':'✓'}</span><div>Remuneração esperada calculada de ${mesTxt(S.esp.linhas[0].comp)} a ${mesTxt(S.esp.linhas[S.esp.linhas.length-1].comp)}.${av.length?' Atenção: '+av.map(a=>esc(a.texto)+' ('+faixas(a.meses)+')').join('; ')+'.':''}</div></div>`;
}

// ------------------------------------------------------------ etapa 2
function renderArquivos(){
  $('files').innerHTML = S.arquivos.map(a=>`<li><span class="sit ${a.erro?'att':'ok'}">${esc(a.nome)}</span><span class="q">${a.erro?esc(a.erro):esc(a.anos)+(a.dup?` · ${a.dup} lançamentos repetidos ignorados`:'')}</span></li>`).join('')
    + (S.arquivos.length?`<li><button class="btn link" id="limpar">Remover todos os arquivos da ficha</button></li>`:'');
  if($('limpar')) $('limpar').onclick=()=>{ S.arquivos=[];S.recs=[];S.refs={};S.res=null; S.devol=S.devol.filter(p=>p.origem!=='ficha'); calc(); };
}
function faixas(lista){ const fx=[]; for(const k of [...lista].sort()){ const u=fx[fx.length-1]; if(u && RBC.addM(u[1],1)===k) u[1]=k; else fx.push([k,k]); } return fx.map(f=>f[0]===f[1]?mesTxt(f[0]):mesTxt(f[0])+' a '+mesTxt(f[1])).join(', '); }
function renderCobertura(){
  const el=$('cobertura'); if(!S.res){ el.innerHTML=S.recs.length?'<div class="aviso att"><span class="ic">!</span><div>Confira as datas de ingresso e desligamento na etapa 1.</div></div>':''; return; }
  const ls=S.res.linhas, ehBorda=l=>l===ls[0]||l===ls[ls.length-1];
  // mês de ingresso/desligamento sem ficha, mas com valor ligado a ele (atrasado da folha seguinte), não é falta de ficha
  const sem=ls.filter(l=>!l.fonte&&!l.daTabela&&!(ehBorda(l)&&Math.abs(l.total)>0.005)).map(l=>l.comp);
  const tab=ls.filter(l=>!l.fonte&&l.daTabela&&!l.borda).map(l=>l.comp), borda=ls.filter(l=>!l.fonte&&(l.borda||(ehBorda(l)&&!l.daTabela&&Math.abs(l.total)>0.005)));
  const semBorda=sem.filter(k=>ehBorda(ls.find(l=>l.comp===k))), semMeio=sem.filter(k=>!semBorda.includes(k));
  el.innerHTML = (borda.length?`<div class="aviso info"><span class="ic">i</span><div>${borda.map(l=>`${mesTxt(l.comp)} (${l===ls[0]?'mês de ingresso':'mês de desligamento'}) não tem ficha própria: ${l.borda?'a RBC usa a tabela pelos dias de exercício':'o valor veio como atrasado na folha seguinte'}.`).join(' ')} Confira o detalhe do mês na etapa 4.</div></div>`:'') + (semBorda.length?`<div class="aviso info"><span class="ic">i</span><div>${semBorda.map(mesTxt).join(' e ')} (início ou fim do período) não tem ficha própria. O proporcional costuma vir na folha seguinte; com a progressão informada na etapa 1, a RBC usa a tabela pelos dias de exercício.</div></div>`:'') + (tab.length?`<div class="aviso info"><span class="ic">i</span><div>Sem ficha em <b>${faixas(tab)}</b>: a RBC desses meses sai da tabela de remuneração, como nos demais meses anteriores a 07/1994. Função e substituição sem tabela precisam ser lançadas na etapa 3.</div></div>`:'') + (semMeio.length
    ? `<div class="aviso att"><span class="ic">!</span><div>Falta a ficha de ${semMeio.length} mês(es): <b>${faixas(semMeio)}</b>. Esses meses sairão zerados na RBC. Envie a ficha que cobre esse intervalo.</div></div>`
    : (tab.length||borda.length||semBorda.length)?'':`<div class="aviso ok"><span class="ic">✓</span><div>A ficha cobre todo o período, de ${mesTxt(S.res.meses[0])} a ${mesTxt(S.res.meses[S.res.meses.length-1])}.</div></div>`);
}
const OPC_CAT = ['SUBSIDIO','FC_PREV','VB','GAJ','ATS','VPI','VPNI','VPNI_JUD','FC','SUBST','AQ','AQ_TREIN','GAE','GAS','APJ','DIF2886','GEXTRA','REDUTOR','V1323_VB','V1323_GAJ','V1323_ATS','V1323_VPNI','V1323_FC','VPI_DED','FALTAS','V1198','PSS','GN','PASSIVO','IGNORAR','CLASSIFICAR'];
const catSelect = (k,sel) => `<select data-k="${esc(k)}" aria-label="Categoria">${OPC_CAT.map(c=>`<option value="${c}"${c===sel?' selected':''}>${esc(c==='CLASSIFICAR'?'— escolha —':nome(c))}</option>`).join('')}</select>`;
// Sugestão para rubrica não reconhecida: a rubrica mais parecida entre as ~400 já classificadas nas fichas das RBCs da DIPROF
// (similaridade de cosseno de trigramas de caracteres). No teste "deixa uma de fora", acerta 80% quando a similaridade é ≥ 0,7.
// É só sugestão: a escolha continua com o usuário.
const nrmRub = s => String(s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toUpperCase().replace(/[^A-Z0-9%]+/g,' ').trim();
const tri = s => { s=' '+nrmRub(s)+' '; const f=new Map(); for(let i=0;i<s.length-2;i++){ const k=s.slice(i,i+3); f.set(k,(f.get(k)||0)+1); } let n=0; for(const v of f.values()) n+=v*v; n=Math.sqrt(n)||1; for(const [k,v] of f) f.set(k,v/n); return f; };
let RUBVEC=null;
function sugerirCategoria(desc){
  if(!RUBVEC) RUBVEC=(typeof RUBREF!=='undefined'?RUBREF:[]).map(([d,c])=>({d,c,v:tri(d)}));
  const v=tri(desc); let best=null;
  for(const r of RUBVEC){ let s=0; for(const [k,x] of v){ const y=r.v.get(k); if(y) s+=x*y; } if(!best||s>best.s) best={s,d:r.d,c:r.c}; }
  return best&&best.s>=0.6?best:null;
}
function renderRubricas(C){
  const el=$('rubricas'); if(!C){ el.innerHTML=''; return; }
  const linha=e=>{ const sg=e.cat==='CLASSIFICAR'?sugerirCategoria(e.desc):null; return `<tr><td class="l">${esc(e.cod)}</td><td class="l wrap">${esc(e.desc)}</td><td class="l">${mesTxt(e.primeiro)} a ${mesTxt(e.ultimo)}</td><td>${f2(e.total)}</td><td class="l">${catSelect(e.cod+'|'+e.desc,e.cat)}${S.cats[e.cod+'|'+e.desc]?' <span class="muted small">alterada</span>':''}${sg?`<div class="muted small" style="margin-top:4px">Sugestão: <b>${esc(nome(sg.c))}</b> — parecida com “${esc(sg.d)}” (${Math.round(sg.s*100)}%) <button class="btn link" data-sug="${esc(e.cod+'|'+e.desc)}" data-cat="${sg.c}">usar</button></div>`:''}</td></tr>`; };
  const cab='<thead><tr><th class="l">Código</th><th class="l">Descrição na ficha</th><th class="l">Aparece em</th><th>Soma</th><th class="l">É o quê?</th></tr></thead>';
  let h='';
  if(C.naoRec.length) h+=`<div class="bloco"><h3>${C.naoRec.length} rubrica(s) não reconhecida(s)</h3><p class="muted small" style="margin:0 0 12px">Escolha o que cada uma representa. Se não fizer parte da remuneração (desconto, auxílio, indenização), escolha "Não entra na RBC".</p><div class="tw"><table>${cab}<tbody>${C.naoRec.map(linha).join('')}</tbody></table></div></div>`;
  else h+=`<div class="aviso ok" style="margin:0 0 16px"><span class="ic">✓</span><div>As ${C.inv.length} rubricas da ficha foram reconhecidas. Nada a fazer aqui.</div></div>`;
  const outras=C.inv.filter(e=>e.cat!=='CLASSIFICAR');
  h+=`<details class="bloco"><summary>Ver como cada rubrica foi classificada (${outras.length})</summary><p class="muted small">Corrija se alguma estiver errada. A mudança vale para a ficha inteira.</p><div class="tw"><table>${cab}<tbody>${outras.map(linha).join('')}</tbody></table></div></details>`;
  el.innerHTML=h;
  el.querySelectorAll('select[data-k]').forEach(s=>s.onchange=()=>{ const k=s.dataset.k, i=k.indexOf('|'); if(s.value===RBC.classify(k.slice(0,i),k.slice(i+1))) delete S.cats[k]; else S.cats[k]=s.value; calc(); });
  el.querySelectorAll('button[data-sug]').forEach(b=>b.onclick=()=>{ S.cats[b.dataset.sug]=b.dataset.cat; calc(); });
}

// ------------------------------------------------------------ etapa 3
const REMUN_OPC = RBC.REMUN.filter(c=>c!=='FALTAS');
function formDist(key, o){
  const id=k=>`d_${k}_${key}`;
  return `<div class="form-dist" data-form="${key}">
    <div class="campos">
      <label class="c2">Lançar como<select id="${id('cat')}">${REMUN_OPC.map(c=>`<option value="${c}"${c===o.cat?' selected':''}>${esc(nome(c))}</option>`).join('')}</select></label>
      <label class="c2">Refere-se a partir de<input type="date" id="${id('ini')}"></label>
      <label class="c2">até<input type="date" id="${id('fim')}"></label>
    </div>
    <div class="modos" role="radiogroup" aria-label="Como distribuir">
      <label class="modo"><input type="radio" name="${id('modo')}" value="igual" checked><div><b>Dividir igualmente</b><span>O valor pago é repartido em partes iguais entre os meses.</span></div></label>
      <label class="modo"><input type="radio" name="${id('modo')}" value="unidade"><div><b>Valor fixo por mês</b><span>Ex.: VPI de R$ 59,87. Preenche do último mês para trás.</span></div></label>
      <label class="modo"><input type="radio" name="${id('modo')}" value="percentualVB"><div><b>Percentual do vencimento</b><span>Ex.: AQ de 7,5%, calculado sobre o vencimento de cada mês.</span></div></label>
    </div>
    <div class="campos">
      <label class="c2">Valor pago (R$)<input type="number" step="0.01" id="${id('valor')}" value="${o.valor!=null?o.valor:''}"></label>
      <label class="c2" id="${id('parBox')}" hidden><span id="${id('parLbl')}">Valor por mês (R$)</span><input type="number" step="0.01" id="${id('par')}"></label>
    </div>
    <div style="display:flex;gap:14px;align-items:center;margin-top:14px;flex-wrap:wrap"><button class="btn peq" data-ok="${key}">Lançar nos meses</button><button class="btn link" data-cancel="${key}">Cancelar</button><span class="small" id="${id('msg')}" role="alert" style="color:var(--att)"></span></div>
  </div>`;
}
function ligarForm(key, o){
  const id=k=>`d_${k}_${key}`;
  const radios=[...document.getElementsByName(id('modo'))];
  const upd=()=>{ const m=radios.find(r=>r.checked).value; $(id('parBox')).hidden = m==='igual'; $(id('parLbl')).textContent = m==='unidade'?'Valor por mês (R$)':'Percentual do vencimento (%)'; };
  radios.forEach(r=>r.onchange=upd); upd();
  document.querySelector(`[data-cancel="${key}"]`).onclick=()=>{ delete S.abertos[key]; renderTudo(); };
  document.querySelector(`[data-ok="${key}"]`).onclick=()=>{
    const modo=radios.find(r=>r.checked).value, valor=parseFloat($(id('valor')).value), par=parseFloat($(id('par')).value), ini=$(id('ini')).value, fim=$(id('fim')).value;
    const msg=t=>{ $(id('msg')).textContent=t; };
    if(!ini||!fim) return msg('Informe o período a que o valor se refere.');
    if(ini>fim) return msg('A data inicial precisa ser anterior à final.');
    if(modo!=='percentualVB' && !valor) return msg('Informe o valor pago.');
    if(modo==='unidade' && !par) return msg('Informe o valor por mês.');
    if(modo==='percentualVB' && !par) return msg('Informe o percentual.');
    const m={cat:$(id('cat')).value, modo, valor:valor||0, ini, fim, origem:o.origem||'manual'};
    if(o.id) m.id=o.id; if(modo==='unidade') m.unidade=par; if(modo==='percentualVB') m.pct=par/100;
    S.manual.push(m); delete S.abertos[key]; calc();
  };
}
function renderPend(C){
  const el=$('pend'); if(!C){ el.innerHTML=''; return; }
  const R=S.res; let h=''; const ate=S.esp?(getRegras().tabelaAte||''):''; const vale=k=>!ate||k>ate;
  const abrir=(key,txt)=>S.abertos[key]?'':`<button class="btn sec peq" data-abrir="${key}">${txt||'Distribuir'}</button>`;
  const desc=(key)=>S.abertos[key]?'':`<button class="btn link" data-ack="${key}">Desconsiderar</button>`;
  h+=`<div class="bloco"><h3>Valores sem mês de referência</h3>`;
  if(C.pend.length){
    h+=`<p class="muted small" style="margin:0">Pagamentos que a calculadora não conseguiu ligar a um mês. Informe a que período se referem ou desconsidere. Enquanto não forem distribuídos, não entram na RBC.</p>`;
    R.pend.forEach((p,i)=>{ if(S.ack[p.id]||!vale(p.comp)) return; const key='p'+i; h+=`<div class="item"><div class="item-top"><span class="t">${esc(nome(p.cat))}</span><span class="muted small">pago em ${mesTxt(p.comp)}</span><span class="v">${rs(p.valor)}</span>${abrir(key)}${desc(key)}</div><p class="d">${p.motivo==='Sobra após alocar retroativo'?'Parte de um atrasado que sobrou depois da distribuição automática.':'Pago sem indicação do mês a que se refere.'}</p>${S.abertos[key]?formDist(key,{cat:p.cat,valor:p.valor}):''}</div>`; });
  } else h+=`<div class="aviso ok"><span class="ic">✓</span><div>Todos os pagamentos foram ligados a um mês${R.pend.length?' ou desconsiderados':''}.</div></div>`;
  h+=`</div><div class="bloco"><h3>Datas a confirmar</h3>`;
  if(C.parc.length){
    h+=`<p class="muted small" style="margin:0 0 12px">Nestes meses o atrasado cobriu só parte do mês. A data de início foi deduzida do valor pago e pode variar um dia. Confirme no ato (progressão, título, portaria).</p><div class="tw"><table><thead><tr><th class="l">Mês</th><th class="l">Parcela</th><th class="l">Início deduzido</th><th>Valor no mês</th><th class="l">Pago em</th></tr></thead><tbody>`+
      C.parc.map(a=>`<tr><td class="l">${mesTxt(a.comp)}</td><td class="l">${esc(nome(a.cat))}</td><td class="l">${a.diaInicio?'dia '+a.diaInicio+' ('+a.dias+' dias)':''}</td><td>${f2(a.valor)}</td><td class="l">${mesTxt(a.pagoEm)}</td></tr>`).join('')+`</tbody></table></div>`;
  } else h+=`<div class="aviso ok"><span class="ic">✓</span><div>Nenhuma data a confirmar.</div></div>`;
  h+=`</div>`;
  // atrasados que a calculadora distribuiu sozinha: o usuário pode desconsiderar
  const auto=R.log.filter(l=>l.tipo==='retroativo');
  if(auto.length){
    h+=`<details class="bloco"><summary>Atrasados distribuídos automaticamente (${auto.length})</summary><p class="muted small">Pagamentos posteriores que a calculadora ligou aos meses de origem comparando com a tabela ou com o valor do mês seguinte. Desconsidere os que não devem entrar na RBC.</p><div class="tw"><table><thead><tr><th class="l">Parcela</th><th class="l">Pago em</th><th>Valor</th><th class="l">Distribuído em</th><th></th></tr></thead><tbody>`+
      auto.map(l=>`<tr><td class="l">${esc(nome(l.cat))}</td><td class="l">${mesTxt(l.pagoEm)}</td><td>${f2(l.valor)}</td><td class="l">${faixas(l.aloc.map(a=>a.comp))}</td><td><button class="btn link" data-ign="${l.pagoEm}|${l.cat}" data-v="${l.valor}">Desconsiderar</button></td></tr>`).join('')+`</tbody></table></div></details>`;
  }
  if(S.manual.length){
    const logs=R.log.filter(l=>l.tipo==='manual');
    h+=`<div class="bloco"><h3>Distribuições feitas por você</h3>`+S.manual.map((m,i)=>{
      const lg=logs.find(l=>l.cat===m.cat && Math.abs((l.valor||0)-(m.valor||0))<0.005); const tot=lg?lg.aloc.reduce((s,a)=>s+a.valor,0):null;
      const como=m.modo==='igual'?'em partes iguais':m.modo==='unidade'?'em '+rs(m.unidade)+' por mês':(m.pct*100).toLocaleString('pt-BR')+'% do vencimento';
      const dif=tot!=null&&m.valor?m.valor-tot:0;
      return `<div class="item feito"><div class="item-top"><span class="t">${esc(nome(m.cat))}</span><span class="muted small">${dataBr(m.ini)} a ${dataBr(m.fim)}, ${como}</span><span class="v">${tot==null?'':rs(tot)}</span><button class="btn link" data-rm="${i}">Desfazer</button></div>${Math.abs(dif)>0.05?`<p class="d">Pago: ${rs(m.valor)}. Diferença de ${rs(dif)} entre o pago e o calculado.</p>`:''}</div>`; }).join('')+`</div>`;
  }
  const descs=[...Object.entries(S.ack).map(([id,a])=>({tipo:'ack',id,...a})),...Object.entries(S.ignorar).map(([id,a])=>({tipo:'ign',id,...a}))];
  if(descs.length){
    h+=`<div class="bloco"><h3>Desconsiderados por você (${descs.length})</h3><p class="muted small" style="margin:0 0 6px">Ficam fora da RBC e são listados na planilha.</p>`+
      descs.map(d=>`<div class="item"><div class="item-top"><span class="t">${esc(d.desc||nome(d.cat))}</span><span class="muted small">pago em ${mesTxt(d.comp)}</span><span class="v">${rs(d.valor)}</span><button class="btn link" data-undo="${d.tipo}|${esc(d.id)}">Desfazer</button></div></div>`).join('')+`</div>`;
  }
  const pas=R.passivos.map((p,i)=>({p,i})).filter(x=>!S.ack[x.p.id]);
  h+=`<details class="bloco"${Object.keys(S.abertos).some(k=>k[0]==='q')?' open':''}><summary>Passivos e exercícios anteriores (${pas.length})</summary><p class="muted small">Pagamentos judiciais e de exercícios anteriores. Em geral não entram na RBC porque não tiveram contribuição. Distribua só se a DIPROF decidir incluir; desconsidere para registrar a exclusão.</p>`+
    pas.map(({p,i})=>{ const key='q'+i; return `<div class="item"><div class="item-top"><span class="t">${esc(p.desc)}</span><span class="muted small">pago em ${mesTxt(p.comp)}</span><span class="v">${rs(p.valor)}</span>${abrir(key)}${desc(key)}</div>${S.abertos[key]?formDist(key,{cat:'VB',valor:p.valor}):''}</div>`; }).join('')+`</details>`;
  h+=`<div class="bloco"><h3>Contribuição devolvida ao servidor</h3><p class="muted small" style="margin:0 0 10px">Períodos em que a contribuição foi restituída. Continuam na RBC e na média, mas ficam fora da base do benefício especial (coluna própria na planilha). A calculadora preenche o que a ficha informa.</p>`+
    (S.devol.length?`<div class="tw" style="max-height:none"><table class="ed"><thead><tr><th class="l">Fora do benefício especial</th><th class="l">De</th><th class="l">Até</th><th class="l">Origem</th><th></th></tr></thead><tbody>${S.devol.map((p,i)=>`<tr><td><input type="checkbox" data-dvap="${i}"${p.aplicar!==false?' checked':''} aria-label="Excluir do benefício especial"></td><td><input type="date" data-dv="${i}" data-c="ini" value="${esc(p.ini)}" aria-label="Início"></td><td><input type="date" data-dv="${i}" data-c="fim" value="${esc(p.fim)}" aria-label="Fim"></td><td class="l wrap small">${p.semPeriodo&&!(p.ini&&p.fim)?'<span class="tag att">informe o período</span> ':''}${p.origem==='ficha'&&p.aplicar===false?'<span class="tag info">pode ser devolução parcial: marque se foi integral</span> ':''}${esc(p.obs||'informado por você')}</td><td><button class="btn link" data-dvrm="${i}">Remover</button></td></tr>`).join('')}</tbody></table></div>`:'<p class="muted small" style="margin:0 0 8px">Nenhuma devolução encontrada na ficha.</p>')+
    `<button class="btn sec peq" id="dvAdd" style="margin-top:10px">Adicionar período</button></div>`;
  h+=`<div class="bloco"><h3>Lançar outro valor</h3><p class="muted small" style="margin:0 0 10px">Para um valor que não aparece na ficha, como a VPNI judicial informada pela DIPROF.</p>${S.abertos.livre?formDist('livre',{cat:'VB'}):abrir('livre','Lançar valor')}</div>`;
  el.innerHTML=h;
  el.querySelectorAll('[data-abrir]').forEach(b=>b.onclick=()=>{ const k=b.dataset.abrir; S.abertos={[k]:true}; renderTudo(); const f=document.querySelector(`[data-form="${k}"]`); if(f){ f.scrollIntoView({block:'center'}); f.querySelector('input[type=date]').focus(); } });
  el.querySelectorAll('[data-rm]').forEach(b=>b.onclick=()=>{ S.manual.splice(+b.dataset.rm,1); calc(); });
  el.querySelectorAll('input[data-dv]').forEach(x=>x.onchange=()=>{ const p=S.devol[+x.dataset.dv]; if(p){ p[x.dataset.c]=x.value; renderTudo(); } });
  el.querySelectorAll('input[data-dvap]').forEach(x=>x.onchange=()=>{ const p=S.devol[+x.dataset.dvap]; if(p){ p.aplicar=x.checked; renderTudo(); } });
  el.querySelectorAll('[data-dvrm]').forEach(b=>b.onclick=()=>{ S.devol.splice(+b.dataset.dvrm,1); renderTudo(); });
  if($('dvAdd')) $('dvAdd').onclick=()=>{ S.devol.push({ini:'',fim:'',obs:'',origem:'manual',aplicar:true}); renderTudo(); const l=document.querySelectorAll('input[data-dv][data-c="ini"]'); if(l.length) l[l.length-1].focus(); };
  el.querySelectorAll('[data-ack]').forEach(b=>b.onclick=()=>{ const k=b.dataset.ack, i=+k.slice(1);
    const p=k[0]==='p'?R.pend[i]:R.passivos[i]; if(!p) return;
    S.ack[p.id]={cat:p.cat||'PASSIVO',desc:p.desc||'',comp:p.comp,valor:p.valor}; renderTudo(); });
  el.querySelectorAll('[data-ign]').forEach(b=>b.onclick=()=>{ const [comp,cat]=b.dataset.ign.split('|'); S.ignorar[comp+'|'+cat]={cat,comp,valor:+b.dataset.v}; calc(); });
  el.querySelectorAll('[data-undo]').forEach(b=>b.onclick=()=>{ const [t,...r]=b.dataset.undo.split('|'); const id=r.join('|'); if(t==='ack') delete S.ack[id]; else delete S.ignorar[id]; calc(); });
  for(const key of Object.keys(S.abertos)){
    let o={cat:'VB'};
    if(key[0]==='p'){ const p=R.pend[+key.slice(1)]; if(p) o={cat:p.cat,valor:p.valor,id:p.id,origem:p.comp}; }
    else if(key[0]==='q'){ const p=R.passivos[+key.slice(1)]; if(p) o={cat:'VB',valor:p.valor,id:p.id,origem:p.comp}; }
    if(document.querySelector(`[data-form="${key}"]`)) ligarForm(key,o);
  }
}

// ------------------------------------------------------------ etapa 4
const SIT_TXT={ok:'confere',comp:'diferença no mês, compensada no ano',att:'diferença a verificar',nv:'não verificado',none:'sem ficha'};
const SIT_CMP={'moeda diferente':['none','Ficha em outra escala de moeda'],'pago a menor':['att','Pago abaixo do esperado'],'pago a maior':['comp','Pago acima do esperado'],'não pago':['att','Esperado e não pago'],'pago sem previsão':['comp','Pago sem previsão nos relatórios'],'sem ficha':['none','Sem ficha']};
const GRUPO_NOME={TOTAL:'Remuneração total',VPNI:'VPNI (inclui judicial)',GAJ:'GAJ / abono',VPI:'VPI'};
function renderComparacao(C){
  const el=$('comparacao');
  if(!S.esp){ el.innerHTML=`<div class="bloco"><h3>Remuneração esperada × paga</h3><div class="aviso info" style="margin:0"><span class="ic">i</span><div>Para comparar o que foi pago com o que era devido, informe o cargo e a progressão na etapa 1. <button class="btn link" id="irE1">Ir para a etapa 1</button></div></div></div>`; $('irE1').onclick=()=>irPara(1); return; }
  const cmp=S.cmp||[]; const gr={};
  for(const m of cmp) for(const i of m.itens){ if(i.sit==='sem ficha') continue; const k=i.cat+'|'+i.sit; const g=gr[k]||(gr[k]={cat:i.cat,sit:i.sit,meses:[],soma:0}); g.meses.push(m.comp); g.soma+=i.dif; }
  const lista=Object.values(gr).sort((a,b)=>b.meses.length-a.meses.length);
  const comFicha=cmp.filter(m=>m.itens.every(i=>i.sit!=='sem ficha'));
  const iguais=comFicha.filter(m=>!m.itens.length).length;
  const av=S.esp.avisos;
  el.innerHTML=`<div class="bloco"><h3>Remuneração esperada × paga</h3>
    <p class="muted small" style="margin:0 0 12px">A esperada vem dos relatórios do RH e das tabelas de remuneração; a paga, da ficha (antes das regras de incidência). A RBC usa os valores pagos; as diferenças abaixo mostram onde conferir: erro de pagamento, relatório incompleto ou parcela fora da base.</p>
    <div class="numeros"><div><span>Meses comparados</span><b>${comFicha.length}</b></div><div><span>Pagos como esperado</span><b style="color:var(--ok)">${iguais}</b></div><div><span>Com diferença</span><b style="color:${comFicha.length-iguais?'var(--att)':'var(--ok)'}">${comFicha.length-iguais}</b></div></div>
    ${lista.length?`<div class="tw"><table><thead><tr><th class="l">Parcela</th><th class="l">O que aconteceu</th><th class="l">Períodos</th><th>Meses</th><th>Pago − esperado</th></tr></thead><tbody>${lista.map(g=>`<tr class="clic" data-mes="${g.meses[0]}" tabindex="0"><td class="l">${esc(GRUPO_NOME[g.cat]||nome(g.cat))}</td><td class="l"><span class="sit ${SIT_CMP[g.sit][0]}">${SIT_CMP[g.sit][1]}</span></td><td class="l wrap">${faixas(g.meses)}</td><td>${g.meses.length}</td><td>${f2(RBC.r2(g.soma))}</td></tr>`).join('')}</tbody></table></div><p class="muted small" style="margin:8px 0 0">Clique em uma linha para ver o primeiro mês no detalhe abaixo.</p>`:'<div class="aviso ok"><span class="ic">✓</span><div>Todos os meses foram pagos como esperado.</div></div>'}
    ${av.length?`<div class="aviso att"><span class="ic">!</span><div>Avisos da remuneração esperada: ${av.map(a=>esc(a.texto)+' ('+faixas(a.meses)+')').join('; ')}.</div></div>`:''}
  </div>`;
  el.querySelectorAll('tr[data-mes]').forEach(tr=>{ const go=()=>{ S.sel=tr.dataset.mes; renderConferencia(C); $('detalhe').scrollIntoView({block:'start'}); }; tr.onclick=go; tr.onkeydown=e=>{ if(e.key==='Enter') go(); }; });
}
function renderConferencia(C){
  const R=S.res; if(!R) return;
  const pend=[]; if(C.naoRec.length) pend.push(`${C.naoRec.length} rubrica(s) não reconhecida(s)`); if(C.pend.length) pend.push(`${C.pend.length} valor(es) sem mês`); if(C.none) pend.push(`${C.none} mês(es) sem ficha`);
  const ok=!C.att && !pend.length;
  const titulo = ok ? 'A RBC está consistente com a ficha' : C.att ? `A contribuição não confere em ${C.att} ano(s)` : 'Há pendências antes de gerar';
  const lista = C.anosAtt.map(a=>`<li><b>${a.ano}</b>: diferença de ${rs(a.dif)} ${a.dif>0?'(descontado a mais do que a RBC explica)':'(descontado a menos do que a RBC exige)'}${a.causas.length?'. Provável causa: '+esc(a.causas.join('; ')):'. Sem causa identificada: confira a composição dos meses em laranja'}.</li>`).join('');
  $('veredito').innerHTML=`<div class="veredito ${ok?'ok':'att'}"><div class="selo" aria-hidden="true">${ok?'✓':'!'}</div><div>
    <h3>${titulo}</h3>
    <p>${C.anosVerif?`A contribuição descontada confere com a RBC em ${C.anosOk} de ${C.anosVerif} anos verificáveis (tolerância de 1% da contribuição do ano).`:'Nenhum ano verificável no período.'}${C.nv?` Antes de ${mesTxt(R.regras.conferirDesde)} não há verificação.`:''}${S.cmp?` O pagamento difere do esperado em ${C.divMes.size} mês(es); veja abaixo.`:''}</p>
    ${pend.length?`<p>Pendente: ${pend.join('; ')}. <button class="btn link" id="irPend">Resolver</button></p>`:''}
  </div></div>
  ${lista?`<details class="bloco"${C.anosAtt.length<=6?' open':''}><summary>Anos com diferença na contribuição (${C.anosAtt.length})</summary><ul style="margin:10px 0 0;padding-left:20px;display:grid;gap:6px">${lista}</ul></details>`:''}
  <div class="numeros"><div><span>Contribuição descontada na ficha</span><b>${rs(R.resumo.pssFicha)}</b></div><div><span>Contribuição esperada pela RBC</span><b>${rs(R.resumo.pssCalc)}</b></div><div><span>Diferença no período</span><b style="color:${Math.abs(R.resumo.dif)>1?'var(--att)':'var(--ok)'}">${rs(R.resumo.dif)}</b></div></div>`;
  if($('irPend')) $('irPend').onclick=()=>irPara(C.naoRec.length?2:C.pend.length?3:2);
  renderComparacao(C);
  const gn={}; for(const g of R.gns) gn[g.ano]=g;
  const anos=[...new Set(R.meses.map(k=>k.slice(0,4)))];
  const parcMes=new Set(C.parc.map(p=>p.comp));
  let m='<span></span>'+MESES.map(x=>`<span class="cab">${x}</span>`).join('')+'<span class="cab">13º</span><span class="cab">ano</span>';
  for(const y of anos){
    m+=`<span class="ano">${y}</span>`;
    for(let i=1;i<=12;i++){ const k=y+'-'+String(i).padStart(2,'0'); const s=C.sit[k];
      if(!s){ m+='<span class="cel vazio"></span>'; continue; }
      const dv=C.divMes.has(k);
      const rot=mesTxt(k)+': contribuição '+SIT_TXT[s]+(parcMes.has(k)?', data a confirmar':'')+(dv?', pagamento diferente do esperado':'');
      m+=`<button class="cel ${s}${parcMes.has(k)?' parc':''}${dv?' div':''}${S.sel===k?' sel':''}" data-k="${k}" title="${rot}" aria-label="${rot}"></button>`; }
    m+= gn[y]?`<button class="cel gn${S.sel==='GN'+y?' sel':''}" data-k="GN${y}" title="13º de ${y}" aria-label="13º de ${y}"></button>`:'<span class="cel vazio"></span>';
    const ay=C.anos[y]; m+= !ay||!ay.verif?'<span class="anoSt"></span>':ay.ok?`<span class="anoSt ok" title="${y}: confere no ano">✓</span>`:`<span class="anoSt att" title="${y}: diferença de ${rs(ay.dif)}">!</span>`;
  }
  $('mapa').innerHTML=m;
  $('legDiv').hidden=!S.cmp;
  $('mapa').querySelectorAll('button.cel').forEach(b=>b.onclick=()=>{ S.sel=b.dataset.k; renderConferencia(C); const d=$('detalhe'); if(d.getBoundingClientRect().top>window.innerHeight-120) d.scrollIntoView({block:'nearest'}); });
  renderDetalhe(C); renderTabela(C);
  const alt=regrasAlteradas(); $('regrasResumo').textContent = alt.length?`(${alt.length} alterada(s) em relação ao padrão)`:'(padrão DIPROF)';
}
function renderDetalhe(C){
  const R=S.res, el=$('detalhe'); if(!S.sel){ el.hidden=true; return; } el.hidden=false;
  if(S.sel.startsWith('GN')){ const g=R.gns.find(x=>'GN'+x.ano===S.sel); if(!g){el.hidden=true;return;}
    el.innerHTML=`<h3 style="margin:0 0 8px">13º de ${g.ano}</h3><div style="max-width:460px"><div class="lin"><span>Base: remuneração de ${mesTxt(g.baseComp)}${g.obs?', sem VPI':''}</span><span>${rs(g.base)}</span></div><div class="lin"><span>Meses no ano</span><span>${g.avos}/12</span></div><div class="lin tot"><span>Valor na RBC</span><span>${rs(g.valor)}</span></div></div>`; return; }
  const l=R.linhas.find(x=>x.comp===S.sel); if(!l){ el.hidden=true; return; }
  const s=C.sit[l.comp], e=S.espBy[l.comp];
  const cats=[...new Set([...Object.keys(e?e.v:{}),...Object.keys(l.bruto||{}),...Object.keys(l.v)])].filter(c=>(e&&Math.abs(e.v[c]||0)>=0.005)||Math.abs((l.bruto||{})[c]||0)>=0.005||Math.abs(l.v[c]||0)>=0.005);
  const ordem=RBC.REMUN.concat(['VPNI_JUD_SEM_PSS']); cats.sort((a,b)=>(ordem.indexOf(a)+1||99)-(ordem.indexOf(b)+1||99));
  const linhas=cats.map(c=>{ const ve=e?(e.v[c]||0):null, vp=(l.bruto||{})[c]||0, dif=e&&Math.abs(vp-ve)>0.05; return `<tr${dif?' class="dif"':''}><td class="l">${esc(nome(c))}</td>${e?`<td>${f2(ve||null)}</td>`:''}<td>${f2(vp||null)}</td><td>${f2(l.v[c]||null)}</td></tr>`; }).join('');
  const ajTxt=l.ajustes?`<div class="aviso info"><span class="ic">i</span><div>Pela tabela neste mês: ${esc(l.ajustes.join('; '))}. A coluna "Pago" mostra a ficha.</div></div>`:'';
  const tabTxt=l.daTabela?`<div class="aviso info"><span class="ic">i</span><div>Competência anterior a 07/1994: a RBC usa a tabela de remuneração (coluna "Esperado"); a ficha fica só como conferência.</div></div>`:'';
  const parc=l.parcialInferido&&l.parcialInferido.length?`<div class="aviso info"><span class="ic">i</span><div>Data a confirmar: ${l.parcialInferido.map(p=>esc(nome(p.cat))+(p.diaInicio?' a partir do dia '+p.diaInicio:'')).join('; ')}.</div></div>`:'';
  const txt={ok:'A contribuição descontada confere com a esperada.',comp:'Há diferença na contribuição deste mês, mas o ano confere. Em geral é atrasado: a contribuição é descontada no mês em que ele é pago.',att:'O ano não confere. Veja a provável causa no quadro "Anos com diferença" e confira a composição abaixo.',nv:'Antes de '+mesTxt(R.regras.conferirDesde)+' a calculadora não modela as alíquotas e devoluções da época; a contribuição do mês não é verificada.',none:'Não há ficha para este mês. Envie a ficha correspondente na etapa 2.'}[s];
  const info=e?[e.ref&&'enquadramento '+e.ref, e.funcao&&'função '+e.funcao, e.subst&&'substituição '+e.subst, e.vpni&&'VPNI '+e.vpni, e.aq&&'AQ '+e.aq, e.atsPct&&'ATS '+(e.atsPct*100).toLocaleString('pt-BR')+'%'].filter(Boolean).join(' · '):'';
  el.innerHTML=`<h3 style="margin:0 0 4px">${mesTxt(l.comp)}${moedaDe(l.comp)!=='R$'?` <span class="tag info">valores em ${moedaDe(l.comp)} · fora da média</span>`:''}</h3>${info?`<p class="small" style="margin:0 0 4px">Pelos relatórios: ${esc(info)}</p>`:''}<p class="muted small" style="margin:0">${txt}</p>${tabTxt}${ajTxt}${parc}
   <div class="cols2"><div><div class="tw" style="max-height:none"><table><thead><tr><th class="l">Parcela</th>${e?'<th>Esperado</th>':''}<th>Pago</th><th>Na RBC</th></tr></thead><tbody>${linhas||'<tr><td class="l">Sem valores</td></tr>'}</tbody>
     <tfoot><tr class="tot"><td class="l">Remuneração de contribuição</td>${e?`<td>${f2(e.total)}</td>`:''}<td></td><td>${f2(l.total)}</td></tr></tfoot></table></div>
     ${e?'<p class="muted small" style="margin:6px 0 0">"Pago" é o valor da ficha já ligado ao mês de origem, antes das regras de incidência; "Na RBC", o que entra na relação.</p>':''}</div>
   <div><b class="small">Contribuição previdenciária</b><div class="lin"><span>Descontada na ficha</span><span>${l.fonte?rs(l.pssFicha):'—'}</span></div><div class="lin"><span>Calculada sobre a RBC</span><span>${rs(l.pssCalc)}</span></div><div class="lin tot"><span>Diferença</span><span>${l.fonte&&l.conferir?rs(l.dif):'—'}</span></div>${e?`<div class="lin"><span>Calculada sobre a esperada</span><span>${rs(e.pss)}</span></div>`:''}${(()=>{ const b=baseBE(l); return b!=null&&Math.abs(b-l.total)>0.005?`<div class="lin"><span>Base do benefício especial (contribuição devolvida em ${fracDevolvida(l.comp).dias} dia(s))</span><span>${rs(b)}</span></div>`:''; })()}</div></div>`;
}
function renderTabela(C){
  if(!$('tabelaBox').open || !S.res) return;
  const R=S.res, ver=$('verParcelas').checked;
  const usadas=ver?RBC.REMUN.filter(c=>R.linhas.some(l=>l.v[c])):[];
  const gnPor={}; for(const g of R.gns) gnPor[g.depois]=g;
  const sitHtml={ok:'<span class="sit ok">Confere</span>',comp:'<span class="sit comp">Compensada no ano</span>',att:'<span class="sit att">Verificar</span>',nv:'<span class="sit none">Não verificado</span>',none:'<span class="sit none">Sem ficha</span>'};
  const temE=!!S.esp, temM=R.linhas.some(l=>!naMedia(l.comp));
  let rows='';
  for(const l of R.linhas){
    const e=S.espBy[l.comp];
    rows+=`<tr class="${!l.fonte?'sem':''}"><td class="l">${mesTxt(l.comp)}</td>${temM?`<td class="l">${moedaDe(l.comp)}</td>`:''}${usadas.map(c=>`<td>${f2(l.v[c])}</td>`).join('')}<td><b>${f2(l.total)}</b></td>${temE?`<td>${e?f2(e.total):''}</td>`:''}<td>${l.fonte?f2(l.pssFicha):''}</td><td>${f2(l.pssCalc)}</td><td class="l">${sitHtml[C.sit[l.comp]]}${l.conferir&&l.fonte&&Math.abs(l.dif)>0.5?' <span class="muted small">'+f2(l.dif)+'</span>':''}</td></tr>`;
    const g=gnPor[l.comp]; if(g) rows+=`<tr class="gn"><td class="l">13º ${g.ano}</td>${temM?'<td></td>':''}${usadas.map(()=>'<td></td>').join('')}<td>${f2(g.valor)}</td>${temE?'<td></td>':''}<td></td><td></td><td class="l">${g.avos}/12</td></tr>`;
  }
  $('resultado').innerHTML=`<div class="tw"><table><thead><tr><th class="l">Mês</th>${temM?'<th class="l">Moeda</th>':''}${usadas.map(c=>`<th>${esc(CURTO[c]||c)}</th>`).join('')}<th>Remuneração (RBC)</th>${temE?'<th>Esperada</th>':''}<th>PSS descontada</th><th>PSS sobre a RBC</th><th class="l">Contribuição</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
$('tabelaBox').addEventListener('toggle',()=>renderTabela(contagens()));
$('verParcelas').onchange=()=>renderTabela(contagens());

// ------------------------------------------------------------ escolhas salvas
function baixar(blob,nomeArq){ const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=nomeArq; document.body.appendChild(a); a.click(); setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove();},500); }
$('x_dec').onclick=()=>{
  const sv={versao:2, devol:S.devol, regras:getRegras(), cats:S.cats, manual:S.manual, ignorar:S.ignorar, ack:S.ack, rel:S.rel,
    servidor:{cargo:$('cargo').value, especialidade:$('especialidade').value, espDesde:$('espDesde').value, inicio:$('inicio').value, fim:$('fim').value}};
  baixar(new Blob([JSON.stringify(sv,null,1)],{type:'application/json'}),'escolhas_rbc.json');
  $('x_msg').textContent='Escolhas salvas (relatórios conferidos, distribuições e regras). Para refazer, envie a mesma ficha e abra este arquivo.'; };
$('x_load').onclick=()=>$('decfile').click();
$('decfile').onchange=async e=>{ const f=e.target.files[0]; if(!f) return; try{ const d=JSON.parse(await f.text());
  setRegras(Object.assign({},RBC.REGRAS_PADRAO,d.regras||{})); S.cats=d.cats||{}; S.manual=d.manual||[]; S.ignorar=d.ignorar||{}; S.ack=d.ack||{}; if(d.devol) S.devol=d.devol;
  if(d.rel) for(const t of TIPOS_REL) S.rel[t]=d.rel[t]||[];
  const sv=d.servidor||{inicio:d.inicio,fim:d.fim}; for(const k of ['cargo','especialidade','espDesde','inicio','fim']) if(sv[k]!=null) $(k).value=sv[k];
  renderRelTabelas(); calc(); $('x_msg').textContent='Escolhas aplicadas.'; }catch(err){ $('x_msg').textContent='Este arquivo não é um arquivo de escolhas da calculadora.'; } e.target.value=''; };

// ------------------------------------------------------------ exportação (modelo DIPROF)
const COLS = { C:['VB','SUBSIDIO'], D:['DIF2886'], E:['GEXTRA'], F:['GAJ'], G:['APJ'], H:['REDUTOR'], J:['ATS'], K:['VPI','VPI_DED'], M:['VPNI'], N:['VPNI_JUD'], Q:['FC','SUBST','V1323_FC','FC_PREV'], R:['V1323_VB'], S:['V1323_GAJ'], T:['V1323_ATS'], U:['V1323_VPNI'], V:['AQ','AQ_TREIN'], W:['GAE','GAS'], AA:['FALTAS','V1198'] };
const HEAD = { A:' ', B:'CLASSE/ PADRÃO', C:'Vencimento', D:'Dif. Lei 8622/8627', E:'Grat Extraordinária 170%', F:'GAJ / Abono', G:'APJ', H:'(Redutor)', I:'ATS (%)', J:'ATS- Valor', K:'VPI', L:'VPNI', M:'VPNI-Valor', N:'VPNI Judicial', O:'Função', P:'Substituição', Q:'Valor - FC/Subst', R:'13,23% Vencimento', S:'13,23% GAJ', T:'13,23% ATS', U:'13,23% VPNI', V:'AQP', W:'GAE/GAS', X:'Remuneração', Y:'Fator de conversão', Z:'Remuneração em real', AA:'Outros (faltas / 11,98%)' };
const SOMA = ['C','D','E','F','G','H','J','K','M','N','Q','R','S','T','U','V','W'];
$('x_rbc').onclick=async()=>{
  const R=S.res; if(!R) return;
  const btn=$('x_rbc'); btn.disabled=true; btn.textContent='Gerando…';
  try{
    const wb=new ExcelJS.Workbook(); wb.creator='Calculadora de RBC — TRT-17';
    const ws=wb.addWorksheet('RBC',{views:[{state:'frozen',ySplit:4,xSplit:1}]});
    const temOutros=R.linhas.some(l=>l.v.FALTAS||l.v.V1198);
    const letras=['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z'].concat(temOutros?['AA']:[]);
    const temPre=R.linhas.some(l=>!naMedia(l.comp)); const cMoeda=temOutros?'AB':'AA', cMedia=temOutros?'AC':'AB';
    if(temPre){ letras.push(cMoeda,cMedia); HEAD[cMoeda]='Moeda'; HEAD[cMedia]='Entra na média'; }
    const cBE=temPre?(temOutros?'AD':'AC'):(temOutros?'AB':'AA'); letras.push(cBE); HEAD[cBE]='Base p/ benefício especial';
    const nm=$('nome').value.trim(), cargo=$('cargo').value;
    const fd=d=>d?d.split('-').reverse().join('-'):'';
    const espTxt={SEGURANCA:'Agente de segurança / polícia judicial',OFICIAL:'Oficial de justiça'}[$('especialidade').value];
    ws.getCell('A1').value=nm||'(nome)'; ws.getCell('A1').font={bold:true,size:12};
    ws.getCell('A2').value=[cargo,espTxt].filter(Boolean).join(' — ');
    ws.getCell('A3').value=`Período de ${fd(iniEf())} a ${fd(fimEf())}`;
    letras.forEach(c=>{ const cell=ws.getCell(c+'4'); cell.value=HEAD[c]; cell.font={bold:true,size:9}; cell.alignment={wrapText:true,vertical:'middle',horizontal:'center'}; cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FFE4EDF3'}}; cell.border={bottom:{style:'thin'}}; });
    ws.getRow(4).height=42;
    const somaCols=SOMA.concat(temOutros?['AA']:[]);
    let r=5; const linhaDe={}; const gnPor={}; for(const g of R.gns) gnPor[g.depois]=g;
    const cod=s=>String(s||'').split(' / ').map(x=>x.replace(/\s*\(.*$/,'')).filter(Boolean).join(' / ');
    for(const l of R.linhas){
      const y=+l.comp.slice(0,4), m=+l.comp.slice(5,7), e=S.espBy[l.comp];
      ws.getCell('A'+r).value=new Date(Date.UTC(y,m-1,1)); ws.getCell('A'+r).numFmt='mmm-yy';
      ws.getCell('B'+r).value=e&&e.ref?e.ref:(l.ref||'').replace(' (inferido)','');
      if(e){ if(e.vpni) ws.getCell('L'+r).value=e.vpni.replace(/\s*\(\d+\/\d+ judicial\)/g,''); if(e.funcao) ws.getCell('O'+r).value=cod(e.funcao); if(e.subst) ws.getCell('P'+r).value=e.subst; }
      for(const [c,cats] of Object.entries(COLS)){ if(c==='AA'&&!temOutros) continue; const v=cats.reduce((s,k)=>s+(l.v[k]||0),0); if(Math.abs(v)>=0.005) ws.getCell(c+r).value=RBC.r2(v); }
      if(l.atsPct) ws.getCell('I'+r).value=l.atsPct;
      const notas=[];
      if(l.parcialInferido && l.parcialInferido.length) notas.push('Data a confirmar: '+l.parcialInferido.map(p=>nome(p.cat)+(p.diaInicio?' a partir do dia '+p.diaInicio:'')).join('; '));
      if(l.daTabela) notas.push('Valores da tabela de remuneração (competência anterior a 07/1994)');
      if(l.ajustes) notas.push('Pela tabela: '+l.ajustes.join('; '));
      if(!l.fonte) notas.push('Sem ficha financeira para esta competência');
      if(notas.length) ws.getCell('B'+r).note=notas.join('. ');
      { const soma=somaCols.map(c=>c+r).join('+'); ws.getCell('X'+r).value={formula:l.tetoRGPS!=null?`MIN(${soma},${l.tetoRGPS})`:soma, result:l.total};
        if(l.tetoRGPS!=null) ws.getCell('X'+r).note=`Base limitada ao teto do RGPS (${fmt.format(l.tetoRGPS)}) — regime de previdência complementar`;
        else if(l.semFicha) ws.getCell('X'+r).note='Sem ficha para este mês: remuneração esperada pela tabela'; }
      if(naMedia(l.comp)){ ws.getCell('Y'+r).value=1; ws.getCell('Z'+r).value={formula:`X${r}/Y${r}`, result:l.total}; }
      if(temPre){ ws.getCell(cMoeda+r).value=moedaDe(l.comp); ws.getCell(cMedia+r).value=naMedia(l.comp)?'sim':'não'; }
      { const b=baseBE(l); if(b!=null){ const {dias,n}=fracDevolvida(l.comp); ws.getCell(cBE+r).value=dias?{formula:dias>=n?'0':`ROUND(X${r}/${n}*${n-dias},2)`,result:b}:{formula:`X${r}`,result:b}; if(dias) ws.getCell(cBE+r).note=`Contribuição devolvida em ${dias} de ${n} dia(s): fora da base do benefício especial`; } }
      linhaDe[l.comp]=r; r++;
      const g=gnPor[l.comp];
      if(g){ const rb=linhaDe[g.baseComp]; ws.getCell('A'+r).value='GN'; ws.getCell('B'+r).value=g.avos<12?g.avos+'/12':'';
        const base=g.obs==='sem VPI'?`(X${rb}-K${rb})`:`X${rb}`; let f=g.avos<12?`ROUND(${base}/12*${g.avos},2)`:base; if(g.tetoRGPS!=null) f=`MIN(${f},${g.tetoRGPS})`;
        if(g.daFicha){ ws.getCell('X'+r).value=g.valor; ws.getCell('X'+r).note='13º pelo valor pago na ficha (gratificação natalina do ano, sem o adiantamento)'; } else ws.getCell('X'+r).value={formula:f,result:g.valor}; if(naMedia(g.depois)){ ws.getCell('Y'+r).value=1; ws.getCell('Z'+r).value={formula:`X${r}/Y${r}`,result:g.valor}; }
        ws.getRow(r).font={bold:true}; r++; }
    }
    const ultima=r-1;
    for(let i=5;i<=ultima;i++){ for(const c of letras.slice(2)) if(!['I','L','O','P','Y',cMoeda,cMedia].includes(c)) ws.getCell(c+i).numFmt='#,##0.00'; ws.getCell('I'+i).numFmt='0.0%'; }
    r+=1;
    const notas=[];
    if($('processo').value.trim()) notas.push('Processo: '+$('processo').value.trim());
    const rg=getRegras();
    notas.push(`Regras: 11,98% de ${rg.ajuste1198Desde} a ${rg.ajuste1198Ate||'—'}; FC/substituição até ${rg.fcAte}; ATS a partir de ${rg.atsDesde}; GAS ${rg.gas?'incide':'não incide'}; AQ-Treinamento ${rg.aqTrein==='ficha'?'conforme a ficha (entra no ano em que houve contribuição sobre ele'+(Object.keys(R.aqTreinAnos||{}).length?': '+(Object.entries(R.aqTreinAnos).filter(e=>e[1]).map(e=>e[0]).join(', ')||'nenhum ano'):'')+')':rg.aqTrein?'incide':'não incide'}; faltas ${rg.descontarFaltas?'descontadas':'não descontadas'}; GN a partir de ${rg.gnDesde||'—'}${rg.gnSemVPIAte?', sem VPI até '+rg.gnSemVPIAte:''}; pro rata pelos dias do mês a partir de ${rg.divisorDiasDesde} (Res. CSJT 211/2017; antes, mês de 30 dias); AQ e AQ-Treinamento conferidos pela ficha: direito presumido quando pagos, valor devido pela tabela da carreira.`);
    if(R.linhas.some(l=>l.daTabela)) notas.push(`Até ${mesTxt(rg.tabelaAte)}, valores pelas tabelas de remuneração da época (prática da DIPROF), com pro rata pelos dias do mês; função, substituição e lançamentos sem tabela conforme a ficha ou informados.`);
    { const comBE=R.linhas.filter(l=>{const b=baseBE(l); return b!=null&&b>0;}).length, dv=S.devol.filter(p=>p.aplicar!==false&&p.ini&&p.fim);
      notas.push(`Base p/ benefício especial (Lei 12.618/2012, art. 3º, § 2º): remuneração das competências a partir de 07/1994 com contribuição mantida; ${dv.length?'excluídos os períodos de contribuição devolvida: '+dv.map(p=>fd(p.ini)+' a '+fd(p.fim)).join('; ')+' (pro rata pelos dias do mês)':'sem períodos de contribuição devolvida informados'}. Competências com base positiva: ${comBE} (13º não incluído).`); }
    if(R.linhas.some(l=>l.ajustes)) notas.push(`Pela tabela (modelo da DIPROF), nas competências indicadas: ${rg.vpniTabela!==false?'VPNI conforme o relatório de VPNI, exceto dez/1999 a dez/2005 (VPNI judicial sem contribuição: valor da ficha); ':''}${rg.fcTabela!==false?'função e redutor até '+mesTxt(rg.fcAte)+'; ':''}parcelas do cargo efetivo nos meses sem vencimento na ficha.`);
    if(temPre) notas.push('Competências anteriores a 07/1994 na moeda da época, sem conversão (fator e remuneração em real em branco). A média da aposentadoria considera só as competências a partir de 07/1994 (Lei 10.887/2004, art. 1º; EC 103/2019, art. 26).');
    notas.push('Valores conforme a ficha financeira (remuneração paga). Classe/padrão, VPNI, função e substituição conforme os relatórios do RH. Divergências entre o pago e o esperado na aba "Esperada x paga".');
    for(const m of S.manual) notas.push(`Distribuição manual: ${nome(m.cat)} ${m.modo==='percentualVB'?(m.pct*100).toLocaleString('pt-BR')+'% do vencimento':'R$ '+f2(m.valor)+(m.modo==='unidade'?' em parcelas de '+f2(m.unidade):' em partes iguais')} de ${fd(m.ini)} a ${fd(m.fim)}${m.origem&&m.origem!=='manual'?' (pago em '+m.origem+')':''}.`);
    for(const a of Object.values(S.ack)) notas.push(`Desconsiderado: ${a.desc||nome(a.cat)}, R$ ${f2(a.valor)} pago em ${mesTxt(a.comp)}.`);
    for(const a of Object.values(S.ignorar)) notas.push(`Desconsiderado: atrasado de ${nome(a.cat)}, R$ ${f2(a.valor)} pago em ${mesTxt(a.comp)}.`);
    const pendN=R.pend.filter(p=>!S.ack[p.id]).length; if(pendN) notas.push(`Valores sem mês não distribuídos: ${pendN} (ver aba Ajustes).`);
    notas.push('Gerado pela Calculadora de RBC. Conferência da contribuição na aba "Conferência PSS".');
    for(const t of notas){ ws.getCell('A'+r).value=t; ws.getCell('A'+r).font={size:9,italic:true}; r++; }
    const larg={A:9,B:10,I:7,L:16,O:9,P:9,Y:7,[cBE]:13}; letras.forEach(c=>ws.getColumn(c).width=larg[c]||10.5);
    ws.pageSetup={orientation:'landscape',fitToPage:true,fitToWidth:1,fitToHeight:0,paperSize:9};

    const C=contagens();
    const wc=wb.addWorksheet('Conferência PSS',{views:[{state:'frozen',ySplit:1}]});
    wc.columns=[{header:'Competência',key:'c',width:12},{header:'Remuneração (RBC)',key:'t',width:16},{header:'PSS descontada (ficha)',key:'f',width:18},{header:'PSS sobre a RBC',key:'p',width:16},{header:'Diferença',key:'d',width:12},{header:'Diferença acumulada',key:'a',width:18},{header:'Situação',key:'o',width:30}];
    for(const l of R.linhas) wc.addRow({c:l.comp,t:l.total,f:l.fonte?l.pssFicha:null,p:l.pssCalc,d:l.conferir&&l.fonte?l.dif:null,a:l.acumDif,o:SIT_TXT[C.sit[l.comp]]});
    wc.addRow({}); wc.addRow({c:'Ano',f:'PSS ficha',p:'PSS sobre a RBC',d:'Diferença'}).font={bold:true};
    for(const a of R.porAno) wc.addRow({c:a.ano,f:a.pssFicha,p:a.pssCalc,d:a.dif,o:(!a.conferir?'não verificado':'')+(a.mesesSemFicha?' '+a.mesesSemFicha+' mês(es) sem ficha':'')});
    wc.getRow(1).font={bold:true}; ['B','C','D','E','F'].forEach(c=>wc.getColumn(c).numFmt='#,##0.00');

    if(S.esp){
      const cats=[...new Set(S.esp.linhas.flatMap(l=>Object.keys(l.v)))];
      const ordem=RBC.REMUN.concat(['VPNI_JUD_SEM_PSS']); cats.sort((a,b)=>(ordem.indexOf(a)+1||99)-(ordem.indexOf(b)+1||99));
      const we=wb.addWorksheet('Esperada',{views:[{state:'frozen',ySplit:1,xSplit:1}]});
      we.columns=[{header:'Competência',width:12},{header:'Classe/padrão',width:12},{header:'Função',width:12},{header:'Substituição',width:12},{header:'VPNI',width:24},{header:'ATS (%)',width:8}].concat(cats.map(c=>({header:CURTO[c]||nome(c),width:12})),[{header:'Remuneração esperada',width:16},{header:'PSS esperada',width:13},{header:'Remuneração paga (RBC)',width:16},{header:'Diferença',width:12}]);
      for(const l of S.esp.linhas){ const rl=R.linhas.find(x=>x.comp===l.comp);
        we.addRow([l.comp,l.refCurta,cod(l.funcao),l.subst,l.vpni,l.atsPct||null].concat(cats.map(c=>l.v[c]||null),[l.total,l.pss,rl?rl.total:null,rl?RBC.r2(rl.total-l.total):null])); }
      we.getRow(1).font={bold:true}; we.getRow(1).alignment={wrapText:true,vertical:'middle'}; we.getColumn(6).numFmt='0.0%';
      for(let i=7;i<=6+cats.length+4;i++) we.getColumn(i).numFmt='#,##0.00';
      if(S.esp.avisos.length){ we.addRow([]); for(const a of S.esp.avisos) we.addRow(['Aviso',a.texto+': '+faixas(a.meses)]); }
      const wx=wb.addWorksheet('Esperada x paga',{views:[{state:'frozen',ySplit:1}]});
      wx.columns=[{header:'Competência',width:12},{header:'Parcela',width:30},{header:'Situação',width:30},{header:'Esperado',width:13},{header:'Pago (ficha)',width:13},{header:'Pago − esperado',width:15}];
      for(const m of (S.cmp||[])) for(const i of m.itens) wx.addRow([m.comp,GRUPO_NOME[i.cat]||nome(i.cat),(SIT_CMP[i.sit]||[,i.sit])[1],i.esperado,i.recebido,i.dif]);
      wx.getRow(1).font={bold:true}; [4,5,6].forEach(c=>wx.getColumn(c).numFmt='#,##0.00');
      wx.autoFilter={from:'A1',to:'F1'};
    }

    const wa=wb.addWorksheet('Ajustes');
    wa.columns=[{header:'Tipo',width:20},{header:'Parcela',width:28},{header:'Pago em',width:10},{header:'Competência',width:12},{header:'Valor',width:12},{header:'Fração do mês',width:12},{header:'Início deduzido',width:14},{header:'Observação',width:40}];
    const tipo={retroativo:'atrasado distribuído',manual:'distribuição manual',pico:'atrasado no mês'};
    for(const l of R.log) for(const a of (l.aloc||[])) wa.addRow([tipo[l.tipo]||l.tipo,nome(l.cat),l.pagoEm||'',a.comp,a.valor,a.fracao<1?a.fracao:null,a.diaInicio?'dia '+a.diaInicio:'',a.fonteNivel||'']);
    for(const p of R.pend) wa.addRow(['sem mês',nome(p.cat),p.comp,'',p.valor,null,'',S.ack[p.id]?'desconsiderado':'não incluído na RBC']);
    for(const a of Object.values(S.ignorar)) wa.addRow(['atrasado desconsiderado',nome(a.cat),a.comp,'',a.valor,null,'','não incluído na RBC']);
    for(const p of R.passivos) wa.addRow(['passivo',p.desc,p.comp,'',p.valor,null,'',S.ack[p.id]?'desconsiderado':'não incluído salvo distribuição manual']);
    wa.getRow(1).font={bold:true}; wa.getColumn(5).numFmt='#,##0.00'; wa.getColumn(6).numFmt='0.0%';

    if((S.gnCert||[]).some(x=>x.valor>0)){
      const wg=wb.addWorksheet('Certidão GN'); wg.columns=[{header:'Ano',width:8},{header:'Avos',width:8},{header:'Mês-base',width:12},{header:'Moeda',width:8},{header:'Valor',width:16},{header:'Por extenso',width:90}];
      for(const x of S.gnCert.filter(x=>x.valor>0)){ const m=moedaAno(x.ano); wg.addRow([+x.ano,x.avos+'/12',mesTxt(x.baseComp),m,x.valor,porExtenso(x.valor,m)]); }
      wg.getColumn(5).numFmt='#,##0.00'; wg.getRow(1).font={bold:true};
      wg.addRow([]); const rt=wg.addRow([$('gnCertTxt').value||textoCertidaoGN()]); wg.mergeCells(rt.number,1,rt.number,6); rt.getCell(1).alignment={wrapText:true,vertical:'top'}; rt.height=150;
    }
    const wr=wb.addWorksheet('Rubricas');
    wr.columns=[{header:'Código',width:10},{header:'Descrição',width:46},{header:'Lançamentos',width:12},{header:'Primeiro',width:10},{header:'Último',width:10},{header:'Soma',width:14},{header:'Categoria',width:28},{header:'Alterada',width:9}];
    for(const e of RBC.inventario(S.recs,S.cats)) wr.addRow([e.cod,e.desc,e.n,e.primeiro,e.ultimo,e.total,nome(e.cat),S.cats[e.cod+'|'+e.desc]?'sim':'']);
    wr.getRow(1).font={bold:true}; wr.getColumn(6).numFmt='#,##0.00';

    const buf=await wb.xlsx.writeBuffer();
    baixar(new Blob([buf],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}),'RBC_'+(nm?nm.split(/\s+/)[0]:'servidor')+'_'+iniEf().slice(0,4)+'-'+fimEf().slice(0,4)+'.xlsx');
    $('x_msg').textContent='Planilha gerada. Confira as abas "Conferência PSS" e "Esperada x paga" antes de juntar ao processo.';
  }catch(e){ console.error(e); $('x_msg').textContent='Não foi possível gerar a planilha: '+e.message; }
  btn.disabled=false; btn.textContent='Baixar RBC em Excel';
};

renderRelTabelas(); renderArqRel(); renderTudo();
window.__RBC_STATE=S; window.__RBC_IR=irPara; window.__RBC_CALC=calc; // usados nos testes automatizados
})();
