"""Fix mobile v6 — separa cards de KPI (2 col) de cards de gráfico (1 col).

Lições do v5:
- Forçar repeat(2,1fr) em .two-col/.three-col/.grid-2/.grid-main espremeu
  gráficos (donut, bar chart) que precisam de largura mínima
- Regra em `header` (tag, sem classe) afetou o Hub que tem layout diferente

v6 corrige:
- KPIs (.kpi-row, .cards, .metrics-grid, .insights-grid) → 2 colunas em mobile
- Charts (.two-col, .three-col, .grid-2, .grid-main, .grid-pag) → 1 COLUNA em mobile
- Regras de header só em .header (classe), NÃO na tag <header> genérica
  → preserva Hub que usa <header> sem classe
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

SENTINEL_VS = ['/* fix-mobile-overflow */', '/* fix-mobile-overflow-v2 */',
               '/* fix-mobile-overflow-v3 */', '/* fix-mobile-overflow-v4 */',
               '/* fix-mobile-overflow-v5 */']
SENTINEL_V6 = '/* fix-mobile-overflow-v6 */'

REGRA_V6 = (
    f'\n{SENTINEL_V6}\n'
    'html,body{overflow-x:hidden!important;max-width:100vw;}\n'
    '@media(max-width:600px){\n'
    '  body{padding:0!important;margin:0!important;}\n'
    '  /* === Header (APENAS .header — não toca em <header> genérico do Hub) === */\n'
    '  .header{\n'
    '    flex-wrap:wrap!important;height:auto!important;min-height:0!important;\n'
    '    padding-left:14px!important;padding-right:14px!important;\n'
    '    gap:8px!important;\n'
    '  }\n'
    '  .header > .header-logo{flex:1 1 auto!important;min-width:0;}\n'
    '  .header > .header-actions{\n'
    '    flex:0 0 100%!important;justify-content:flex-end!important;\n'
    '    gap:6px!important;margin-top:4px;\n'
    '  }\n'
    '  .header > .header-actions .header-action-btn{padding:5px 10px!important;font-size:11px!important;}\n'
    '  /* === Login boxes === */\n'
    '  .login-card,.login-box,.senha-box,.login-input-wrap{\n'
    '    width:auto!important;max-width:calc(100vw - 24px)!important;\n'
    '  }\n'
    '  /* === Padding lateral em barras === */\n'
    '  .admin-nav,.portais-nav,.admin-portais-nav,.main,.hub-body{\n'
    '    padding-left:14px!important;padding-right:14px!important;\n'
    '    box-sizing:border-box;\n'
    '  }\n'
    '  /* === Periodo-bloco em coluna === */\n'
    '  .periodo-bloco{flex-direction:column!important;align-items:stretch!important;gap:10px!important;\n'
    '    box-sizing:border-box;max-width:100%;}\n'
    '  .periodo-bloco .f-grp{flex-wrap:wrap!important;width:100%;}\n'
    '  .periodo-bloco .range-sep{display:none!important;}\n'
    '  .range-filter{flex-wrap:wrap!important;gap:6px!important;width:100%;}\n'
    '  .range-filter select{flex:1 1 calc(50% - 3px)!important;min-width:0!important;}\n'
    '  .range-filter .range-ate{flex:0 0 100%!important;text-align:center;}\n'
    '  .range-btn{flex:1 1 calc(50% - 3px)!important;}\n'
    '  .prof-select{flex:1 1 100%!important;min-width:0!important;max-width:100%!important;width:100%;}\n'
    '  .tabs-flex,.periodo-tabs{flex-wrap:wrap!important;}\n'
    '  /* === Nav portais: scroll horizontal interno === */\n'
    '  .portais-nav,.admin-nav,.admin-portais-nav{\n'
    '    flex-wrap:nowrap!important;overflow-x:auto!important;\n'
    '    -webkit-overflow-scrolling:touch;scrollbar-width:none;\n'
    '  }\n'
    '  .portais-nav::-webkit-scrollbar,.admin-nav::-webkit-scrollbar,.admin-portais-nav::-webkit-scrollbar{display:none;}\n'
    '  .portais-nav-btn,.admin-nav-btn,.admin-portais-nav-btn{flex-shrink:0!important;}\n'
    '  /* === KPIs (pequenos): 2 colunas === */\n'
    '  .kpi-row,.cards,.metrics-grid,.insights-grid{\n'
    '    grid-template-columns:repeat(2,minmax(0,1fr))!important;\n'
    '    gap:8px!important;width:100%;max-width:100%;\n'
    '  }\n'
    '  /* === Cards de gráfico (grandes): 1 coluna === */\n'
    '  .two-col,.three-col,.grid-2,.grid-main,.grid-pag{\n'
    '    grid-template-columns:1fr!important;\n'
    '    gap:14px!important;\n'
    '  }\n'
    '  /* Cards individuais: travados em max-width 100% */\n'
    '  .kpi,.metric-card,.card,.card-box,.chart-card,.full-col,.insight-card,.hub-card{\n'
    '    max-width:100%!important;\n'
    '    box-sizing:border-box!important;\n'
    '  }\n'
    '  .kpi{padding:14px 14px 14px 12px!important;}\n'
    '  .kpi-ic{top:10px!important;right:10px!important;width:26px!important;height:26px!important;font-size:12px!important;}\n'
    '  .kpi-label{font-size:10px!important;letter-spacing:0.3px!important;}\n'
    '  .kpi-val{font-size:16px!important;word-break:break-word;line-height:1.2;}\n'
    '  .kpi-foot{font-size:10px!important;}\n'
    '  .metric-valor{font-size:18px!important;word-break:break-word;}\n'
    '  /* Hub cards: 1 coluna (eram 3 em desktop) */\n'
    '  .hub-cards{grid-template-columns:1fr!important;gap:14px!important;}\n'
    '  /* Chart wrappers */\n'
    '  .chart-wrap{max-width:100%!important;overflow:hidden;}\n'
    '  canvas{max-width:100%!important;}\n'
    '  /* === Tabelas: container scrollavel === */\n'
    '  .table-scroll,.table-wrap,#bottom-detail{overflow-x:auto!important;-webkit-overflow-scrolling:touch;max-width:100%;}\n'
    '  /* === Chips Produtividade === */\n'
    '  .destaques{flex-wrap:wrap!important;gap:6px!important;max-width:100%;}\n'
    '  .chip{font-size:10px!important;padding:5px 7px!important;}\n'
    '  img{max-width:100%!important;height:auto;}\n'
    '}\n'
    '@media(max-width:380px){\n'
    '  .kpi-row,.cards,.metrics-grid,.insights-grid{\n'
    '    grid-template-columns:1fr!important;\n'
    '  }\n'
    '}\n'
)

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if SENTINEL_V6 in html:
        return 'JA_V6', html
    # Remove sentinels antigos
    for sentinel in SENTINEL_VS:
        if sentinel in html:
            pat = re.compile(
                re.escape(sentinel) + r'.*?\n}\n(?:@media[^{]*\{[^}]*\}\n)*',
                re.DOTALL
            )
            html = pat.sub('', html, count=1)
    # Insere v6 logo após o primeiro <style>
    m = re.search(r'<style[^>]*>', html)
    if not m:
        return 'SEM_STYLE', html
    pos = m.end()
    novo = html[:pos] + REGRA_V6 + html[pos:]
    if 'name="viewport"' not in novo and "name='viewport'" not in novo:
        novo = novo.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0">', 1)
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

htmls = listar_htmls()
print(f"Aplicando fix mobile v6 em {len(htmls)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {'OK': 0, 'JA_V6': 0, 'SEM_STYLE': 0}
for arq in htmls:
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1

print(f'\nTotal: OK={stats["OK"]}  ja-v6={stats["JA_V6"]}  sem-style={stats["SEM_STYLE"]}')
