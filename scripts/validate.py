"""Confere a base contra as listas oficiais de recordes da Anastra.

Cada recorde oficial precisa aparecer na base com o mesmo atleta (ou delegação, nos
revezamentos), ano, prova, faixa e marca. Uso direto: python3 scripts/validate.py [N]
(N = quantas divergências listar). check() devolve os percentuais para atualizar.py.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from norm import ROOT, name_key

def _eq(a, b):
    if abs(a - b) < 0.015: return True
    cent = round((b - int(b)) * 100)          # décimos publicados como centésimos (12.2 -> 12.02)
    return cent < 10 and abs(a - (int(b) + cent / 10)) < 0.015

def check(show=20):
    D = json.load(open(os.path.join(ROOT, 'data/onjt.json')))
    ev, ages = D['events'], D['ages']
    idx = {}
    for y, e, g, a, pl, n, d, v, st, rec in D['rows']:
        idx.setdefault((y, e, g, ages[a]), []).append((name_key(D['names'][n]), v))
    ok = 0; bad = []
    for e, g, a, pool, name, dl, v, y, *_ in D['records']:
        k = (y, e, g, ages[a]); toks = set(name_key(name).split())
        hit = [x for x in idx.get(k, []) if x[1] is not None and _eq(x[1], v)]
        if hit and any(len(toks & set(h[0].split())) >= 2 for h in hit): ok += 1
        else: bad.append((y, ev[e]['label'], g, ages[a], name, v, 'prova ausente' if k not in idx else 'diverge'))
    ind = ok / max(ok + len(bad), 1)
    print(f'Recordes individuais: {ok} de {ok + len(bad)} conferem ({ind:.0%})')
    for b in bad[:show]: print('   ', b)

    REV, RC = D['rel_events'], D['rel_cats']
    ok = 0; rbad = []
    for e, g, c, pool, dl, v, y, corr in D['rel_records']:
        hits = [r for r in D['relays'] if r[0] == y and r[1] == e and r[2] == g and r[3] == c and r[6] is not None and abs(r[6] - v) < 0.015]
        if hits and any(D['dels'][h[5]] == dl for h in hits): ok += 1
        else: rbad.append((y, REV[e]['label'], g, RC[c], pool, dl, v))
    rel = ok / max(ok + len(rbad), 1)
    print(f'Recordes de revezamento: {ok} de {ok + len(rbad)} conferem ({rel:.0%})')
    for b in rbad[:show]: print('   ', b)
    return ind, rel

if __name__ == '__main__':
    check(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
