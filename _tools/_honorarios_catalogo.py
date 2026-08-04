# -*- coding: utf-8 -*-
"""
_honorarios_catalogo.py — tradução procedimento -> categoria, num lugar só.

O catálogo tem duas origens:

  1. A aba "Apoio" do Excel de fechamento (184 linhas, 177 procedimentos únicos).
     É o legado — continua sendo lida enquanto o Excel existir.

  2. EXTRAS, abaixo: procedimentos que apareceram depois e foram classificados
     pelo Thiago ao resolver a fila de exceções.

Tanto o motor quanto o gerador do seed usam esta função, para que o catálogo do
código e o do Supabase nunca divirjam.
"""
from __future__ import annotations
import unicodedata

PLANILHA = r"G:\Drives compartilhados\Endovascular SP\2. Financeiro\4. Honorários médicos\Fechamento - Endovascular SP.xlsx"

# Grafias que o Excel deixou duplicadas — a da direita é a canônica.
CANONICA = {
    "exames de imagem": "Exames de imagem",
    "medicacao injetavel": "Medicação injetável",
}

# Classificados pelo Thiago em 03/08/2026, ao resolver a fila de Julho.
EXTRAS = {
    "Cirurgia - Tenotomia":                                                   "Cirurgia - Hospital",
    "Preenchimento (Por seringa) - Tabela Diretoria":                         "Procedimentos",
    "Exossomos - Terapia Regenerativa":                                       "Procedimentos",
    "Hybrius EVO - Sessão individual (1 área)":                               "Laser (clínica)",
    "Exérese e sutura simples de pequenas lesões (por grupo de até 5 lesões)": "Procedimentos",
    "Taxa compacta de sala de pequenas cirurgias":                            "Cirurgia - Clínica",
}

# ---------------------------------------------------------------------------
# Procedimentos AMBÍGUOS — nunca entram no catálogo
# ---------------------------------------------------------------------------
# Cadastro legado: o campo Procedimento traz só "Laser", que pode ser tanto
# Laser Transdérmico (categoria "Laser (clínica)") quanto fibra de laser usada em
# cirurgia (categoria "Cirurgia - Hospital"). O NOME não permite decidir — a
# semelhança com a categoria "Laser (clínica)" é coincidência e cadastrar por ela
# jogaria linhas cirúrgicas de 80-90% para 60%, de forma silenciosa.
#
# Só o contexto da OS resolve: ver quais outros procedimentos foram lançados na
# mesma OS. Por isso ficam SEMPRE fora do catálogo e SEMPRE caem na fila.
AMBIGUOS = {"laser", "laser - pacote"}

# ---------------------------------------------------------------------------
# Resolução por linha: (Nº OS, chave do procedimento) -> categoria
# ---------------------------------------------------------------------------
# É o que a fila de exceções produz quando o nome do procedimento não basta.
# Decidido pelo Thiago em 03/08/2026, a partir do cruzamento por OS.
OVERRIDES_POR_OS = {
    # Josefa Hortencia / Manoel — a mesma OS tem 30 lançamentos de "Laser Transdérmico"
    ("13858952", "laser"):          "Laser (clínica)",
    # Convivem com "Endolaser Cirúrgico" na mesma OS -> é a fibra de laser
    ("13055855", "laser"):          "Cirurgia - Hospital",  # Karina Geraldini / Igor
    ("13647510", "laser"):          "Cirurgia - Hospital",  # Cristiane de Araújo / Igor
    ("13892404", "laser"):          "Cirurgia - Hospital",  # Laurinda Yamanishi / Manoel
    ("13225365", "laser - pacote"): "Cirurgia - Hospital",  # Débora de Mattos / Igor
}


def chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def carregar(planilha: str = PLANILHA) -> dict:
    """{chave_normalizada: categoria} — Apoio do Excel + EXTRAS."""
    import openpyxl
    cat = {}
    wb = openpyxl.load_workbook(planilha, data_only=True, read_only=True)
    for r in wb["Apoio"].iter_rows(min_row=3, max_row=500, min_col=2, max_col=3, values_only=True):
        if r[0] and r[1]:
            cat.setdefault(chave(r[0]), CANONICA.get(chave(r[1]), str(r[1]).strip()))
    wb.close()
    for proc, c in EXTRAS.items():
        cat[chave(proc)] = CANONICA.get(chave(c), c)
    return cat


def categoria_de(procedimento, os_numero, catalogo: dict):
    """(categoria, origem) — ou (None, motivo) quando precisa de decisão humana.

    Ordem: override da linha vence o catálogo; procedimento ambíguo nunca é
    resolvido pelo nome."""
    k = chave(procedimento)
    over = OVERRIDES_POR_OS.get((str(os_numero).strip(), k))
    if over:
        return over, "categoria definida por OS"
    if k in AMBIGUOS:
        return None, (f"Procedimento '{procedimento}' é ambíguo: o nome não diz a "
                      "categoria. Ver os outros procedimentos da mesma OS.")
    cat = catalogo.get(k)
    if cat:
        return cat, None
    return None, f"Procedimento '{procedimento}' não está no catálogo"


def itens(planilha: str = PLANILHA) -> list:
    """[(chave, procedimento_original, categoria)] — para gerar o seed SQL."""
    import openpyxl
    out, vistos = [], set()
    wb = openpyxl.load_workbook(planilha, data_only=True, read_only=True)
    linhas = [(r[0], r[1]) for r in wb["Apoio"].iter_rows(min_row=3, max_row=500,
                                                          min_col=2, max_col=3,
                                                          values_only=True) if r[0] and r[1]]
    wb.close()
    for proc, c in linhas + list(EXTRAS.items()):
        k = chave(proc)
        if k in vistos:
            continue
        vistos.add(k)
        out.append((k, str(proc).strip(), CANONICA.get(chave(c), str(c).strip())))
    return out
