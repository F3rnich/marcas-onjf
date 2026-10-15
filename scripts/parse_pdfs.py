"""Parsers dos PDFs de resultados (2017-2025). Cada parser recebe o texto
(pdftotext -layout) e devolve linhas cruas normalizadas parcialmente."""
import re, sys, json, os
sys.path.insert(0, os.path.dirname(__file__))
from norm import *

MARK_TOKEN = re.compile(r"^J?\d{1,2}(?:[:'.,\"]\d{1,2}){1,3}m?$|^\d{1,2}[.,]\d{1,2}m?$")
STATUS_TOKEN = re.compile(r'^(DNS|DNF|DQ|DSQ|NC|N/C|NT|NM|DES|W\.?O\.?|DESC\w*|AUS|ABANDONOU|FALTOU)$', re.I)

def pcd(ev, header):
    if ev and re.search(r'PCD|DEFICI', header, re.I):
        return (ev[0], ev[1] + '_pcd', ev[2] + ' (PCD)')
    return ev

def row(year, src, ev, gender, age, place, name, deleg, mark, status=None, record=False, modality_hint=None):
    if not ev: return None
    mod, key, lab = ev
    return dict(year=year, source=src, modality=mod, event=key, event_label=lab, gender=gender, age=age,
                place=place, name=title_name(name), deleg_raw=norm_space(deleg or ''), mark_raw=mark,
                status=(status or '').upper() or None, record=record)

def split_tail(tail):
    """Do texto após a delegação extrai (marca, status, place_inline, record)."""
    toks = [re.sub(r'(?<=\d)(RC|RB|RN|PB|SB|\*)$', '', t) for t in tail.split()]
    mark = status = None; place = None
    rec = bool(re.search(r'RECORD|(?<![A-Z])RC(?![A-Z])', tail, re.I))
    for t in toks:
        if mark is None and status is None and MARK_TOKEN.match(t):
            mark = t; continue
        if status is None and mark is None and STATUS_TOKEN.match(t):
            status = t; continue
    return mark, status, rec

def age_group(age, year):
    if age <= 34: return 'até 34'
    if age >= 60 and year <= 2019: return '60+'
    a = age - age % 5; return f'{a}-{a+4}'

def infer_age_from_birth(rows, year):
    from collections import defaultdict
    grp = defaultdict(list)
    for r in rows:
        if r and not r['age'] and r.get('_birth'): grp[(r['event'], r['gender'])].append(r)
    for k, rs in grp.items():
        labs = {age_group(year - r['_birth'], year) for r in rs}
        if len(labs) == 1:
            for r in rs: r['age'] = labs.pop() if False else age_group(year - r['_birth'], year)
    for r in rows:
        if r: r.pop('_birth', None)
    return rows

RELAY_RX = re.compile(r'REVEZ|\b\d\s*[xX]\s*\d{2,3}', re.I)

def find_deleg(line):
    ms = list(DELEG_RX.finditer(line))
    return ms[-1] if ms else None

# ---------------------------------------------------------------- 2017
def p2017(text, year, src, modality):
    lines = text.splitlines()
    gender = None; ev = None
    groups = []  # cada grupo: dict(ev, gender, rows=[(lineno,row)], labels=[])
    cur = None; labels = []
    events_seen = []
    def flush_labels():
        pass
    out_events = []  # (ev, gender, rows, labels)
    rows = []; lab_lines = []
    def close_event():
        if ev and rows:
            out_events.append((ev, gender, list(rows), list(lab_lines)))
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s: continue
        m = find_deleg(ln)
        if m:
            pre = ln[:m.start()]
            tail = ln[m.end():]
            agepre = None
            # remove rótulo de faixa no início
            mm = re.match(r'\s*((?:at[eé]\s+\d{2}|de\s+\d{2}\s*a\s*\d{2}|de\s+60|60\s+anos|acima(?:\s+de\s+\d{2})?|\d{2}\s*anos\s*(?:e\s*acima|ou\s*mais|\+))(?:\s*anos)?|anos)\s+(.*)$', pre, re.I)
            if mm:
                a_ = '60+' if re.match(r'(de\s+60|60\s+anos)\s*$', mm.group(1), re.I) else detect_age(mm.group(1))
                if a_: lab_lines.append((i, a_))
                pre = mm.group(2)
            name = pre.strip()
            toks = tail.split()
            mark, status, rec = split_tail(tail)
            place = None
            after = [t for t in tail.split() if t.lower() != 'm']
            for k, t in enumerate(after):
                if (mark and t == mark) or (status and t == status):
                    if k + 1 < len(after) and after[k + 1].isdigit(): place = int(after[k + 1])
                    break
            rows.append((i, dict(place=place, name=name, deleg=m.group(0), mark=mark, status=status, rec=rec)))
            continue
        up = strip_acc(s).upper()
        if re.fullmatch(r'(NATACAO\s+|ATLETISMO\s+)?(MASCULINO|FEMININO|MISTO)', up):
            close_event(); rows.clear(); lab_lines.clear(); ev = None
            gender = detect_gender(up); continue
        if up.startswith('FAIXA ETARIA') or up.startswith('BOLETIM') or up.startswith('NC -'):
            continue
        if RELAY_RX.search(s) and len(s) < 60:
            close_event(); rows.clear(); lab_lines.clear(); ev = None; continue
        a = detect_age(s)
        if a and len(s) < 30:
            lab_lines.append((i, a)); continue
        e = detect_event(s, modality)
        if e and len(s) < 45:
            close_event(); rows.clear(); lab_lines.clear()
            ev = e; continue
    close_event()
    out = []
    for ev_, g, rws, labs in out_events:
        # agrupa: novo grupo quando place == 1
        grp = []
        for ln, r in rws:
            if r['place'] == 1 or not grp:
                grp.append([ln, ln, [r]])
            else:
                grp[-1][1] = ln; grp[-1][2].append(r)
        glabs = [None] * len(grp)
        for ln, a in labs:
            if not a: continue
            best = min(range(len(grp)), key=lambda k: 0 if grp[k][0] <= ln <= grp[k][1] else min(abs(ln - grp[k][0]), abs(ln - grp[k][1])) + 0.5)
            if glabs[best] is None: glabs[best] = a
        for k in range(len(glabs)):
            if glabs[k] is None and k > 0 and glabs[k - 1] in ('55-59', '50-54') and k == len(glabs) - 1:
                glabs[k] = '60+'
        for (a0, a1, rs), age in zip(grp, glabs):
            for r in rs:
                out.append(row(year, src, ev_, g, age, r['place'], r['name'], r['deleg'], r['mark'], r['status'], r['rec']))
    return out

# ---------------------------------------------------------------- 2018
def p2018(text, year, src, modality):
    out = []; ev = g = age = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s: continue
        m = find_deleg(ln)
        if m and ev:
            name = ln[:m.start()].strip()
            tail = ln[m.end():]
            mark, status, rec = split_tail(tail)
            toks = tail.split()
            place = int(toks[0]) if toks and toks[0].isdigit() else None
            if name:
                out.append(row(year, src, ev, g, age, place, name, m.group(0), mark, status, rec))
            continue
        if RELAY_RX.search(s) and not m and len(s) < 80:
            ev = None; continue
        e = detect_event(s, modality)
        if e and not m:
            ev = e; g = detect_gender(s); age = detect_age(s)
    return out

# ---------------------------------------------------------------- 2019 natação
def p2019n(text, year, src, modality):
    out = []; ev = g = age = None
    for ln in text.splitlines():
        s = ln.strip()
        mh = re.match(r'\d+ª\s+PROVA\s+(.*)', s)
        if mh:
            h = mh.group(1); ev = detect_event(h, 'Natação'); g = detect_gender(h); age = detect_age(h.split(' - ')[-1] if ' - ' in h else h)
            continue
        mr = re.match(r'^\s*(\d+)º\s+\d+\s+\d+\s+(.+?)\s+\d{5,6}\s+\d{2}\s+(.*)$', ln)
        ms = re.match(r'^\s*(N/C|NC|DQ|DESC\w*)\s+\d+\s+\d+\s+(.+?)\s+\d{5,6}\s+\d{2}\s+(.*)$', ln)
        mm = mr or ms
        if mm and ev:
            tail = mm.group(3)
            m = find_deleg(tail)
            mark, status, rec = split_tail(tail[m.end():] if m else tail)
            place = int(mm.group(1)) if mr else None
            if ms: status = mm.group(1)
            r = row(year, src, ev, g, age, place, mm.group(2), m.group(0) if m else '', mark, status, rec)
            yy = re.search(r'\s(\d{2})\s+\S', ln[ln.find(mm.group(2)) + len(mm.group(2)):])
            if r and yy: r['_birth'] = 1900 + int(yy.group(1))
            out.append(r)
    return infer_age_from_birth(out, year)

# ---------------------------------------------------------------- Hy-Tek (2019 atletismo)
def phytek(text, year, src, modality):
    out = []; ev = g = age = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]; s = ln.strip()
        mh = re.match(r'^(Feminino|Masculino|Misto)\s+(\S+)\s+(.*)$', s)
        if mh and not find_deleg(s):
            g = detect_gender(mh.group(1)); age = detect_age(mh.group(2)) or detect_age(s)
            ev = detect_event(mh.group(3), 'Atletismo'); i += 1; continue
        mr = re.match(r'^\s*(\d+|--)\s+\d+\s+(.+?)\s*(\d{2})\s+\d+\s+((?:Trt|Tst)\S*)\s*(.*)$', ln)
        if not mr and re.match(r'^\s*(\d+|--)\s+\d+\s+\D+$', ln) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if re.match(r'^\s+\d{2}\s+\d+\s+(Trt|Tst)', nxt):
                ln = ln.rstrip() + ' ' + nxt.strip(); i += 1
                mr = re.match(r'^\s*(\d+|--)\s+\d+\s+(.+?)\s*(\d{2})\s+\d+\s+((?:Trt|Tst)\S*)\s*(.*)$', ln)
        if mr and ev:
            tail = mr.group(5)
            toks = tail.split()
            marks = [t for t in toks if MARK_TOKEN.match(t) or STATUS_TOKEN.match(t)]
            mark = status = None
            if marks:
                last = marks[-1]
                if STATUS_TOKEN.match(last): status = last
                else: mark = last
            place = int(mr.group(1)) if mr.group(1).isdigit() else None
            name = mr.group(2).replace(',', ' ')
            out.append(row(year, src, ev, g, age, place, name, mr.group(4), mark, status, bool(re.search('RECORD', tail, re.I))))
        i += 1
    return out

# ---------------------------------------------------------------- 2022 atletismo (tabela CBAt simplificada)
def p2022a(text, year, src, modality):
    out = []; ev = g = None; age = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s: continue
        m = find_deleg(ln)
        if not m:
            if RELAY_RX.search(s) and re.search(r'Final|Feminino|Masculino|Misto', s, re.I):
                ev = None; continue
            e = detect_event(s, 'Atletismo')
            if e and re.search(r'Final|Feminino|Masculino', s, re.I):
                ev = e; g = detect_gender(s); age = None; continue
            s = re.sub(r'^\d+ª\s+', '', s)
            if re.match(r'(\d{2}\s*A\s*\d{2}|AT[EÉ]\s*\d{2}|\d{2}\s*\+|\d{2}\s*(ANOS)?\s*(E\s*ACIMA|\+|OU\s*MAIS)|ACIMA\s*DE\s*\d{2})(\s|$|[–-])', s.upper()):
                age = detect_age(re.split(r'\s[–-]\s', s)[0]); continue
            continue
        mr = re.match(r'^\s*(\d+)?\s+(\d+)\s+(.+?)\s*$', ln[:m.start()])
        if mr and ev:
            name = re.sub(r'\d{2}/\d{2}/\d{4}', '', mr.group(3)).strip()
            mark, status, rec = split_tail(ln[m.end():])
            out.append(row(year, src, ev, g, age, int(mr.group(1)) if mr.group(1) else None, name, m.group(0), mark, status, rec))
    return out

# ---------------------------------------------------------------- 2022 natação
def p2022n(text, year, src, modality):
    out = []; ev = g = age = None
    for ln in text.splitlines():
        s = ln.strip()
        mh = re.match(r'\d+ª\s*PROVA\s*[–-]\s*(.*)', s)
        if mh:
            h = mh.group(1); ev = detect_event(h, 'Natação'); g = detect_gender(h)
            age = detect_age(re.split(r'[–-]', h)[-1]); continue
        m = find_deleg(ln)
        if m and ev:
            pre = re.sub(r'^\s*\d{1,2}\s+', '', ln[:m.start()]).strip()
            tail = ln[m.end():]
            mark, status, rec = split_tail(tail)
            mp = re.search(r'(\d+)\s*º', tail)
            if pre:
                out.append(row(year, src, ev, g, age, int(mp.group(1)) if mp else None, pre, m.group(0), mark, status, rec))
    return out

# ---------------------------------------------------------------- software de natação 2023/2024
def pswim2324(text, year, src, modality):
    out = []; ev = g = age = None
    for ln in text.splitlines():
        s = ln.strip()
        mh = re.match(r'\d+\s*ª\s*PROVA\s+(.*?)(\s{3,}\d{2}/\d{2}/\d{4})?$', s)
        if mh:
            h = mh.group(1); ev = detect_event(h, 'Natação'); g = detect_gender(h)
            age = detect_age(h.split(' - ', 1)[1]) if ' - ' in h else None; continue
        mr = re.match(r'^\s*(\d+º|N/C|NC|DQL?|D\.Q\.|DESC\w*|DNS|W\.?O\.?)\s+\d+\s+\d+\s+(.+?)\s+V?\d{5,}\s+(\d{4})\s+(.*)$', ln)
        if mr and ev:
            tail = mr.group(4)
            m = find_deleg(tail)
            mark, status, rec = split_tail(tail[m.end():] if m else '')
            p = mr.group(1)
            place = int(p[:-1]) if p.endswith('º') else None
            if place is None: status = p
            out.append(row(year, src, ev, g, age, place, mr.group(2), m.group(0) if m else '', mark, status, rec))
    return out

# ---------------------------------------------------------------- CBAt (2023 e 2025 atletismo)
def pcbat(text, year, src, modality):
    out = []; ev = g = age = None
    for ln in text.splitlines():
        s = ln.strip()
        if re.search(r'-\s*(Feminino|Masculino|Misto)\s*-\s*(Final|Eliminat|Semi)', s, re.I):
            h = re.sub(r'\s{2,}Recorde.*$', '', s)
            e = pcd(detect_event(h, 'Atletismo'), h)
            ev = e; g = detect_gender(h)
            age = detect_age(h) if not (e and e[1].endswith('_pcd')) else 'única'
            continue
        mr = re.match(r'^\s*(\d+)?\s+\d+\s+\d+\s+(?:\(est\)\s*)?(.+?)\s+\d{2}/\d{2}/\d{2,4}\s+(.*)$', ln)
        if mr and ev:
            tail = mr.group(3)
            m = find_deleg(tail)
            if not m: continue
            mark, status, rec = split_tail(tail[m.end():])
            out.append(row(year, src, ev, g, age, int(mr.group(1)) if mr.group(1) else None, mr.group(2), m.group(0), mark, status, rec))
    return out

# ---------------------------------------------------------------- 2024 atletismo
def p2024a(text, year, src, modality):
    out = []; ev = g = age = None; last = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s: last = None; continue
        if re.search(r'[–-]\s*(FEMININO|MASCULINO|MISTO)\s*[–-]', s, re.I) and not find_deleg(s):
            ev = pcd(detect_event(s, 'Atletismo'), s); g = detect_gender(s); age = detect_age(s); last = None
            if ev and ev[1].endswith('_pcd'): age = 'única'
            continue
        m = find_deleg(ln)
        if m and ev:
            pre = ln[:m.start()]
            mp = re.match(r'^\s*(\d+)\s*[°º]\s*(.*)$', pre)
            name = (mp.group(2) if mp else pre)
            name = re.sub(r'\b\d{2}/\d{2}/\d{2,4}\b|\b(19|20)\d{2}\b', '', name).strip()
            mark, status, rec = split_tail(ln[m.end():])
            r = row(year, src, ev, g, age, int(mp.group(1)) if mp else None, name, m.group(0), mark, status, rec)
            out.append(r); last = r; continue
        if last and re.fullmatch(r"[A-ZÀ-Ú' ]{3,}", s) and len(ln) - len(ln.lstrip()) > 4:
            last['name'] = title_name(last['name'] + ' ' + s); continue
        last = None
    return out

# ---------------------------------------------------------------- 2025 natação (FDAP)
def pfdap(text, year, src, modality):
    out = []; ev = g = None; age = None
    for ln in text.splitlines():
        s = ln.strip()
        mh = re.match(r'^Prova\s+\d+\s+(.*?)\s{3,}(\S.*)$', s)
        if mh:
            h = mh.group(1); ev = detect_event(h, 'Natação'); g = detect_gender(h); age = None; continue
        mc = re.search(r'Classe de Prova:\s*(\S+(?: \S+)?)', s)
        if mc:
            c = mc.group(1); age = detect_age(c.replace('/', ' a ')) if '/' in c else detect_age(c); continue
        mr = re.match(r'^\s*(\d+\.|DSQ|DNS|DQ|NC)?\s*\d+\s*/\s*\d+\s+(.+?)\s+(\d{4})\s+(\S.*)$', ln)
        if mr and ev:
            name = re.sub(r'\s+S\d{3,}\s*$|\bS\d{3,}\b', '', mr.group(2)).strip()
            tail = mr.group(4)
            m = find_deleg(tail)
            mark, status, rec = split_tail(tail[m.end():] if m else tail)
            p = mr.group(1)
            place = int(p[:-1]) if p and p.endswith('.') else None
            if p and not p.endswith('.'): status = p
            out.append(row(year, src, ev, g, age, place, name, m.group(0) if m else '', mark, status, rec))
    return out

SOURCES = [
    # (ano, arquivo txt, parser, modalidade)
    (2017, '2017__BOLETIM-GERAL-ATLETISMO1', p2017, 'Atletismo'),
    (2017, '2017__BOLETIM-GERAL-NATACAO', p2017, 'Natação'),
    (2018, '2018__Atletismo', p2018, 'Atletismo'),
    (2018, '2018__Natacao', p2018, 'Natação'),
    (2019, '2019__anastra-dia-1-evento-por-pagina', phytek, 'Atletismo'),
    (2019, '2019__Atletismo-segundo-dia', phytek, 'Atletismo'),
    (2019, '2019__Resultados-primeiro-dia', p2019n, 'Natação'),
    (2019, '2019__Resultados-segundo-Dia', p2019n, 'Natação'),
    (2022, '2022__BOLETIM-ANASTRA', p2022a, 'Atletismo'),
    (2022, '2022__resultados-etapa-1-natacao', p2022n, 'Natação'),
    (2022, '2022__RESULTADO-NATACAO-2a-etapa', p2022n, 'Natação'),
    (2023, '2023__Resultado-Completo-do-Atletismo', pcbat, 'Atletismo'),
    (2023, '2023__Resultado-Final-da-Natacao-1', pswim2324, 'Natação'),
    (2024, '2024__Resultados-do-Atletismo-1o-dia-Corrigido', p2024a, 'Atletismo'),
    (2024, '2024__Resultados-do-Atletismo-2o-dia', p2024a, 'Atletismo'),
    (2024, '2024__Resultados-do-Atletismo-3o-dia', p2024a, 'Atletismo'),
    (2024, '2024__Resultados-Finais-da-Natacao-2024-2-dias', pswim2324, 'Natação'),
    (2025, '2025__Resultado-final-1', pcbat, 'Atletismo'),
    (2025, '2025__Resultados-Completo', pfdap, 'Natação'),
]

if __name__ == '__main__':
    txtdir = sys.argv[1]; outp = sys.argv[2]
    allr = []
    for y, f, fn, mod in SOURCES:
        t = open(os.path.join(txtdir, f + '.txt'), encoding='utf-8', errors='replace').read()
        rs = [r for r in fn(t, y, f, mod) if r]
        ev = len({(r['event'], r['gender'], r['age']) for r in rs})
        noage = sum(1 for r in rs if not r['age']); nog = sum(1 for r in rs if not r['gender'])
        nomark = sum(1 for r in rs if not r['mark_raw'] and not r['status'])
        print(f'{y} {f[:48]:48} rows={len(rs):4} provas={ev:3} sem_faixa={noage:3} sem_genero={nog:3} sem_marca={nomark:3}')
        allr += rs
    json.dump(allr, open(outp, 'w'), ensure_ascii=False, indent=0)
