# Marcas ONJT/ONJF

Painel com os resultados históricos de **atletismo e natação** da Olimpíada Nacional do Judiciário (ONJT/ONJF), de 2009 a 2026, incluindo revezamentos.

**Acesse:** https://f3rnich.github.io/marcas-onjf/

O que dá para fazer:
- comparar a sua marca com o recorde e com os tempos que deram ouro, prata e bronze na sua prova e faixa etária;
- ver o top 10 de todos os tempos de cada prova e faixa;
- consultar o histórico de qualquer atleta (participações, medalhas, evolução e onde melhorar);
- ver o quadro de medalhas histórico entre delegações;
- comparar tempos de revezamento por delegação.

Fonte dos dados: resultados e recordes publicados em [anastra.com.br](https://www.anastra.com.br) e nos sistemas de cronometragem de cada edição. Erros de grafia e de súmula das fontes originais podem aparecer; correções são bem-vindas.

## Publicar uma atualização
Depois de rodar o pipeline (seção abaixo), gere a página e envie:
```
python3 scripts/build_site.py index.html
git add -A && git commit -m "Atualiza resultados" && git push
```
O GitHub Pages republica em cerca de um minuto.

## Pipeline de dados


## Requisitos
- Python 3.10+ com `pypdf` (`pip install pypdf`)
- `pdftotext` (pacote poppler-utils)
- Os scripts assumem a raiz em `/home/claude`. Para rodar em outra máquina, troque `ROOT`/`D` no topo de cada script.

## Atualizar após uma nova edição
```
python3 scripts/atualizar.py --ano 2027
```
O script lista os PDFs da edição pela API do site, baixa boletins e resultados, segue os links internos dos boletins, escolhe sozinho o parser compatível e regenera o painel. No fim ele imprime a validação contra a lista oficial de recordes.

Se os resultados estiverem em site externo (como em 2026), passe os PDFs:
```
python3 scripts/atualizar.py --ano 2026 --pdf https://.../Resultado_Natacao.pdf --pdf https://.../Atletismo.pdf
```

Se a organização mudar de software de cronometragem, nenhum parser vai servir; o relatório mostra 0 linhas para aquele arquivo e é preciso escrever um parser novo em `parse_pdfs.py` (cada um tem cerca de 30 linhas).

## Atletismo 2026 (sistema Gerentrack)
Os resultados de atletismo de 2026 não estão em PDF: vêm da API pública do sistema de cronometragem.
```
python3 scripts/fetch_gt.py   # baixa resultados e inscrições (usa a chave pública que o site expõe, salva em raw/ext/hdr.json)
python3 scripts/parse_gt.py   # converte para data/y2026atl_raw.json
python3 scripts/atualizar.py  # reconstrói base e painel
```
Se a Anastra usar o mesmo sistema em 2027, basta trocar os IDs de evento no topo de `fetch_gt.py` e `parse_gt.py`.

## Revezamentos
```
python3 scripts/parse_relays.py raw/txt data/relay_raw.json        # 2017–2025 (PDFs)
python3 -c "import sys,json; sys.path.insert(0,'scripts'); import parse_legacy as L; json.dump(L.all_legacy_relays(), open('data/legacy_relays.json','w'), ensure_ascii=False)"
python3 scripts/parse_gt.py relays                                 # 2026 (Gerentrack)
python3 scripts/parse_records.py raw/rec data/records.json data/relay_records.json
python3 scripts/atualizar.py                                       # reconstrói tudo
```
O motor de revezamento associa integrantes à equipe em quatro modos (after, inline, around, none), definidos por fonte em `parse_relays.py`. Categorias: livre ou soma de idades (ex.: 180 anos).

## Arquivos
| Script | Função |
|---|---|
| `norm.py` | Normaliza provas, faixas etárias, delegações e marcas |
| `parse_legacy.py` | 2009–2016 (páginas antigas do site) |
| `parse_pdfs.py` | 2017–2025, um parser por layout de PDF |
| `parse_records.py` | Lista oficial de recordes por faixa |
| `build_data.py` | Junta, deduplica, valida e exporta `data/onjt.json` |
| `validate.py` | Confere cada recorde oficial contra a base |
| `build_panel.py` | Injeta os dados no template do painel |
| `atualizar.py` | Executa tudo para uma edição nova |
| `fetch_gt.py` / `parse_gt.py` | Atletismo vindo do sistema Gerentrack (2026) |
| `parse_relays.py` | Revezamentos 2017–2025 |

## Limitações conhecidas
- 2007 e 2008: as páginas de modalidade no site são cópias de 2011, então ficam fora.
- 2012–2016: o site só guarda os medalhistas.
- Revezamentos de natação de 2026 não constam dos PDFs publicados.
- Revezamentos mistos de 2026 vieram como "misto por categorias", sem a regra de soma de idades; ficam numa categoria própria.
- Piscina de 2009–2011, 2013 e 2025 não informada nas fontes.
