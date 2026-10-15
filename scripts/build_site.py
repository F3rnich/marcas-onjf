"""Gera site/index.html: o painel como página autônoma (sem o envelope do Claude), pronta para GitHub Pages."""
import sys
body = open('/home/claude/panel/marcas-onjt.html', encoding='utf-8').read()
head = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Resultados históricos de atletismo e natação da Olimpíada Nacional do Judiciário (ONJT/ONJF), 2009–2026: compare sua marca com pódio e recordes por faixa etária.">
<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,-apple-system,"Segoe UI",sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>
"""
out = head + body.replace('<header class="band">', '</head>\n<body>\n<header class="band">', 1) + '\n</body>\n</html>\n'
open(sys.argv[1], 'w', encoding='utf-8').write(out)
print('ok', len(out))
