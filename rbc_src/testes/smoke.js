// Teste rápido da página (caso sintético, sem dados pessoais): node rbc_src/testes/smoke.js — abre a página, calcula um técnico 2013–2017 sem ficha, confere 3 meses contra a RRC, usa o mapa e baixa Excel, certidão e escolhas.
const path=require('path'),fs=require('fs');
const CALC=path.resolve(__dirname,'..','calc'), NM=CALC+'/node_modules';
const {chromium}=require(NM+'/playwright'); const JSZip=require(NM+'/jszip'); const XLSX=require(NM+'/xlsx');
const PAGINA=path.resolve(CALC,'..','..','calculadora_rbc.html');
const MAP={'jszip.min.js':'jszip/dist/jszip.min.js','xlsx.full.min.js':'xlsx/dist/xlsx.full.min.js','pdf.min.js':'pdfjs-dist/build/pdf.min.js','pdf.worker.min.js':'pdfjs-dist/build/pdf.worker.min.js','exceljs.min.js':'exceljs/dist/exceljs.min.js'};
const ok=(c,m)=>console.log((c?'OK   ':'FALHA')+' '+m);
(async()=>{
 const b=await chromium.launch(); const ctx=await b.newContext({viewport:{width:1440,height:900},acceptDownloads:true});
 const p=await ctx.newPage(); const errs=[]; p.on('pageerror',e=>errs.push(String(e))); p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
 await ctx.route(/cdnjs/,r=>r.fulfill({path:NM+'/'+MAP[r.request().url().split('/').pop()],contentType:'application/javascript'}));
 await ctx.route(/fonts\.(googleapis|gstatic)/,r=>r.fulfill({body:'',contentType:'text/css'}));
 await p.goto('file://'+PAGINA); await p.waitForTimeout(800);
 ok(errs.length===0,'página abre sem erro '+errs.join(' | '));
 ok(/Arraste a pasta/.test(await p.textContent('#barraSt')),'barra inicial');
 // caso sintético sem ficha: técnico 02/05/2013 a 01/03/2017, progressão A1..A4
 await p.evaluate(()=>{ const S=window.__RBC_STATE; const set=(id,v)=>{const e=document.getElementById(id); e.value=v; e.dispatchEvent(new Event('change',{bubbles:true}));};
   set('cargo','TÉCNICO JUDICIÁRIO'); set('inicio','2013-05-02'); set('fim','2017-03-01');
   S.rel.PROGRESSAO=[['2013-05-02','2014-05-01','A','1'],['2014-05-02','2015-05-01','A','2'],['2015-05-02','2016-05-01','A','3'],['2016-05-02','','A','4']].map(([ini,fim,classe,padrao])=>({ini,fim,classe,padrao,origem:'manual'}));
   S.rel.AQ.push({ini:'2013-05-02',fim:'',tipo:'ESPECIALIZACAO'}); S.rel.V1323.push({ini:'2015-01-01',fim:'2016-03-31'}); window.__RBC_CALC(); });
 await p.waitForTimeout(800);
 const r=await p.evaluate(()=>{const S=window.__RBC_STATE; const L=S.res&&S.res.linhas||[]; const g=k=>{const l=L.find(x=>x.comp===k);return l&&l.total;}; return {n:L.length,m1:g('2013-06'),m2:g('2015-01'),m3:g('2017-01'),gn:(S.res&&S.res.gns||[]).length}});
 ok(r.n===47,'47 meses calculados ('+r.n+')');
 ok(Math.abs(r.m1-4846.84)<0.02,'jun/2013 = 4.846,84 da RRC ('+r.m1+')');
 ok(Math.abs(r.m2-5906.47)<0.02,'jan/2015 com 13,23% = 5.906,47 ('+r.m2+')');
 ok(Math.abs(r.m3-7225.89)<0.02,'jan/2017 com VPI pela tabela = 7.225,89 ('+r.m3+')');
 ok(r.gn>=4,'13º calculado ('+r.gn+' anos)');
 // abre a conferência
 await p.click('#avancar').catch(()=>{}); await p.waitForTimeout(800);
 ok(await p.evaluate(()=>/Mês a mês/.test(document.body.innerText)),'conferência aberta');
 // mapa: modos e dica
 const modos=await p.$$eval('#mapaModos button',bs=>bs.map(x=>x.dataset.m));
 ok(modos.includes('contrib'),'mapa com modos: '+modos.join(','));
 const cel=await p.$$('#mapa .cel'); ok(cel.length>=50,'mapa com '+cel.length+' células');
 for(const m of modos){ await p.click(`#mapaModos button[data-m="${m}"]`); await p.waitForTimeout(150); }
 const cel2=await p.$$('#mapa .cel.ok, #mapa .cel'); await cel2[5].hover(); await p.waitForTimeout(150); ok(await p.evaluate(()=>!document.getElementById('mapaTip').hidden),'dica do mapa aparece');
 await cel2[5].click(); await p.waitForTimeout(200); ok((await p.textContent('#detalhe')).length>50,'detalhe do mês abre');
 // downloads
 const dl=async(id)=>{ const [d]=await Promise.all([p.waitForEvent('download',{timeout:20000}),p.click('#'+id)]); const f=require('os').tmpdir()+'/_'+id+path.extname(d.suggestedFilename()); await d.saveAs(f); return {f,name:d.suggestedFilename()}; };
 try{ await p.evaluate(()=>{document.getElementById('x_rbc').disabled=false;}); const x=await dl('x_rbc'); const wb=XLSX.readFile(x.f); ok(wb.SheetNames.includes('RBC'),'Excel baixado ('+x.name+'): abas '+wb.SheetNames.join(', ')); }catch(e){ ok(false,'Excel: '+e.message); }
 try{ await p.evaluate(()=>{const s=(id,v)=>{const e=document.getElementById(id); if(e){e.value=v; e.dispatchEvent(new Event('input',{bubbles:true}));}}; s('c_nome','SERVIDOR TESTE'); s('c_matricula','0000'); });
   const c=await dl('x_cert'); const z=await JSZip.loadAsync(fs.readFileSync(c.f)); const xml=await z.file('word/document.xml').async('string'); ok(/SERVIDOR TESTE/.test(xml)&&/4\.846,84/.test(xml),'certidão .docx baixada com nome e valores ('+c.name+')'); }catch(e){ ok(false,'certidão: '+e.message); }
 try{ const s=await dl('x_dec'); const j=JSON.parse(fs.readFileSync(s.f,'utf8')); ok(j&&typeof j==='object','escolhas salvas (JSON) ('+s.name+')'); }catch(e){ ok(false,'salvar escolhas: '+e.message); }
 // tema escuro e tela estreita
 await p.setViewportSize({width:800,height:900}); await p.waitForTimeout(200); ok(await p.evaluate(()=>document.documentElement.scrollWidth<=820),'sem rolagem horizontal em 800 px');
 ok(errs.length===0,'nenhum erro de JavaScript durante o uso '+errs.join(' | '));
 await b.close();
})();
