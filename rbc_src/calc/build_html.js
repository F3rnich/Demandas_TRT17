// Monta a página autocontida: node build_html.js  -> ../../calculadora_rbc.html (raiz do Hub)
const fs=require('fs'), path=require('path');
const D=__dirname, rd=f=>fs.readFileSync(path.join(D,f),'utf8');
let t=rd('template.html');
const core=rd('rbc_core.js'), tab=rd('tabela.json'), ui=rd('ui.js'), esp=rd('esperada.js')+'\n'+rd('relatorios.js')+'\n'+rd('certidao.js'), base=rd('base_calc.json'), rubref=rd('rubricas_ref.json'), rubcod=rd('rubricas_cod.json');
for(const [n,s] of [['core',core],['ui',ui],['esp',esp]]) if(s.includes('</script')) throw new Error(n+' contém </script');
t=t.replace('/*__CORE__*/',()=>core).replace('/*__TABELA__*/',()=>tab).replace('/*__ESP__*/',()=>esp).replace('/*__BASE__*/',()=>base).replace('/*__RUBREF__*/',()=>rubref).replace('/*__RUBCOD__*/',()=>rubcod).replace('/*__UI__*/',()=>ui);
// versão = hash do conteúdo (muda só quando a página muda) + data do build; rbc_versao.json ao lado da página
// permite à página aberta saber que há versão mais nova (cache do navegador)
const id=require('crypto').createHash('sha1').update(t).digest('hex').slice(0,8);
const out=process.argv[2]||path.join(D,'..','..','calculadora_rbc.html'), vfile=path.join(path.dirname(out),'rbc_versao.json');
let data=new Date().toISOString().slice(0,10);
try{ const v=JSON.parse(fs.readFileSync(vfile,'utf8')); if(v.id===id) data=v.data; }catch(e){}   // rebuild sem mudança mantém a data
t=t.replace('/*__VERSAO__*/',()=>JSON.stringify({id,data}));
fs.writeFileSync(out,t); if(!process.argv[2]) fs.writeFileSync(vfile,JSON.stringify({id,data})+'\n');
console.log('ok',out,t.length,'versão',id,data);
