// Monta a página autocontida: node build_html.js  -> ../../calculadora_rbc.html (raiz do Hub)
const fs=require('fs'), path=require('path');
const D=__dirname, rd=f=>fs.readFileSync(path.join(D,f),'utf8');
let t=rd('template.html');
const core=rd('rbc_core.js'), tab=rd('tabela.json'), ui=rd('ui.js'), esp=rd('esperada.js')+'\n'+rd('relatorios.js'), base=rd('base_calc.json'), rubref=rd('rubricas_ref.json');
for(const [n,s] of [['core',core],['ui',ui],['esp',esp]]) if(s.includes('</script')) throw new Error(n+' contém </script');
t=t.replace('/*__CORE__*/',()=>core).replace('/*__TABELA__*/',()=>tab).replace('/*__ESP__*/',()=>esp).replace('/*__BASE__*/',()=>base).replace('/*__RUBREF__*/',()=>rubref).replace('/*__UI__*/',()=>ui);
const out=process.argv[2]||path.join(D,'..','..','calculadora_rbc.html');
fs.writeFileSync(out,t); console.log('ok',out,t.length);
