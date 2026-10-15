import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from norm import name_key
D = json.load(open('/home/claude/data/onjt.json'))
ev = D['events']; ages = D['ages']
rows = D['rows']
idx = {}
for r in rows:
    y, e, g, a, pl, n, d, v, st, rec = r
    idx.setdefault((y, e, g, ages[a]), []).append((name_key(D['names'][n]), v, pl))
ok = miss_ev = mism = 0; bad = []
for e, g, a, pool, name, dl, v, y, *_ in D['records']:
    k = (y, e, g, ages[a])
    if k not in idx:
        miss_ev += 1; bad.append(('PROVA AUSENTE', y, ev[e]['label'], g, ages[a], name, v)); continue
    nk = name_key(name); toks = set(nk.split())
    def eq(a, b):
        if abs(a - b) < 0.015: return True
        # recordes publicados com décimos transcritos como centésimos (12.2 -> 12.02)
        cent = round((b - int(b)) * 100)
        return cent < 10 and abs(a - (int(b) + cent / 10)) < 0.015
    hit = [x for x in idx[k] if x[1] is not None and eq(x[1], v)]
    if hit and any(len(toks & set(h[0].split())) >= 2 for h in hit): ok += 1
    else:
        mism += 1; bad.append(('DIVERGE', y, ev[e]['label'], g, ages[a], name, v, sorted(idx[k], key=lambda x: (x[1] is None, x[1] or 0))[:2]))
tot = ok + miss_ev + mism
print(f'recordes oficiais verificados: {tot} | conferem: {ok} ({ok/tot:.0%}) | prova ausente na base: {miss_ev} | divergentes: {mism}')
for b in bad[:int(sys.argv[1]) if len(sys.argv) > 1 else 40]: print('  ', b)

# ---------- revezamentos ----------
REV = D['rel_events']; RC = D['rel_cats']
ok = bad = 0; lst = []
for e, g, c, pool, dl, v, y, corr in D['rel_records']:
    hits = [r for r in D['relays'] if r[0] == y and r[1] == e and r[2] == g and r[3] == c and r[6] is not None and abs(r[6] - v) < 0.015]
    if hits and any(D['dels'][h[5]] == dl for h in hits): ok += 1
    else:
        bad += 1
        cand = sorted([(r[6], D['dels'][r[5]]) for r in D['relays'] if r[0] == y and r[1] == e and r[2] == g and r[6] is not None])[:2]
        lst.append((y, REV[e]['label'], g, RC[c], pool, dl, v, 'base:', cand))
tot = ok + bad
print(f'recordes de revezamento verificados: {tot} | conferem: {ok} ({ok/max(tot,1):.0%})')
for x in lst: print('  ', x)
