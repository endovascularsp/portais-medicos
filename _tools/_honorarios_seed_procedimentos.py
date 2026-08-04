# -*- coding: utf-8 -*-
"""
_honorarios_seed_procedimentos.py — gera o seed da tabela `honorarios_procedimentos`
a partir da aba "Apoio" do Excel de fechamento (o VLOOKUP que traduz
procedimento -> categoria).

Normaliza as duas grafias que o Excel tratava como categorias diferentes:
  "Exames de Imagem"    -> "Exames de imagem"
  "Medicação Injetável" -> "Medicação injetável"

Uso:
    python _tools/_honorarios_seed_procedimentos.py --dry-run
    python _tools/_honorarios_seed_procedimentos.py
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_catalogo as C  # noqa: E402

SAIDA = Path(__file__).resolve().parent.parent / "db" / "seed_010_procedimentos.sql"
SAIDA_NOVOS = Path(__file__).resolve().parent.parent / "db" / "seed_011_procedimentos_novos.sql"


def lit(v) -> str:
    return "'" + str(v).strip().replace("'", "''") + "'"


def bloco(itens, titulo, origem="apoio_excel"):
    vals = ",\n  ".join(f"({lit(k)}, {lit(p)}, {lit(c)}, {lit(origem)})" for k, p, c in itens)
    return (f"{titulo}\n\n"
            "INSERT INTO public.honorarios_procedimentos (chave, procedimento, categoria, origem) VALUES\n"
            f"  {vals}\n"
            "ON CONFLICT (chave) DO UPDATE SET categoria = EXCLUDED.categoria;\n\n"
            "-- Conferência:\n"
            "-- SELECT categoria, count(*) FROM public.honorarios_procedimentos\n"
            "--  GROUP BY categoria ORDER BY categoria;\n")


def main(dry_run: bool):
    itens = C.itens()
    novos = [(C.chave(p), p, C.CANONICA.get(C.chave(c), c)) for p, c in C.EXTRAS.items()]

    print(f"Procedimentos no catálogo .: {len(itens)}")
    print(f"  vindos da aba Apoio .....: {len(itens) - len(novos)}")
    print(f"  classificados na fila ...: {len(novos)}")
    print(f"Categorias ................: {len(set(c for _, _, c in itens))}")
    for c in sorted(set(c for _, _, c in itens)):
        n = sum(1 for _, _, x in itens if x == c)
        print(f"    {c:24s} {n:4d}")
    if novos:
        print("\n  --- classificados ao resolver a fila ---")
        for _, p, c in novos:
            print(f"    {p[:62]:62s} -> {c}")

    if dry_run:
        print("\n[dry-run] nada foi escrito.")
        return

    SAIDA.write_text(bloco(
        itens,
        '-- Seed 010: catálogo completo de procedimentos (aba "Apoio" do Excel + classificados na fila)\n'
        "-- Gerado por _tools/_honorarios_seed_procedimentos.py. Rodar DEPOIS de migration_010.\n"
        "-- Reexecutável: ON CONFLICT pela chave normalizada."), encoding="utf-8")
    print(f"\nGerado: {SAIDA.name}  ({SAIDA.stat().st_size/1024:.0f} KB, {len(itens)} procedimentos)")

    if novos:
        SAIDA_NOVOS.write_text(bloco(
            novos,
            "-- Seed 011: procedimentos classificados pelo Thiago ao resolver a fila de Julho/2026.\n"
            "-- Incremental — só os novos. Quem já rodou o seed_010 antes precisa só deste.",
            origem="fila"), encoding="utf-8")
        print(f"Gerado: {SAIDA_NOVOS.name}  ({SAIDA_NOVOS.stat().st_size/1024:.1f} KB, {len(novos)} novos)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
