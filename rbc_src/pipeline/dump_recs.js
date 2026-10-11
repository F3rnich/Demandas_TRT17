const path=require('path'),fs=require('fs');
const CALC='/home/claude/Demandas_TRT17/rbc_src/calc';
const req=require('module').createRequire(CALC+'/package.json');
const XLSX=req('xlsx'), RBC=require(CALC+'/rbc_core.js'), H=require(CALC+'/harness.js');
const ROOT='/home/claude/corpus'; const CODREF=JSON.parse(fs.readFileSync(CALC+'/rubricas_cod.json','utf8'));
const cases=JSON.parse(fs.readFileSync('/home/claude/work/cases.json'));
const pref=f=>(/c[oó]pia|lavinia|mara|luan|\(\d\)|DIPROF-|renatha/i.test(path.basename(f))?1:0);
(async()=>{
 for(const c of cases){
  const files=c.fichas.slice().sort((a,b)=>pref(a)-pref(b)||a.localeCompare(b));
  let all=[], cov={}, basePSO={}, baseGN={}, info={}, refs={}, log=[];
  for(const f of files){
    const p=path.join(ROOT,f); let recs=[], tipo='';
    try{
      if(/\.pdf$/i.test(f)){ const pg=await H.pdfPages(p); const sg=RBC.isFichaSGRH(pg); const pa=!sg&&RBC.isFichaAntigaPDF(pg); const pf=!sg&&!pa&&RBC.isFolhaWebPorFolha(pg); const r=sg?RBC.parseFichaSGRH(pg):pa?RBC.parseFichaAntigaPDF(pg):pf?RBC.parseFolhaWebPorFolha(pg):RBC.parseFolhaWebPages(pg); recs=r.recs; Object.assign(refs,r.refs||{}); if(r.info)Object.assign(info,r.info); tipo=sg?'pdfS':pa?'pdfA':pf?'pdfF':'pdf'; }
      else { const wb=XLSX.readFile(p);
        for(const n of wb.SheetNames){ const rows=XLSX.utils.sheet_to_json(wb.Sheets[n]);
          if(recs.length) break; if(RBC.isBigGrid(rows)){ const r=RBC.parseBigGrid(rows); if(r.recs.length){recs=r.recs; Object.assign(basePSO,r.basePSO); Object.assign(baseGN,r.baseGN); Object.assign(info,r.info); tipo='biggrid';} }
          else if(rows.length && ('Código Rubrica' in rows[0] || RBC.isLongDB(rows))){ if(!recs.length){recs=RBC.parseLongRows(rows,CODREF); tipo=RBC.isLongDB(rows)?'longdb':'long';} }
        } }
    }catch(e){ log.push(f+': ERRO '+e.message); continue; }
    const comps=[...new Set(recs.map(r=>r.comp))];
    const novos=comps.filter(k=>!cov[k]);
    if(!novos.length){ log.push(f+': '+tipo+' '+recs.length+' recs — duplicada'); continue; }
    const ns=new Set(novos); all=all.concat(recs.filter(r=>ns.has(r.comp))); novos.forEach(k=>cov[k]=tipo);
    log.push(f+': '+tipo+' '+recs.length+' recs, '+novos.length+' comps novas');
  }
  for(const r of all) r.cat=RBC.classify(r.cod,r.desc);
  fs.writeFileSync('/home/claude/work/recs/'+c.id+'.json',JSON.stringify({id:c.id,recs:all,basePSO,baseGN,info,refs,log}));
  console.log(c.id,c.nome.slice(0,30),all.length,'|',log.join(' ; ').slice(0,300));
 }
})();
