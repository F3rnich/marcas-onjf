"""Junta legado + PDFs (+ 2026 quando disponível), normaliza, deduplica,
valida e exporta o JSON compacto que o painel consome."""
import json, sys, os, re, datetime
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from norm import *

D = os.path.join(ROOT, 'data')
FIELD = {'salto_altura', 'salto_distancia', 'salto_triplo', 'peso', 'dardo', 'disco'}

EDITIONS = {
    2009: ('VIII ONJT', None, 'completa'), 2010: ('IX ONJT', None, 'completa'), 2011: ('X ONJT', None, 'completa'),
    2012: ('XI ONJT', None, 'pódio'), 2013: ('XII ONJT', None, 'pódio'), 2014: ('XIII ONJT', None, 'pódio'),
    2015: ('XIV ONJT', None, 'pódio'), 2016: ('XV ONJT', None, 'pódio'), 2017: ('XVI ONJT', None, 'completa'),
    2018: ('XVII ONJT', None, 'completa'), 2019: ('XVIII ONJT', 'Belo Horizonte/MG', 'completa'),
    2022: ('XIX ONJT', 'Blumenau/SC', 'completa'), 2023: ('XX ONJT', 'João Pessoa/PB', 'completa'),
    2024: ('XXI ONJF', 'Manaus/AM', 'completa'), 2025: ('XXII ONJF', 'Foz do Iguaçu/PR', 'completa'),
    2026: ('XXIII ONJF', 'Aracaju/SE', 'completa'),
}
# comprimento da piscina por edição (fonte: anos citados nos PDFs oficiais de recordes 25 m / 50 m)
POOL = {2026: 50, 2012: 25, 2018: 25, 2022: 25, 2014: 50, 2015: 50, 2016: 50, 2017: 50, 2019: 50, 2023: 50, 2024: 50}

NOTES = {2026: 'só natação; atletismo pendente (sistema externo)'}

# limites inferiores de sanidade para provas de campo (abaixo disso é erro de digitação na súmula)
FIELD_MIN = {'salto_distancia': (1.5, 9), 'salto_triplo': (3, 17), 'salto_altura': (0.7, 2.4),
             'peso': (2, 20), 'disco': (5, 70), 'dardo': (4, 80)}

def load(p):
    return json.load(open(p)) if os.path.exists(p) else []

import glob
rows = load(f'{D}/legacy_raw.json') + load(f'{D}/pdf_raw.json')
for _f in sorted(glob.glob(f'{D}/y*_raw.json')): rows += load(_f)
for _y in {r['year'] for r in rows}:
    EDITIONS.setdefault(_y, (f'{_y}', None, 'completa'))
recs = load(f'{D}/records.json')

out = []; issues = Counter()
for r in rows:
    if r['year'] not in EDITIONS: continue
    kind = 'dist' if r['event'] in FIELD else 'time'
    st = (r.get('status') or '').upper().replace('N/C', 'NC').rstrip('.') or None
    if st and st.startswith('DES'): st = 'DQ'
    if st in ('DSQ', 'D.Q', 'DQL'): st = 'DQ'
    pr = plausible_range(r['modality'], r['event']) if kind == 'time' else FIELD_MIN.get(r['event'])
    v = parse_mark(r.get('mark_raw'), kind, pr) if not st else None
    if v is None and not st:
        if r.get('mark_raw'):
            # marca publicada mas incoerente com a prova (erro de diagramação da fonte): descarta a linha
            issues['descartada_marca_implausivel'] += 1; continue
        st = 'SM'
    dl = canon_deleg(r['deleg_raw'])
    nm = re.sub(r'^\d+\s+', '', r['name'] or '')
    if re.search(r'\s+PCD$', nm, re.I) and not r['event'].endswith('_pcd'):
        # natação 2026: prova PCD publicada dentro da faixa etária, com 'PCD' colado ao nome
        nm = re.sub(r'\s+PCD$', '', nm, flags=re.I)
        r = dict(r, event=r['event'] + '_pcd', event_label=r['event_label'] + ' (PCD)', age='única')
    if not nm or len(nm) < 4 or not re.search('[A-Za-zÀ-ú]{2}', nm):
        issues['nome_invalido'] += 1; continue
    out.append(dict(y=r['year'], mod=r['modality'], ev=r['event'], evl=r['event_label'], g=r['gender'] or '?',
                    age=canon_age(r['age']) or 'livre', pl=r['place'] if not st else None, n=nm, nk=name_key(nm),
                    d=dl or norm_space(r['deleg_raw']).upper() or 'NÃO INFORMADA', v=v, st=st, rec=bool(r.get('record')),
                    src=r['source']))

# unifica grafias do mesmo nome que só diferem por espaços (ex.: 'Rafaellagolzio Duarte')
by_compact = defaultdict(Counter)
for r in out: by_compact[r['nk'].replace(' ', '')][r['n']] += 1
canon_name = {}
for comp, cnt in by_compact.items():
    pick = max(cnt, key=lambda n: (n.count(' '), cnt[n]))
    for n in cnt: canon_name[n] = pick
for r in out:
    r['n'] = canon_name[r['n']]; r['nk'] = name_key(r['n'])

# unifica variações do mesmo atleta: partículas (di/de/da), abreviações (R.) e nomes cortados
PART = {'de', 'da', 'do', 'dos', 'das', 'di', 'e', 'del', 'du'}
def toks(n): return [t for t in name_key(n).split() if t not in PART]
def tok_eq(a, b):
    if a == b: return True
    if len(a) == 1 or len(b) == 1: return a[0] == b[0]
    return min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))
def contained(small, big):
    # cada token de 'small' casa, em ordem, com um token de 'big' (último token pode estar cortado: 'Ma' = 'Maia')
    i = 0
    for j, t in enumerate(small):
        last = j == len(small) - 1
        while i < len(big) and not (tok_eq(t, big[i]) or (last and len(t) >= 2 and big[i].startswith(t))): i += 1
        if i == len(big): return False
        i += 1
    return True
info = defaultdict(lambda: {'g': set(), 'd': Counter(), 'ye': set(), 'cnt': 0})
for r in out:
    o = info[r['n']]; o['g'].add(r['g']); o['d'][r['d']] += 1; o['ye'].add((r['y'], r['ev'])); o['cnt'] += 1
by_first = defaultdict(list)
for n in info:
    t = toks(n)
    if t: by_first[t[0]].append(n)
parent = {}
def find(n):
    while parent.get(n, n) != n: n = parent[n]
    return n
merges = []
for first, names in by_first.items():
    names.sort(key=lambda n: (-len(toks(n)), -info[n]['cnt']))
    for i, a in enumerate(names):
        for bn in names[i + 1:]:
            ta, tb = toks(a), toks(bn)
            small, big = (tb, ta) if len(tb) <= len(ta) else (ta, tb)
            if len(small) < 3 and not (len(small) == 2 and len(big) == 2): continue
            if not contained(small, big): continue
            ia, ib = info[a], info[bn]
            if not (ia['g'] & ib['g']) or not (set(ia['d']) & set(ib['d'])): continue
            if ia['ye'] & ib['ye']: continue          # mesma prova no mesmo ano: pessoas diferentes
            ra, rb = find(a), find(bn)
            if ra != rb:
                keep = max((ra, rb), key=lambda n: (info[n]['cnt'], len(toks(n)), len(n)))
                drop = rb if keep == ra else ra
                parent[drop] = keep; merges.append((drop, keep))
for r in out:
    k = find(r['n'])
    if k != r['n']: r['n'] = k; r['nk'] = name_key(k)
print('variações de nome unificadas', len(merges))
if os.environ.get('DEBUG_NAMES'):
    for d_, k_ in merges: print('   ', d_, '->', k_)

# deduplicação (mesma pessoa, mesma prova/faixa/ano)
best = {}
for r in out:
    k = (r['y'], r['ev'], r['g'], r['age'], r['nk'])
    if k not in best or (best[k]['v'] is None and r['v'] is not None):
        best[k] = r
dups = len(out) - len(best)
out = list(best.values())

# erros de diagramação da fonte (auditoria):
# 1) linha com gênero oposto ao de todas as outras participações do atleta (ex.: atleta masculino
#    impresso na lista feminina) é descartada
gcount = defaultdict(Counter)
for r in out: gcount[r['n']][r['g']] += 1
def wrong_gender(r):
    c = gcount[r['n']]; tot = sum(c.values())
    return c[r['g']] == 1 and tot >= 4 and (tot - 1) / tot >= 0.75
fixes = Counter()
kept = []
for r in out:
    if wrong_gender(r): fixes['genero_trocado_descartado'] += 1
    else: kept.append(r)
out = kept
# 2) delegação divergente do mesmo atleta na mesma edição: vale a da maioria das provas
dcount = defaultdict(Counter)
for r in out: dcount[(r['n'], r['y'])][r['d']] += 1
for r in out:
    c = dcount[(r['n'], r['y'])]
    if len(c) > 1:
        (top, n1), (_, n2) = c.most_common(2)
        if n1 > n2 and r['d'] != top: r['d'] = top; fixes['delegacao_unificada'] += 1
print('correções automáticas', dict(fixes))

# validação: colocação repetida dentro da mesma prova
grp = defaultdict(list)
for r in out: grp[(r['y'], r['ev'], r['g'], r['age'])].append(r)
for k, rs in grp.items():
    pls = [r['pl'] for r in rs if r['pl']]
    if len(pls) != len(set(pls)): issues['colocacao_repetida'] += 1
    # edições completas: colocações ausentes ou repetidas pela fonte são refeitas pela marca,
    # mantendo as colocações únicas publicadas; as refeitas vêm depois da maior colocação mantida
    if EDITIONS[k[0]][2] == 'completa':
        val = [r for r in rs if r['v'] is not None]
        rev = k[1] in FIELD
        val.sort(key=lambda r: -r['v'] if rev else r['v'])
        cnt = Counter(r['pl'] for r in val if r['pl'])
        redo = [r for r in val if not r['pl'] or cnt[r['pl']] > 1]
        if redo:
            keep = {r['pl'] for r in val if r['pl'] and cnt[r['pl']] == 1}
            dup_pl = [p for p in cnt if cnt[p] > 1]
            nxt = min(dup_pl) if dup_pl else (max(keep) + 1 if keep else 1)
            if any(not r['pl'] for r in redo) and not dup_pl: nxt = max(keep, default=0) + 1
            prev = None
            for r in redo:
                while nxt in keep: nxt += 1
                if prev and prev['v'] == r['v']: r['pl'] = prev['pl']
                else: r['pl'] = nxt; nxt += 1
                prev = r
            issues['colocacoes_refeitas'] += 1

print('linhas', len(out), 'duplicatas removidas', dups, dict(issues))
print('por ano', sorted(Counter(r['y'] for r in out).items()))

# ---------- export compacto ----------
evs = sorted({(r['mod'], r['ev'], r['evl']) for r in out} | {(x['modality'], x['event'], x['event_label']) for x in recs},
             key=lambda e: (e[0], e[1] in FIELD, int(re.match(r'(\d+)', e[1]).group(1)) if re.match(r'\d', e[1]) else 0, e[1]))
ev_ix = {e[1]: i for i, e in enumerate(evs)}
ages = sorted({r['age'] for r in out} | {x['age'] for x in recs if x['age']},
              key=lambda a: (a == 'livre', a == 'única', int(re.search(r'\d+', a).group()) if re.search(r'\d+', a) else 0, a))
age_ix = {a: i for i, a in enumerate(ages)}
# ---------- revezamentos ----------
rel_raw = load(f'{D}/relay_raw.json') + load(f'{D}/legacy_relays.json')
for _f in sorted(glob.glob(f'{D}/y*_relays.json')): rel_raw += load(_f)
# fontes transcritas à mão (resultados publicados só em telas/app, sem PDF): raw/manual/*revezamentos*.json
for _f in sorted(glob.glob(os.path.join(ROOT, 'raw/manual/*revezamentos*.json'))): rel_raw += load(_f)
# mapa de nomes: liga integrantes aos atletas já unificados (mesma chave de nome)
nk_to_name = {}
for r in out: nk_to_name.setdefault(r['nk'], r['n'])
ath_by_first = defaultdict(list)
ath_dels = defaultdict(set)
for r in out: ath_dels[r['n']].add(r['d'])
for n in ath_dels:
    t = toks(n)
    if t: ath_by_first[t[0]].append(n)
member_links = Counter()
def canon_member(n, deleg):
    k = name_key(n)
    if k in nk_to_name: member_links['exato'] += 1; return nk_to_name[k]
    t = toks(n)
    if not t: return n
    cands = [a for a in ath_by_first.get(t[0], []) if deleg in ath_dels[a]]
    hits = [a for a in cands if contained(t, toks(a)) or contained(toks(a), t)]
    if len(hits) == 1: member_links['aproximado'] += 1; return hits[0]
    member_links['sem_par'] += 1
    return n
def member_ok(m):
    # descarta lixo de diagramação lido como integrante ('Piscina', 'R', 'Rt')
    return bool(m) and len(toks(m)) >= 2 and not re.search(r'\d|piscina|revez|equipe', m, re.I)
rel = []; rel_issues = Counter()
for r in rel_raw:
    if r['year'] not in EDITIONS or not r.get('event'): continue
    leg = int(re.search(r'4x(\d+)', r['event']).group(1))
    st = (r.get('status') or '').upper().replace('N/C', 'NC') or None
    if st and (st.startswith('DES') or st in ('DSQ', 'DQL')): st = 'DQ'
    if st == 'CORTE': st = 'NC'
    lo = 4 * leg / (2.4 if r['modality'] == 'Natação' else 10.5)
    v = parse_mark(r.get('mark_raw'), 'time', (lo, lo * 10)) if not st else None
    keep_pl = False
    if v is None and not st:
        if r.get('mark_raw'): rel_issues['marca_implausivel_mantida_sem_tempo'] += 1; keep_pl = True
        st = 'SM'
    dl = canon_deleg(r['deleg_raw']) or norm_space(r['deleg_raw']).upper() or 'NÃO INFORMADA'
    cat = r.get('cat') or 'livre'
    rel.append(dict(y=r['year'], mod=r['modality'], ev=r['event'], evl=r['event_label'], g=r.get('gender') or '?', cat=cat,
                    pl=r.get('place') if (not st or keep_pl) else None, d=dl, v=v, st=st, mem=list(dict.fromkeys(canon_member(m, dl) for m in (r.get('members') or []) if member_ok(m)))))
seen = {}; 
for r in rel:
    k = (r['y'], r['ev'], r['g'], r['cat'], r['d'], r['v'], r['st'], tuple(sorted(r['mem'])))
    if k not in seen or len(r['mem']) > len(seen[k]['mem']): seen[k] = r
rel = list(seen.values())
rg = defaultdict(list)
for r in rel: rg[(r['y'], r['ev'], r['g'], r['cat'])].append(r)
for k, rs in rg.items():
    if EDITIONS[k[0]][2] == 'completa':
        val = sorted([r for r in rs if r['v'] is not None], key=lambda r: r['v'])
        if any(r['pl'] is None for r in val) or len({r['pl'] for r in val}) != len(val):
            for i, r in enumerate(val): r['pl'] = i + 1
print('integrantes ligados', dict(member_links))
print('revezamentos', len(rel), dict(rel_issues), sorted(Counter(r['y'] for r in rel).items()))

names = sorted({r['n'] for r in out} | {m for r in rel for m in r['mem']}); n_ix = {n: i for i, n in enumerate(names)}
dels = sorted({r['d'] for r in out} | {r['d'] for r in rel}); d_ix = {d: i for i, d in enumerate(dels)}
ST = ['', 'DNS', 'DNF', 'DQ', 'NC', 'SM', 'NM', 'NT', 'AUS', 'WO']
def st_ix(s):
    s = (s or '').upper()
    if s.startswith('W'): s = 'WO'
    return ST.index(s) if s in ST else ST.index('SM')

# recordes oficiais; corrige a transcrição de décimos como centésimos (12.2 -> '12.02')
# quando a súmula da própria prova (mesmo atleta, mesmo ano) confirma o valor em décimos
res_idx = defaultdict(list)
for r in out: res_idx[(r['y'], r['ev'], r['g'], r['age'])].append(r)
rec_out = []; fixed = 0
for x in recs:
    if x['age'] not in age_ix: continue
    kind = 'dist' if x['event'] in FIELD else 'time'
    v = parse_mark(x['mark_raw'], kind)
    if not v: continue
    corr = 0
    cent = round((v - int(v)) * 100)
    if kind == 'time' and 0 < cent < 10:
        alt = int(v) + cent / 10
        toks = set(name_key(x['name']).split())
        for r in res_idx.get((x['year'], x['event'], x['gender'], x['age']), []):
            if r['v'] is not None and abs(r['v'] - alt) < 0.005 and len(toks & set(r['nk'].split())) >= 2:
                v = alt; corr = 1; fixed += 1; break
    rec_out.append([ev_ix[x['event']], x['gender'], age_ix[x['age']], x['pool'] or 0, x['name'], x['deleg'], round(v, 2), x['year'], corr])
print('recordes corrigidos (décimos)', fixed)

rel_events = sorted({(r['mod'], r['ev'], r['evl']) for r in rel}, key=lambda e: (e[0], int(re.search(r'4x(\d+)', e[1]).group(1)), e[1]))
rev_ix = {e[1]: i for i, e in enumerate(rel_events)}
rel_events = [dict(mod=e[0], key=e[1], label=e[2]) for e in rel_events]
rel_cats = sorted({r['cat'] for r in rel}, key=lambda c: (c != 'livre', c)); rcat_ix = {c: i for i, c in enumerate(rel_cats)}
rel_rec_out = []
for x in load(f'{D}/relay_records.json'):
    if x['event'] not in rev_ix or x['cat'] not in rcat_ix: continue
    v = parse_mark(x['mark_raw'], 'time'); corr = 0
    cent = round((v - int(v)) * 100) if v else 0
    if v and 0 < cent < 10:
        alt = int(v) + cent / 10
        if any(r['y'] == x['year'] and r['ev'] == x['event'] and r['g'] == x['gender'] and r['v'] is not None and abs(r['v'] - alt) < 0.005 for r in rel):
            v = alt; corr = 1
    if v: rel_rec_out.append([rev_ix[x['event']], x['gender'], rcat_ix[x['cat']], x['pool'] or 0, x['deleg'], round(v, 2), x['year'], corr])

data = dict(
    meta=dict(generated=datetime.date.today().isoformat(),
              editions=[dict(y=y, ed=e[0], city=e[1], cov=e[2], pool=POOL.get(y), note=NOTES.get(y) if not ({'Atletismo','Natação'} <= {r['mod'] for r in out if r['y']==y}) else None) for y, e in sorted(EDITIONS.items())
                        if any(r['y'] == y for r in out)],
              missing=[2007, 2008] + ([2026] if not any(r['y'] == 2026 for r in out) else [])),
    events=[dict(mod=e[0], key=e[1], label=e[2], field=e[1] in FIELD) for e in evs],
    ages=ages, names=names, dels=dels, st=ST,
    rows=[[r['y'], ev_ix[r['ev']], r['g'], age_ix[r['age']], r['pl'] or 0, n_ix[r['n']], d_ix[r['d']],
           round(r['v'], 2) if r['v'] is not None else None, st_ix(r['st']), 1 if r['rec'] else 0] for r in out],
    records=rec_out,
    rel_events=rel_events, rel_cats=rel_cats,
    relays=[[r['y'], rev_ix[r['ev']], r['g'], rcat_ix[r['cat']], r['pl'] or 0, d_ix[r['d']],
             round(r['v'], 2) if r['v'] is not None else None, st_ix(r['st']), [n_ix[m] for m in r['mem']]] for r in rel],
    rel_records=rel_rec_out,
)
# fatores de idade da WMA (age-grading), se disponíveis
if os.path.exists(f'{D}/wma.json'):
    data['wma'] = {g: {ev_ix[k]: v for k, v in evs.items() if k in ev_ix} for g, evs in json.load(open(f'{D}/wma.json'))['factors'].items()}
json.dump(data, open(f'{D}/onjt.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('json bytes', os.path.getsize(f'{D}/onjt.json'), 'eventos', len(evs), 'faixas', ages)

if os.environ.get('DEBUG_DUP'):
    n = 0
    for k, rs in grp.items():
        pls = [r['pl'] for r in rs if r['pl']]
        if len(pls) != len(set(pls)):
            dupl = {p for p in pls if pls.count(p) > 1}
            print(k, [(r['pl'], r['n'], r['v'], r['src'][:25]) for r in rs if r['pl'] in dupl][:6]); n += 1
            if n > 14: break
