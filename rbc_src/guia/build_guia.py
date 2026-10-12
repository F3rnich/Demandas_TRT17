#!/usr/bin/env python3
"""Gera ../../guia_rbc.html (raiz do Hub) a partir de guia_rbc.md: python3 rbc_src/guia/build_guia.py
Requer pandoc. Mesmas cores e fontes da calculadora, tema claro/escuro, sem scripts."""
import pathlib, subprocess, datetime
D = pathlib.Path(__file__).resolve().parent
md = (D / 'guia_rbc.md').read_text(encoding='utf-8')
corpo = subprocess.run(['pandoc', '-f', 'gfm', '-t', 'html5'], input=md, capture_output=True, text=True, check=True).stdout
# ids sem acento (estáveis para links da calculadora: guia_rbc.html#conferencia-o-mapa-mes-a-mes)
import unicodedata, re
corpo = re.sub(r'id="([^"]+)"', lambda m: 'id="%s"' % unicodedata.normalize('NFKD', m.group(1)).encode('ascii', 'ignore').decode(), corpo)
hoje = datetime.date.today().strftime('%d/%m/%Y')
html = f'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Guia da calculadora de RBC</title>
<link rel="icon" href="favicon.ico" sizes="any"><link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--navy:#003A5C;--yellow:#FFD040;--bg:#EEF2F5;--paper:#FFFFFF;--ink:#17242C;--mute:#55666F;--line:#D3DDE3;--soft:#E4EDF3;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--navy:#7DB6DA;--bg:#11181D;--paper:#1A242B;--ink:#E5ECF0;--mute:#9AABB4;--line:#2F3E47;--soft:#1C2E3A;color-scheme:dark}}}}
:root[data-theme="dark"]{{--navy:#7DB6DA;--bg:#11181D;--paper:#1A242B;--ink:#E5ECF0;--mute:#9AABB4;--line:#2F3E47;--soft:#1C2E3A;color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 "Public Sans",system-ui,"Segoe UI",Arial,sans-serif}}
a{{color:var(--navy)}}
:focus-visible{{outline:3px solid var(--yellow);outline-offset:2px}}
.topo{{background:#003A5C;border-bottom:4px solid #FFD040}}
.topo-in{{max-width:960px;margin:0 auto;padding:8px 16px;display:flex;justify-content:space-between;font-family:ui-monospace,Consolas,monospace;font-size:11px;letter-spacing:.08em;color:#BFD6E6}}
.topo-in b{{color:#FFD040}}
.head{{background:#003A5C;color:#fff;padding:22px 16px 26px}}
.head-in{{max-width:960px;margin:0 auto}}
.head h1{{margin:0;font-size:30px;font-weight:800}}
.head p{{margin:6px 0 0;color:#D5E3EC}}
.head a{{color:#FFD040}}
main{{max-width:960px;margin:0 auto;padding:8px 16px 48px}}
main>section,main>.card{{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:4px 22px 18px;margin:18px 0}}
h2{{font-size:21px;margin:20px 0 8px;color:var(--navy)}}
p,li{{max-width:78ch}}
table{{border-collapse:collapse;width:100%;font-size:14.5px;margin:10px 0}}
th,td{{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}}
th{{background:var(--soft)}}
.tw{{overflow-x:auto}}
.btn{{display:inline-block;background:var(--navy);color:var(--paper);padding:9px 16px;border-radius:8px;text-decoration:none;font-weight:700}}
footer{{color:var(--mute);font-size:13px;max-width:960px;margin:0 auto;padding:0 16px 30px}}
@media print{{.topo,.head{{background:none;color:#000;border:0}} .head p,.head a{{color:#000}} main>section{{border:0;padding:0}}}}
</style>
</head>
<body>
<div class="topo"><div class="topo-in"><span>SGP — DIPROF · GUIA</span><b>TRT-17</b></div></div>
<div class="head"><div class="head-in"><h1>Guia da calculadora de RBC</h1><p>Como montar, conferir e emitir a relação das remunerações de contribuição. <a href="calculadora_rbc.html">Abrir a calculadora</a> · <a href="index.html">Hub</a></p></div></div>
<main>
{corpo}
</main>
<footer>Atualizado em {hoje}.</footer>
</body>
</html>
'''
# cada seção (##) num cartão; tabelas com rolagem própria em tela estreita
partes = html.split('<h2 ')
html = partes[0] + ''.join('</section><section><h2 ' + p for p in partes[1:])
html = html.replace('<main>\n', '<main>\n<section class="card">', 1).replace('\n</main>', '</section>\n</main>', 1)
html = html.replace('<table>', '<div class="tw"><table>').replace('</table>', '</table></div>')
html = html.replace('<a href="calculadora_rbc.html">Abrir a calculadora</a></p>', '<a class="btn" href="calculadora_rbc.html">Abrir a calculadora</a></p>', 1)
out = D.parent.parent / 'guia_rbc.html'
out.write_text(html, encoding='utf-8'); print('ok', out, len(html))
