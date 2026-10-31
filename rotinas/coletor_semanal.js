// Coleta semanal (incremental) da seção Legislação do portal do TRT-17 — roda no Chrome do Leo,
// numa aba aberta em https://www.trt17.jus.br/web/legislacao/... (mesma origem, sessão normal do navegador).
// Faz poucos pedidos (as pastas do ano corrente e as seções sem subpastas), um a cada 6 s, como o
// coletor lento já aprovado. Regras do firewall (vedado contornar):
//   - resposta 202 ou erro de rede => PARA na hora e devolve o que tiver; não repete, não recarrega,
//     não renova token, não troca de rede. A rotina só avisa o Leo.
// Uso pelo javascript_tool, em duas chamadas:
//   1) colar este arquivo + a linha  __coletaSemanal(<JSON de "alvos" gerado por incorpora_coleta_site.py alvos>);
//   2) consultar  window.__coleta  até  fim === true  (a cada ~30 s) e copiar  JSON.stringify(window.__coleta.resultado).
(() => {
  const API = '/o/headless-delivery/v1.0/document-folders/', PAUSA = 6000;
  const dorme = ms => new Promise(r => setTimeout(r, ms));
  window.__coletaSemanal = (alvos) => {
    if (window.__coleta && !window.__coleta.fim) return 'coleta já em andamento';
    const st = window.__coleta = {inicio: new Date().toISOString(), fim: false, pedidos: 0, bloqueado: null, log: [],
      resultado: {pastas: [], novos: [], paginas_incompletas: [], bloqueado: null}};
    const conhecidos = new Set(alvos.conhecidos || []), pastasConhecidas = new Set(alvos.pastas_conhecidas || []);
    const pega = async (url) => {
      await dorme(PAUSA);
      st.pedidos++;
      let r;
      try { r = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'application/json'}}); }
      catch (e) { st.bloqueado = 'erro de rede: ' + e.message; return null; }
      const t = await r.text();
      if (r.status === 202 || !t) { st.bloqueado = 'HTTP ' + r.status + ' (firewall) em ' + url; return null; }
      if (!r.ok) { st.log.push('HTTP ' + r.status + ' ' + url); return {items: []}; }
      try { return JSON.parse(t); } catch (e) { st.bloqueado = 'resposta não-JSON (provável desafio do firewall) em ' + url; return null; }
    };
    const subpastas = async (id) => {
      const j = await pega(API + id + '/document-folders?pageSize=200');
      if (!j) return null;
      return j.items.map(f => ({id: f.id, paiId: id, nome: f.name, n: f.numberOfDocuments, nf: f.numberOfDocumentFolders}));
    };
    const documentos = async (id) => {
      const j = await pega(API + id + '/documents?pageSize=200&sort=dateCreated:desc');
      if (!j) return false;
      if ((j.totalCount || 0) > j.items.length) st.resultado.paginas_incompletas.push({pastaId: id, total: j.totalCount, vistos: j.items.length});
      j.items.forEach(d => { if (!conhecidos.has(d.id)) st.resultado.novos.push({id: d.id, pastaId: id, titulo: d.title, descricao: d.description || '',
        arquivo: d.fileName, ext: d.fileExtension, url: (d.contentUrl || '').split('?')[0], bytes: d.sizeInBytes, criado: d.dateCreated,
        modificado: d.dateModified, kw: d.keywords || [], cat: (d.taxonomyCategoryBriefs || []).map(t => t.taxonomyCategoryName)}); });
      return true;
    };
    (async () => {
      try {
        const filaDocs = [...(alvos.docs || [])];
        // pastas-mãe: descobrir subpastas novas (ex.: a pasta do ano que começa, ou uma unidade nova)
        for (const id of (alvos.maes || [])) {
          const fs = await subpastas(id); if (!fs) break;
          fs.forEach(f => { st.resultado.pastas.push(f); if (!pastasConhecidas.has(f.id)) { st.log.push('pasta nova: ' + f.nome + ' (' + f.id + ')'); if (f.n) filaDocs.push(f.id); } });
        }
        if (!st.bloqueado) for (const id of [...new Set(filaDocs)]) { if (!(await documentos(id))) break; }
      } catch (e) { st.bloqueado = st.bloqueado || 'erro: ' + e.message; }
      st.resultado.bloqueado = st.bloqueado;
      st.fim = true; st.termino = new Date().toISOString();
    })();
    return 'coleta iniciada: ' + ((alvos.maes || []).length + (alvos.docs || []).length) + ' pedidos previstos, ~' + Math.ceil(((alvos.maes || []).length + (alvos.docs || []).length) * PAUSA / 60000) + ' min';
  };
  return 'coletor semanal carregado';
})();
