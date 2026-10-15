"""Revezamentos (atletismo e natação), 2017-2025 a partir dos PDFs.
Um motor genérico com quatro modos de associar integrantes à equipe:
  after   integrantes vêm depois da linha da equipe
  inline  a linha da equipe já traz o 1º integrante; os demais vêm depois
  around  2 integrantes antes e 2 depois da linha da equipe
  none    a fonte não lista integrantes
"""
import re, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from norm import strip_acc, detect_gender, detect_age, detect_event, DELEG_RX, title_name, norm_space

MARK = re.compile(r"^J?\d{1,2}(?:[:'.,\"]\d{1,2}){1,3}$")
STAT = re.compile(r'^(DNS|DNF|DQ|DSQ|NC|N/C|DESC\w*|CORTE|W\.?O\.?)$', re.I)
STOP = {'ONJT', 'ONJF', 'PROGRAMA', 'PROVAS', 'PROVA', 'RESULTADO', 'RESULTADOS', 'OLIMPIADA', 'NACIONAL', 'JUDICIARIO',
        'ARBITRAGEM', 'PAGINA', 'RELATORIO', 'TEMPO', 'CLASSIFICACAO', 'NOME', 'ATLETA', 'EQUIPE', 'MASTER', 'FINAL',
        'CATEGORIA', 'ETAPA', 'LOCAL', 'DATA', 'HORA', 'UMIDADE', 'TEAM', 'REVEZAMENTO', 'TRIBUNAL', 'DELEGACAO', 'RAIA',
        'COMPARECEU', 'PATROCINIO', 'ENTIDADE', 'CLUBE', 'OBTIDO', 'ANOTACOES', 'TENTATIVAS', 'SERIE', 'VENTO', 'JUSTICA',
        'TRABALHO', 'FEDERAL', 'BOLETIM', 'GERAL', 'TABELA', 'PONTOS', 'AQUA', 'ABSOLUTO', 'RECORDE', 'MODALIDADE'}

def relay_header(s, modality, gctx):
    t = strip_acc(norm_space(s)).upper()
    t = re.sub(r'^\d+\s*ª?\s*PROVA\b|^PROVA\s+\d+', ' ', t)          # número da prova não é categoria
    t = re.sub(r'\d{2}/\d{2}/\d{4}', ' ', t)
    if not re.search(r'REVEZ|\bREV\.|\b4\s*X\s*\d{2,3}', t): return None
    m = re.search(r'4\s*X\s*(\d{2,3})', t)
    if not m: return None
    leg = int(m.group(1))
    if re.search(r'MEDLEY|4 ESTILOS|MEDLEI', t): style = 'medley'
    elif 'LIVRE' in t or modality == 'Natação': style = 'livre'
    else: style = 'rasos'
    mod = 'Natação' if style in ('livre', 'medley') else 'Atletismo'
    if mod == 'Atletismo' and leg not in (100, 400): return None
    if mod == 'Natação' and leg not in (50, 100): return None
    g = detect_gender(t) or gctx
    mc = re.search(r'(?<![X\d])(?<!X )\b(1[2-9]0|2[0-4]0)\b(?!\s*M\b|\s*METROS|M\b)', t)
    # revezamentos só têm categoria livre ou por soma de idades (ex.: 180 anos); rótulos de faixa do software são ignorados
    cat = f'{mc.group(1)} anos' if mc else 'livre'
    key = f'rev_4x{leg}_{style}'
    lab = f'4x{leg} m' + ('' if style == 'rasos' else f' {style}')
    return dict(mod=mod, key=key, label=lab, g=g, cat=cat)

def clean_member(s):
    s = re.sub(r'\(est\)', ' ', s, flags=re.I)
    s = re.sub(r'\bV?\d{3,}[A-Z]?\b|\b\d{2}/\d{2}/\d{2,4}\b|\b\d{1,2}\b|"[A-Z]"', ' ', s)
    s = norm_space(s)
    words = [w for w in s.split() if re.fullmatch(r"[A-Za-zÀ-ÿ.'-]+", w)]
    if len(words) < 2: return None
    if any(strip_acc(w).upper().strip('.') in STOP for w in words): return None
    return title_name(' '.join(words))

def member_chunks(line):
    out = []
    for ch in re.split(r'\s{2,}', line.strip()):
        n = clean_member(ch)
        if n: out.append(n)
    return out

def parse(text, year, src, modality, mode):
    out = []; cur = None; gctx = None; team = None; pending = []
    lines = text.splitlines()
    for ln in lines:
        s = ln.strip()
        if not s: continue
        up = strip_acc(s).upper()
        if re.fullmatch(r'(NATACAO\s+|ATLETISMO\s+)?(MASCULINO|FEMININO|MISTO)', up):
            gctx = detect_gender(up); continue
        h = relay_header(s, modality, gctx)
        if h:
            cur = h; team = None; pending = []; continue
        mcl = re.search(r'Classe de Prova:\s*(\S+)', s)
        if cur and mcl:
            c = mcl.group(1)
            cur = dict(cur, cat=(c + ' anos') if re.fullmatch(r'\d{3}', c) else 'livre'); continue
        if re.match(r'^(RE|RC|RB|RN|RS|RSA)\s', s):   # linhas de recorde no cabeçalho da prova
            continue
        # saída do modo revezamento ao encontrar prova individual
        hs = norm_space(re.split(r'\s{3,}Recorde', s)[0])
        if cur and not DELEG_RX.search(ln) and len(hs) < 120:
            e = detect_event(hs, modality)
            if e and re.search(r'PROVA|RASOS|METROS|SALTO|ARREMESSO|LAN[CÇ]AMENTO|FEMININO|MASCULINO|\d+M\b|\dm\b', up):
                cur = None; team = None; pending = []; continue
        if not cur: continue
        if up.startswith('RC ') or 'RECORDE' in up and not re.search(r'\d{1,2}[.:]\d{2}', s.split('Recorde')[0] if 'Recorde' in s else ''):
            if up.startswith('RC '): continue
        ms = list(DELEG_RX.finditer(ln))
        if ms:
            m = ms[-1]
            tail = ln[m.end():].split()
            mark = st = None; place = None
            for i, tk in enumerate(tail):
                tk2 = re.sub(r'(RC|RB|PB)$', '', tk)
                if MARK.match(tk2) and not mark and not st:
                    mark = tk2
                    if i + 1 < len(tail) and tail[i + 1].isdigit() and int(tail[i + 1]) < 40 and not re.search(r'[º°.]', ln[:m.start()].strip()[:3] or 'x'):
                        nxt = int(tail[i + 1])
                        if not re.match(r'^\s*\d', ln): place = nxt
                    break
                if STAT.match(tk2) and not mark:
                    st = tk2; break
                if tk2.isdigit() and int(tk2) < 40 and place is None and i == 0 and not re.match(r'^\s*\d', ln):
                    place = int(tk2)
            pre = ln[:m.start()]
            lp = re.match(r'^\s*(\d{1,2})\s*[º°.]?\s', pre)
            if lp: place = int(lp.group(1))
            ls = re.match(r'^\s*(N/C|NC|DQ|DSQ|DNS|DNF|CORTE|DESC\w*)\b', pre, re.I)
            if ls: st = ls.group(1); place = None
            if not mark and not st:
                st = 'SM'
            if st: place = None
            members = []
            if mode == 'inline':
                pre2 = DELEG_RX.sub(' ', pre)
                n = clean_member(re.sub(r'^\s*\d{1,2}\s*[º°.]?\s', ' ', pre2))
                if n: members.append(n)
            if mode == 'around':
                members = pending[:2]; pending = []
            team = dict(year=year, source=src, modality=cur['mod'], event=cur['key'], event_label=cur['label'],
                        gender=cur['g'], cat=cur['cat'], place=place, deleg_raw=m.group(0), mark_raw=mark,
                        status=st.upper() if st else None, members=members)
            out.append(team)
            continue
        # tempo/colocação impressos na linha de um integrante (layout 2022)
        if team and team['mark_raw'] is None and team['status'] in (None, 'SM'):
            toks = ln.split()
            mk = next((x for x in toks if MARK.match(x)), None)
            if mk:
                team['mark_raw'] = mk; team['status'] = None
                pc = re.search(r'(\d+)\s*º', ln)
                if pc: team['place'] = int(pc.group(1))
                ln = ln.replace(mk, ' ')
                if pc: ln = ln.replace(pc.group(0), ' ')
        if mode == 'none': continue
        names = member_chunks(ln)
        if not names: continue
        for n in names:
            if mode == 'around':
                if team and len(team['members']) < 4 and len(pending) == 0 and team.get('_after', 0) < 2:
                    team['members'].append(n); team['_after'] = team.get('_after', 0) + 1
                else:
                    pending.append(n)
            elif team and len(team['members']) < 4:
                team['members'].append(n)
    for r in out: r.pop('_after', None)
    return out

SOURCES = [
    (2017, '2017__BOLETIM-GERAL-ATLETISMO1', 'Atletismo', 'none'),
    (2017, '2017__BOLETIM-GERAL-NATACAO', 'Natação', 'none'),
    (2018, '2018__Atletismo', 'Atletismo', 'around'),
    (2018, '2018__Natacao', 'Natação', 'around'),
    (2019, '2019__anastra-dia-1-evento-por-pagina', 'Atletismo', 'none'),
    (2019, '2019__Atletismo-segundo-dia', 'Atletismo', 'none'),
    (2019, '2019__Resultados-primeiro-dia', 'Natação', 'after'),
    (2019, '2019__Resultados-segundo-Dia', 'Natação', 'after'),
    (2022, '2022__BOLETIM-ANASTRA', 'Atletismo', 'inline'),
    (2022, '2022__resultados-etapa-1-natacao', 'Natação', 'around'),
    (2022, '2022__RESULTADO-NATACAO-2a-etapa', 'Natação', 'around'),
    (2023, '2023__Resultado-Completo-do-Atletismo', 'Atletismo', 'inline'),
    (2023, '2023__Resultado-Final-da-Natacao-1', 'Natação', 'after'),
    (2024, '2024__Resultados-do-Atletismo-1o-dia-Corrigido', 'Atletismo', 'around'),
    (2024, '2024__Resultados-do-Atletismo-2o-dia', 'Atletismo', 'around'),
    (2024, '2024__Resultados-do-Atletismo-3o-dia', 'Atletismo', 'around'),
    (2024, '2024__Resultados-Finais-da-Natacao-2024-2-dias', 'Natação', 'after'),
    (2025, '2025__Resultados-Revezamentos-final', 'Atletismo', 'inline'),
    (2025, '2025__Resultados-Completo', 'Natação', 'after'),
]

if __name__ == '__main__':
    txt = sys.argv[1]; allr = []
    from collections import Counter
    for y, f, mod, mode in SOURCES:
        p = os.path.join(txt, f + '.txt')
        if not os.path.exists(p): print('falta', f); continue
        rs = parse(open(p, encoding='utf-8', errors='replace').read(), y, f, mod, mode)
        allr += rs
        ev = Counter((r['event_label'], r['gender'], r['cat']) for r in rs)
        mem = Counter(len(r['members']) for r in rs)
        print(f'{y} {f[:44]:44} equipes={len(rs):3} provas={len(ev):2} integrantes={dict(sorted(mem.items()))} sem_marca={sum(1 for r in rs if not r["mark_raw"])}')
    json.dump(allr, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
