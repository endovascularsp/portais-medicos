"""URGENTE: limpa chaves `}` órfãs e regras zumbis que sobraram da migração
dos sentinels v1-v6 → v7. Causa: o regex de limpeza não casava `@media`
com regras aninhadas, deixando blocos órfãos.

Estratégia segura:
1. Encontra o fim do bloco v7 (sentinel + @media(max-width:600px) + @media(max-width:380px))
2. Logo após, detecta e remove até a próxima regra CSS válida (geralmente :root, *, ou /*comentario*/)
3. As linhas no meio que são só `}\n` ou regras zumbi tipo `.header-action-btn span{display:none;}`
   sao removidas
"""
import os, glob, re

# Padrão do FIM do meu bloco v7 (último } do último @media)
# Espera-se que termine com:
#   @media(max-width:380px){
#     .kpi-row,.cards,.metrics-grid,.insights-grid{
#       grid-template-columns:1fr!important;
#     }
#   }
PAT_END_V7 = re.compile(
    r'(@media\(max-width:380px\)\{\s*\n'
    r'\s*\.kpi-row,\.cards,\.metrics-grid,\.insights-grid\{\s*\n'
    r'\s*grid-template-columns:1fr!important;\s*\n'
    r'\s*\}\s*\n'
    r'\})',  # fecha o @media
    re.DOTALL
)

# Após esse ponto, removemos órfãos até encontrar o início do CSS original
# (':root{', '*{', '@media' válido sem ser nosso, ou outro seletor)
ORFAO_PAT = re.compile(
    r'(?:\s*\n)*'                                          # linhas vazias
    r'(?:\s*\.header-action-btn[^{]*\{[^}]*\}\s*\n)?'      # regra zumbi v4
    r'(?:\s*\}\s*\n)+',                                    # 1+ chaves órfãs
    re.MULTILINE
)

def aplicar(arq):
    with open(arq, 'r', encoding='utf-8') as f:
        html = f.read()
    if '/* fix-mobile-overflow-v7 */' not in html:
        return 'SEM_V7', 0
    m = PAT_END_V7.search(html)
    if not m:
        return 'FIM_V7_NAO_ACHADO', 0
    pos_apos_v7 = m.end()
    # A partir daqui, remover orfaos
    # Vamos pegar o trecho [pos_apos_v7 .. próxima ocorrência de :root{ ou *{ ou /*]
    tail = html[pos_apos_v7:]
    # Acha o início da próxima regra "válida"
    m2 = re.search(r'(:root\{|\*\{|\/\*[^v])', tail)
    if not m2:
        return 'NAO_ACHEI_INICIO_CSS_ORIG', 0
    pos_inicio_orig = m2.start()
    # Trecho entre v7 e início original
    entre = tail[:pos_inicio_orig]
    # Remove órfãos desse trecho
    limpo = ORFAO_PAT.sub('\n', entre)
    # Conta diferença
    delta = len(entre) - len(limpo)
    if delta == 0:
        return 'SEM_ORFAO', 0
    novo_html = html[:pos_apos_v7] + limpo + tail[pos_inicio_orig:]
    with open(arq, 'w', encoding='utf-8', newline='') as f:
        f.write(novo_html)
    return 'OK', delta

# Roda em todos os HTMLs
all_files = []
for f in glob.glob('*.html'): all_files.append(f)
for sub in ['oxy', 'cirurgias', 'hub', 'produtividade', 'oxy-produtividade',
            'dashboard-insights', 'admin', 'previas', 'atendimentos', 'fotona',
            'gestao-administrativa', 'dashboard-operacional', 'login']:
    if os.path.isdir(sub):
        for f in glob.glob(f'{sub}/*.html'): all_files.append(f)

stats = {}
total_bytes = 0
for arq in sorted(all_files):
    try:
        status, delta = aplicar(arq)
    except Exception as e:
        print(f'  ERRO {arq}: {e}')
        continue
    stats[status] = stats.get(status, 0) + 1
    total_bytes += delta

print(f'Stats: {stats}')
print(f'Total bytes removidos: {total_bytes}')
