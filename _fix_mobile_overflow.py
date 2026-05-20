"""Fix mobile v4 — completa v3 com 2 problemas adicionais reportados pelo Thiago:

- Recebimento: botão Home sobrepondo título 'Endovascular' no header
- Produtividade: cards extrapolando à direita

Soluções:
- Header em mobile: altura auto, esconde subtítulo, h1 menor com ellipsis,
  logo menor, botões action mais compactos. Mantém em 1 linha com flex 1:auto:auto
- Cards (kpi/metric/chart/card-box): max-width:100% + overflow:hidden + box-sizing,
  grid em 2 colunas fixas (em vez de auto-fit que pode vazar), KPI label/valor com
  word-break pra acomodar valores grandes
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
SENTINEL_V4 = '/* fix-mobile-overflow-v4 */'

REGRA_V4 = (
    f'\n{SENTINEL_V4}\n'
    'html,body{overflow-x:hidden!important;max-width:100vw;}\n'
    '@media(max-width:600px){\n'
    '  /* === Header === */\n'
    '  .header{\n'
    '    height:auto!important;min-height:56px!important;\n'
    '    padding:8px 14px!important;\n'
    '    flex-wrap:nowrap!important;gap:8px!important;\n'
    '    box-sizing:border-box;\n'
    '  }\n'
    '  .header-logo{flex:1 1 auto!important;min-width:0!important;overflow:hidden;gap:8px!important;}\n'
    '  .header-logo img,.header-logo .logo-svg{width:32px!important;height:32px!important;}\n'
    '  .header-logo h1{font-size:13px!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}\n'
    '  .header-logo span{display:none!important;}\n'
    '  .header-info h1{font-size:13px!important;}\n'
    '  .header-info p{font-size:10px!important;}\n'
    '  .header-actions{flex:0 0 auto!important;gap:4px!important;}\n'
    '  .header-action-btn{padding:5px 8px!important;font-size:10px!important;gap:3px!important;}\n'
    '  .header-action-btn .icon-text,.header-badge{display:none;}\n'
    '  /* === Containers/widths === */\n'
    '  .login-card,.login-box,.senha-box,.login-input-wrap{\n'
    '    width:auto!important;max-width:calc(100vw - 24px)!important;\n'
    '  }\n'
    '  body{padding:0!important;margin:0!important;}\n'
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
    '  /* === Cards: travam largura e quebram conteudo === */\n'
    '  .kpi,.metric-card,.card,.card-box,.chart-card,.full-col,.insight-card{\n'
    '    max-width:100%!important;\n'
    '    overflow:hidden!important;\n'
    '    box-sizing:border-box!important;\n'
    '  }\n'
    '  .kpi-row,.cards,.metrics-grid,.two-col,.three-col,.grid-2,.grid-main,.insights-grid{\n'
    '    grid-template-columns:repeat(2,minmax(0,1fr))!important;\n'
    '    gap:8px!important;\n'
    '    width:100%;max-width:100%;\n'
    '  }\n'
    '  .kpi{padding:14px 14px 14px 12px!important;}\n'
    '  .kpi-ic{top:10px!important;right:10px!important;width:26px!important;height:26px!important;font-size:12px!important;}\n'
    '  .kpi-label{font-size:10px!important;letter-spacing:0.3px!important;}\n'
    '  .kpi-val{font-size:16px!important;word-break:break-word;line-height:1.2;}\n'
    '  .kpi-foot{font-size:10px!important;}\n'
    '  .metric-valor{font-size:18px!important;word-break:break-word;}\n'
    '  /* Chart wrappers */\n'
    '  .chart-wrap{max-width:100%!important;overflow:hidden;}\n'
    '  canvas{max-width:100%!important;}\n'
    '  /* === Tabelas: container scrollavel === */\n'
    '  .table-scroll,.table-wrap,#bottom-detail{overflow-x:auto!important;-webkit-overflow-scrolling:touch;max-width:100%;}\n'
    '  /* === Chips (Produtividade) === */\n'
    '  .destaques{flex-wrap:wrap!important;gap:6px!important;max-width:100%;}\n'
    '  .chip{font-size:10px!important;padding:5px 7px!important;}\n'
    '  /* === Imagens === */\n'
    '  img{max-width:100%!important;height:auto;}\n'
    '  /* === Em telas MUITO estreitas (<360px): 1 KPI por linha === */\n'
    '}\n'
    '@media(max-width:360px){\n'
    '  .kpi-row,.cards,.metrics-grid,.two-col,.three-col,.grid-2,.grid-main,.insights-grid{\n'
    '    grid-template-columns:1fr!important;\n'
    '  }\n'
    '  .header-action-btn span{display:none;}\n'
    '}\n'
)

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if SENTINEL_V4 in html:
        return 'JA_V4', html
    # Remove sentinels antigos
    for sentinel in (SENTINEL_V3, SENTINEL_V2, SENTINEL_V1):
        if sentinel in html:
            pat = re.compile(re.escape(sentinel) + r'.*?\n}\n(?:@media[^{]*\{[^}]*\}\n)?', re.DOTALL)
            html = pat.sub('', html, count=1)
    # Insere v4 logo após o primeiro <style>
    m = re.search(r'<style[^>]*>', html)
    if not m:
        return 'SEM_STYLE', html
    pos = m.end()
    novo = html[:pos] + REGRA_V4 + html[pos:]
    if 'name="viewport"' not in novo and "name='viewport'" not in novo:
        novo = novo.replace('<head>', '<head>\n  <meta name="viewport" content="width=device-width,initial-scale=1.0">', 1)
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

htmls = listar_htmls()
print(f"Aplicando fix mobile v4 em {len(htmls)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {'OK': 0, 'JA_V4': 0, 'SEM_STYLE': 0}
for arq in htmls:
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1

print(f'\nTotal: OK={stats["OK"]}  ja-v4={stats["JA_V4"]}  sem-style={stats["SEM_STYLE"]}')
