# -*- coding: utf-8 -*-
"""
_limpar_codigo_morto_admins.py — remove a cópia morta de inicializarPortalPermanente
e mudarPeriodo em oxy/index.html e cirurgias/index.html.

Os dois admins têm DUAS declarações de cada função. Em JavaScript, declarações de
função são içadas e a ÚLTIMA vence — então quem roda é a segunda. A primeira é a
versão antiga (abas de mês lado a lado, antes do menu suspenso) e nunca executa.

Ela é perigosa justamente por parecer viva: quem for editar o comportamento do
seletor de período tende a achar a primeira e mexer nela, sem efeito nenhum.

Segurança: só apaga se o bloco removido for reconhecidamente o ANTIGO (usa
'periodo-tab' e não conhece os filtros) e se sobrar exatamente uma declaração
de cada função.

Uso:
    python _tools/_limpar_codigo_morto_admins.py            # simula
    python _tools/_limpar_codigo_morto_admins.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ALVOS = ["oxy/index.html", "cirurgias/index.html"]

INI = "function inicializarPortalPermanente(){"
MUD = "function mudarPeriodo(id, updateTabs){"


def limpar(t: str) -> tuple[str, str]:
    if t.count(INI) != 2 or t.count(MUD) != 2:
        raise SystemExit(f"ABORTADO: esperava 2 declarações de cada, achei "
                         f"{t.count(INI)} e {t.count(MUD)}.")
    i = t.index(INI)
    j = t.index(MUD, i)
    if t.index(INI, i + 1) < j:
        raise SystemExit("ABORTADO: a 2ª cópia de inicializar vem antes do "
                         "mudarPeriodo da 1ª — o arquivo não está no formato esperado.")
    m = re.compile(r"\n\}\n").search(t, j)
    if not m:
        raise SystemExit("ABORTADO: não achei o fim do mudarPeriodo antigo.")
    morto = t[i:m.end()]

    # É mesmo a versão antiga?
    if "periodo-tab" not in morto:
        raise SystemExit("ABORTADO: o bloco não parece a versão antiga (sem 'periodo-tab').")
    for novo in ("_aplicarFiltros", "_atualizarSelectsFiltros", "periodo-select"):
        if novo in morto:
            raise SystemExit(f"ABORTADO: o bloco a remover conhece '{novo}' — é o vivo.")

    resto = t[:i] + t[m.end():]
    if resto.count(INI) != 1 or resto.count(MUD) != 1:
        raise SystemExit("ABORTADO: sobrou número errado de declarações.")
    # o que sobrou tem de ser a versão nova
    if "periodo-select" not in resto[resto.index(INI):resto.index(INI) + 1200]:
        raise SystemExit("ABORTADO: a cópia que sobrou não é a do menu suspenso.")
    return resto, morto


def main(escrever: bool):
    print(f"\n=== Limpeza de código morto · escrever={escrever} ===\n")
    for rel in ALVOS:
        p = REPO / rel
        bruto = p.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        t = io.open(p, encoding="utf-8").read()
        novo, morto = limpar(t)
        print(f"  {rel:22s} remove {len(morto.splitlines()):3d} linhas "
              f"({len(morto):,} chars) · sobra 1 declaração de cada")
        if escrever:
            io.open(p, "w", encoding="utf-8", newline=fim).write(novo)
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    main(ap.parse_args().escrever)
