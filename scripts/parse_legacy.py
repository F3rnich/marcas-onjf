"""Parser do arquivo antigo: 2009-2011 (classificação completa, páginas PHP)
e 2012-2016 (apenas medalhistas, páginas JSP por regional).
2007 e 2008: as páginas de modalidade no site são cópias de 2011 -> descartadas."""
import re, html, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from norm import *

def fixenc(b):
    s = b.decode('utf-8', 'surrogateescape')
    return ''.join(ch if not ('\udc80' <= ch <= '\udcff') else bytes([ord(ch) - 0xdc00]).decode('latin-1') for ch in s)

def legacy_event(head, modality):
    """'Natação - 50 m Livres de 36 a 40 anos masculino' -> (ev, gender, age)"""
    h = norm_space(head)
    h = re.sub(r'^(Nata\S*|Atletismo)\s*-\s*', '', h)
    g = detect_gender(h)
    age = detect_age(h)
    if age is None and re.search(r'at[eé]\s*(\d{2})', h, re.I):
        age = 'até ' + re.search(r'at[eé]\s*(\d{2})', h, re.I).group(1)
    return detect_event(h, modality), g, age

def parse_php(path):
    y, mid = os.path.basename(path)[:-5].split('_')
    y = int(y)
    modality = 'Atletismo' if mid == '4' else 'Natação'
    t = fixenc(open(path, 'rb').read())
    out = []
    parts = re.split(r'<td colspan="3"[^>]*class="internas_14"><strong>', t)
    for p in parts[1:]:
        head = html.unescape(p[:p.find('</strong>')]).replace('\xa0', ' ').strip()
        if 'vencedoras' in head: continue
        ev, g, age = legacy_event(head, modality)
        if not ev: continue
        body = p[p.find('</strong>'):]
        for tr in re.split(r'<tr>', body):
            m = re.search(r'class="link_resultados">([^<]+)</a>(?:<span class="link_resultados">([^<]*)</span>)?', tr)
            if not m: continue
            deleg = html.unescape(m.group(1)).replace('\xa0', ' ').strip()
            mark = html.unescape(m.group(2) or '').replace('\xa0', ' ').strip(' -') or None
            medal = re.search(r'medal_(ouro|prata|bronze)', tr)
            pl = re.search(r'>\s*(\d+)º\s*<', tr)
            place = {'ouro': 1, 'prata': 2, 'bronze': 3}[medal.group(1)] if medal else (int(pl.group(1)) if pl else None)
            names = [html.unescape(n).strip() for n in re.findall(r'&bull;\s*([^<]+)', tr)]
            if len(names) != 1: continue
            out.append(dict(year=y, source=f'legado_{y}_{mid}', modality=ev[0], event=ev[1], event_label=ev[2],
                            gender=g, age=age, place=place, name=title_name(names[0]), deleg_raw=deleg,
                            mark_raw=mark, status=None if mark else 'SM', record=bool(re.search(r'recorde\.gif', tr))))
    return out

def parse_jsp(path):
    y = int(os.path.basename(path).split('_')[0])
    t = fixenc(open(path, 'rb').read())
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
    nm = re.search(r'((?:TRT|TST)[^0-9]*?(?:\d{1,2}ª[^0-9]*?)?)\s+\d+ \d+ \d+ \d+ Tabela medalhas de Ouro', txt)
    nation = norm_space(nm.group(1)) if nm else ''
    out = []
    for medal, place in (('gold', 1), ('silver', 2), ('bronze', 3)):
        mt = re.search(rf'<table class="{medal}medalsdetails medaldetails">(.*?)</table>', t, re.S)
        if not mt: continue
        for tr in re.findall(r'<tr>(.*?)</tr>', mt.group(1), re.S):
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
            if len(tds) < 4: continue
            clean = lambda x: norm_space(html.unescape(re.sub(r'<[^>]+>', ' ', x)))
            mod, prova, ath, res = (clean(x) for x in tds[:4])
            if mod not in ('Atletismo', 'Natação'): continue
            ev, g, age = legacy_event(prova, mod)
            if not ev: continue
            names = [n.strip() for n in ath.split(';') if n.strip()]
            if len(names) != 1: continue
            mk = re.search(r't=\s*([\d:.,]+)|([\d.,]+)\s*m\b', res)
            mark = (mk.group(1) or mk.group(2)) if mk else None
            out.append(dict(year=y, source=f'legado_{y}_medalhistas', modality=ev[0], event=ev[1], event_label=ev[2],
                            gender=g, age=age, place=place, name=title_name(names[0]), deleg_raw=nation,
                            mark_raw=mark, status=None, record='RECORD' in res.upper()))
    return out

if __name__ == '__main__':
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'raw/leg/php/20*_*.html'))):
        if os.path.basename(f)[:4] in ('2007', '2008'): continue
        r = parse_php(f); out += r; print(os.path.basename(f), len(r))
    for f in sorted(glob.glob(os.path.join(ROOT, 'raw/leg/jsp/20*_[0-9]*.html'))):
        r = parse_jsp(f); out += r
    from collections import Counter
    print(Counter(r['year'] for r in out))
    print('sem faixa', Counter(r['year'] for r in out if not r['age']))
    print('sem deleg', Counter(r['year'] for r in out if not canon_deleg(r['deleg_raw'])))
    json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=0)

# ---------------- revezamentos do arquivo antigo ----------------
def relays_php(path):
    from parse_relays import relay_header
    y, mid = os.path.basename(path)[:-5].split('_'); y = int(y)
    modality = 'Atletismo' if mid == '4' else 'Natação'
    t = fixenc(open(path, 'rb').read()); out = []
    for p in re.split(r'<td colspan="3"[^>]*class="internas_14"><strong>', t)[1:]:
        head = html.unescape(p[:p.find('</strong>')]).replace('\xa0', ' ').strip()
        h = relay_header(re.sub(r'^(Nata\S*|Atletismo)\s*-\s*', '', head), modality, None)
        if not h: continue
        for tr in re.split(r'<tr>', p[p.find('</strong>'):]):
            m = re.search(r'class="link_resultados">([^<]+)</a>(?:<span class="link_resultados">([^<]*)</span>)?', tr)
            if not m: continue
            medal = re.search(r'medal_(ouro|prata|bronze)', tr); pl = re.search(r'>\s*(\d+)º\s*<', tr)
            place = {'ouro': 1, 'prata': 2, 'bronze': 3}[medal.group(1)] if medal else (int(pl.group(1)) if pl else None)
            mark = html.unescape(m.group(2) or '').replace('\xa0', ' ').strip(' -') or None
            names = [title_name(html.unescape(n).strip()) for n in re.findall(r'&bull;\s*([^<]+)', tr)]
            out.append(dict(year=y, source=f'legado_{y}_{mid}', modality=h['mod'], event=h['key'], event_label=h['label'],
                            gender=h['g'], cat=h['cat'], place=place if mark else None,
                            deleg_raw=html.unescape(m.group(1)).replace('\xa0', ' ').strip(), mark_raw=mark,
                            status=None if mark else 'SM', members=names[:4]))
    return out

def relays_jsp(path):
    from parse_relays import relay_header
    y = int(os.path.basename(path).split('_')[0])
    t = fixenc(open(path, 'rb').read())
    txt = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', t)))
    nm = re.search(r'((?:TRT|TST)[^0-9]*?(?:\d{1,2}ª[^0-9]*?)?)\s+\d+ \d+ \d+ \d+ Tabela medalhas de Ouro', txt)
    nation = norm_space(nm.group(1)) if nm else ''
    out = []
    for medal, place in (('gold', 1), ('silver', 2), ('bronze', 3)):
        mt = re.search(rf'<table class="{medal}medalsdetails medaldetails">(.*?)</table>', t, re.S)
        if not mt: continue
        for tr in re.findall(r'<tr>(.*?)</tr>', mt.group(1), re.S):
            tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)
            if len(tds) < 4: continue
            clean = lambda x: norm_space(html.unescape(re.sub(r'<[^>]+>', ' ', x)))
            mod, prova, ath, res = (clean(x) for x in tds[:4])
            if mod not in ('Atletismo', 'Natação'): continue
            h = relay_header(prova, mod, None)
            if not h: continue
            mk = re.search(r't=\s*([\d:.,]+)', res)
            out.append(dict(year=y, source=f'legado_{y}_medalhistas', modality=h['mod'], event=h['key'], event_label=h['label'],
                            gender=h['g'], cat=h['cat'], place=place, deleg_raw=nation, mark_raw=mk.group(1) if mk else None,
                            status=None, members=[title_name(n) for n in ath.split(';') if n.strip()][:4]))
    return out

def all_legacy_relays():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'raw/leg/php/20*_*.html'))):
        if os.path.basename(f)[:4] in ('2007', '2008'): continue
        out += relays_php(f)
    for f in sorted(glob.glob(os.path.join(ROOT, 'raw/leg/jsp/20*_[0-9]*.html'))):
        out += relays_jsp(f)
    return out
