# -*- coding: utf-8 -*-
"""
_coluna_os.py — põe o número da OS como PRIMEIRA coluna da lista de
atendimentos, nos dois cards: Recebimento e Produtividade.

Pedido do Thiago em 13/08/2026: ao rolar a página e chegar na lista, a OS tem
de ser a primeira coisa que aparece — é por ela que se cruza qualquer linha com
o Saudevianet.

O dado já viaja no PDATA dos dois cards, então isto é só tela:
  - Produtividade: campo `os` em cada atendimento, cheio em TODOS os meses;
  - Recebimento:  campo `Nº OS`, que só existe de ABRIL/2026 em diante (entrou
    no gerador em 27/07 e foi backfillado até Abril). Em Janeiro–Março a
    coluna aparece com "—", de propósito: é ausência de dado, não erro.

Também tira do Recebimento os DOIS botões "Imprimir" (o do cabeçalho, ao lado do
Home, e o que fica ao lado do "Exportar Excel" na faixa do profissional). O
Excel FICA nos dois lugares — é o export em .xlsx, que ninguém encosta. A
Produtividade não tem botão de imprimir, então não é tocada por isto.

Uso:
    python _tools/_coluna_os.py --conferir
    python _tools/_coluna_os.py --piloto
    python _tools/_coluna_os.py --todos
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCA = "os-col"          # já aplicado? não repete

CSS_RECEB = (
    "<style id='coluna-os'>\n"
    ".atend-table th.os-col,.atend-table td.os-col{white-space:nowrap;width:1%;\n"
    "  font-variant-numeric:tabular-nums;color:var(--texto-secundario);}\n"
    "</style>\n"
)

CSS_PROD = (
    "<style id='coluna-os'>\n"
    ".os-col{white-space:nowrap;width:1%;font-variant-numeric:tabular-nums;color:var(--texto2);}\n"
    "</style>\n"
)

# ---------------------------------------------------------------------------
# Recebimento — individuais (raiz, cirurgias/, oxy/) e os 3 admins
# ---------------------------------------------------------------------------
# A tabela e a linha são montadas no mesmo lugar nos 39 arquivos: o template é
# um só. Quem não casar com os âncoras é PULADO e listado no fim — nunca
# remendado por aproximação.
SUB_RECEB = [
    # cabeçalho da tabela
    ("<th>Paciente</th><th>Procedimento</th><th>Categoria</th>",
     "<th class='os-col'>Nº OS</th><th>Paciente</th><th>Procedimento</th><th>Categoria</th>"),
    # linha
    ("'<td>'+(a.Paciente||'—')+'</td>",
     "'<td class=\"os-col\">'+(a['Nº OS']||'—')+'</td>'+"
     "'<td>'+(a.Paciente||'—')+'</td>"),
    # a linha de "sem atendimentos" tem de cobrir a coluna nova
    ('colspan="9"', 'colspan="10"'),
    # "Ver conta" mostrava o campo como "Nota fiscal", mas o que vem ali é a
    # conta de recebimento ("SP Itau - Endovascular"). Mesmo acerto de rótulo
    # feito no Excel exportado (_tools/_xlsx_export_bloco.js).
    ("_idItem('Nota fiscal', a.NF)", "_idItem('Conta', a.NF)"),
]

# Os dois "Imprimir" saem inteiros, com a quebra de linha, para não deixar linha
# em branco no meio do bloco. Nem todo arquivo tem os dois (os admins variam),
# por isso a ausência não invalida o arquivo — o que invalida é aparecer duas
# vezes, aí é template diferente e alguém tem de olhar.
BOTOES_IMPRIMIR = [
    "    <button class='header-action-btn' onclick='window.print()' "
    "title='Imprimir página'>🖨️ Imprimir</button>\n",
    "          <button class='btn-export' onclick='window.print()'>"
    "&#128438; Imprimir</button>\n",
]

# ---------------------------------------------------------------------------
# Produtividade — portais individuais (Endo e Oxy)
# ---------------------------------------------------------------------------
SUB_PROD_INDIV = [
    ("<th>Data</th>",
     "<th class='os-col'>OS</th>\n              <th>Data</th>"),
    ("<td style=\"white-space:nowrap;color:var(--texto2)\">${a.data||''}</td>",
     "<td class=\"os-col\">${a.os||'—'}</td>\n"
     "      <td style=\"white-space:nowrap;color:var(--texto2)\">${a.data||''}</td>"),
    # export: a OS entra como primeira coluna também no arquivo exportado
    ("const linhas = [['Data','Paciente'",
     "const linhas = [['OS','Data','Paciente'"),
    ("linhas.push([ a.data || '', a.paciente || ''",
     "linhas.push([ a.os || '', a.data || '', a.paciente || ''"),
    # a linha de TOTAL tem de andar uma casa, senão cai embaixo da coluna errada
    ("linhas.push(['', '', '', '', '', 'TOTAL'",
     "linhas.push(['', '', '', '', '', '', 'TOTAL'"),
]

# ---------------------------------------------------------------------------
# Produtividade — os 2 admins (visão geral, com filtro de profissional)
# ---------------------------------------------------------------------------
SUB_PROD_ADMIN = [
    # o campo não era copiado para a linha achatada
    ("prof:nome, data:a.data||'', data_iso:a.data_iso||'',",
     "prof:nome, os:a.os||'', data:a.data||'', data_iso:a.data_iso||'',"),
    ("const head = `<tr>${showProf?'<th>Profissional</th>':''}<th>Data</th>",
     "const head = `<tr><th class='os-col'>OS</th>"
     "${showProf?'<th>Profissional</th>':''}<th>Data</th>"),
    ("return `<tr>${showProf?`<td class='pac-prof'>${l.prof}</td>`:''}",
     "return `<tr><td class='os-col'>${l.os||'—'}</td>"
     "${showProf?`<td class='pac-prof'>${l.prof}</td>`:''}"),
    ("const head = ['Profissional','Data','Paciente'",
     "const head = ['OS','Profissional','Data','Paciente'"),
    ("_pacLast.map(l=>[l.prof,l.data,l.paciente",
     "_pacLast.map(l=>[l.os,l.prof,l.data,l.paciente"),
]


def alvos_recebimento() -> list[Path]:
    fs = sorted(RAIZ.glob("*.html")) + sorted((RAIZ / "cirurgias").glob("*.html")) \
        + sorted((RAIZ / "oxy").glob("*.html"))
    return [f for f in fs if "body-atend" in f.read_text(encoding="utf-8")]


def alvos_prod_indiv() -> list[Path]:
    return sorted((RAIZ / "produtividade").glob("*_Produtividade.html")) + \
        sorted((RAIZ / "oxy-produtividade").glob("*_Oxy_Produtividade.html"))


def alvos_prod_admin() -> list[Path]:
    return [RAIZ / "produtividade" / "index.html",
            RAIZ / "oxy-produtividade" / "index.html"]


def aplicar(caminho: Path, subs, css: str, tirar_imprimir: bool) -> tuple[bool, str]:
    """Devolve (mudou, motivo). Não grava nada aqui — só devolve o texto novo."""
    s = caminho.read_text(encoding="utf-8")
    if MARCA in s:
        return False, "já tem a coluna"
    for antes, _ in subs:
        n = s.count(antes)
        if n != 1:
            return False, f"âncora {n}x (esperado 1): {antes[:44]}…"
    novo = s
    for antes, depois in subs:
        novo = novo.replace(antes, depois, 1)
    tirados = 0
    if tirar_imprimir:
        for b in BOTOES_IMPRIMIR:
            n = novo.count(b)
            if n > 1:
                return False, "botão Imprimir aparece %dx — template diferente" % n
            if n == 1:
                novo = novo.replace(b, "", 1)
                tirados += 1
    if "</head>" not in novo:
        return False, "sem </head>"
    novo = novo.replace("</head>", css + "</head>", 1)
    caminho.write_text(novo, encoding="utf-8")
    return True, "ok" + (f" (−{tirados} Imprimir)" if tirar_imprimir else "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--conferir", action="store_true", help="só lista os alvos")
    ap.add_argument("--piloto", action="store_true", help="um arquivo de cada família")
    ap.add_argument("--todos", action="store_true", help="aplica em todos")
    a = ap.parse_args()

    familias = [
        ("Recebimento", alvos_recebimento(), SUB_RECEB, CSS_RECEB, True),
        ("Produtividade individual", alvos_prod_indiv(), SUB_PROD_INDIV, CSS_PROD, False),
        ("Produtividade admin", alvos_prod_admin(), SUB_PROD_ADMIN, CSS_PROD, False),
    ]

    if a.conferir:
        for nome, fs, _, _, _ in familias:
            print(f"\n{nome}: {len(fs)} arquivo(s)")
            for f in fs:
                print("   ", f.relative_to(RAIZ))
        return 0

    if not (a.piloto or a.todos):
        ap.print_help()
        return 1

    pilotos = {"Igor_Rafael_Sincos.html",
               "Igor_Rafael_Sincos_Produtividade.html",
               "index.html"}
    total = pulados = 0
    for nome, fs, subs, css, botao in familias:
        if a.piloto:
            fs = [f for f in fs if f.name in pilotos][:1]
        print(f"\n── {nome} ──")
        for f in fs:
            mudou, motivo = aplicar(f, subs, css, botao)
            if mudou:
                total += 1
                print("  ✓", f.relative_to(RAIZ), "—", motivo)
            else:
                pulados += 1
                print("  ⚠", f.relative_to(RAIZ), "—", motivo)
    print(f"\n{total} arquivo(s) alterado(s), {pulados} pulado(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
