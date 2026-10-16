"""Converte os dados do sistema Gerentrack (atletismo ONJF 2026) para o formato cru do pipeline.
Tempos de pista vêm em milissegundos ('17200' = 17,20 s); provas de campo em metros."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from norm import ROOT, detect_event, detect_age, title_name

EXT = os.path.join(ROOT, 'raw/ext')

def eventos(year):
    """IDs de evento do ano (gravados por fetch_gt.py) -> é PCD."""
    p = os.path.join(EXT, f'eventos_{year}.json')
    if os.path.exists(p):
        return {e['id']: e['pcd'] for e in json.load(open(p))}
    return {'1789646392246': False, '1790212007822': True} if year == 2026 else {}

def convert(year=2026):
    out = []
    for ev, is_pcd in eventos(year).items():
        res = json.load(open(f'{EXT}/resultados_{ev}.json'))
        ins = {(i['dados'].get('atletaId'), i['dados'].get('provaId')): i['dados'] for i in json.load(open(f'{EXT}/inscricoes_{ev}.json')) if i['dados'].get('atletaId')}
        for r in res:
            if r.get('competidor_tipo') not in (None, 'atleta'): continue
            d = ins.get((r['competidor_id'], r['prova_id']))
            if not d or not (d.get('atletaNome') or d.get('nome')): continue
            e = detect_event(d['provaNome'], 'Atletismo')
            if not e: continue  # revezamentos
            if is_pcd: e = (e[0], e[1] + '_pcd', e[2] + ' (PCD)')
            field = e[1].split('_')[0] in ('salto', 'peso', 'dardo', 'disco')
            st = r.get('status')
            m = (r.get('marca') or '').strip()
            mark = None
            if not st and m:
                if not field and re.fullmatch(r'\d{4,}', m):
                    mark = f'{int(m) / 1000:.2f}'
                else:
                    mark = m.replace(',', '.')
            out.append(dict(year=year, source=f'gerentrack_{year}', modality='Atletismo', event=e[1], event_label=e[2],
                            gender=d['sexo'], age='única' if is_pcd else detect_age(d.get('categoriaOficial') or d['categoria']),
                            place=None, name=title_name(d.get('atletaNome') or d.get('nome')), deleg_raw=d.get('equipeCadastro') or '',
                            mark_raw=mark, status=st, record=False))
    return out

def convert_relays(year=2026):
    """Revezamentos 2026: competidor é a equipe; integrantes vêm por atletasIds."""
    from parse_relays import relay_header
    out = []
    for ev, is_pcd in eventos(year).items():
        ins = json.load(open(f'{EXT}/inscricoes_{ev}.json'))
        names = {i['dados'].get('atletaId'): i['dados'].get('atletaNome') for i in ins if i['dados'].get('atletaId')}
        rel = {(i['dados'].get('equipeId'), i['dados'].get('provaId')): i['dados'] for i in ins if i['dados'].get('tipo') == 'revezamento'}
        for r in json.load(open(f'{EXT}/resultados_{ev}.json')):
            if r.get('competidor_tipo') != 'equipe': continue
            d = rel.get((r['competidor_id'], r['prova_id'])) or {}
            nome = d.get('provaNome') or r['prova_id']
            h = relay_header(nome, 'Atletismo', None)
            if not h: continue
            g = 'X' if 'mix' in r['prova_id'] or 'Misto' in nome else r['sexo']
            cat = (d.get('categoriaOficial') or d.get('categoria') or 'livre')
            cat = 'livre' if cat.lower().startswith('misto (categ') and g != 'X' else cat.lower()
            st = r.get('status') or None
            m = (r.get('marca') or '').strip()
            mark = f'{int(m) / 1000:.2f}' if (not st and re.fullmatch(r'\d{4,}', m)) else (m or None)
            ids = (r.get('dados') or {}).get('atletasIds') or d.get('atletasIds') or []
            out.append(dict(year=year, source=f'gerentrack_{year}', modality='Atletismo', event=h['key'], event_label=h['label'],
                            gender=g, cat=cat, place=None, deleg_raw=(r.get('dados') or {}).get('nomeEquipe') or '',
                            mark_raw=mark, status=st, members=[title_name(names[i]) for i in ids if names.get(i)]))
    return out

def run(year):
    """Converte o ano e grava data/y<ano>gt_raw.json (individuais) e data/y<ano>gt_relays.json."""
    rows, rel = convert(year), convert_relays(year)
    json.dump(rows, open(os.path.join(ROOT, f'data/y{year}gt_raw.json'), 'w'), ensure_ascii=False)
    json.dump(rel, open(os.path.join(ROOT, f'data/y{year}gt_relays.json'), 'w'), ensure_ascii=False)
    return len(rows), len(rel)

if __name__ == '__main__':
    print(run(int(sys.argv[1]) if len(sys.argv) > 1 else 2026))
