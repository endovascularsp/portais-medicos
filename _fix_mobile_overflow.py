"""Garante TODOS os portais com fix mobile robusto:
1. html,body{overflow-x:hidden} (já fazia)
2. Em mobile (<600px), login-overlays com width fixo viram max-width responsivo
3. Em mobile, paddings laterais grandes (>=24px) são reduzidos
4. Garante viewport meta tag

Idempotente. Pula arquivos sem <style>.
"""
import os, glob, re, sys

DRY = '--dry-run' in sys.argv

def listar_htmls():
    fora = []
    for f in glob.glob('*.html'): fora.append(f)
    for sub in ['oxy', 'cirurgias', 'hub', 'produtividade', 'oxy-produtividade',
                'dashboard-insights', 'admin', 'previas', 'atendimentos', 'fotona',
                'gestao-administrativa', 'dashboard-operacional', 'login']:
        if os.path.isdir(sub):
            for f in glob.glob(f'{sub}/*.html'): fora.append(f)
    return sorted(set(fora))

SENTINEL_V1 = '/* fix-mobile-overflow */'
SENTINEL_V2 = '/* fix-mobile-overflow-v2 */'

REGRA_V2 = (
    f'\n{SENTINEL_V2}\n'
    'html,body{overflow-x:hidden!important;max-width:100vw;}\n'
    '@media(max-width:600px){\n'
    '  .login-card,.login-box,.senha-box,.login-input-wrap{\n'
    '    width:auto!important;max-width:calc(100vw - 24px)!important;\n'
    '  }\n'
    '  body{padding:0!important;margin:0!important;}\n'
    '  .header,.admin-nav,.portais-nav,.admin-portais-nav,.main,.hub-body{\n'
    '    padding-left:14px!important;padding-right:14px!important;\n'
    '  }\n'
    '  img{max-width:100%!important;height:auto;}\n'
    '  table{max-width:100%;}\n'
    '}\n'
)

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if SENTINEL_V2 in html:
        return 'JA_V2', html
    # Remove v1 se tiver, pra evitar conflito
    if SENTINEL_V1 in html:
        html = re.sub(re.escape(SENTINEL_V1) + r'[^\n]*\n', '', html)
    # Insere v2 logo após o primeiro <style>
    m = re.search(r'<style[^>]*>', html)
    if not m:
        return 'SEM_STYLE', html
    pos = m.end()
    novo = html[:pos] + REGRA_V2 + html[pos:]
    # Garante viewport meta
    if 'name="viewport"' not in novo and "name='viewport'" not in novo:
        novo = novo.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0">')
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

htmls = listar_htmls()
print(f"Aplicando fix mobile v2 em {len(htmls)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {'OK': 0, 'JA_V2': 0, 'SEM_STYLE': 0}
for arq in htmls:
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1

print(f'\nTotal: OK={stats["OK"]}  ja-v2={stats["JA_V2"]}  sem-style={stats["SEM_STYLE"]}')
