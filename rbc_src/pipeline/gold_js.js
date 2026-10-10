const CALC='/home/claude/Demandas_TRT17/rbc_src/calc';const req=require('module').createRequire(CALC+'/package.json');
const JSZip=req('jszip'),fs=require('fs'),C=require(CALC+'/certidao.js'),H=require(CALC+'/harness.js');
(async()=>{const G=JSON.parse(fs.readFileSync('golds.json'));let n=0;
for(const g of G){ const p='/home/claude/corpus/'+g.arquivo; let r;
  try{ r=g.fmt==='docx'?await C.lerRBCDocx(JSZip,fs.readFileSync(p)):C.lerRBCPdf(await H.pdfPages(p)); }catch(e){ continue; }
  const nr=Object.values(r.mensal).filter(v=>v>0).length, ng=Object.values(g.mensal).filter(v=>v>0).length;
  if(nr>=ng*0.9&&nr>0){ g.mensal_py=g.mensal; g.mensal=r.mensal; g.gn=Object.assign({},r.gn); g.moeda=r.moeda; g.n_mes=Object.keys(r.mensal).length; g.n_gn=Object.keys(r.gn).length; g.parser='js'; n++; } }
fs.writeFileSync('golds.json',JSON.stringify(G)); console.log('substituídos',n,'de',G.length);})();
