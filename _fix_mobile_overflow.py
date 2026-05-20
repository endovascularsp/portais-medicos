"""Fix mobile v3 — completa o v2 com regras pros casos identificados no celular do Thiago:

- Print 1: range-filter vazando (Aplicar/Limpar cortados) → flex-wrap forçado, selects 50% cada
- Print 2: tabela "Produção por Profissional" vaza → containers .table-scroll/.table-wrap
  com overflow-x:auto sempre; tabela com width auto
- Print 3: portais-nav corta Cirurgias → confirmar scroll horizontal interno; chips do Produtividade
  com flex-wrap pra empilhar

Mantém v2 + adiciona v3. Idempotente.
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
SENTINEL_V3 = '/* fix-mobile-overflow-v3 */'

REGRA_V3 = (
    f'\n{SENTINEL_V3}\n'
    'html,body{overflow-x:hidden!important;max-width:100vw;}\n'
    '@media(max-width:600px){\n'
    '  /* Containers e widths */\n'
    '  .login-card,.login-box,.senha-box,.login-input-wrap{\n'
    '    width:auto!important;max-width:calc(100vw - 24px)!important;\n'
    '  }\n'
    '  body{padding:0!important;margin:0!important;}\n'
    '  .header,.admin-nav,.portais-nav,.admin-portais-nav,.main,.hub-body{\n'
    '    padding-left:14px!important;padding-right:14px!important;\n'
    '  }\n'
    '  /* Periodo-bloco: empilha tudo em coluna */\n'
    '  .periodo-bloco{flex-direction:column!important;align-items:stretch!important;gap:10px!important;}\n'
    '  .periodo-bloco .f-grp{flex-wrap:wrap!important;width:100%;}\n'
    '  .periodo-bloco .range-sep{display:none!important;}\n'
    '  /* Range filter: selects e botoes em 2 colunas */\n'
    '  .range-filter{flex-wrap:wrap!important;gap:6px!important;width:100%;}\n'
    '  .range-filter select{flex:1 1 calc(50% - 3px)!important;min-width:0!important;}\n'
    '  .range-filter .range-ate{flex:0 0 100%!important;text-align:center;}\n'
    '  .range-btn{flex:1 1 calc(50% - 3px)!important;}\n'
    '  /* Prof-select: full width */\n'
    '  .prof-select{flex:1 1 100%!important;min-width:0!important;max-width:100%!important;width:100%;}\n'
    '  /* Tabs */\n'
    '  .tabs-flex,.periodo-tabs{flex-wrap:wrap!important;}\n'
    '  /* Portais/admin-nav: scroll horizontal interno (nao vazam pro corpo) */\n'
    '  .portais-nav,.admin-nav,.admin-portais-nav{\n'
    '    flex-wrap:nowrap!important;\n'
    '    overflow-x:auto!important;\n'
    '    -webkit-overflow-scrolling:touch;\n'
    '    scrollbar-width:none;\n'
    '  }\n'
    '  .portais-nav::-webkit-scrollbar,.admin-nav::-webkit-scrollbar,.admin-portais-nav::-webkit-scrollbar{display:none;}\n'
    '  .portais-nav-btn,.admin-nav-btn,.admin-portais-nav-btn{flex-shrink:0!important;}\n'
    '  /* Tabelas: container com overflow-x */\n'
    '  .table-scroll,.table-wrap,#bottom-detail{overflow-x:auto!important;-webkit-overflow-scrolling:touch;}\n'
    '  /* Chips destaques (Produtividade): empilham */\n'
    '  .destaques{flex-wrap:wrap!important;gap:6px!important;}\n'
    '  .chip{font-size:11px!important;padding:5px 8px!important;}\n'
    '  /* Imagens */\n'
    '  img{max-width:100%!important;height:auto;}\n'
    '}\n'
)

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if SENTINEL_V3 in html:
        return 'JA_V3', html
    # Remove sentinels antigos (v1, v2) e seus blocos pra evitar conflito
    for sentinel in (SENTINEL_V2, SENTINEL_V1):
        if sentinel in html:
            # Remove o bloco que segue: do sentinel até a próxima '}' fechando o @media (procura padrão)
            # Estratégia mais segura: deleta apenas a linha do sentinel + o bloco contíguo até linha em branco depois do '}' final
            # Como nossos sentinels v1/v2 inseriram um bloco coeso, vou tentar deletar tudo até a 1ª linha em branco depois de uma `}` solitária após o sentinel.
            # Mais simples: usar regex que case do sentinel até o `}` que fecha o último @media
            pat = re.compile(re.escape(sentinel) + r'.*?\n}\n', re.DOTALL)
            html = pat.sub('', html, count=1)
    # Insere v3 logo após o primeiro <style>
    m = re.search(r'<style[^>]*>', html)
    if not m:
        return 'SEM_STYLE', html
    pos = m.end()
    novo = html[:pos] + REGRA_V3 + html[pos:]
    # Garante viewport meta
    if 'name="viewport"' not in novo and "name='viewport'" not in novo:
        novo = novo.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0">', 1)
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

htmls = listar_htmls()
print(f"Aplicando fix mobile v3 em {len(htmls)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {'OK': 0, 'JA_V3': 0, 'SEM_STYLE': 0}
for arq in htmls:
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1

print(f'\nTotal: OK={stats["OK"]}  ja-v3={stats["JA_V3"]}  sem-style={stats["SEM_STYLE"]}')
