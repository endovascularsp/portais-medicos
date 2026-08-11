# -*- coding: utf-8 -*-
"""
_plano_medsenior.py — MEDSÊNIOR passa a contar como plano de saúde.

O corte Particular x Planos nasceu com um teste só: a tabela de preço tem OMINT
ou SULAM no nome? Então é plano. MEDSÊNIOR ficava de fora e era somado como
particular — em Julho/2026, só no Dr. Igor, R$ 6.480,00 do lado errado.

É convênio (confirmado pelo Thiago em 11/08/2026), e a regra de repasse sempre
soube disso: cirurgia com OMINT, SULAMÉRICA **ou MEDSÊNIOR** paga 85%. Quem
estava errado era só a leitura da tela.

A troca vale para os DOIS portais — Recebimento e Produtividade. Corrigir só um
faria o mesmo médico ver dois percentuais diferentes de "Particular" no mesmo mês.

O `Ê` entra como `[EÊ]` porque a tabela aparece acentuada no SVN e sem acento em
publicação antiga; o `i` do final do regex já cuida de maiúscula e minúscula.

Uso:
    python _tools/_plano_medsenior.py --conferir
    python _tools/_plano_medsenior.py --aplicar
"""
from __future__ import annotations
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VELHO = "/OMINT|SULAM/i"
NOVO = "/OMINT|SULAM|MEDS[EÊ]N/i"

# O comentário do código também mentia; se a regra muda, a explicação muda junto.
TEXTOS = [
    ("// Plano é a tabela de preço que traz OMINT ou SULAM no nome; o resto é",
     "// Plano é a tabela de preço que traz OMINT, SULAM ou MEDSÊNIOR no nome; o"),
    ("// particular. É o MESMO teste do card de Recebimento, de propósito: se um dia",
     "// resto é particular. É o MESMO teste do card de Recebimento, de propósito:"),
    ("// mudar, muda nos dois, senão o médico vê dois números para a mesma coisa.",
     "// se um dia mudar, muda nos dois, senão o médico vê dois números para a\n// mesma coisa. MEDSÊNIOR entrou em 11/08/2026: é convênio, e a regra de\n// repasse sempre o tratou como plano (cirurgia com plano paga 85%)."),
]

PASTAS = [".", "cirurgias", "oxy", "produtividade", "oxy-produtividade"]


def arquivos():
    vistos = []
    for p in PASTAS:
        d = RAIZ / p
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.html")):
            vistos.append(f)
    return vistos


def main():
    aplicar = "--aplicar" in sys.argv
    if not aplicar and "--conferir" not in sys.argv:
        print(__doc__)
        return

    tocados = trocas = 0
    for f in arquivos():
        txt = f.read_text(encoding="utf-8")
        if VELHO not in txt:
            continue
        n = txt.count(VELHO)
        novo_txt = txt.replace(VELHO, NOVO)
        for de, para in TEXTOS:
            novo_txt = novo_txt.replace(de, para)
        if aplicar:
            f.write_text(novo_txt, encoding="utf-8")
        tocados += 1
        trocas += n
        print(f"  {n} troca(s)  {f.relative_to(RAIZ)}")

    print(f"\n{tocados} arquivo(s), {trocas} ocorrência(s)"
          f"{'' if aplicar else ' — nada gravado, rode com --aplicar'}.")


if __name__ == "__main__":
    main()
