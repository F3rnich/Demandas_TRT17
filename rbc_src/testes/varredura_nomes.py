#!/usr/bin/env python3
"""Varredura de dados pessoais antes de publicar (o repositório é público).

Uso: python3 varredura_nomes.py <arquivo_de_nomes.txt> [arquivos ...]
  - arquivo_de_nomes.txt: um nome por linha (fica FORA do repositório, junto dos casos).
  - sem arquivos: verifica a página publicada e os fontes de rbc_src/calc.
Procura os nomes (sem acento, maiúsculas, dois primeiros nomes) e qualquer CPF (000.000.000-00).
Código de saída 1 se encontrar algo.
"""
import re, sys, unicodedata, pathlib
RAIZ = pathlib.Path(__file__).resolve().parents[2]
n = lambda s: unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().upper()
nomes = {n(' '.join(l.split()[:2])) for l in open(sys.argv[1], encoding='utf-8') if len(l.split()) >= 2}
arqs = sys.argv[2:] or [str(RAIZ / 'calculadora_rbc.html')] + [str(p) for p in (RAIZ / 'rbc_src' / 'calc').glob('*.*') if p.suffix in ('.js', '.json', '.html')]
falha = 0
for a in arqs:
    t = n(open(a, encoding='utf-8', errors='replace').read())
    achados = sorted(x for x in nomes if x in t) + re.findall(r'\d{3}\.\d{3}\.\d{3}-\d{2}', t)[:5]
    if achados: falha = 1; print('ATENÇÃO', a, achados)
print('varredura:', 'encontrou dados pessoais' if falha else f'nada encontrado em {len(arqs)} arquivo(s) ({len(nomes)} nomes)')
sys.exit(falha)
