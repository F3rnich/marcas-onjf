# Marcas ONJT/ONJF

Painel com os resultados históricos de **atletismo e natação** da Olimpíada Nacional do Judiciário (ONJT/ONJF), de 2009 a 2026, incluindo revezamentos.

**Acesse:** https://f3rnich.github.io/marcas-onjf/

O que dá para fazer:
- comparar a sua marca com o recorde e com os tempos que deram ouro, prata e bronze na sua prova e faixa etária;
- ver o top 10 de todos os tempos de cada prova e faixa;
- consultar o histórico de qualquer atleta (participações, medalhas, evolução e onde melhorar);
- ver o quadro de medalhas histórico entre delegações;
- comparar tempos de revezamento por delegação.

Fonte dos dados: resultados e recordes publicados em [anastra.com.br](https://www.anastra.com.br) e nos sistemas de cronometragem de cada edição.

**Encontrou um erro?** [Reporte uma correção](https://github.com/F3rnich/marcas-onjf/issues/new?template=correcao.yml) (exige conta gratuita no GitHub).

---

## Atualizar após uma nova edição

Um comando faz tudo: baixa a edição, reconstrói a base, confere contra os recordes oficiais, gera o painel e publica.

```
python3 scripts/atualizar.py --ano 2027 --publicar
```

O que ele faz:
1. Reprocessa as fontes arquivadas em `raw/` (2009 em diante).
2. Lista os PDFs da edição no site da Anastra, baixa, segue os links internos dos boletins (inclusive para resultados hospedados fora do site) e escolhe sozinho o leitor compatível com cada arquivo, para provas individuais e revezamentos.
3. Procura a edição no sistema de cronometragem Gerentrack (atletismo desde 2026), descobrindo sozinho o endereço, a chave pública e os eventos.
4. Confere a base contra as listas oficiais de recordes. **Se menos de 95% dos recordes individuais ou 70% dos de revezamento conferirem, para e não publica**: sinal de que alguma fonte mudou de formato.
5. Gera `index.html` e, com `--publicar`, grava no Git e envia. O GitHub Pages republica em cerca de um minuto.

Variações:
- `--ano 2027` sem `--publicar`: gera tudo para revisar antes (abra `index.html`).
- `--pdf URL`: inclui um PDF de resultado que não esteja linkado no site da Anastra.
- Sem `--ano`: só reconstrói a partir do que já está no repositório (útil depois de corrigir um leitor).

### Requisitos
- Python 3.10+ com `pypdf` (`pip install pypdf`)
- `pdftotext` (pacote `poppler-utils`), só para edições novas

### Se a conferência barrar a publicação
O relatório lista os recordes que não conferiram. Em geral a organização mudou de software de cronometragem e nenhum leitor existente serve. É preciso escrever um leitor novo em `scripts/parse_pdfs.py` (provas individuais, cerca de 30 linhas) ou ajustar `scripts/parse_relays.py` (revezamentos), e rodar de novo.

---

## Organização do repositório

| Caminho | Conteúdo |
|---|---|
| `index.html` | O painel publicado (gerado; não editar à mão) |
| `panel/template.html` | Código do painel; os dados são injetados nele |
| `data/onjt.json` | Base final consolidada |
| `data/*_raw.json`, `data/*relays.json` | Dados intermediários por fonte |
| `raw/txt/` | Texto extraído dos PDFs de resultados (arquivo das fontes) |
| `raw/leg/` | Páginas do arquivo antigo do site (2009–2016) |
| `raw/rec/` | Listas oficiais de recordes |
| `raw/ext/` | Dados do sistema Gerentrack |
| `preview.png` | Imagem da prévia do link (WhatsApp, redes) |

As fontes ficam arquivadas porque o site original perde arquivos com o tempo (vários PDFs de 2017–2019 e as páginas de 2007–2008 já estão fora do ar). Com elas, a base pode ser reconstruída a qualquer momento.

| Script | Função |
|---|---|
| `atualizar.py` | Executa todo o processo (comando principal) |
| `norm.py` | Normaliza provas, faixas etárias, delegações, marcas e nomes |
| `parse_legacy.py` | 2009–2016 (páginas antigas do site), individuais e revezamentos |
| `parse_pdfs.py` | Provas individuais em PDF, um leitor por formato |
| `parse_relays.py` | Revezamentos em PDF |
| `parse_records.py` | Listas oficiais de recordes |
| `fetch_gt.py` / `parse_gt.py` | Sistema Gerentrack (atletismo desde 2026) |
| `build_data.py` | Junta, unifica nomes, deduplica e exporta `data/onjt.json` |
| `validate.py` | Confere a base contra os recordes oficiais |
| `build_panel.py` / `build_site.py` | Geram o painel e o `index.html` |

## Limitações conhecidas
- 2007 e 2008: o site não tem resultados individuais desses anos (as páginas existentes são cópias de 2011).
- 2012–2016: o site guarda só os medalhistas.
- Faixas etárias mudaram ao longo dos anos; as comparações usam sempre a faixa exatamente igual.
- Piscina de 25 m e 50 m: tempos não são comparáveis; o painel tem filtro de piscina. 2009–2011, 2013 e 2025 não informam o tamanho.
- Revezamentos mistos de 2026 vieram como "misto por categorias", sem a regra de soma de idades; ficam numa categoria própria.
- 2026, natação: os revezamentos e o 50 m livre PCD só foram publicados no site da Federação Aquática de Sergipe, fora do alcance do coletor; ainda não estão no painel.
- A base reproduz as súmulas oficiais, inclusive quando o atleta competiu em faixas etárias diferentes no mesmo ano. Erros evidentes de diagramação das fontes são corrigidos automaticamente em `build_data.py`: colocação repetida ou ausente (refeita pela marca), delegação divergente do mesmo atleta na mesma edição (vale a da maioria) e atleta impresso na lista do gênero oposto (linha descartada).
- Auditoria de outubro/2026: 98% dos recordes oficiais individuais conferem com a base, e 98% das medalhas de atletismo e natação por delegação (2017–2026) batem com o quadro de medalhas oficial da Anastra.
- Nomes de atletas são unificados por regras (partículas, abreviações, nomes cortados); casos raros podem ficar duplicados ou ser unidos por engano. Use o formulário de correção.
