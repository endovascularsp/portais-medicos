"""Pente fino de autenticação em todos os HTMLs do repo. Lista quais arquivos pedem senha
e quais permitem SSO Google + navegação livre."""
import re, os

all_htmls = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
    for f in files:
        if f.endswith('.html'):
            rel = os.path.relpath(os.path.join(root, f))
            all_htmls.append(rel.replace(os.sep, '/'))

print(f"{'arquivo':<70} {'tipo':<7} {'gate':<5} {'senha-adm':<10} {'login-ov':<10} {'auto':<6} {'PDATA':<6}")
print('-' * 125)

categorias = {}

for arq in sorted(all_htmls):
    if 'assets' in arq:
        continue
    try:
        with open(arq, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception:
        continue

    tem_gate = 'sb.auth.getUser' in html
    tem_senha_adm = 'senha-overlay' in html or ("verificarSenha" in html and "senha-input" in html)
    tem_login_overlay = ("id='login-overlay'" in html) or ('id="login-overlay"' in html)
    tem_xpa = "'_xpa'" in html or '"_xpa"' in html
    tem_pdata_plain = '/*PDATA*/' in html

    nome = os.path.basename(arq)
    if 'Hub' in nome or 'hub/' in arq:
        tipo = 'hub'
    elif arq == 'recebimento.html' or arq.endswith('/index.html'):
        tipo = 'admin'
    elif arq.startswith('login/'):
        tipo = 'login'
    elif re.search(r'(Insights|Oxy_Recovery|Oxy_Produtividade|Produtividade|_Cir)', nome) or re.match(r'^[A-Z][a-z]+_[A-Z]', nome):
        tipo = 'indiv'
    else:
        tipo = 'outro'

    line = f"{arq:<70} {tipo:<7} {'SIM' if tem_gate else '   ':<5} {'SENHA-ADM' if tem_senha_adm else '         ':<10} {'LOGIN-OV' if tem_login_overlay else '        ':<10} {'XPA' if tem_xpa else '   ':<6} {'CLARO' if tem_pdata_plain else '     ':<6}"
    categorias.setdefault(tipo, []).append((arq, line))

for tipo in ['admin', 'hub', 'indiv', 'login', 'outro']:
    if tipo not in categorias:
        continue
    lst = categorias[tipo]
    print(f"\n=== {tipo.upper()} ({len(lst)} arquivos) ===")
    for _, line in lst[:25]:
        print(line)
    if len(lst) > 25:
        print(f"  (... e mais {len(lst) - 25} do tipo {tipo})")

print(f"\nTOTAL: {sum(len(v) for v in categorias.values())} arquivos analisados")
