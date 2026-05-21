"""Fix do bug 'tela de login a cada navegação':
- Troca sb.auth.getUser() (rede, lento) por sb.auth.getSession() (localStorage, instantâneo)
- Cacheia `cards` em sessionStorage por 30min pra evitar query no Supabase a cada navegação

Idempotente: detecta arquivos já migrados pela ausência de getUser().
"""
import os, glob, re, sys

DRY = '--dry-run' in sys.argv

ARQUIVOS = []
for f in glob.glob('*.html'):
    with open(f, 'r', encoding='utf-8') as fp:
        if 'sb.auth.getUser()' in fp.read(): ARQUIVOS.append(f)
for sub in ['oxy', 'cirurgias', 'hub', 'produtividade', 'oxy-produtividade',
            'dashboard-insights', 'admin', 'previas', 'atendimentos']:
    if os.path.isdir(sub):
        for f in glob.glob(f'{sub}/*.html'):
            with open(f, 'r', encoding='utf-8') as fp:
                if 'sb.auth.getUser()' in fp.read(): ARQUIVOS.append(f)

# Padrão antigo (gate dos 6 admins migrados nesta sessão):
OLD_PATTERN = re.compile(
    r"const \{ data: \{ user \} \} = await sb\.auth\.getUser\(\);\s*\n"
    r"\s*if \(!user\) \{ window\.location\.replace\('/login/'\); return; \}\s*\n"
    r"\s*const \{ data: me \} = await sb\.from\('users'\)\s*\n"
    r"\s*\.select\('cards'\)\s*\n"
    r"\s*\.eq\('email', \(user\.email \|\| ''\)\.toLowerCase\(\)\)\s*\n"
    r"\s*\.maybeSingle\(\);\s*\n"
    r"\s*const cards = \(me && me\.cards\) \|\| \[\];",
    re.MULTILINE
)

NEW_PATTERN = """// Usa getSession() (lê localStorage, instantâneo) em vez de getUser() (vai no servidor)
        const { data: { session } } = await sb.auth.getSession();
        if (!session) { window.location.replace('/login/'); return; }
        const user = session.user;
        const email = (user.email || '').toLowerCase();
        // Cache de cards em sessionStorage (30 min). Evita query no Supabase a cada navegação.
        const _cacheKey = '_cards_' + email;
        const _cacheT   = '_cards_t_' + email;
        let cards = null;
        try {
          const stored = sessionStorage.getItem(_cacheKey);
          const storedT = parseInt(sessionStorage.getItem(_cacheT) || '0', 10);
          if (stored && (Date.now() - storedT) < 30 * 60 * 1000) {
            cards = JSON.parse(stored);
          }
        } catch (e) {}
        if (!cards) {
          const { data: me } = await sb.from('users')
            .select('cards')
            .eq('email', email)
            .maybeSingle();
          cards = (me && me.cards) || [];
          try {
            sessionStorage.setItem(_cacheKey, JSON.stringify(cards));
            sessionStorage.setItem(_cacheT, String(Date.now()));
          } catch (e) {}
        }"""

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if NEW_PATTERN.split('\n')[0] in html or 'getSession()' in html and 'getUser()' not in html:
        return 'JA_OK', html
    m = OLD_PATTERN.search(html)
    if not m:
        return 'PADRAO_DIFERENTE', html
    novo = OLD_PATTERN.sub(NEW_PATTERN.strip(), html, count=1)
    if not DRY:
        with open(arq, 'w', encoding='utf-8', newline='') as f:
            f.write(novo)
    return 'OK', novo

print(f"Aplicando fix de sessão em {len(ARQUIVOS)} arquivos. Modo: {'DRY-RUN' if DRY else 'APLICANDO'}")
print('=' * 80)

stats = {}
for arq in sorted(ARQUIVOS):
    try:
        status, _ = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1
    print(f'  [{status:<15}] {arq}')

print(f'\nTotal: {stats}')
