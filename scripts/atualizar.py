"""Atualiza a base de resultados e o painel. Um comando faz tudo.

Uso:
  python3 scripts/atualizar.py --ano 2027 --publicar   # baixa a edição nova, reconstrói, valida e publica
  python3 scripts/atualizar.py --ano 2027              # mesmo processo, sem publicar (para revisar antes)
  python3 scripts/atualizar.py --ano 2027 --pdf URL    # inclui PDFs hospedados fora do site da Anastra
  python3 scripts/atualizar.py --publicar              # só reconstrói a partir do que está no repositório

Etapas:
 1. Reprocessa as fontes arquivadas em raw/ (2009–2025): provas individuais, revezamentos e recordes.
 2. Com --ano: lista os PDFs da edição no site da Anastra, baixa, segue os links internos dos boletins,
    converte para texto e escolhe sozinho o leitor compatível com cada arquivo (individuais e revezamentos).
    Também procura a edição no sistema de cronometragem Gerentrack (atletismo desde 2026).
 3. Junta tudo (build_data.py), confere contra os recordes oficiais e interrompe se a conferência cair
    abaixo do mínimo, para não publicar dados quebrados.
 4. Gera o painel (index.html).
 5. Com --publicar: grava no Git e envia ao GitHub; o GitHub Pages republica em cerca de um minuto.
"""
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.error, urllib.parse, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from norm import ROOT
import parse_pdfs as P
import parse_relays as PR

MIN_INDIVIDUAL, MIN_REVEZAMENTO = 0.95, 0.70   # mínimo de recordes oficiais que precisam conferir
UA = {'User-Agent': 'Mozilla/5.0'}
PARSERS = [P.p2017, P.p2018, P.p2019n, P.phytek, P.p2022a, P.p2022n, P.pswim2324, P.pcbat, P.p2024a, P.pfdap]
RAW_TXT = os.path.join(ROOT, 'raw/txt')

def step(msg): print(f'\n== {msg}', flush=True)

def run(*args):
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)

def get(u, binary=False, tries=4):
    import time
    for i in range(tries):
        try:
            req = urllib.request.Request(urllib.parse.quote(u, safe=':/%?=&'), headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
            return b if binary else b.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) or i == tries - 1: raise
        except Exception:
            if i == tries - 1: raise
        time.sleep(3 * (i + 1))   # falhas de rede momentâneas

# ---------------------------------------------------------------- descoberta e download
def wp_pdfs(year):
    urls = set()
    for site in (f'olimpiadas-{year}/', ''):
        for pg in range(1, 20):
            u = (f'https://www.anastra.com.br/{site}wp-json/wp/v2/media?per_page=100&page={pg}'
                 f'&mime_type=application/pdf&after={year}-01-01T00:00:00&before={year}-12-31T23:59:59&_fields=source_url')
            try:
                d = json.loads(get(u))
            except Exception:
                break
            urls |= {x['source_url'] for x in d}
            if len(d) < 100: break
    keep = re.compile(r'result|boletim|etapa|atlet|nata|revez', re.I)
    skip = re.compile(r'tabela|lista|manual|sequen|regulamento|balizamento|horario|recorde|participantes|informativo', re.I)
    return sorted(u for u in urls if keep.search(u.rsplit('/', 1)[-1]) and not skip.search(u.rsplit('/', 1)[-1]))

def pdf_links(path):
    import pypdf
    out = set()
    try:
        for p in pypdf.PdfReader(path).pages:
            for a in p.get('/Annots') or []:
                u = a.get_object().get('/A', {}).get('/URI')
                if u and str(u).lower().endswith('.pdf'): out.add(str(u))
    except Exception:
        pass
    return out

def download(u, year):
    name = f'{year}__' + re.sub(r'[^\w.-]', '_', urllib.parse.unquote(u.rsplit('/', 1)[-1]))
    os.makedirs(os.path.join(ROOT, 'raw/pdf'), exist_ok=True)
    p = os.path.join(ROOT, 'raw/pdf', name)
    if not os.path.exists(p):
        open(p, 'wb').write(get(u, binary=True))
    t = os.path.join(RAW_TXT, name[:-4] + '.txt')
    subprocess.run(['pdftotext', '-layout', p, t], check=False)
    return p, t

# ---------------------------------------------------------------- escolha automática do leitor
def _name_ok(nm):
    return not re.search(r'\d|\(', nm) and 2 <= len(nm.split()) <= 8

def best_individual(text, year, src):
    best = (0, None, [])
    for fn in PARSERS:
        for mod in ('Atletismo', 'Natação'):
            try:
                rs = [r for r in fn(text, year, src, mod) if r]
            except Exception:
                continue
            ok = lambda r: (r['mark_raw'] or r['status']) and r['deleg_raw'] and r['gender'] and r['age'] and _name_ok(r['name'])
            score = sum(1 for r in rs if ok(r)) - sum(1 for r in rs if not ok(r))
            if score > best[0]: best = (score, f'{fn.__name__}/{mod}', rs)
    return best

def best_relays(text, year, src):
    best = (0, None, [])
    for mod in ('Atletismo', 'Natação'):
        for mode in ('after', 'inline', 'around', 'none'):
            try:
                rs = PR.parse(text, year, src, mod, mode)
            except Exception:
                continue
            full = sum(1 for r in rs if (r['mark_raw'] or r['status']) and len(r['members']) in (0, 4))
            score = full - (len(rs) - full) + sum(1 for r in rs if len(r['members']) == 4) * 0.1
            if score > best[0]: best = (score, f'{mode}/{mod}', rs)
    return best

def nova_edicao(y, extra_pdfs):
    step(f'Edição {y}: PDFs no site da Anastra')
    urls = wp_pdfs(y) + extra_pdfs
    print(f'{len(urls)} PDF(s) candidatos')
    seen, queue, files = set(), list(urls), []
    while queue:
        u = queue.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            p, t = download(u, y); files.append(t)
            queue += [l for l in pdf_links(p) if l not in seen]
        except Exception as e:
            print('  falhou:', u, e)
    rows, rels = [], []
    for t in files:
        text = open(t, encoding='utf-8', errors='replace').read(); src = os.path.basename(t)[:-4]
        n, which, rs = best_individual(text, y, src)
        if n >= 10: rows += rs; print(f'  individuais  {src[:50]:50} {which:22} {len(rs)}')
        n, which, rr = best_relays(text, y, src)
        if n >= 3: rels += rr; print(f'  revezamentos {src[:50]:50} {which:22} {len(rr)}')
    json.dump(rows, open(os.path.join(ROOT, f'data/y{y}_raw.json'), 'w'), ensure_ascii=False)
    json.dump(rels, open(os.path.join(ROOT, f'data/y{y}_relays.json'), 'w'), ensure_ascii=False)
    print(f'PDFs: {len(rows)} resultados individuais e {len(rels)} equipes de revezamento')

    step(f'Edição {y}: sistema Gerentrack')
    try:
        run('scripts/fetch_gt.py', '--ano', str(y))
        import parse_gt
        print('Gerentrack (individuais, revezamentos):', parse_gt.run(y))
    except subprocess.CalledProcessError:
        print('  sem dados no Gerentrack para este ano (normal se a edição publicou só PDFs)')

# ---------------------------------------------------------------- publicação
def publicar(msg):
    step('Publicando no GitHub')
    git = lambda *a: subprocess.run(['git', *a], cwd=ROOT, check=True)
    git('add', '-A')
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=ROOT).returncode == 0:
        print('Nada mudou; nada a publicar.'); return
    git('commit', '-m', msg)
    git('push')
    print('Publicado. O site atualiza em cerca de um minuto: https://f3rnich.github.io/marcas-onjf/')

def main():
    ap = argparse.ArgumentParser(description='Atualiza a base e o painel Marcas ONJT/ONJF.')
    ap.add_argument('--ano', type=int, help='edição nova a baixar')
    ap.add_argument('--pdf', action='append', default=[], help='PDF de resultado fora do site da Anastra')
    ap.add_argument('--publicar', action='store_true', help='grava no Git e envia ao GitHub')
    ap.add_argument('--mensagem', default=None, help='mensagem do commit')
    a = ap.parse_args()

    step('Reprocessando fontes arquivadas')
    run('scripts/parse_pdfs.py', 'raw/txt', 'data/pdf_raw.json')
    run('scripts/parse_relays.py', 'raw/txt', 'data/relay_raw.json')
    if os.path.isdir(os.path.join(ROOT, 'raw/leg/php')):
        run('scripts/parse_legacy.py', 'data/legacy_raw.json')
        import parse_legacy
        json.dump(parse_legacy.all_legacy_relays(), open(os.path.join(ROOT, 'data/legacy_relays.json'), 'w'), ensure_ascii=False)
    run('scripts/parse_records.py', 'raw/rec', 'data/records.json', 'data/relay_records.json')

    if a.ano: nova_edicao(a.ano, a.pdf)

    step('Montando a base')
    run('scripts/build_data.py')

    step('Conferindo contra os recordes oficiais')
    import validate
    ind, rel = validate.check(show=10)
    if ind < MIN_INDIVIDUAL or rel < MIN_REVEZAMENTO:
        sys.exit(f'\nConferência abaixo do mínimo ({MIN_INDIVIDUAL:.0%} individuais, {MIN_REVEZAMENTO:.0%} revezamentos). '
                 'Nada foi publicado. Provável mudança de formato numa fonte: revise as divergências acima.')

    step('Gerando o painel')
    run('scripts/build_panel.py', 'panel/marcas-onjt.html')
    run('scripts/build_site.py', 'index.html')

    if a.publicar:
        publicar(a.mensagem or f'Atualiza resultados ({datetime.date.today().isoformat()})' + (f': edição {a.ano}' if a.ano else ''))
    else:
        print('\nPronto. Abra index.html para revisar; rode de novo com --publicar para enviar ao site.')

if __name__ == '__main__':
    main()
