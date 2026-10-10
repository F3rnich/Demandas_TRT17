const fs=require('fs'), XLSX=require('xlsx'), RBC=require('./rbc_core.js');
const pdfjs=require('pdfjs-dist/legacy/build/pdf.js');
async function pdfPages(path){
  const doc=await pdfjs.getDocument({data:new Uint8Array(fs.readFileSync(path)),verbosity:0}).promise; const pages=[];
  for(let n=1;n<=doc.numPages;n++){const p=await doc.getPage(n); const vp=p.getViewport({scale:1}); const tc=await p.getTextContent();
    pages.push({items:tc.items.map(it=>{const t=pdfjs.Util.transform(vp.transform,it.transform); return {str:it.str,x:t[4],y:t[5],w:it.width};})});}
  return pages;
}
function xlsRows(path){const wb=XLSX.readFile(path); return XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);}
async function load(xls, pdfs){
  let recs=RBC.parseLongRows(xlsRows(xls)); let refs={};
  for(const p of pdfs){const r=RBC.parseFolhaWebPages(await pdfPages(p)); recs=recs.concat(r.recs); Object.assign(refs,r.refs);}
  return {recs,refs};
}
module.exports={load,pdfPages,xlsRows};
