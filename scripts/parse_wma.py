"""Lê os fatores de idade (age-grading) de um ano da WMA 2023 (Rulebook, Appendix B) e grava data/wma.json.

Uso: python3 scripts/parse_wma.py raw/wma/2023-WMA-Appendix-B.pdf data/wma.json
Fator de idade: marca × fator = marca equivalente no auge (30–34 anos). Só provas sem
implemento variável por idade (corridas e saltos); arremessos ficam de fora porque a WMA
muda o peso do implemento por faixa e a regra da ONJ pode ser outra.
"""
import json, os, re, subprocess, sys
TYPES = {
    'A': ['60', '100', '200', '400', '800', '1000', '1500', 'mile', '3000', '5000', '10000'],
    'B': ['60h', 'sh', 'lh', 'steeple', 'hj', 'pv', 'lj', 'tj', 'sp', 'discus', 'hammer'],
    'C': ['javelin', 'weight', 'rw3', 'rw5', 'rw10', 'rw20', 'half', 'marathon'],
}
KEEP = {'100': '100_rasos', '200': '200_rasos', '400': '400_rasos', '800': '800_rasos', '1500': '1500_rasos',
        '3000': '3000_rasos', '5000': '5000_rasos', 'hj': 'salto_altura', 'lj': 'salto_distancia', 'tj': 'salto_triplo'}

def parse(pdf):
    txt = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout
    out = {'F': {}, 'M': {}}
    g = t = None
    for line in txt.splitlines():
        if "ONE-YEAR AGE FACTORS" in line:
            g = 'F' if 'WOMEN' in line else 'M'; t = None; continue
        if g is None: continue
        if re.match(r'\s*Age\s+60m\s+100m', line): t = 'A'; continue
        if 'Short' in line and 'Steeple' in line: t = 'B'; continue
        if re.search(r'Age\s+Javelin', line): t = 'C'; continue
        if 'COMBINED EVENTS' in line: g = None; continue
        m = re.match(r'\s*(\d{2,3})\s+((?:\d\.\d{4}\s*)+)$', line)
        if m and t:
            age = int(m.group(1)); vals = [float(v) for v in m.group(2).split()]
            if len(vals) != len(TYPES[t]): continue
            for k, v in zip(TYPES[t], vals):
                if k in KEEP: out[g].setdefault(KEEP[k], {})[age] = v
    # vetores contínuos por idade (30..100)
    res = {}
    for g, evs in out.items():
        for ev, d in evs.items():
            ages = sorted(d)
            res.setdefault(g, {})[ev] = {'from': ages[0], 'f': [d.get(a) for a in range(ages[0], ages[-1] + 1)]}
    return res

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    r = parse(src)
    for g in r:
        for ev, x in r[g].items():
            assert None not in x['f'], (g, ev)
            print(g, ev, x['from'], x['from'] + len(x['f']) - 1, x['f'][:1], x['f'][20:21])
    json.dump({'src': '2023 WMA Appendix B (one-year age factors)', 'factors': r}, open(dst, 'w'), separators=(',', ':'))
