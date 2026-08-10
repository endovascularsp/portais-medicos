# -*- coding: utf-8 -*-
"""
_honorarios_seed_categoria_os.py — leva as decisões de categoria por OS do
código para o banco, de onde o portal consegue mostrá-las e editá-las.

O QUE MUDA DE LUGAR
`OVERRIDES_POR_OS`, em _honorarios_catalogo.py: 22 decisões sobre "Laser" e
"Laser - Pacote", tomadas em 03 e 05/08/2026 cruzando cada OS com os outros
procedimentos lançados junto. O nome sozinho não decide — "Laser" tanto é Laser
Transdérmico (60%) quanto a fibra usada em cirurgia (80% ou 90%).

POR QUE MUDAR
Enquanto viviam num dicionário Python, essas decisões não apareciam em lugar
nenhum do portal. Quem quisesse conferir tinha que abrir o código, e quem
quisesse mudar precisava de alguém que soubesse editá-lo. O card de Fechamento
foi feito justamente para tirar decisão de dentro do código.

Roda uma vez, depois da migration_011. É idempotente: o índice único
(os_numero, chave) impede duplicar, e o script pula o que já está lá.

Uso:
    python _tools/_honorarios_seed_categoria_os.py            # simula
    python _tools/_honorarios_seed_categoria_os.py --gravar
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_catalogo as CAT  # noqa: E402
import _honorarios_db as DB  # noqa: E402

# Por que cada grupo foi decidido assim. Vai para a coluna `motivo` e é o que a
# tela mostra ao lado da OS — sem isso, a decisão vira um número sem defesa.
MOTIVO = {
    "Cirurgia - Hospital": "A mesma OS traz 'Endolaser Cirúrgico' ou varizes: "
                           "o laser aqui é a fibra usada na cirurgia.",
    "Laser (clínica)":     "A mesma OS traz 'Laser Transdérmico': "
                           "é laser estético feito na clínica.",
}


def contexto() -> tuple:
    """Devolve (por_os_e_procedimento, por_os).

    A grafia original some ao normalizar, e é ela que a tela mostra; paciente e
    profissional evitam que alguém precise abrir o Saudevianet só para saber de
    quem é a OS.

    O segundo índice existe porque 16 das 22 OS só aparecem em meses antigos,
    onde o mesmo laser entrou com o nome completo ("Laser Transdérmico") em vez
    de "Laser". Casar só por (OS, procedimento) deixava a tela mostrando
    "(sem contexto)" justamente onde o nome do paciente mais ajuda a conferir.
    O paciente da OS é o mesmo em qualquer linha dela.
    """
    exato, por_os = {}, {}
    for l in DB.buscar("honorarios_lancamentos", "os_numero,procedimento,paciente,profissional"):
        os_numero = str(l.get("os_numero") or "").strip()
        dados = {"procedimento": l.get("procedimento"),
                 "paciente": l.get("paciente"),
                 "profissional": l.get("profissional")}
        exato.setdefault((os_numero, CAT.chave(l.get("procedimento"))), dados)
        por_os.setdefault(os_numero, dados)
    return exato, por_os


def main(gravar: bool) -> int:
    exato, por_os = contexto()
    try:
        ja = {(str(r["os_numero"]).strip(), r["chave"])
              for r in DB.buscar("honorarios_categoria_os", "os_numero,chave")}
    except SystemExit:
        print("ABORTADO: a tabela honorarios_categoria_os não existe. "
              "Rode db/migration_011_procedimentos_revisao.sql primeiro.")
        return 1

    print(f"\n=== Categoria por OS · gravar={gravar} ===")
    print(f"    {len(CAT.OVERRIDES_POR_OS)} no código · {len(ja)} já no banco\n")

    novos = pulados = 0
    for (os_numero, k), categoria in sorted(CAT.OVERRIDES_POR_OS.items()):
        if (os_numero, k) in ja:
            pulados += 1
            continue
        # A grafia vem do casamento exato; paciente e médico podem vir do
        # casamento só por OS, que cobre os meses antigos.
        c = exato.get((os_numero, k)) or {}
        amplo = por_os.get(os_numero) or {}
        reg = {
            "os_numero": os_numero,
            "chave": k,
            "procedimento": c.get("procedimento") or k.title(),
            "categoria": categoria,
            "motivo": MOTIVO.get(categoria),
            "paciente": c.get("paciente") or amplo.get("paciente"),
            "profissional": c.get("profissional") or amplo.get("profissional"),
            "decidido_por": "thiago.luiz@endovascularsp.com.br",
        }
        print(f"  OS {os_numero} · {k:16s} -> {categoria:20s} "
              f"{(reg['paciente'] or '(sem contexto)')[:30]}")
        if gravar:
            DB.inserir("honorarios_categoria_os", reg)
        novos += 1

    print(f"\n  {novos} a inserir · {pulados} já existia(m)")
    if not gravar:
        print("\n  [simulação] nada gravado. Rode com --gravar.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gravar", action="store_true")
    raise SystemExit(main(ap.parse_args().gravar))
