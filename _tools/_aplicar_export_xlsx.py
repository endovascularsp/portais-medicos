# -*- coding: utf-8 -*-
"""
Troca o export de honorários dos portais individuais: em vez de um CSV com
blocos empilhados (RESUMO / ORIGEM / ATENDIMENTOS), passa a gerar um .xlsx
real — tabela plana, uma linha por atendimento, colunas da Base Compensação.

O bloco JS injetado vive em _tools/_xlsx_export_bloco.js (fonte única).
Rodar da raiz do repo:
    python _tools/_aplicar_export_xlsx.py            # aplica onde ainda nao tem
    python _tools/_aplicar_export_xlsx.py --resync   # re-injeta o bloco onde ja tem
    python _tools/_aplicar_export_xlsx.py --dry-run  # só mostra o que mudaria
    python _tools/_aplicar_export_xlsx.py Simone_Matsuda_Torricelli.html

Depois de mexer em _xlsx_export_bloco.js, rodar SEMPRE com --resync — senao os
portais ficam com a versao antiga do bloco.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BLOCO = (RAIZ / "_tools" / "_xlsx_export_bloco.js").read_text(encoding="utf-8").strip()

MARCA = "XLSX-EXPORT-BLOCO-INICIO"
RE_FUNC = re.compile(r"function exportarCSVProf\(\)\{.*?\r?\n\}\r?\n", re.S)
# Bloco ja injetado, para re-sincronizar quando _xlsx_export_bloco.js muda.
RE_BLOCO = re.compile(r"/\* ══ XLSX-EXPORT-BLOCO-INICIO.*?XLSX-EXPORT-BLOCO-FIM ═+ \*/", re.S)

# Rótulos de botão: o arquivo deixa de ser CSV.
ROTULOS = [
    ("title='Exportar CSV do período'>⬇ CSV<", "title='Exportar planilha Excel do período'>⬇ Excel<"),
    ("&#11123; Exportar CSV<", "&#11123; Exportar Excel<"),
]

# No modo range (multi-mês) o agregado zera mes/ano; carimba cada atendimento
# com o mês/ano de origem para as colunas Mês/Ano saírem corretas.
RANGE_DE = "(p.atendimentos||[]).forEach(a => agg.atendimentos.push(a));"
RANGE_PARA = (
    "(p.atendimentos||[]).forEach(a => agg.atendimentos.push("
    "Object.assign({}, a, {_mes: p.mes, _ano: p.ano})));"
)


def alvos():
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        return [RAIZ / a for a in sys.argv[1:]]
    return sorted(
        p for p in RAIZ.rglob("*.html")
        if ".git" not in p.parts and "exportarCSVProf" in p.read_text(encoding="utf-8", errors="ignore")
    )


def main():
    dry = "--dry-run" in sys.argv
    resync = "--resync" in sys.argv
    ok = pulados = 0
    for caminho in alvos():
        src = caminho.read_text(encoding="utf-8")
        rel = caminho.relative_to(RAIZ)

        # Casa a quebra de linha do arquivo para não misturar CRLF/LF.
        nl = "\r\n" if "\r\n" in src[:5000] else "\n"
        bloco = BLOCO.replace("\r\n", "\n").replace("\n", nl)

        if MARCA in src:
            if not resync:
                print(f"  =  {rel} (ja aplicado)")
                pulados += 1
                continue
            novo, n = RE_BLOCO.subn(lambda _: bloco, src)
            if n != 1:
                print(f"  !  {rel} - esperava 1 bloco, achou {n}")
                pulados += 1
                continue
            acao = "resync"
        else:
            m = RE_FUNC.search(src)
            if not m:
                print(f"  !  {rel} - exportarCSVProf() nao encontrada no formato esperado")
                pulados += 1
                continue
            novo = src[: m.start()] + bloco + nl + src[m.end():]
            acao = "novo"

        for de, para in ROTULOS:
            novo = novo.replace(de, para)
        novo = novo.replace(RANGE_DE, RANGE_PARA)

        if novo == src:
            print(f"  =  {rel} (ja atualizado)")
            pulados += 1
            continue

        if not dry:
            caminho.write_text(novo, encoding="utf-8", newline="")
        print(f"  OK {rel} [{acao}]")
        ok += 1

    print(f"\n{ok} portal(is) atualizado(s), {pulados} pulado(s){' (dry-run)' if dry else ''}")


if __name__ == "__main__":
    main()
