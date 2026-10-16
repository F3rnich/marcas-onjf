"""Baixa resultados de atletismo do sistema Gerentrack (usado pela ONJF a partir de 2026).

Uso: python3 scripts/fetch_gt.py --ano 2027

Descobre sozinho, a cada execução:
- o endereço da base e a chave pública de leitura, lidos do próprio site (a chave é pública e
  muda quando o site é republicado, por isso não fica gravada no repositório);
- os eventos da Olimpíada do Judiciário no ano pedido (incluindo o evento PCD, quando houver).
Grava em raw/ext/: resultados_<id>.json, inscricoes_<id>.json e eventos_<ano>.json.
"""
import argparse, json, os, re, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from norm import ROOT, strip_acc

SITE = 'https://www.gerentrackopen.com.br'
UA = {'User-Agent': 'Mozilla/5.0'}
OUT = os.path.join(ROOT, 'raw/ext')

def http(url, headers=None, tries=4):
    import time
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception:
            if i == tries - 1: raise
            time.sleep(3 * (i + 1))   # falhas de rede momentâneas

def credentials():
    home = http(SITE + '/')
    for js in re.findall(r'src="(/assets/[^"]+\.js)"', home):
        b = http(SITE + js)
        key = re.search(r'sb_publishable_[\w-]+', b) or re.search(r'eyJ[\w-]{10,}\.[\w-]{20,}\.[\w-]{20,}', b)
        url = re.search(r'https://[a-z0-9]+\.supabase\.co', b)
        if key and url:
            return url.group(0) + '/rest/v1/', key.group(0)
    raise SystemExit('Não encontrei a chave pública no site do Gerentrack; o site pode ter mudado de estrutura.')

def get_all(api, key, path):
    out, off = [], 0
    while True:
        d = json.loads(http(f'{api}{path}&offset={off}&limit=1000', {'apikey': key, 'Authorization': 'Bearer ' + key}))
        out += d
        if len(d) < 1000: return out
        off += 1000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ano', type=int, required=True)
    ap.add_argument('--evento', action='append', default=[], help='ID de evento, se a descoberta automática falhar')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    api, key = credentials()
    eventos = get_all(api, key, 'eventos?select=id,dados&order=id.asc')
    alvo = []
    for e in eventos:
        d = e['dados']; nome = strip_acc(d.get('nome') or '').upper()
        if e['id'] in a.evento or ('JUDICI' in nome and str(d.get('data', ''))[:4] == str(a.ano)):
            alvo.append({'id': e['id'], 'nome': d.get('nome'), 'pcd': 'PCD' in nome})
    if not alvo:
        raise SystemExit(f'Nenhum evento da Olimpíada do Judiciário em {a.ano} no Gerentrack. Use --evento ID.')
    for ev in alvo:
        for t, sel in (('resultados', 'select=*'), ('inscricoes', 'select=id,dados')):
            d = get_all(api, key, f'{t}?{sel}&order=id.asc&evento_id=eq.{ev["id"]}')
            json.dump(d, open(os.path.join(OUT, f'{t}_{ev["id"]}.json'), 'w'), ensure_ascii=False)
            print(f'{ev["nome"]}: {len(d)} {t}')
    json.dump(alvo, open(os.path.join(OUT, f'eventos_{a.ano}.json'), 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
