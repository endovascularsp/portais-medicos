"""
Reconstroi Abril/2026 nos admins oxy/index.html e cirurgias/index.html
a partir dos individuais (que ja tem Abril decriptavel com senha canonica).

Estrategia:
1. Pra cada individual em oxy/*.html (exceto index): decripta Abril -> chave com sufixo _Oxy_Recovery
2. Pra cada individual em cirurgias/*.html (exceto index): decripta Abril -> chave SEM sufixo (igual ao admin)
3. Injeta o periodo "2026-04" no PDATA dos 2 admins
4. Imprime resumo pro user validar antes de commit

NAO commita. NAO faz push. So edita os 2 arquivos localmente.
"""
import re, os, json, base64, hashlib, glob, unicodedata
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO = os.path.dirname(os.path.abspath(__file__))
HUBDIR = os.path.join(REPO, 'hub')

def try_dec(blob, senha):
    raw = base64.b64decode(blob)
    try:
        key = hashlib.pbkdf2_hmac('sha256', senha.encode(), raw[:16], 100000, 32)
        pt = AESGCM(key).decrypt(raw[16:28], raw[28:], None)
        return json.loads(pt.decode())
    except Exception:
        return None

# Tabela autoritativa de senhas (do CLAUDE.md + extras conhecidos)
SENHAS_CANON = {
    'Igor_Rafael_Sincos': 'igo2026',
    'Jonathan_Batista_Souza': 'jon2026',
    'Carolina_Mardegan': 'car2026',
    'Christiane_Sayuri_Lopes_Inoue': 'chr2026',
    'Manoel_Augusto_Lobato': 'man2026',
    'João_Fukuda': 'joa2026',
    'Maria_Fernanda_R_Fernandes': 'maf2026',
    'Simone_Matsuda_Torricelli': 'sim2026',
    'Andrea_Ostaszewski_Klepacz': 'and2026',
    'Clara_Silva_Freitas': 'cla2026',
    'Larissa_Medeiros_Santos': 'lar2026',
    'Eduardo_Araujo_Pires': 'edu2026',
    'Daniela_Viese_Roth': 'dan2026',
    'Gabriela_Richards': 'gab2026',
    'Augusto_Ferreira_de_Carvalho_Caparica': 'aug2026',
    'Fernanda_Liporaci_Villela_Zuchi': 'fer2026',
    'Julia_do_Valle_Bargieri': 'jul2026b',
    'Juliana_Olimpio_de_Paula': 'jul2026',
    'Luiz_Severo_Bem_Junior': 'lui2026',
    'Mateus_Antunes_Nogueira': 'mat2026',
}

def canonica_para_arquivo(slug_arquivo):
    """Acha senha. Primeiro tenta a tabela canonica, depois heuristica."""
    base = slug_arquivo.replace('_Oxy_Recovery','').replace('_Oxy','').replace('_Cir','')
    # 1. Tabela canonica
    if base in SENHAS_CANON:
        cand = SENHAS_CANON[base]
        # Valida com o Hub (se existir)
        hp = os.path.join(HUBDIR, base + '_Hub.html')
        if os.path.exists(hp):
            t = open(hp, encoding='utf-8').read()
            m = re.search(r'const BLOB = "([^"]+)"', t)
            if m and try_dec(m.group(1), cand) is not None:
                return cand
        else:
            return cand  # Sem Hub pra validar, mas confio na tabela
    # 2. Heuristica (legado)
    hp = os.path.join(HUBDIR, base + '_Hub.html')
    if not os.path.exists(hp):
        return None
    t = open(hp, encoding='utf-8').read()
    m = re.search(r'const BLOB = "([^"]+)"', t)
    if not m: return None
    blob_hub = m.group(1)
    p1 = unicodedata.normalize('NFKD', base.split('_')[0].lower()).encode('ascii','ignore').decode()
    candidatos = [p1[:3]+'2026b', p1[:3]+'2026', p1[:3]+'2026r', p1+'2026', p1[:3]+'2026c']
    for c in candidatos:
        if try_dec(blob_hub, c) is not None:
            return c
    return None

def decriptar_abril_individual(arq, esperar_blob_de='Igor_Rafael_Sincos'):
    """Abre o individual, pega blob de Abril, decripta. Retorna o dict do unico prof,
    ou (None, motivo)."""
    base = os.path.basename(arq).rsplit('.',1)[0]
    canon = canonica_para_arquivo(base)
    if not canon:
        return None, 'sem-Hub-ou-senha'
    t = open(arq, encoding='utf-8', errors='ignore').read()
    m = re.search(r'TODOS_PERIODOS_ENC\s*=\s*/\*PDATA\*/(\{.*?\})/\*PDATA\*/', t, re.S)
    if not m:
        return None, 'sem-PDATA_ENC'
    try:
        enc = json.loads(m.group(1))
    except Exception as e:
        return None, f'json-falhou: {e}'
    abril = enc.get('2026-04')
    if not abril:
        return None, 'sem-Abril-no-individual'
    dec = try_dec(abril.get('blob',''), canon)
    if dec is None:
        return None, f'decriptar-falhou-com-{canon}'
    # dec eh um dict {slug: {...}}. Retorna o unico (geralmente 1).
    if not dec:
        return None, 'dict-vazio'
    # Pega a primeira chave (o prof do individual)
    k = next(iter(dec))
    return dec[k], None

# === OXY ===
print('=== OXY RECOVERY ===')
abril_oxy = {}
for arq in sorted(glob.glob(os.path.join(REPO, 'oxy', '*.html'))):
    base = os.path.basename(arq).rsplit('.',1)[0]
    if base == 'index': continue
    if 'Endovascular' in base or 'Enfermagem' in base or 'Oxy_Prime' in base:
        print(f'  [SKIP generico] {base}')
        continue
    data, err = decriptar_abril_individual(arq)
    if data is None:
        print(f'  [FAIL] {base:55s} {err}')
        continue
    chave_admin = base  # ex: Igor_Rafael_Sincos_Oxy_Recovery
    abril_oxy[chave_admin] = data
    n_atend = len(data.get('atendimentos', []))
    print(f'  [OK]   {chave_admin:55s} {n_atend} atendimentos')

print(f'\n  TOTAL Oxy Abril: {len(abril_oxy)} profs\n')

# === CIRURGIAS ===
print('=== CIRURGIAS ===')
abril_cir = {}
for arq in sorted(glob.glob(os.path.join(REPO, 'cirurgias', '*.html'))):
    base = os.path.basename(arq).rsplit('.',1)[0]
    if base == 'index': continue
    data, err = decriptar_abril_individual(arq)
    if data is None:
        print(f'  [FAIL] {base:55s} {err}')
        continue
    # No admin de cirurgias as chaves NAO tem sufixo (igual ao base do arquivo)
    chave_admin = base
    abril_cir[chave_admin] = data
    n_atend = len(data.get('atendimentos', []))
    print(f'  [OK]   {chave_admin:55s} {n_atend} atendimentos')

print(f'\n  TOTAL Cirurgias Abril: {len(abril_cir)} profs\n')

# === INJETAR ABRIL no PDATA dos 2 admins ===
def injetar(arq, abril_dict, label='Abril/2026'):
    t = open(arq, encoding='utf-8').read()
    m = re.search(r'(/\*PDATA\*/)(.*?)(/\*PDATA\*/)', t, re.S)
    if not m:
        print(f'  [ERRO] {arq}: sem markers PDATA')
        return False
    raw = m.group(2).strip()
    try:
        d = json.loads(raw)
    except Exception as e:
        print(f'  [ERRO] {arq}: json falhou: {e}')
        return False
    d['2026-04'] = {'label': label, 'profs': abril_dict}
    # Re-serializa preservando ensure_ascii=False (acentos)
    novo = json.dumps(d, ensure_ascii=False)
    novo_t = t[:m.start(2)] + novo + t[m.end(2):]
    open(arq, 'w', encoding='utf-8', newline='').write(novo_t)
    novo_size = len(novo_t)
    print(f'  [OK] {arq} -> novo tamanho: {novo_size:,} bytes')
    return True

print('=== INJETANDO no oxy/index.html ===')
if abril_oxy:
    injetar(os.path.join(REPO, 'oxy', 'index.html'), abril_oxy)

print('\n=== INJETANDO no cirurgias/index.html ===')
if abril_cir:
    injetar(os.path.join(REPO, 'cirurgias', 'index.html'), abril_cir)

print('\nFEITO. Validar visualmente nos 2 admins antes de commit.')
