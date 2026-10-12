// Teste rápido da página (caso sintético, sem dados pessoais): node rbc_src/testes/smoke.js — abre a página, calcula um técnico 2013–2017 sem ficha, confere 3 meses contra a RRC, usa o mapa e baixa Excel, certidão e escolhas.
const path=require('path'),fs=require('fs');
const CALC=path.resolve(__dirname,'..','calc'), NM=CALC+'/node_modules';
const {chromium}=require(NM+'/playwright'); const JSZip=require(NM+'/jszip'); const XLSX=require(NM+'/xlsx');
const PAGINA=path.resolve(CALC,'..','..','calculadora_rbc.html');
const MAP={'jszip.min.js':'jszip/dist/jszip.min.js','xlsx.full.min.js':'xlsx/dist/xlsx.full.min.js','pdf.min.js':'pdfjs-dist/build/pdf.min.js','pdf.worker.min.js':'pdfjs-dist/build/pdf.worker.min.js','exceljs.min.js':'exceljs/dist/exceljs.min.js'};
let falhas=0; const ok=(c,m)=>{ if(!c) falhas++; console.log((c?'OK   ':'FALHA')+' '+m); };
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
 // ---- versão: rótulo e aviso de versão mais nova (página servida por http)
 { const http=require('http'), raiz=path.resolve(CALC,'..','..');
   const srv=http.createServer((q,r)=>{ const f=path.join(raiz,decodeURIComponent(q.url.split('?')[0])); if(!f.startsWith(raiz)||!fs.existsSync(f)){r.writeHead(404);return r.end();} r.writeHead(200,{'content-type':/\.json$/.test(f)?'application/json':'text/html; charset=utf-8'}); fs.createReadStream(f).pipe(r); }).listen(0);
   const porta=srv.address().port, v=JSON.parse(fs.readFileSync(path.join(raiz,'rbc_versao.json'),'utf8'));
   const p2=await ctx.newPage(); await p2.goto(`http://127.0.0.1:${porta}/calculadora_rbc.html`); await p2.waitForTimeout(800);
   ok((await p2.textContent('#versao')).includes(v.id),'rótulo de versão: '+(await p2.textContent('#versao')));
   ok(await p2.evaluate(()=>document.getElementById('novaVersao').hidden),'sem aviso quando a versão é a mesma');
   await p2.route(/rbc_versao\.json/,r=>r.fulfill({body:JSON.stringify({id:'ffffffff',data:'2099-01-01'}),contentType:'application/json'}));
   await p2.reload(); await p2.waitForTimeout(800);
   ok(!(await p2.evaluate(()=>document.getElementById('novaVersao').hidden)),'aviso de versão mais nova aparece');
   await p2.close(); srv.close(); }
 // ---- leitura de ficha: planilha longa sintética (analista A-1, jan–jun/2012), pela entrada única
 { const rows=[]; const lan=(ano,mes,cod,desc,nat,v)=>rows.push({'Ano':ano,'Mês':mes,'Tipo':0,'Código Rubrica':cod,'Descrição Rubrica':desc,'Tipo Rubrica':nat,'Sequencial Rubrica':0,'Valor Rubrica':v});
   for(let m=1;m<=6;m++){ lan(2012,m,'1','VENCIMENTO LEI 11416/06','R',4367.68); lan(2012,m,'2','GRAT.ATIV.JUDIC. LEI 11416/06','R',2183.84); lan(2012,m,'3','VANTAGEM PECUNIÁRIA LEI 10698/03','R',59.87); lan(2012,m,'4','AUXILIO-ALIMENTACAO','R',710); lan(2012,m,'5','PREVIDENCIA SOCIAL','D',727.25); }
   const wb=XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb,XLSX.utils.json_to_sheet(rows),'Ficha'); const fx=require('os').tmpdir()+'/ficha_sintetica.xlsx'; XLSX.writeFile(wb,fx);
   const p3=await ctx.newPage(); const e3=[]; p3.on('pageerror',e=>e3.push(String(e)));
   await p3.goto('file://'+PAGINA); await p3.waitForTimeout(500); await p3.setInputFiles('#fileTudo',[fx]);
   await p3.waitForFunction(()=>/ignorado/.test(document.getElementById('tudoSt').textContent),null,{timeout:60000}); await p3.waitForTimeout(800);
   const q=await p3.evaluate(()=>{const S=window.__RBC_STATE; const L=(S.res&&S.res.linhas)||[]; return {cargo:document.getElementById('cargo').value,n:L.length,t:L.map(l=>l.total),dif:L.map(l=>l.dif),ali:!!(S.res&&S.res.linhas.every(l=>!('AUXALIM' in (l.v||{}))))};});
   ok(/ANALISTA/.test(q.cargo),'ficha sintética: cargo deduzido = '+q.cargo);
   ok(q.n===6&&q.t.every(x=>Math.abs(x-6611.39)<0.02),'ficha sintética: 6 meses de R$ 6.611,39 ('+q.t.join(', ')+')');
   ok(q.dif.every(x=>Math.abs(x||0)<0.02),'ficha sintética: contribuição descontada confere');
   ok(e3.length===0,'ficha sintética sem erro de JavaScript '+e3.join(' | '));
   await p3.close(); }
 // ---- ingresso deduzido da ficha: exercício em 18/01/2012, janeiro pago por 13/30
 { const rows=[]; const lan=(ano,mes,cod,desc,nat,v)=>rows.push({'Ano':ano,'Mês':mes,'Tipo':0,'Código Rubrica':cod,'Descrição Rubrica':desc,'Tipo Rubrica':nat,'Sequencial Rubrica':0,'Valor Rubrica':v});
   for(let m=1;m<=4;m++){ const f=m===1?13/30:1, r2=x=>Math.round(x*f*100)/100; lan(2012,m,'1','VENCIMENTO LEI 11416/06','R',r2(4367.68)); lan(2012,m,'2','GRAT.ATIV.JUDIC. LEI 11416/06','R',r2(2183.84)); lan(2012,m,'3','VANTAGEM PECUNIÁRIA LEI 10698/03','R',r2(59.87)); lan(2012,m,'5','PREVIDENCIA SOCIAL','D',r2(727.25)); }
   const wb=XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb,XLSX.utils.json_to_sheet(rows),'Ficha'); const fx=require('os').tmpdir()+'/ficha_ingresso.xlsx'; XLSX.writeFile(wb,fx);
   const p4=await ctx.newPage(); const e4=[]; p4.on('pageerror',e=>e4.push(String(e)));
   await p4.goto('file://'+PAGINA); await p4.waitForTimeout(500); await p4.setInputFiles('#fileTudo',[fx]);
   await p4.waitForFunction(()=>/ignorado/.test(document.getElementById('tudoSt').textContent),null,{timeout:60000}); await p4.waitForTimeout(800);
   const q=await p4.evaluate(()=>{const S=window.__RBC_STATE; const L=S.res.linhas; return {auto:S.iniAuto, jan:L[0].total, n:L.length, aviso:/Ingresso deduzido da ficha/.test(document.body.innerText)};});
   ok(q.auto==='2012-01-18','ingresso deduzido da ficha = 18/01/2012 ('+q.auto+')');
   ok(Math.abs(q.jan-2864.94)<0.03&&q.n===4,'jan/2012 proporcional = 2.864,94 ('+q.jan+')');
   ok(q.aviso,'aviso do ingresso deduzido na conferência');
   ok(e4.length===0,'ingresso deduzido sem erro de JavaScript '+e4.join(' | '));
   await p4.close(); }
 await b.close();
 process.exitCode=falhas?1:0;
})();
