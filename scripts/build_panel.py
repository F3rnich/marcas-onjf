"""Injeta data/onjt.json no template e grava o painel final."""
import json, sys
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from norm import ROOT
tpl = open(os.path.join(ROOT, 'panel/template.html'), encoding='utf-8').read()
data = open(os.path.join(ROOT, 'data/onjt.json'), encoding='utf-8').read().replace('</', '<\\/')
out = tpl.replace('/*DATA*/', data)
open(sys.argv[1], 'w', encoding='utf-8').write(out)
print('ok', len(out))
