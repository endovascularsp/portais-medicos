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


def gravar_no_banco(itens, simular: bool):
    """Leva o catálogo para `honorarios_procedimentos` direto pela API.

    Antes isto gerava um .sql para o Thiago colar no Supabase. Colar SQL à mão
    era um dos passos manuais do fechamento — e o que mais convidava a erro,
    porque ninguém confere 200 linhas de INSERT.

    Mostra a diferença ANTES de gravar: é catálogo, não dinheiro, mas mudar a
    categoria de um procedimento muda o percentual de repasse dele.
    """
    import _honorarios_db as DB
    atual = {r["chave"]: r["categoria"]
             for r in DB.buscar("honorarios_procedimentos", "chave,categoria")}
    faltando = [(k, p, c) for k, p, c in itens if k not in atual]
    mudando = [(k, p, c, atual[k]) for k, p, c in itens if k in atual and atual[k] != c]
    sumindo = sorted(set(atual) - {k for k, _, _ in itens})

    print(f"\n=== Banco: {len(atual)} procedimentos · catálogo local: {len(itens)} ===")
    print(f"  a inserir ............: {len(faltando)}")
    for k, p, c in faltando:
        print(f"      + {p[:58]:60s} -> {c}")
    print(f"  a mudar de categoria ..: {len(mudando)}")
    for k, p, c, velha in mudando:
        print(f"      ~ {p[:48]:50s} {velha:22s} -> {c}")
    print(f"  só no banco (mantidos) : {len(sumindo)}")

    if not faltando and not mudando:
        print("\n  Banco já está em dia. Nada a gravar.")
        return
    if simular:
        print("\n  [simulação] nada gravado. Rode com --gravar.")
        return
    n = DB.upsert("honorarios_procedimentos",
                  [{"chave": k, "procedimento": p, "categoria": c, "origem": "fila"}
                   for k, p, c in faltando] +
                  [{"chave": k, "procedimento": p, "categoria": c, "origem": "fila"}
                   for k, p, c, _ in mudando],
                  conflito="chave")
    depois = {r["chave"] for r in DB.buscar("honorarios_procedimentos", "chave")}
    faltam = [k for k, _, _ in itens if k not in depois]
    if faltam:
        raise SystemExit(f"ABORTADO: {len(faltam)} procedimento(s) não chegaram ao banco.")
    print(f"\n  {n} registro(s) gravados · banco agora tem {len(depois)} procedimentos.")


def main(dry_run: bool, gravar: bool = False, so_banco: bool = False):
    itens = C.itens()
    novos = [(C.chave(p), p, C.CANONICA.get(C.chave(c), c)) for p, c in C.EXTRAS.items()]

    if so_banco or gravar:
        gravar_no_banco(itens, simular=not gravar)
        return

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
    ap.add_argument("--dry-run", action="store_true",
                    help="mostra o catálogo, não escreve o .sql")
    ap.add_argument("--conferir", action="store_true",
                    help="compara o catálogo local com o banco, sem gravar")
    ap.add_argument("--gravar", action="store_true",
                    help="grava o catálogo direto no Supabase (sem SQL para colar)")
    a = ap.parse_args()
    main(a.dry_run, gravar=a.gravar, so_banco=a.conferir)
