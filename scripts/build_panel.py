"""Injeta data/onjt.json no template e grava o painel final."""
import json, sys
tpl = open('/home/claude/panel/template.html', encoding='utf-8').read()
data = open('/home/claude/data/onjt.json', encoding='utf-8').read().replace('</', '<\\/')
out = tpl.replace('/*DATA*/', data)
open(sys.argv[1], 'w', encoding='utf-8').write(out)
print('ok', len(out))
