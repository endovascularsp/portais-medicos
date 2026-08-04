# -*- coding: utf-8 -*-
"""
_honorarios_normalizar_3a.py — põe linhas de Regra 3A no formato canônico.

Regra 3A: a NF saiu na conta do profissional, ele recebeu direto e deve 10% do
BRUTO à clínica. O formato canônico é:

    imposto = 0 · taxa comercial = 0 · taxa cartão = 0 · líquido = 0
    repasse_profissional = -10% do bruto     (o que ele deve, a abater)
    repasse_clinica      = +10% do bruto

Algumas linhas vieram do Excel só com o lado da clínica lançado. Corrigir MUDA o
repasse do médico — por isso o script exige a OS explícita, nunca varre a base.

Uso:
    python _tools/_honorarios_normalizar_3a.py 15199929            # dry-run
    python _tools/_honorarios_normalizar_3a.py 15199929 --aplicar
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB  # noqa: E402

PCT_CLINICA = 0.10


def main(oss: list, aplicar: bool):
    L = DB.buscar("honorarios_lancamentos", "*")
    alvo = [l for l in L if str(l["os_numero"]).strip() in oss and l["nf_propria"]]
    if not alvo:
        raise SystemExit(f"Nenhuma linha 3A com OS em {oss}.")

    print(f"{len(alvo)} linha(s) de Regra 3A nas OS {', '.join(oss)}:\n")
    delta_prof = 0.0
    planos = []
    for l in alvo:
        b = float(l["valor_recebido"] or 0)
        novo = {"imposto": 0, "taxa_comercial": 0, "taxa_cartao": 0, "valor_liquido": 0,
                "repasse_profissional": round(-PCT_CLINICA * b, 4),
                "repasse_clinica": round(PCT_CLINICA * b, 4)}
        delta_prof += novo["repasse_profissional"] - float(l["repasse_profissional"] or 0)
        planos.append((l, novo))
        print(f"  {l['periodo_id']} · OS {l['os_numero']} · {l['profissional']}")
        print(f"     {l['paciente']} · {l['procedimento']}")
        print(f"     bruto {b:>12,.2f} · NF em {l['conta_pagamento']!r}")
        for c in ("imposto", "taxa_comercial", "taxa_cartao", "valor_liquido",
                  "repasse_profissional", "repasse_clinica"):
            de, para = float(l[c] or 0), float(novo[c])
            marca = "  <-- muda" if abs(de - para) > 0.01 else ""
            print(f"       {c:22s} {de:>12,.2f}  ->  {para:>12,.2f}{marca}")
        print()

    print(f"  EFEITO NO REPASSE DO PROFISSIONAL: {delta_prof:+,.2f}")
    if not aplicar:
        print("\n[dry-run] nada gravado. Rode com --aplicar.")
        return

    for l, novo in planos:
        novo["observacao"] = ("Regra 3A normalizada em 04/08/2026: contrapartida do "
                              "profissional não havia sido lançada; valor ainda não acertado.")
        DB.atualizar("honorarios_lancamentos", l["id"], novo)
        print(f"  OK · OS {l['os_numero']} · {l['periodo_id']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("os_numero", nargs="+")
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    main([str(x).strip() for x in a.os_numero], a.aplicar)
