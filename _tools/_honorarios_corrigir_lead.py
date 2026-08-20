# -*- coding: utf-8 -*-
"""
_honorarios_corrigir_lead.py — devolve o repasse de lançamentos que perderam os
20 pontos da Taxa de Aquisição por uma classificação de lead que hoje se sabe
errada.

Por que existe: a regra de lead casa por PEDAÇO de texto, e dois pedaços
colidiram. "amil" (o plano) está dentro de "c-amil-o" e de "Dr Amilton" — então
"São Camilo", que é o hospital onde o médico atende, e "Dr Amilton", que é uma
pessoa, foram lidos como plano de saúde e viraram lead da clínica. Ninguém
decidiu isso; foi a letra. As regras foram corrigidas em 20/08/2026; este script
acerta o dinheiro dos meses JÁ FECHADOS, onde o motor não roda de novo.

O que ele faz, linha a linha:
  - devolve o percentual da categoria (pct + 20 pontos);
  - recalcula repasse do profissional e da clínica sobre o MESMO líquido;
  - tira o sufixo da taxa da regra aplicada;
  - marca a linha como revisão manual, para uma sincronização automática não
    apagar a decisão depois.

Não mexe em mês aberto: lá o motor recalcula sozinho no fechamento.
O período continua congelado — a escrita é por id, uma linha de cada vez.

Uso:
    python _tools/_honorarios_corrigir_lead.py --periodo 2026-07
    python _tools/_honorarios_corrigir_lead.py --periodo 2026-07 --aplicar
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB          # noqa: E402
import _honorarios_regras as R       # noqa: E402

QUEM = "thiago.luiz@endovascularsp.com.br"
DATA = "2026-08-20"
SUFIXO_TAXA = " + taxa de aquisição (−20 pts)"
OBS = ("Lead reclassificado em 20/08/2026: o texto casava com o plano Amil por "
       "conter 'amil' ('São Camilo', 'Dr Amilton'). É lead do médico — a Taxa "
       "de Aquisição foi devolvida.")


def nomes_da_casa(linhas) -> list:
    vistos, out = set(), []
    for l in linhas:
        for v in (l.get("profissional"), l.get("solicitante")):
            if not v:
                continue
            toks = frozenset(t for t in R.chave(v).split() if len(t) > 3)
            if toks and toks not in vistos:
                vistos.add(toks)
                out.append(toks)
    return out


def main(periodo: str, aplicar: bool) -> int:
    per = [p for p in DB.buscar("honorarios_periodos", "periodo_id,status,congelado")
           if p["periodo_id"] == periodo]
    if per:
        print(f"Período {periodo}: status={per[0]['status']} congelado={per[0]['congelado']}")
        if per[0]["status"] != "publicado":
            print("  (mês ainda não publicado — o motor recalcula sozinho, "
                  "este script é para mês fechado)")

    todos = DB.buscar("honorarios_lancamentos", "profissional,solicitante")
    nomes = nomes_da_casa(todos)

    cols = ("id,periodo_id,profissional,indicacao,categoria,valor_liquido,pct_aplicado,"
            "repasse_profissional,repasse_indicador,repasse_clinica,regra_aplicada")
    linhas = DB.buscar("honorarios_lancamentos", cols, {"periodo_id": f"eq.{periodo}"})

    alvos = []
    for l in linhas:
        # só quem está com a taxa aplicada E que a regra de hoje diz ser do médico
        if SUFIXO_TAXA not in (l["regra_aplicada"] or ""):
            continue
        lado, _ = R.lado_do_lead(l["indicacao"] or "", nomes, l["profissional"])
        if lado != "medico":
            continue
        pct_novo = round(float(l["pct_aplicado"]) + R.TAXA_AQUISICAO, 4)
        liq = float(l["valor_liquido"] or 0)
        rep_novo = round(pct_novo * liq, 4)
        ind = float(l["repasse_indicador"] or 0)
        alvos.append((l, pct_novo, rep_novo, round(liq - rep_novo - ind, 4)))

    if not alvos:
        print("\nNada a corrigir neste período.")
        return 0

    print(f"\n{len(alvos)} lançamento(s) a corrigir em {periodo}:\n")
    por_prof = {}
    for l, pct, rep, cli in alvos:
        d = rep - float(l["repasse_profissional"] or 0)
        por_prof[l["profissional"]] = por_prof.get(l["profissional"], 0.0) + d
        print(f"  {l['profissional'][:26]:28s} {(l['indicacao'] or '')[:18]:20s} "
              f"{(l['categoria'] or '')[:18]:20s} liq {float(l['valor_liquido']):>9,.2f}  "
              f"{float(l['pct_aplicado']):.0%} -> {pct:.0%}   repasse "
              f"{float(l['repasse_profissional']):>8,.2f} -> {rep:>8,.2f}  ({d:+,.2f})")
    print()
    for p, d in sorted(por_prof.items()):
        print(f"  TOTAL  {p[:30]:32s} {d:+,.2f}")

    if not aplicar:
        print("\n(simulação — nada gravado. Rode com --aplicar.)")
        return 0

    for l, pct, rep, cli in alvos:
        DB.atualizar("honorarios_lancamentos", l["id"], {
            "pct_aplicado": pct,
            "repasse_profissional": rep,
            "repasse_clinica": cli,
            "regra_aplicada": (l["regra_aplicada"] or "").replace(SUFIXO_TAXA, ""),
            "observacao": OBS,
            "revisado_em": DATA,
            "revisado_por": QUEM,
        })
    print(f"\nGravado: {len(alvos)} lançamento(s). "
          "Republicar o portal de cada profissional com _honorarios_republicar_ajuste.py.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.periodo, a.aplicar))
