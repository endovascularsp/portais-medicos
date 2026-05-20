"""Extrai dados unicos do Excel inicial e gera SQL de seed."""
import openpyxl, os, re

XLSX = 'C:/Users/thiag/Downloads/novo_relatrio_20-05-2026.xlsx'
OUT_SQL = os.path.join(os.path.dirname(__file__), '02_seed.sql')

def sanitize(s):
    """Limpa string pra usar em SQL"""
    if s is None: return None
    return str(s).strip().replace("'", "''")

wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
ws = wb['Planilha1']
rows = list(ws.iter_rows(min_row=2, values_only=True))

depts = set()
ccs = set()
metodos = set()
fornecs = set()
for r in rows:
    if r[0]: depts.add(sanitize(r[0]))
    if r[1]: ccs.add(sanitize(r[1]))
    if r[2]: metodos.add(sanitize(r[2]))
    if r[3]: fornecs.add(sanitize(r[3]))

# Normaliza nomes (capitalize basico)
fornecs_norm = sorted({f for f in fornecs if f})

sql = """-- =====================================================================
-- SEED INICIAL — Portal Compras
-- Gerado de C:/Users/thiag/Downloads/novo_relatrio_20-05-2026.xlsx
-- (261 linhas históricas do Pipefy)
-- =====================================================================

-- Departamentos (6)
INSERT INTO compras_departamentos (nome) VALUES
"""
sql += ',\n'.join(f"  ('{d}')" for d in sorted(depts)) + ';\n\n'

sql += """-- Centros de Custo (2 unidades)
INSERT INTO compras_centros_custo (codigo, nome) VALUES
"""
ccs_sorted = sorted(ccs)
sql += ',\n'.join(f"  ('{c[:3].upper()}', '{c}')" for c in ccs_sorted) + ';\n\n'

sql += """-- Métodos de Pagamento já são ENUM no schema, não precisa seed.
-- Valores aceitos: 'pix', 'boleto', 'cartao_credito', 'link_pagamento'

-- Fornecedores ({n}) - extraidos do historico
INSERT INTO compras_fornecedores (nome) VALUES
""".format(n=len(fornecs_norm))
sql += ',\n'.join(f"  ('{f}')" for f in fornecs_norm) + ';\n'

with open(OUT_SQL, 'w', encoding='utf-8', newline='') as f:
    f.write(sql)
print(f"SQL gerado: {OUT_SQL}")
print(f"  - {len(depts)} departamentos")
print(f"  - {len(ccs)} centros de custo")
print(f"  - {len(metodos)} metodos pagamento (ja em ENUM no schema)")
print(f"  - {len(fornecs_norm)} fornecedores")
