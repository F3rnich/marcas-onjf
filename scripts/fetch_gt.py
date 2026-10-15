"""Baixa os resultados de atletismo 2026 (sistema Gerentrack) pela API pública que o site usa."""
import json, urllib.request, sys, os
H = 'https://oarffiaduoffgrtckjsn.supabase.co/rest/v1/'
key = json.load(open('/home/claude/raw/ext/hdr.json'))['apikey']
def get(path):
    out = []; off = 0
    while True:
        req = urllib.request.Request(f'{H}{path}&offset={off}&limit=1000', headers={'apikey': key, 'Authorization': 'Bearer ' + key})
        d = json.load(urllib.request.urlopen(req, timeout=120))
        out += d
        if len(d) < 1000: return out
        off += 1000
OUT = '/home/claude/raw/ext'
for ev in ('1789646392246', '1790212007822'):
    for t, sel in (('resultados', 'select=*'), ('inscricoes', 'select=id,dados')):
        d = get(f'{t}?{sel}&order=id.asc&evento_id=eq.{ev}')
        json.dump(d, open(f'{OUT}/{t}_{ev}.json', 'w'), ensure_ascii=False); print(t, ev, len(d))
eq = get('equipes_publicas?select=id,dados&order=id.asc')
json.dump(eq, open(f'{OUT}/equipes.json', 'w'), ensure_ascii=False); print('equipes', len(eq))
