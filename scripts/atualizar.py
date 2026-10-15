"""Atualiza a base com uma edição nova e regenera o painel.

Uso:
  python3 atualizar.py --ano 2026            # descobre, baixa, detecta o layout, reconstrói
  python3 atualizar.py --ano 2026 --pdf URL  # acrescenta PDFs de resultado hospedados fora do site
  python3 atualizar.py                       # só reconstrói a partir do que já foi baixado

Passos:
 1. Lista os PDFs da edição pela API do WordPress (olimpiadas-ANO e site principal).
 2. Baixa boletins e PDFs de resultado; segue os links internos dos boletins.
 3. Converte para texto (pdftotext -layout).
 4. Testa todos os parsers conhecidos em cada arquivo e fica com o que extrai mais
    resultados válidos (marca + delegação + prova). Arquivos sem atletismo/natação são ignorados.
 5. Grava data/y{ANO}_raw.json, roda build_data.py e build_panel.py.
"""
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
import parse_pdfs as P

ROOT = '/home/claude'
UA = {'User-Agent': 'Mozilla/5.0'}
PARSERS = [P.p2017, P.p2018, P.p2019n, P.phytek, P.p2022a, P.p2022n, P.pswim2324, P.pcbat, P.p2024a, P.pfdap]

def get(u, binary=False):
    req = urllib.request.Request(urllib.parse.quote(u, safe=':/%?=&'), headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        b = r.read()
    return b if binary else b.decode('utf-8', 'replace')

def wp_pdfs(year):
    urls = set()
    for site in (f'olimpiadas-{year}/', ''):
        for pg in range(1, 20):
            u = f'https://www.anastra.com.br/{site}wp-json/wp/v2/media?per_page=100&page={pg}&mime_type=application/pdf&after={year}-01-01T00:00:00&before={year}-12-31T23:59:59&_fields=source_url'
            try:
                d = json.loads(get(u))
            except Exception:
                break
            urls |= {x['source_url'] for x in d}
            if len(d) < 100: break
    keep = re.compile(r'result|boletim|etapa|atlet|nata', re.I)
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
    p = os.path.join(ROOT, 'raw/pdf', name)
    if not os.path.exists(p):
        open(p, 'wb').write(get(u, binary=True))
    t = os.path.join(ROOT, 'raw/txt', name[:-4] + '.txt')
    subprocess.run(['pdftotext', '-layout', p, t], check=False)
    return p, t

def best_parse(txtpath, year):
    text = open(txtpath, encoding='utf-8', errors='replace').read()
    src = os.path.basename(txtpath)[:-4]
    best = (0, None, [])
    for fn in PARSERS:
        for mod in ('Atletismo', 'Natação'):
            try:
                rs = [r for r in fn(text, year, src, mod) if r]
            except Exception:
                continue
            def ok(r):
                nm = r['name']
                return ((r['mark_raw'] or r['status']) and r['deleg_raw'] and r['gender'] and r['age']
                        and not re.search(r'\d|\(', nm) and 2 <= len(nm.split()) <= 8)
            good = sum(1 for r in rs if ok(r)) - sum(1 for r in rs if not ok(r))
            if good > best[0]: best = (good, f'{fn.__name__}/{mod}', rs)
    return best

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ano', type=int)
    ap.add_argument('--pdf', action='append', default=[])
    a = ap.parse_args()
    if a.ano:
        y = a.ano
        urls = wp_pdfs(y) + a.pdf
        print(f'{len(urls)} PDFs candidatos para {y}')
        seen, queue, files = set(), list(urls), []
        while queue:
            u = queue.pop(0)
            if u in seen: continue
            seen.add(u)
            try:
                p, t = download(u, y); files.append(t)
                queue += [l for l in pdf_links(p) if l not in seen]
            except Exception as e:
                print('  falhou', u, e)
        rows, report = [], []
        for t in files:
            n, which, rs = best_parse(t, y)
            if n >= 10:
                rows += rs; report.append((os.path.basename(t), which, n))
        for r in report: print('  usado:', *r)
        # evita duplicar a mesma prova vinda de boletim parcial e de arquivo final
        json.dump(rows, open(os.path.join(ROOT, f'data/y{y}_raw.json'), 'w'), ensure_ascii=False)
        print(f'{len(rows)} linhas extraídas de {len(report)} arquivo(s)')
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/build_data.py')], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/validate.py'), '0'], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, 'scripts/build_panel.py'), os.path.join(ROOT, 'panel/marcas-onjt.html')], check=True)

if __name__ == '__main__':
    main()
