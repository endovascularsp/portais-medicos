"""Padroniza h1+subtítulo dos 13 admins.

Padrão: 'Tipo Curto' / 'Contexto Curto', com separador '·' implícito (apenas
duas linhas h1+span no header — sem inline separator no HTML).

NÃO mexe nos overlays de login (h1 deles fica). Faz match só do primeiro par
h1+(span|p) que vier APÓS um <header> ou após <div ...header...>.
"""
import re, os

# arquivo → (h1_novo, sub_novo, h1_velho_que_casa, sub_velho_que_casa OU None)
MAP = {
    'recebimento.html':              ('Recebimento',        'Endovascular SP'),
    'oxy/index.html':                ('Recebimento',        'Oxy Recovery'),
    'cirurgias/index.html':          ('Recebimento',        'Cirurgias'),
    'produtividade/index.html':      ('Produtividade',      'Endovascular SP'),
    'oxy-produtividade/index.html':  ('Produtividade',      'Oxy Recovery'),
    'dashboard-insights/index.html': ('Insights',           'Endovascular SP'),
    'dashboard-operacional/index.html':('Operacional',      'WhatsApp & Instagram'),
    'fotona/index.html':             ('Beauty Legs',        'Projeto Fotona'),
    'previas/index.html':            ('Prévias',            'Recepção'),
    'atendimentos/index.html':       ('Atendimentos',       'Hospitalares'),
    'gestao-administrativa/index.html':('Gestão Administrativa','Funcionários, Cargos, Folha'),
    'admin/index.html':              ('Acessos',            'Cadastro de usuários'),
    'hub/Gestor_Hub.html':           ('Endovascular SP',    'Painel de Gestão'),  # mantém
}

# Padrão regex que casa o PRIMEIRO par h1+sub DEPOIS de <header (open tag).
# Pega o conteúdo de h1, o conteúdo do span/p, e mantém o resto intacto.
PAT_HEADER = re.compile(
    r'(<header[^>]*>.*?<h1[^>]*>)([^<]+)(</h1>\s*<(?:span|p)[^>]*>)([^<]+)(</(?:span|p)>)',
    re.DOTALL
)

def aplicar(arq, h1_novo, sub_novo):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    m = PAT_HEADER.search(html)
    if not m:
        # tenta sem <header>: alguns usam <div class="header">
        pat_alt = re.compile(
            r'(<div[^>]*class=["\']header[^"\']*["\'][^>]*>.*?<h1[^>]*>)([^<]+)(</h1>\s*<(?:span|p)[^>]*>)([^<]+)(</(?:span|p)>)',
            re.DOTALL
        )
        m = pat_alt.search(html)
        if not m: return False, 'PADRAO_NAO_CASOU', None
    h1_atual = m.group(2).strip()
    sub_atual = m.group(4).strip()
    # Se já está como queremos, pula
    h1_clean = h1_novo
    # idempotência: se atual já bate, skip
    h1_atual_norm = re.sub(r'&#\d+;', '?', h1_atual)  # ignora entidades
    if h1_clean == h1_atual or h1_clean.lower() == h1_atual.lower():
        if sub_atual == sub_novo: return False, f'JA_OK ({h1_atual} / {sub_atual})', None
    new_html = (
        html[:m.start()] +
        m.group(1) + h1_novo + m.group(3) + sub_novo + m.group(5) +
        html[m.end():]
    )
    with open(arq, 'w', encoding='utf-8', newline='') as f:
        f.write(new_html)
    return True, f'OK ({h1_atual} / {sub_atual}) -> ({h1_novo} / {sub_novo})', None

print('Padronizando headers em 13 admins')
print('='*100)
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
for arq, (h1, sub) in MAP.items():
    if not os.path.exists(arq):
        print(f'  [SKIP] {arq} nao existe')
        continue
    ok, msg, _ = aplicar(arq, h1, sub)
    marker = '+' if ok else '-'
    print(f'  [{marker}] {arq:<55} {msg}')
