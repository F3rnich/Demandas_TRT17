# Cargos Efetivos Vagos — denominador real do art. 6º

## O que colocar aqui

Os arquivos mensais "Cargos efetivos vagos" do portal de transparência do TRT-17:

  https://www.trt17.jus.br/web/transparencia/w/estrutura-de-cargos-e-funcoes

Colunas esperadas: `Cargo/Área/Especialidade` e `Quantitativo`.
Cobertura desejada: janeiro de 2022 até a referência corrente (56 arquivos até 08/2026).

## Por que

O art. 6º da Res. CSJT 296/2021 põe teto de 80% para
(cargos em comissão + funções comissionadas) ÷ **cargos efetivos autorizados**.

O painel 12 usa hoje um *proxy*: divide pelos cargos efetivos **providos**, porque
a base de pessoal só traz postos ocupados. Isso superestima a razão, e por isso o
painel não emite veredito de conformidade.

  proxy publicado hoje:  85,45%   (552 comissionados ÷ 646 efetivos providos)
  teto do art. 6º:       80,00%
  viram o veredito:      ~43 cargos vagos

Com o denominador real, o painel finalmente responde se o tribunal está ou não
dentro do teto.

## Regras

- Estes arquivos **entram no repositório** (exceção explícita no `.gitignore`).
  São públicos e não contêm dado pessoal.
- Nada além deles nesta pasta. **Nunca** colocar aqui a base de pessoal da SGP.
- Nomear preservando a data de referência, como vem do portal
  (ex.: `Cargos-efetivos-vagos---01.07.2023.xlsx`).
- Rodar `python ler_vagos.py` depois de baixar: ele confere o layout (tres variantes),
  reconcilia o TOTAL impresso com a soma da coluna e aborta se divergir.
