"""UX #7 — Spinner de loading na primeira carga dos portais com gate.

Os portais com gate Supabase usam html{visibility:hidden} pra não piscar
conteúdo antes da autorização. Em 4G isso vira uma tela branca de alguns
segundos. Este script injeta um overlay com spinner que aparece nesse meio
-tempo.

Truque: #boot tem visibility:visible (reverte o hidden herdado do html).
Quando o gate libera e faz documentElement.style.visibility='visible',
a regra `html[style*="visible"] #boot{display:none}` esconde o overlay —
sem precisar tocar no JS do gate de cada portal.

Idempotente (sentinela boot-spinner-v1).
"""
import glob, os

SENT = 'boot-spinner-v1'

ALVOS = [
    'recebimento.html', 'cirurgias/index.html', 'oxy/index.html',
    'produtividade/index.html', 'oxy-produtividade/index.html',
    'dashboard-insights/index.html', 'fotona/index.html',
    'compras/kanban/index.html', 'compras/nova/index.html',
]

BOOT_CSS = '''<style id="boot-spinner-v1">
#boot{visibility:visible;position:fixed;inset:0;background:#0B1F3A;z-index:99999;
  display:flex;align-items:center;justify-content:center;flex-direction:column;gap:14px;}
html[style*="visible"] #boot{display:none;}
#boot .sp{width:38px;height:38px;border:4px solid rgba(255,255,255,0.15);
  border-top-color:#fff;border-radius:50%;animation:bootsp .8s linear infinite;}
@keyframes bootsp{to{transform:rotate(360deg)}}
#boot .tx{color:rgba(255,255,255,0.65);font-family:'Segoe UI',system-ui,sans-serif;
  font-size:13px;letter-spacing:.3px;}
</style>'''

BOOT_HTML = '<!--boot-spinner-v1--><div id="boot"><div class="sp"></div>' \
            '<div class="tx">Carregando dados…</div></div>'

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if SENT in html:
        return 'JA_TEM'
    if '</head>' not in html or '<body>' not in html:
        return 'SEM_HEAD_BODY'
    html = html.replace('</head>', BOOT_CSS + '\n</head>', 1)
    html = html.replace('<body>', '<body>\n' + BOOT_HTML, 1)
    with open(arq, 'w', encoding='utf-8', newline='') as f:
        f.write(html)
    return 'OK'

print('UX #7 — injetando spinner de boot')
print('=' * 50)
stats = {}
for arq in ALVOS:
    if not os.path.exists(arq):
        print(f'  [SKIP] {arq}')
        continue
    st = aplicar(arq)
    stats[st] = stats.get(st, 0) + 1
    print(f'  [{st}] {arq}')
print(f'\n{stats}')
