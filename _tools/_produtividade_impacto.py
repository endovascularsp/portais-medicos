# -*- coding: utf-8 -*-
"""
_produtividade_impacto.py — mede o que muda se a Produtividade passar a sair do
relatório #560 (filtrado por RECEBIMENTO) em vez do #66 (fechamento de caixa).

Compara o que ESTÁ PUBLICADO hoje nos admins de Produtividade contra o que o #560
produziria, mês a mês e por profissional.

Regras de atribuição aplicadas dos dois lados (as mesmas que o Thiago validou):
  - executante em branco  -> vale o solicitante
  - "Agendamento Cirúrgico e Visita Hospitalar" -> Igor Rafael Sincos
  - internos (Juliana, Enfermagem, Paulo, Álvaro) não recebem atribuição

Contagem de atendimento: por Nº OS, nunca por linha. O #560 traz uma linha por
parcela × procedimento — contar linhas triplicaria o número.

Uso:
    python _tools/_produtividade_impacto.py
    python _tools/_produtividade_impacto.py --instituicao oxy
"""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\svn_560_cache")
PASTA = {"endo": "produtividade", "oxy": "oxy-produtividade"}

# Regras de atribuição da PRODUTIVIDADE (decisão do Thiago em 05/08/2026).
# Diferentes das dos honorários: aqui interessa quem fez o trabalho, não quem
# recebe repasse. Por isso a Juliana Olimpio ENTRA — ela executa o Fotona na Oxy,
# mesmo sem receber percentual.

# Executante que na verdade é um registro operacional: o trabalho é do SOLICITANTE.
REDIRECIONA = {"agendamento cirurgico e visita hospitalar", "enfermagem"}

# Salas cadastradas como se fossem profissionais no SVN. Não são pessoas e o
# Thiago decidiu desconsiderar em vez de redirecionar.
EXCLUIR = {"sala fotona", "sala spa",
           "paulo laredo pinto", "paulo laredo",
           "alvaro", "alvaro machado gaudencio",
           "oxy recovery", "endovascular sp", "clinica endovascular sp"}


# Mesma pessoa cadastrada com grafias diferentes no SVN. A da direita é a
# canônica — é como o painel já mostra hoje.
# A Juliana tem os dois cadastros: "Juliana Olimpio" e "Juliana Olimpio de Paula".
# O painel atual só a mostra de Jan a Mar justamente porque a grafia mudou e a
# regra de exclusão do gerador antigo passou a pegá-la. Corrigir no SVN evita
# que volte todo mês.
#
# Os casos com "Ã£"/"Ã§" são ACENTOS CORROMPIDOS no banco do SVN — texto gravado
# com codificação errada. Não é erro de leitura: se fosse, todos os nomes viriam
# quebrados, e só esses dois vêm.
CANONICO = {
    "juliana olimpio":                "Juliana Olimpio de Paula",
    "joao fukuda":                    "João Fukuda",       # cobre "JoÃ£o Fukuda"
    "dr igor rafael sincos":          "Igor Rafael Sincos",
    "igor":                           "Igor Rafael Sincos",
    "daniela":                        "Daniela Viese Roth",
    "emanoela da silva goncalves":    "Emanoela da Silva Gonçalves",
    # "GonÃ§alves" normaliza para "gonaalves", não "goncalves": o "ã" corrompido
    # vira "a" (o til é combinante e cai), mas o "§" é descartado inteiro. Cada
    # acento corrompido some de um jeito — por isso a chave literal.
    "emanoela da silva gonaalves":    "Emanoela da Silva Gonçalves",
}


def nrm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def canonico(nome: str) -> str:
    return CANONICO.get(nrm(nome), str(nome).strip())


def dono(prof, solicitante):
    """Quem fica com o atendimento. Executante em branco, operacional ou sala
    manda para o solicitante; se o solicitante também não servir, a linha sai."""
    k = nrm(prof)
    if k in EXCLUIR:
        return None
    if k and k != "nan" and k not in REDIRECIONA:
        return canonico(prof)
    ks = nrm(solicitante)
    if not ks or ks == "nan" or ks in EXCLUIR or ks in REDIRECIONA:
        return None
    return canonico(solicitante)


def json_apos(t: str, i: int) -> str:
    d, k, ins, esc = 0, i, False, False
    while k < len(t):
        c = t[k]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        else:
            if c == '"': ins = True
            elif c == "{": d += 1
            elif c == "}":
                d -= 1
                if d == 0: return t[i:k + 1]
        k += 1
    raise SystemExit("ABORTADO: JSON não balanceado.")


def publicado(inst: str) -> dict:
    """{(periodo, profissional): (n_atend, total)} — o que está no ar hoje."""
    t = (REPO / PASTA[inst] / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const DADOS\s*=\s*(\{)", t)
    dados = json.loads(json_apos(t, m.start(1)))
    out = {}
    for prof, pers in dados.items():
        for pid, v in (pers or {}).items():
            if (v or {}).get("n_atend"):
                out[(pid, prof)] = (v["n_atend"], float(v.get("total") or 0))
    return out


def do_560(inst: str) -> dict:
    """{(periodo, profissional): (n_OS, total)} — o que o #560 daria."""
    out = {}
    for arq in sorted(CACHE.glob(f"560_{inst}_*_baix_dt_pagamento.json")):
        pid = arq.name.split("_")[2]
        linhas = json.loads(arq.read_text(encoding="utf-8"))
        agg = {}
        for r in linhas:
            d = dono(r.get("nome_profissional"), r.get("nome_profissional_solicitante"))
            if not d:
                continue
            a = agg.setdefault(d, [set(), 0.0])
            a[0].add(str(r.get("orca_id")))
            try:
                a[1] += float(r.get("valor_recebido_prop") or 0)
            except (TypeError, ValueError):
                pass
        for prof, (oss, tot) in agg.items():
            out[(pid, prof)] = (len(oss), tot)
    return out


def main(inst: str, de: str | None, ate: str | None):
    pub, novo = publicado(inst), do_560(inst)
    if not novo:
        raise SystemExit(f"ABORTADO: nenhum cache do #560 para '{inst}'. Rode _svn_puxar_560.py.")
    # Comparar mês que só existe de um lado infla o total e engana. O padrão é
    # restringir ao intervalo em que os DOIS têm dado.
    if de is None:
        de = max(min(p for p, _ in pub), min(p for p, _ in novo))
    if ate is None:
        ate = min(max(p for p, _ in pub), max(p for p, _ in novo))
    pub = {k: v for k, v in pub.items() if de <= k[0] <= ate}
    novo = {k: v for k, v in novo.items() if de <= k[0] <= ate}
    print(f"(intervalo comparável: {de} a {ate})")
    periodos = sorted({p for p, _ in pub} | {p for p, _ in novo})
    profs = sorted({x for _, x in pub} | {x for _, x in novo})

    print("=" * 108)
    print(f"IMPACTO DA MIGRACAO · {PASTA[inst]} · #66 (hoje) x #560 filtrado por RECEBIMENTO")
    print("=" * 108)
    print(f"\n{'mês':10s} {'atend hoje':>11s} {'atend #560':>11s} {'R$ hoje':>15s} "
          f"{'R$ #560':>15s} {'diferença':>15s} {'%':>8s}")
    tot = [0, 0, 0.0, 0.0]
    for pid in periodos:
        a = [v for (p, _), v in pub.items() if p == pid]
        b = [v for (p, _), v in novo.items() if p == pid]
        na, va = sum(x[0] for x in a), sum(x[1] for x in a)
        nb, vb = sum(x[0] for x in b), sum(x[1] for x in b)
        tot[0] += na; tot[1] += nb; tot[2] += va; tot[3] += vb
        pct = (vb / va - 1) * 100 if va else 0
        print(f"{pid:10s} {na:11d} {nb:11d} {va:15,.2f} {vb:15,.2f} {vb - va:+15,.2f} {pct:+7.1f}%")
    pct = (tot[3] / tot[2] - 1) * 100 if tot[2] else 0
    print(f"{'TOTAL':10s} {tot[0]:11d} {tot[1]:11d} {tot[2]:15,.2f} {tot[3]:15,.2f} "
          f"{tot[3] - tot[2]:+15,.2f} {pct:+7.1f}%")

    print(f"\n{'POR PROFISSIONAL (todos os meses somados)':^108s}")
    print(f"{'profissional':34s} {'atend hoje':>11s} {'atend #560':>11s} {'R$ hoje':>14s} "
          f"{'R$ #560':>14s} {'diferença':>14s}")
    linhas = []
    for prof in profs:
        na = sum(v[0] for (_, x), v in pub.items() if x == prof)
        va = sum(v[1] for (_, x), v in pub.items() if x == prof)
        nb = sum(v[0] for (_, x), v in novo.items() if x == prof)
        vb = sum(v[1] for (_, x), v in novo.items() if x == prof)
        linhas.append((va, prof, na, nb, va, vb))
    for _, prof, na, nb, va, vb in sorted(linhas, reverse=True):
        marca = "" if abs(vb - va) < 0.02 else ("  <<< some" if vb == 0 else
                                                "  <<< novo" if va == 0 else "")
        print(f"{prof[:34]:34s} {na:11d} {nb:11d} {va:14,.2f} {vb:14,.2f} {vb - va:+14,.2f}{marca}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--instituicao", default="endo", choices=list(PASTA))
    ap.add_argument("--de")
    ap.add_argument("--ate")
    a = ap.parse_args()
    main(a.instituicao, a.de, a.ate)
