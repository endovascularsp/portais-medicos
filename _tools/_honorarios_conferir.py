# -*- coding: utf-8 -*-
"""
_honorarios_conferir.py — confere a carga de um período SEM comparar com o Excel.

O Excel não é padrão-ouro: o próprio histórico tem meses inteiros com percentual
errado, imposto lançado sobre dinheiro não recebido e categorias que escaparam de
filtro. Então a conferência aqui é por INVARIANTE — coisas que têm que ser
verdade pela própria aritmética, independente de qualquer referência externa.

Uso:
    python _tools/_honorarios_conferir.py db/carga_2026_07_honorarios.sql
"""
from __future__ import annotations
import re
import sys
from collections import Counter
from pathlib import Path

TOL = 0.01   # tolerância em reais


def split_top(s: str) -> list:
    out, buf, ins, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if ins:
            if c == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    buf.append("''"); i += 2; continue
                ins = False
            buf.append(c)
        else:
            if c == "'":
                ins = True; buf.append(c)
            elif c == ",":
                out.append("".join(buf).strip()); buf = []
            else:
                buf.append(c)
        i += 1
    out.append("".join(buf).strip())
    return out


def val(x):
    x = x.strip()
    if x == "NULL":
        return None
    if x in ("true", "false"):
        return x == "true"
    if x.startswith("'"):
        return x[1:-1].replace("''", "'")
    try:
        return float(x)
    except ValueError:
        return x


def carregar(caminho):
    sql = Path(caminho).read_text(encoding="utf-8")
    m = re.search(r"INSERT INTO public\.honorarios_lancamentos \(([^)]+)\) VALUES\n(.*?)\nON CONFLICT",
                  sql, re.S)
    cols = [c.strip() for c in m.group(1).split(",")]
    linhas = []
    for t in re.findall(r"^\s{2}\((.*)\)[,]?$", m.group(2), re.M):
        v = split_top(t)
        linhas.append(dict(zip(cols, [val(x) for x in v])))
    return linhas


def main(caminho):
    L = carregar(caminho)
    print(f"Lançamentos: {len(L)}\n")
    falhas = Counter()
    exemplos = {}

    def checar(nome, cond, r):
        if not cond:
            falhas[nome] += 1
            exemplos.setdefault(nome, r)

    for r in L:
        bruto = r["valor_recebido"] or 0
        iss, tcom, tcar = r["imposto"] or 0, r["taxa_comercial"] or 0, r["taxa_cartao"] or 0
        custo, liq = r["custo"] or 0, r["valor_liquido"] or 0
        rp, ri, rc = r["repasse_profissional"] or 0, r["repasse_indicador"] or 0, r["repasse_clinica"] or 0

        # 1. Composição do líquido.
        #    Não se aplica à Regra 3A: ali a clínica não recebeu nada, o líquido é
        #    zerado de propósito e o repasse incide sobre o BRUTO.
        if not r["nf_propria"]:
            checar("líquido != recebido - iss - taxa comercial - taxa cartão - custo",
                   abs(liq - (bruto - iss - tcom - tcar - custo)) < TOL, r)

        # 2. Os três repasses têm que somar o líquido
        checar("prof + indicador + clínica != líquido",
               abs((rp + ri + rc) - liq) < TOL, r)

        # 3. Nada de líquido negativo
        checar("líquido negativo", liq >= -TOL, r)

        # 4. Regra 3A: clínica fica com 10% do BRUTO e o profissional lança o negativo
        if r["nf_propria"]:
            checar("3A: clínica != 10% do bruto", abs(rc - 0.10 * bruto) < TOL, r)
            checar("3A: profissional != -10% do bruto", abs(rp + 0.10 * bruto) < TOL, r)
            checar("3A: não deveria ter imposto", abs(iss) + abs(tcar) < TOL, r)
        else:
            # 5. ISS é sempre 18% do bruto
            checar("ISS != 18% do bruto", abs(iss - 0.18 * bruto) < TOL, r)
            # 6. Taxa comercial é 0 ou 2%
            checar("taxa comercial != 0 nem 2% do bruto",
                   abs(tcom) < TOL or abs(tcom - 0.02 * bruto) < TOL, r)
            # 7. Taxa de cartão só no crédito, e sempre 3%
            if str(r["tipo_pagamento"]).strip().lower() == "cartão de crédito":
                checar("crédito sem os 3%", abs(tcar - 0.03 * bruto) < TOL, r)
            else:
                checar("taxa de cartão fora do crédito", abs(tcar) < TOL, r)
            # 8. O repasse tem que ser o percentual aplicado sobre o líquido
            pct = r["pct_aplicado"]
            alvo = rp if r["papel"] == "executor" else ri
            checar("repasse != pct_aplicado x líquido",
                   pct is None or abs(alvo - pct * liq) < TOL, r)

        # 9. Toda linha tem que ter regra, categoria e dono
        checar("sem regra atribuída", bool(r["regra_aplicada"]), r)
        checar("sem categoria", bool(r["categoria"]), r)
        checar("sem profissional", bool(r["profissional"]), r)

    print("=" * 96)
    print("INVARIANTES")
    print("=" * 96)
    if not falhas:
        print("  Todas passaram. Nenhuma inconsistência aritmética.")
    for nome, n in falhas.most_common():
        r = exemplos[nome]
        print(f"  [{n:4d}] {nome}")
        print(f"         ex: {r['profissional']} | {r['procedimento']} | "
              f"bruto {r['valor_recebido']} | líquido {r['valor_liquido']} | {r['regra_aplicada']}")

    print("\n" + "=" * 96)
    print("DISTRIBUIÇÃO DAS REGRAS APLICADAS")
    print("=" * 96)
    for regra, n in Counter(r["regra_aplicada"] for r in L).most_common():
        tot = sum((x["repasse_profissional"] or 0) + (x["repasse_indicador"] or 0)
                  for x in L if x["regra_aplicada"] == regra)
        print(f"  {n:5d}x  R$ {tot:>13,.2f}   {regra}")

    print("\n" + "=" * 96)
    print("PERCENTUAIS EFETIVOS POR CATEGORIA (o que saiu na prática)")
    print("=" * 96)
    porcat = {}
    for r in L:
        if r["nf_propria"] or not r["pct_aplicado"]:
            continue
        porcat.setdefault((r["empresa"], r["categoria"]), Counter())[r["pct_aplicado"]] += 1
    for (emp, cat), c in sorted(porcat.items()):
        pcts = ", ".join(f"{p:.0%} ({n})" for p, n in sorted(c.items()))
        marca = "  <-- mais de um percentual" if len(c) > 1 else ""
        print(f"  {str(emp)[:12]:12s} {str(cat)[:22]:22s} {pcts}{marca}")

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "db/carga_2026_07_honorarios.sql"))
