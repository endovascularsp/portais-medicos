# -*- coding: utf-8 -*-
"""
_produtividade_trabalho.py — mede a Produtividade pelo VALOR DO TRABALHO feito,
não pelo dinheiro recebido.

O #560 traz, por linha, o valor do procedimento (`valor_total_proc`) além do
valor recebido. O valor do procedimento REPETE em cada parcela — somar direto
multiplica. Para contar uma vez:

    ocorrências = nº de linhas do grupo ÷ nº de parcelas distintas (titu_id)

onde o grupo é (OS, procedimento, valor). Verificado em 3.027 grupos de Jan a
Jul: a razão é inteira em 3.026 deles, o que confirma que o relatório monta uma
linha por procedimento × parcela.

Assim entram na conta os atendimentos realizados que ainda não foram pagos —
convênio faturado e não recebido, e cirurgia faturada na conta do médico.

Uso:
    python _tools/_produtividade_trabalho.py
    python _tools/_produtividade_trabalho.py --instituicao oxy --sem-excluir
"""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _produtividade_impacto as I  # noqa: E402

CACHE = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\svn_560_cache")


def f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def dono(r, sem_excluir: bool):
    """`sem_excluir` mantém até as salas, só para medir quanto elas representam."""
    if sem_excluir:
        p = str(r.get("nome_profissional") or "").strip()
        if not p or p.lower() == "nan":
            p = str(r.get("nome_profissional_solicitante") or "").strip()
        k = I.nrm(p)
        return p if k and k != "nan" else None
    return I.dono(r.get("nome_profissional"), r.get("nome_profissional_solicitante"))


def por_periodo(inst: str, sem_excluir: bool) -> dict:
    """{(periodo, prof): (n_OS, valor_recebido, valor_trabalho)}"""
    out = {}
    for arq in sorted(CACHE.glob(f"560_{inst}_*_baix_dt_pagamento.json")):
        pid = arq.name.split("_")[2]
        linhas = json.loads(arq.read_text(encoding="utf-8"))
        grupos = defaultdict(lambda: {"n": 0, "titus": set()})
        receb, oss = defaultdict(float), defaultdict(set)
        for r in linhas:
            d = dono(r, sem_excluir)
            if not d:
                continue
            receb[d] += f(r.get("valor_recebido_prop"))
            oss[d].add(str(r.get("orca_id")))
            k = (d, str(r.get("orca_id")), str(r.get("proc_tx_nome")), f(r.get("valor_total_proc")))
            grupos[k]["n"] += 1
            grupos[k]["titus"].add(str(r.get("titu_id")))
        trab = defaultdict(float)
        for (d, _os, _p, val), g in grupos.items():
            nparc = max(1, len(g["titus"]))
            trab[d] += val * max(1, round(g["n"] / nparc))
        for d in oss:
            out[(pid, d)] = (len(oss[d]), receb[d], trab[d])
    return out


def main(inst: str, sem_excluir: bool):
    pub = I.publicado(inst)
    novo = por_periodo(inst, sem_excluir)
    if not novo:
        raise SystemExit(f"ABORTADO: sem cache do #560 para '{inst}'.")
    ate = min(max(p for p, _ in pub), max(p for p, _ in novo))
    de = max(min(p for p, _ in pub), min(p for p, _ in novo))
    pub = {k: v for k, v in pub.items() if de <= k[0] <= ate}
    novo = {k: v for k, v in novo.items() if de <= k[0] <= ate}

    print("=" * 100)
    print(f"PRODUTIVIDADE POR TRABALHO FEITO · {I.PASTA[inst]} · {de} a {ate}"
          + ("  (sem excluir internos)" if sem_excluir else ""))
    print("=" * 100)
    print(f"\n{'mês':10s} {'#66 hoje':>15s} {'#560 recebido':>15s} {'#560 trabalho':>15s} "
          f"{'trab - hoje':>15s} {'%':>8s}")
    t = [0.0, 0.0, 0.0]
    for pid in sorted({p for p, _ in pub} | {p for p, _ in novo}):
        a = sum(v[1] for (p, _), v in pub.items() if p == pid)
        b = sum(v[1] for (p, _), v in novo.items() if p == pid)
        c = sum(v[2] for (p, _), v in novo.items() if p == pid)
        t[0] += a; t[1] += b; t[2] += c
        print(f"{pid:10s} {a:15,.2f} {b:15,.2f} {c:15,.2f} {c - a:+15,.2f} "
              f"{(c/a-1)*100 if a else 0:+7.1f}%")
    print(f"{'TOTAL':10s} {t[0]:15,.2f} {t[1]:15,.2f} {t[2]:15,.2f} {t[2]-t[0]:+15,.2f} "
          f"{(t[2]/t[0]-1)*100 if t[0] else 0:+7.1f}%")

    print(f"\n{'profissional':34s} {'R$ hoje':>14s} {'R$ trabalho':>14s} {'diferença':>14s}")
    linhas = []
    for prof in sorted({x for _, x in pub} | {x for _, x in novo}):
        a = sum(v[1] for (_, x), v in pub.items() if x == prof)
        c = sum(v[2] for (_, x), v in novo.items() if x == prof)
        linhas.append((a, prof, a, c))
    for _, prof, a, c in sorted(linhas, reverse=True):
        marca = "  <<< some" if a and not c else ("  <<< novo" if c and not a else "")
        print(f"{prof[:34]:34s} {a:14,.2f} {c:14,.2f} {c - a:+14,.2f}{marca}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--instituicao", default="endo", choices=list(I.PASTA))
    ap.add_argument("--sem-excluir", action="store_true",
                    help="mantém internos (Juliana, Enfermagem, Paulo, Álvaro) na conta")
    a = ap.parse_args()
    main(a.instituicao, a.sem_excluir)
