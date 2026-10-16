"""Gera site/index.html: o painel como página autônoma (sem o envelope do Claude), pronta para GitHub Pages."""
import sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from norm import ROOT
body = open(os.path.join(ROOT, 'panel/marcas-onjt.html'), encoding='utf-8').read()
head = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Resultados históricos de atletismo e natação da Olimpíada Nacional do Judiciário (ONJT/ONJF): compare sua marca com o pódio e os recordes da sua faixa etária.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Marcas ONJT/ONJF">
<meta property="og:title" content="Marcas ONJT/ONJF">
<meta property="og:description" content="Compare sua marca com o pódio e os recordes da sua faixa etária. Atletismo e natação, todas as edições.">
<meta property="og:url" content="https://f3rnich.github.io/marcas-onjf/">
<meta property="og:image" content="https://f3rnich.github.io/marcas-onjf/preview.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='14' fill='%23e0bb4c'/%3E%3Ctext x='16' y='22' font-size='16' font-weight='800' text-anchor='middle' fill='%231b1407' font-family='sans-serif'%3E1%3C/text%3E%3C/svg%3E">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
"""
out = head + body.replace('<header class="band">', '</head>\n<body>\n<header class="band">', 1) + '\n</body>\n</html>\n'
open(sys.argv[1], 'w', encoding='utf-8').write(out)
print('ok', len(out))
