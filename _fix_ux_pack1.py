"""Pack 1 de melhorias UX (#2, #5, #6):

#6 - Esconde admin-nav/portais-nav links que apontam pra arquivo 404
     (medico sem dados em outra empresa). JS no fim do body via fetch HEAD.

#2 - Contexto no header dos 6 ADMINS (recebimento, oxy, cirurgias,
     produtividade, oxy-produtividade, dashboard-insights):
     'Endovascular / Gestão de Honorários' → 'Recebimento · Endovascular SP', etc.

#5 - Timestamp 'Dados de DD/MM/AAAA' no rodapé de cada admin, via JS
     que lê document.lastModified.
"""
import os, glob, re

# Mapeamento ADMIN → contexto pro header (#2)
CONTEXT_ADMIN = {
    'recebimento.html':                'Recebimento · Endovascular SP',
    'oxy/index.html':                  'Recebimento · Oxy Recovery',
    'cirurgias/index.html':            'Recebimento · Cirurgias',
    'produtividade/index.html':        'Produtividade · Endovascular SP',
    'oxy-produtividade/index.html':    'Produtividade · Oxy Recovery',
    'dashboard-insights/index.html':   'Dashboard de Insights',
}

# #6 - JS pra esconder links 404 no admin-nav/portais-nav
JS_HIDE_404 = """
<script>
// UX #6: esconde links em admin-nav/portais-nav que apontam para arquivo inexistente.
// Funciona em producao HTTP. Em file:// local nao roda (silencioso).
(function(){
  if (location.protocol === 'file:') return;
  const seletores = '.portais-nav a[href], .admin-nav a[href], .admin-portais-nav a[href]';
  const links = document.querySelectorAll(seletores);
  links.forEach(async (a) => {
    if (!a.href || a.classList.contains('active') || a.getAttribute('href') === '#') return;
    try {
      const r = await fetch(a.href, {method:'HEAD'});
      if (!r.ok) a.style.display = 'none';
    } catch (e) { /* network err: deixa visivel */ }
  });
})();
</script>
"""

# #5 - JS pro timestamp (rodapé)
JS_TIMESTAMP = """
<script>
// UX #5: mostra 'Dados de DD/MM/AAAA' baseado na ultima atualizacao do arquivo
(function(){
  try {
    const dt = new Date(document.lastModified);
    if (isNaN(dt.getTime())) return;
    const fmt = dt.toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit', year:'numeric'});
    const tag = document.createElement('div');
    tag.className = 'ts-rodape';
    tag.innerHTML = '<style>.ts-rodape{text-align:center;font-size:11px;color:rgba(255,255,255,0.45);padding:14px;letter-spacing:0.3px;}@media(max-width:600px){.ts-rodape{padding:10px;font-size:10px;}}</style>📅 Dados atualizados em <strong style="color:rgba(255,255,255,0.75);">' + fmt + '</strong> · Endovascular SP © 2026';
    document.body.appendChild(tag);
  } catch(e){}
})();
</script>
"""

def aplicar_admin(arq, contexto):
    """Aplica #2 + #5 + #6 em um admin."""
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    log = []

    # #2 - Contexto no header
    if 'UX2-CONTEXT-APPLIED' not in html:
        # Padrão comum: <div><h1>Endovascular</h1><span>Gest&#227;o de Honor&#225;rios M&#233;dicos</span></div>
        # ou similar com 'Endovascular' e 'Gest'
        # Estratégia: trocar pra título contextual
        partes = contexto.split(' · ')
        novo_titulo = partes[0]
        novo_sub = partes[1] if len(partes) > 1 else ''
        # Padrão 1: <h1>Endovascular</h1><span>...</span>
        old1 = '<div><h1>Endovascular</h1><span>Gest&#227;o de Honor&#225;rios M&#233;dicos</span></div>'
        new1 = f'<div><h1>{novo_titulo}</h1><span>{novo_sub}</span></div><!-- UX2-CONTEXT-APPLIED -->'
        if old1 in html:
            html = html.replace(old1, new1, 1)
            log.append('#2-header')
        # Padrão Produtividade: <div class="header-info"><h1>Dashboard de Produtividade</h1>...
        # já tem contexto próprio, pular
        # Padrão Insights: <h1>Dashboard de Insights</h1> — também já tem
        # Geral fallback: procura por <h1>Endovascular</h1>
        if 'UX2-CONTEXT-APPLIED' not in html:
            m = re.search(r'<h1>Endovascular</h1>', html)
            if m:
                html = html.replace('<h1>Endovascular</h1>', f'<h1>{novo_titulo}</h1><!--UX2-CONTEXT-APPLIED-->', 1)
                # tenta também trocar o subtítulo perto
                html = re.sub(r'<span>Gest&#227;o de Honor&#225;rios M&#233;dicos</span>', f'<span>{novo_sub}</span>', html, count=1)
                log.append('#2-h1')

    # #6 - JS de hide 404 + #5 - JS timestamp
    if 'UX6-HIDE-404' not in html:
        sentinela_block = '<!-- UX6-HIDE-404 -->' + JS_HIDE_404
        html = html.replace('</body>', sentinela_block + '\n</body>', 1)
        log.append('#6-hide-404')
    if 'UX5-TIMESTAMP' not in html:
        sentinela_ts = '<!-- UX5-TIMESTAMP -->' + JS_TIMESTAMP
        html = html.replace('</body>', sentinela_ts + '\n</body>', 1)
        log.append('#5-timestamp')

    with open(arq, 'w', encoding='utf-8', newline='') as f:
        f.write(html)
    return log

def aplicar_individual(arq):
    """Aplica só #6 (admin-nav vazio) em portais individuais."""
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    log = []
    if 'UX6-HIDE-404' not in html:
        sentinela_block = '<!-- UX6-HIDE-404 -->' + JS_HIDE_404
        if '</body>' in html:
            html = html.replace('</body>', sentinela_block + '\n</body>', 1)
            log.append('#6-hide-404')
    if log:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(html)
    return log

# Aplica nos 6 admins (com #2 + #5 + #6)
print('=== Aplicando #2 + #5 + #6 nos admins ===')
for arq, ctx in CONTEXT_ADMIN.items():
    if not os.path.exists(arq):
        print(f'  [SKIP] {arq} nao existe')
        continue
    log = aplicar_admin(arq, ctx)
    print(f'  [{",".join(log) or "SEM_MUDANCA"}] {arq}')

# Aplica #6 nos portais individuais (raiz + oxy + cirurgias)
print('\n=== Aplicando #6 nos portais individuais ===')
individuais = []
for f in glob.glob('*.html'):
    if f in CONTEXT_ADMIN: continue
    if f.startswith('Portal_Fevereiro'): continue  # historicos
    if f in ['index.html','Enfermagem.html','Agendamento_Cirúrgico_e_Visita_Hospitalar.html']: continue
    with open(f, 'r', encoding='utf-8') as fp:
        if 'portais-nav' in fp.read(): individuais.append(f)
for sub in ['oxy','cirurgias']:
    for f in glob.glob(f'{sub}/*.html'):
        if f.endswith('/index.html'): continue
        if 'Endovascular_Oxy_Recovery' in f or 'Enfermagem' in f or 'Oxy_Prime' in f: continue
        individuais.append(f)
for arq in sorted(individuais):
    log = aplicar_individual(arq)
    print(f'  [{",".join(log) or "JA_TEM"}] {arq}')

print(f'\nTotal: {len(CONTEXT_ADMIN)} admins + {len(individuais)} individuais')
