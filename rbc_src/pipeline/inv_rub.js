const RBC=require('/home/claude/Demandas_TRT17/rbc_src/calc/rbc_core.js');const fs=require('fs');
const m=new Map();
for(const f of fs.readdirSync('recs')){ const d=JSON.parse(fs.readFileSync('recs/'+f));
  for(const r of d.recs){ const k=r.cod+'|'+r.desc; let e=m.get(k); if(!e){e={cod:r.cod,desc:r.desc,n:0,casos:new Set(),cat:RBC.classify(r.cod,r.desc)};m.set(k,e);} e.n++; e.casos.add(d.id);} }
const out=[...m.values()].map(e=>({cod:e.cod,desc:e.desc,n:e.n,casos:e.casos.size,cat:e.cat}));
fs.writeFileSync('rubricas.json',JSON.stringify(out));
const c={};for(const e of out)c[e.cat]=(c[e.cat]||0)+1;console.log(out.length,c);
