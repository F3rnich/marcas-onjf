"""Recordes oficiais (PDFs 'Recordes por faixa etária', atualizados até 2024)."""
import re, json, sys, os, glob
sys.path.insert(0, os.path.dirname(__file__))
from norm import *

FILES = {
    'Atletismo-masculino': ('Atletismo', 'M', None),
    'Atletismo-feminino': ('Atletismo', 'F', None),
    'Natacao-masculino-50m': ('Natação', 'M', 50),
    'Natacao-feminino-50m': ('Natação', 'F', 50),
    'Natacao-masculino-25m': ('Natação', 'M', 25),
    'Natacao-feminino-25m': ('Natação', 'F', 25),
}

def parse(path, mod, g, pool):
    out = []; ev = None
    for ln in open(path, encoding='utf-8').read().splitlines():
        s = ln.strip()
        if not s: continue
        m = re.match(r'^(at[eé]\s+\d{2}(?:\s+anos)?|de\s+\d{2}\s+a\s+\d{2}\s+anos|de\s+\d{2}\s+anos\s+acima|acima\s+de\s+\d{2}\s+anos)\s+(.*)$', s, re.I)
        if m and ev:
            age = detect_age(m.group(1))
            rest = m.group(2)
            if re.search(r'Sem (tempo|marca)|N[aã]o houve', rest, re.I): continue
            md = find = DELEG_RX.search(rest)
            mm = re.search(r'([\d:.,]+)\s+(\d{4})\s*$', rest)
            if not md or not mm: continue
            out.append(dict(modality=mod, event=ev[1], event_label=ev[2], gender=g, age=age, pool=pool,
                            name=title_name(rest[:md.start()]), deleg=canon_deleg(md.group(0)) or md.group(0),
                            mark_raw=mm.group(1), year=int(mm.group(2))))
            continue
        if RELAY.search(s): ev = None; continue
        e = detect_event(s, mod)
        if e and len(s) < 40: ev = e
    return out

RELAY = re.compile(r'REVEZ|\d\s*x\s*\d', re.I)

if __name__ == '__main__':
    d = sys.argv[1]; out = []
    for key, (mod, g, pool) in FILES.items():
        f = glob.glob(os.path.join(d, f'2025_09_{key}.txt'))[0]
        r = parse(f, mod, g, pool); out += r
        print(key, len(r), sorted({x['year'] for x in r}))
    json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)

# ---------------- recordes de revezamento ----------------
REL_FILES = {'Atletismo-masculino': ('Atletismo', 'M', None), 'Atletismo-feminino': ('Atletismo', 'F', None),
             'Atletismo-misto-1': ('Atletismo', 'X', None),
             'Natacao-masculino-50m': ('Natação', 'M', 50), 'Natacao-feminino-50m': ('Natação', 'F', 50), 'Natacao-misto-50m': ('Natação', 'X', 50),
             'Natacao-masculino-25m': ('Natação', 'M', 25), 'Natacao-feminino-25m': ('Natação', 'F', 25), 'Natacao-misto-25m': ('Natação', 'X', 25)}
def parse_relay_records(d):
    from parse_relays import relay_header
    out = []
    for key, (mod, g, pool) in REL_FILES.items():
        fs = glob.glob(os.path.join(d, f'2025_09_{key}.txt'))
        if not fs: continue
        on = False
        for ln in open(fs[0], encoding='utf-8').read().splitlines():
            s = ln.strip()
            if re.search(r'REVEZAMENTOS', s): on = True; continue
            if not on or not s: continue
            mm = re.search(r'([\d:.,]+)\s+(\d{4})\s*$', s)
            md = list(DELEG_RX.finditer(s))
            if not mm or not md: continue
            h = relay_header(s[:md[0].start()], mod, g)
            if not h: continue
            out.append(dict(modality=h['mod'], event=h['key'], event_label=h['label'], gender=h['g'] or g, cat=h['cat'],
                            pool=pool, deleg=canon_deleg(md[-1].group(0)) or md[-1].group(0), mark_raw=mm.group(1), year=int(mm.group(2))))
    return out

if __name__ == '__main__' and len(sys.argv) > 3:
    rr = parse_relay_records(sys.argv[1]); json.dump(rr, open(sys.argv[3], 'w'), ensure_ascii=False, indent=0)
    for r in rr: print(r['modality'], r['event_label'], r['gender'], r['cat'], r['pool'], r['deleg'], r['mark_raw'], r['year'])
