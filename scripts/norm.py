"""Normalização comum: provas, faixas, delegações, marcas."""
import os, re, unicodedata

# raiz do repositório (pasta acima de scripts/); os caminhos de dados partem daqui
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def strip_acc(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

def norm_space(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()

# ---------------- gênero ----------------
def detect_gender(s):
    t = strip_acc(s).upper()
    if re.search(r'\bMISTO\b', t): return 'X'
    if re.search(r'\bFEM(ININO|ININA)?\b', t): return 'F'
    if re.search(r'\bMASC(ULINO|ULINA)?\b', t): return 'M'
    return None

# ---------------- provas ----------------
# devolve (modalidade, chave_da_prova, rótulo) ou None
SWIM_STYLES = [
    (r'MEDLEY|4 ?ESTILOS|MEDLEI', 'Medley'),
    (r'BORBOLETA', 'Borboleta'),
    (r'COSTAS?', 'Costas'),
    (r'PEITO', 'Peito'),
    (r'LIVRES?|CRAWL', 'Livre'),
]
def detect_event(s, modality_hint=None):
    t = strip_acc(norm_space(s)).upper()
    t = t.replace('METROS', 'M').replace('METRO', 'M')
    if re.search(r'REVEZ|\b\d\s*X\s*\d|\b4X|\bX ?50|\bX ?100|\bX ?400', t):
        return None  # revezamentos ficam fora do escopo individual
    # campo
    field = [
        (r'SALTO\s+(EM\s+)?ALTURA', 'salto_altura', 'Salto em altura'),
        (r'SALTO\s+(EM\s+)?DIST', 'salto_distancia', 'Salto em distância'),
        (r'SALTO\s+(EM\s+)?TRIPLO', 'salto_triplo', 'Salto triplo'),
        (r'(ARREMESSO|LANCAMENTO)\s+(DO|DE)\s+PESO|\bPESO\b', 'peso', 'Arremesso do peso'),
        (r'(ARREMESSO|LANCAMENTO)\s+(DO|DE)\s+DARDO|\bDARDO\b', 'dardo', 'Lançamento do dardo'),
        (r'(ARREMESSO|LANCAMENTO)\s+(DO|DE)\s+DISCO|\bDISCO\b', 'disco', 'Lançamento do disco'),
    ]
    for rx, k, lab in field:
        if re.search(rx, t):
            return ('Atletismo', k, lab)
    m = re.search(r'(\d{1,2}[.,]?\d{3}|\d{2,4})\s*M\b', t)
    if not m:
        return None
    dist = int(re.sub(r'[.,]', '', m.group(1)))
    style = None
    for rx, lab in SWIM_STYLES:
        if re.search(rx, t):
            style = lab; break
    is_swim = style is not None or modality_hint == 'Natação'
    if 'RASOS' in t or 'BARREIRA' in t or modality_hint == 'Atletismo' and style is None:
        is_swim = False
    if is_swim:
        if style is None: style = 'Livre'
        if dist not in (25, 50, 100, 200, 400, 800, 1500): return None
        return ('Natação', f'{dist}_{style.lower()}', f'{dist}m {style.lower()}')
    if dist not in (60, 100, 200, 400, 800, 1500, 3000, 5000, 10000): return None
    lab = f'{dist:,}m'.replace(',', '.') + ' rasos'
    return ('Atletismo', f'{dist}_rasos', lab)

# ---------------- faixas etárias ----------------
def detect_age(s):
    """Devolve rótulo canônico 'até 34', '35-39', '60+', 'livre' etc. ou None."""
    t = strip_acc(norm_space(s)).upper()
    t = t.replace('ANOS', ' ').replace('ANO', ' ')
    m = re.search(r'(?:ATE|&U\b)\s*(\d{2})|(\d{2})\s*&U\b|(\d{2})\s*(?:E\s*)?ABAIXO', t)
    if m:
        return f'até {m.group(1) or m.group(2) or m.group(3)}'
    m = (re.search(r'\b(\d{2})\s*(?:\+|E\s+ACIMA|ACIMA|OU\s+MAIS|&\s*O(?:VER)?\b)', t)
         or re.search(r'ACIMA\s+DE\s+(\d{2})', t) or re.search(r'(?<![\dX])\+\s*(\d{2})\b', t))
    if m:
        return f'{m.group(1)}+'
    m = re.search(r'\b(\d{2})\s*(?:A|-|/|AO?)\s*(\d{2})\b', t)
    if m and 2 <= int(m.group(2)) - int(m.group(1)) <= 15:
        return f'{m.group(1)}-{m.group(2)}'
    m = re.search(r'(?:MASTER|\bM/W|\bM|\bW)\s*(\d{2})\b', t) or re.search(r'[–-]\s*(\d{2})\s*[–-]', t)
    if m:
        a = int(m.group(1))
        if a < 35: return 'até 34'
        return f'{a}-{a+4}'
    m = re.fullmatch(r'\s*(?:[–-]\s*)?(3[45])\s*', t)
    if m:
        return f'até {m.group(1)}'
    if re.search(r'ABSOLUTO|LIVRE\b|FAIXA ETARIA UNICA|UNICA', t):
        return None
    return None

# ---------------- delegações ----------------
UF_TRT = {'RJ': 1, 'SP': 2, 'MG': 3, 'RS': 4, 'BA': 5, 'PE': 6, 'CE': 7, 'PA/AP': 8, 'PA': 8, 'AP': 8,
          'PR': 9, 'DF/TO': 10, 'TO': 10, 'AM/RR': 11, 'AM': 11, 'RR': 11, 'SC': 12, 'PB': 13,
          'RO/AC': 14, 'RO': 14, 'AC': 14, 'MA': 16, 'ES': 17, 'GO': 18, 'AL': 19, 'SE': 20, 'RN': 21,
          'PI': 22, 'MT': 23, 'MS': 24}
TRT_UF = {1: 'RJ', 2: 'SP', 3: 'MG', 4: 'RS', 5: 'BA', 6: 'PE', 7: 'CE', 8: 'PA/AP', 9: 'PR', 10: 'DF/TO',
          11: 'AM/RR', 12: 'SC', 13: 'PB', 14: 'RO/AC', 15: 'Campinas', 16: 'MA', 17: 'ES', 18: 'GO',
          19: 'AL', 20: 'SE', 21: 'RN', 22: 'PI', 23: 'MT', 24: 'MS'}
def trt_code(n):
    return f'TRT{n}-{TRT_UF[n]}'

# associações da era 2007-2011 -> regional (só quando inequívoco pela UF)
LEGACY_ASSOC = {
    'ASTTTER': 3, 'ASJUSTEGO': 18, 'AJUSTES': 17, 'ASJT-RIO': 1, 'ASTRA XXI': 21, 'ASTRA 4': 4,
    'ASTRA 8': 8, 'ASSEJUTRA': 9, 'ASTRA13': 13, 'ASTRA XVI': 16, 'ASTRA XIX': 19, 'ASTRA XX': 20,
    'SITRA-AM/RR': 11, 'SINSJUSTRA': 14, 'GRUDE': 6, 'TRT12-SC': 12, 'TRT22-PI': 22, 'TRT5-BA': 5,
    'TRT6': 6, 'TRT 7': 7, 'ASTRA6': 6, 'ASTRISUTRA': None, 'ASDR': None,
}
DELEG_RX = re.compile(
    r'(?<![A-Za-z])(?:'
    r'T[Ss][Tt]\s*[-–]?\s*(?:D[Ff]|Trib[^ ]*)?'
    r'|T[Rr][Tt]\s*0?\d{1,2}\s*(?:ª\s*Regi[aã]o)?\s*[-–/]?\s*(?:Campinas|[A-Za-z]{2}(?:\s*/\s*[A-Za-z]{2})?)?'
    r'|TRT\s+[A-Z]{2}(?:/[A-Z]{2})?'
    r')(?![A-Za-z])')

def canon_deleg(raw):
    """Devolve código canônico 'TRT17-ES', 'TST-DF' ou None."""
    if not raw: return None
    t = strip_acc(norm_space(raw)).upper()
    if t.startswith('TST'): return 'TST-DF'
    m = re.match(r'TRT\s*0?(\d{1,2})', t)
    if m:
        n = int(m.group(1))
        if n in TRT_UF: return trt_code(n)
    m = re.match(r'TRT\s+([A-Z]{2}(?:/[A-Z]{2})?)$', t)
    if m:
        uf = m.group(1)
        if uf == 'DF': return 'TRT10-DF/TO'
        if '/' in uf and uf not in UF_TRT: uf = '/'.join(reversed(uf.split('/')))
        if uf in UF_TRT: return trt_code(UF_TRT[uf])
    base = re.sub(r'\s*-\s*[A-Z]{2}(/[A-Z]{2})?$', '', t).strip()
    for k, v in LEGACY_ASSOC.items():
        if base == strip_acc(k).upper():
            return trt_code(v) if v else None
    return None

# ---------------- marcas ----------------
STATUS_RX = re.compile(r'\b(DNS|DNF|DQ|DSQ|NC|N/C|NT|NM|W\.?O\.?|DESC|DESCL\w*|AUS|NCOMP|N\.C\.)\b', re.I)
def _time_candidates(s):
    parts = [p for p in re.split(r"[:.']", s) if p != '']
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return []
    if not nums: return []
    c = []
    if len(nums) == 1:
        return [float(nums[0])]
    # 1) último componente = fração (centésimos/décimos)
    frac = nums[-1] / (10 ** len(parts[-1])); rest = nums[:-1]
    while len(rest) > 1 and rest[0] == 0: rest = rest[1:]
    v = 0.0
    for x in rest: v = v * 60 + x
    if all(x < 60 for x in rest[1:]): c.append(v + frac)
    # 2) sem fração: componentes inteiros h:m:s
    rest = nums[:]
    while len(rest) > 1 and rest[0] == 0: rest = rest[1:]
    v = 0.0
    for x in rest: v = v * 60 + x
    if all(x < 60 for x in rest[1:]): c.append(v)
    return c

def parse_mark(raw, kind, plausible=None):
    """kind: 'time' ou 'dist'. plausible=(lo,hi) escolhe a leitura coerente
    quando o formato é ambíguo (ex.: 00:02:48 = 2min48 num 800 m)."""
    if raw is None: return None
    s = raw.strip().upper().lstrip('J').replace('"', "'").replace(',', '.')
    s = re.sub(r"[^0-9:.']", '', s)
    if not s: return None
    if kind == 'dist':
        try:
            v = float(s.replace("'", '.').replace(':', '.'))
            if plausible: return v if plausible[0] <= v <= plausible[1] else None
            return v if 0.5 < v < 100 else None
        except ValueError:
            return None
    c = _time_candidates(s)
    if not c: return None
    if plausible:
        lo, hi = plausible
        ok = [x for x in c if lo <= x <= hi]
        return ok[0] if ok else None
    return c[0]

def plausible_range(modality, event_key):
    if event_key.endswith('_pcd'): return (1, 3600)
    m = re.match(r'(\d+)', event_key)
    if not m: return None
    dist = int(m.group(1))
    lo = dist / 2.4 if modality == 'Natação' else dist / 10.5
    return (lo, lo * 10)

def canon_age(lab, year=None):
    if not lab: return lab
    if lab == '30-34': return 'até 34'
    m = re.match(r'(\d{2})-(\d{2})$', lab)
    if m and int(m.group(1)) >= 70: return '70+'
    return lab

def fmt_time(v):
    if v is None: return ''
    m, s = divmod(v, 60)
    if m >= 60:
        h, m = divmod(m, 60); return f'{int(h)}:{int(m):02d}:{s:05.2f}'
    return f'{int(m)}:{s:05.2f}' if m else f'{s:.2f}'

def title_name(n):
    n = norm_space(n).strip(' ,.-•')
    n = re.sub(r'^\(est\)\s*', '', n, flags=re.I)
    n = re.sub(r'^\d+\s+', '', n)          # número de raia/colocação colado ao nome

    small = {'da', 'de', 'do', 'das', 'dos', 'e', 'di'}
    out = []
    for i, w in enumerate(n.lower().split()):
        out.append(w if (w in small and i) else w[:1].upper() + w[1:])
    return ' '.join(out)

def name_key(n):
    t = strip_acc(n).lower()
    t = re.sub(r'[^a-z ]', ' ', t)
    return ' '.join(t.split())
