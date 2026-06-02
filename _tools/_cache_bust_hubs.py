"""Cache-busting nos links dos Hubs.

Adiciona ?v=YYYYMMDD em todos os links de sub-botoes dos *_Hub.html, forcando
o browser a baixar versao nova dos portais. Rodar SEMPRE depois de fechamento.

Uso: python _cache_bust_hubs.py [YYYYMMDD]
  - sem arg: usa data de hoje
  - com arg: usa a data especifica (ex: 20260519)

Idempotente: se ja tem ?v=NNNN no link, atualiza pra nova versao.
"""
import re, glob, sys, datetime, os

# Script vive em _tools/ — a raiz do repo é um nível acima.
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
HUBDIR = os.path.join(ROOT, 'hub')

version = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime('%Y%m%d')
print(f'Cache-busting version: ?v={version}')

# Casa links como href="../Igor.html" ou href="../oxy/Igor_Oxy_Recovery.html"
# Com ou sem ?v=NNNN existente
PADRAO = re.compile(r'href="(\.\./[^"?]+\.html)(\?v=\d+)?"')
# Casa links de PASTA (sem arquivo), ex: href="../oxy/" ou href="../compras/kanban/"
# usados pelos sub-botoes do Gestor_Hub. Disjunto do PADRAO acima (este termina em "/").
PADRAO_DIR = re.compile(r'href="(\.\./[^"?]+/)(\?v=\d+)?"')

arquivos = sorted(glob.glob(os.path.join(HUBDIR, '*_Hub.html')))
total_links = 0
for arq in arquivos:
    txt = open(arq, encoding='utf-8').read()
    novo, n1 = PADRAO.subn(rf'href="\1?v={version}"', txt)
    novo, n2 = PADRAO_DIR.subn(rf'href="\1?v={version}"', novo)
    n = n1 + n2
    if n and novo != txt:
        open(arq, 'w', encoding='utf-8', newline='').write(novo)
        print(f'  {os.path.basename(arq):50s} {n} links atualizados ({n1} arquivo + {n2} pasta)')
        total_links += n
    else:
        print(f'  {os.path.basename(arq):50s} (sem mudanca)')

print(f'\nTOTAL: {total_links} links atualizados em {len(arquivos)} Hubs')
