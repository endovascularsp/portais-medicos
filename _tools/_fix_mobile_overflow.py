"""Fix mobile v7 — conserta Hub e gráficos.

Lições do v6:
- img{max-width:100%} fez a img base64 do Hub "inchar" porque
  o CSS original só restringia `.header-logo .logo-svg` (class),
  e o HTML usa <img> sem essa class
- chart-wrap{overflow:hidden} + height:220px estava cortando/achatando
  gráficos no mobile

v7 corrige:
- header .header-logo img{width:44px;height:44px} — img mantém tamanho
- chart-wrap em mobile com height:300px (era 220px) — mais legível
- Remove overflow:hidden do chart-wrap (deixa o canvas respirar)
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
               '/* fix-mobile-overflow-v5 */', '/* fix-mobile-overflow-v6 */']
SENTINEL_V7 = '/* fix-mobile-overflow-v7 */'

REGRA_V7 = (
    f'\n{SENTINEL_V7}\n'
    'html,body{overflow-x:hidden!important;max-width:100vw;}\n'
    '@media(max-width:600px){\n'
    '  body{padding:0!important;margin:0!important;}\n'
    '  /* === Header (apenas .header classe) === */\n'
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
    '  /* === Imagens dentro de qualquer header-logo (resolve Hub: img base64 sem class .logo-svg) === */\n'
    '  .header-logo img{width:44px!important;height:44px!important;flex-shrink:0!important;}\n'
    '  /* === Login boxes === */\n'
    '  .login-card,.login-box,.senha-box,.login-input-wrap{\n'
    '    width:auto!important;max-width:calc(100vw - 24px)!important;\n'
    '  }\n'
    '  /* === Padding lateral === */\n'
    '  .admin-nav,.portais-nav,.admin-portais-nav,.main,.hub-body{\n'
    '    padding-left:14px!important;padding-right:14px!important;\n'
    '    box-sizing:border-box;\n'
    '  }\n'
    '  /* === Periodo-bloco === */\n'
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
    '  /* === KPIs: 2 colunas === */\n'
    '  .kpi-row,.cards,.metrics-grid,.insights-grid{\n'
    '    grid-template-columns:repeat(2,minmax(0,1fr))!important;\n'
    '    gap:8px!important;width:100%;max-width:100%;\n'
    '  }\n'
    '  /* === Cards de gráfico: 1 coluna em mobile === */\n'
    '  .two-col,.three-col,.grid-2,.grid-main,.grid-pag{\n'
    '    grid-template-columns:1fr!important;\n'
    '    gap:14px!important;\n'
    '  }\n'
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
    '  /* Hub cards: 1 coluna */\n'
    '  .hub-cards{grid-template-columns:1fr!important;gap:14px!important;}\n'
    '  /* === Chart-wrap: SEM overflow:hidden, altura maior pra legibilidade === */\n'
    '  .chart-wrap{max-width:100%!important;height:300px!important;}\n'
    '  canvas{max-width:100%!important;}\n'
    '  /* === Tabelas: scroll === */\n'
    '  .table-scroll,.table-wrap,#bottom-detail{overflow-x:auto!important;-webkit-overflow-scrolling:touch;max-width:100%;}\n'
    '  /* === Chips Produtividade === */\n'
    '  .destaques{flex-wrap:wrap!important;gap:6px!important;max-width:100%;}\n'
    '  .chip{font-size:10px!important;padding:5px 7px!important;}\n'
    '  /* === Imagens (mas NÃO header-logo img que tem regra propria acima) === */\n'
    '  img:not(.header-logo img){max-width:100%!important;height:auto;}\n'
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
    if SENTINEL_V7 in html:
        return 'JA_V7', html
    for sentinel in SENTINEL_VS:
        if sentinel in html:
            pat = re.compile(
                re.escape(sentinel) + r'.*?\n}\n(?:@media[^{]*\{[^}]*\}\n)*',
                re.DOTALL
            )
            html = pat.sub('', html, count=1)
    m = re.search(r'<style[^>]*>', html)
    if not m:
        return 'SEM_STYLE', html
    pos = m.end()
    novo = html[:pos] + REGRA_V7 + html[pos:]
    if 'name="viewport"' not in novo and "name='viewport'" not in novo:
        novo = novo.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0">', 1)
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

htmls = listar_htmls()
print(f"Aplicando fix mobile v7 em {len(htmls)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {'OK': 0, 'JA_V7': 0, 'SEM_STYLE': 0}
for arq in htmls:
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1

print(f'\nTotal: OK={stats["OK"]}  ja-v7={stats["JA_V7"]}  sem-style={stats["SEM_STYLE"]}')
