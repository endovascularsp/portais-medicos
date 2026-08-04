# -*- coding: utf-8 -*-
"""
_honorarios_limpar_imposto_fantasma.py — zera ISS/taxas nas linhas de Regra 3A.

Quando a NF sai na conta do profissional, a clínica não recebe nada: não há ISS
nem taxa de cartão a deduzir, e o repasse é 10% do BRUTO. Algumas linhas do
histórico vieram do Excel com imposto lançado assim mesmo. Isso NÃO afeta repasse
(o líquido dessas linhas é zero), mas infla o imposto que o médico vê no portal e
qualquer relatório fiscal da clínica.

Só mexe em linha que satisfaça TODAS estas condições:
  - nf_propria = true
  - valor_liquido = 0
  - repasse_profissional = -10% do bruto e repasse_clinica = +10% do bruto

Ou seja: a linha já está correta no que importa, e só carrega imposto indevido.
Qualquer coisa fora disso é reportada e NÃO tocada.

Uso:
    python _tools/_honorarios_limpar_imposto_fantasma.py            # dry-run
    python _tools/_honorarios_limpar_imposto_fantasma.py --aplicar
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB  # noqa: E402

TOL = 0.01


def main(aplicar: bool):
    L = DB.buscar("honorarios_lancamentos", "*")
    alvo, recusadas = [], []
    for l in L:
        if not l["nf_propria"]:
            continue
        sujo = (float(l["imposto"] or 0) + float(l["taxa_comercial"] or 0)
                + float(l["taxa_cartao"] or 0))
        if sujo <= TOL:
            continue
        bruto = float(l["valor_recebido"] or 0)
        ok = (abs(float(l["valor_liquido"] or 0)) < TOL
              and abs(float(l["repasse_profissional"] or 0) + 0.10 * bruto) < TOL
              and abs(float(l["repasse_clinica"] or 0) - 0.10 * bruto) < TOL)
        (alvo if ok else recusadas).append(l)

    print(f"Linhas 3A com imposto/taxa indevidos: {len(alvo) + len(recusadas)}")
    print(f"  seguras para limpar .....: {len(alvo)}")
    print(f"  fora do padrão (não toco): {len(recusadas)}\n")

    total = 0.0
    for l in alvo:
        v = float(l["imposto"] or 0) + float(l["taxa_comercial"] or 0) + float(l["taxa_cartao"] or 0)
        total += v
        print(f"  {l['periodo_id']} | {str(l['profissional'])[:26]:28s} OS {str(l['os_numero']):>10s} | "
              f"bruto {float(l['valor_recebido']):>11,.2f} | zera {v:>10,.2f} | "
              f"repasse {float(l['repasse_profissional']):>10,.2f} (fica igual)")
    print(f"\n  Imposto a zerar: R$ {total:,.2f}")
    for l in recusadas:
        print(f"  [NÃO TOCADA] {l['periodo_id']} OS {l['os_numero']} — líquido "
              f"{l['valor_liquido']}, repasse {l['repasse_profissional']}")

    if not aplicar:
        print("\n[dry-run] nada foi alterado. Rode com --aplicar para gravar.")
        return

    for l in alvo:
        DB.atualizar("honorarios_lancamentos", l["id"],
                     {"imposto": 0, "taxa_comercial": 0, "taxa_cartao": 0,
                      "observacao": "ISS/taxa zerados: NF na conta do profissional, "
                                    "clínica não recebeu (limpeza 04/08/2026)"})
        print(f"  OK {l['periodo_id']} OS {l['os_numero']}")

    resto = [x for x in DB.buscar("honorarios_lancamentos", "id,imposto,taxa_comercial,taxa_cartao,nf_propria")
             if x["nf_propria"] and (float(x["imposto"] or 0) + float(x["taxa_comercial"] or 0)
                                     + float(x["taxa_cartao"] or 0)) > TOL]
    print(f"\nConferência: linhas 3A ainda com imposto = {len(resto)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    main(ap.parse_args().aplicar)
