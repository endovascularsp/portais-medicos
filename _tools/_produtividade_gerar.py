# -*- coding: utf-8 -*-
"""
_produtividade_gerar.py — monta a Produtividade a partir do relatório #560 do SVN.

Substitui o `gerar_pdata_prod_*.py`, que lia o relatório #66 (Fechamento de caixa).
Decisão do Thiago em 05/08/2026, depois da tabela de impacto: +1,3% na
Endovascular e +23,2% na Oxy — sendo que os 23% são a correção da Juliana, que
sumiu do painel a partir de abril por causa de um cadastro duplicado no SVN.

O QUE MUDA EM RELAÇÃO AO #66
  - mede TRABALHO FEITO (valor do procedimento), não dinheiro que entrou no caixa;
  - a venda conta no mês em que foi feita, não pingando pelas parcelas;
  - cada atendimento passa a ter CATEGORIA e TABELA DE PREÇO, que o #66 não tinha;
  - o profissional vem de campo próprio, e não do primeiro nome de uma lista
    separada por vírgula.

COMO O VALOR DO TRABALHO É CONTADO
O #560 traz uma linha por procedimento × parcela, e o valor do procedimento
repete em todas. Para contar uma vez:

    ocorrências = nº de linhas do grupo ÷ nº de parcelas distintas (titu_id)

Verificado em 3.027 grupos de Jan a Jul: razão inteira em 3.026. A exceção é uma
só, em março.

ATENDIMENTO é a OS, nunca a linha — contar linha triplicaria o número.

Uso:
    python _tools/_produtividade_gerar.py --instituicao endo --dry-run
    python _tools/_produtividade_gerar.py --instituicao endo --salvar
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_catalogo as CAT      # noqa: E402
import _produtividade_impacto as R      # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CACHE = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\svn_560_cache")
EMPRESA = {"endo": "Endovascular SP", "oxy": "Oxy Recovery", "cir": "Cirurgias"}

# Cirurgias não é empresa no SVN — é um recorte por CATEGORIA de dentro da
# Endovascular, igual ao que o Recebimento sempre fez. Por isso 'endo' e 'cir'
# leem o MESMO arquivo do cache e se dividem pela categoria do procedimento.
# (Pedido do Thiago em 14/08/2026: Produtividade com os 3 ambientes do
# Recebimento. Só ficou possível quando a Produtividade passou a ler o #560,
# que traz categoria — o relatório antigo não tinha.)
FONTE = {"endo": "endo", "oxy": "oxy", "cir": "endo"}


def eh_cirurgia(categoria) -> bool:
    return "cirurgia" in str(categoria or "").lower()


def aceita(inst: str, categoria) -> bool:
    """A divisão é por PROCEDIMENTO, não por OS: das 1.830 OS da Endovascular,
    12 misturam cirurgia e não-cirurgia e aparecem nos dois ambientes, cada uma
    com os procedimentos que são dela. É como o Recebimento faz — lá a linha é
    procedimento × parcela — e é o que faz os dois portais fecharem entre si."""
    if inst == "cir":
        return eh_cirurgia(categoria)
    if inst == "endo":
        return not eh_cirurgia(categoria)
    return True

MESES = {"01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
         "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
         "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"}


def f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def data_br(v) -> str:
    s = str(v or "")[:10]
    if "/" in s:
        return s
    p = s.split("-")
    return f"{p[2]}/{p[1]}/{p[0]}" if len(p) == 3 else s


def data_iso(v) -> str:
    s = str(v or "")[:10]
    if "-" in s:
        return s
    p = s.split("/")
    return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else s


def montar(inst: str, catalogo: dict) -> dict:
    """{profissional: {periodo: {label, total, n_atend, n_pacientes,
                                 por_pagamento, por_categoria, por_tabela,
                                 atendimentos}}}"""
    saida: dict = defaultdict(dict)
    for arq in sorted(CACHE.glob(f"560_{FONTE[inst]}_*_baix_dt_pagamento.json")):
        pid = arq.name.split("_")[2]
        linhas = json.loads(arq.read_text(encoding="utf-8"))

        # 1) agrupa por (dono, OS, procedimento, valor) para descobrir quantas
        #    vezes cada procedimento aconteceu — o valor repete por parcela.
        grupos: dict = defaultdict(lambda: {"n": 0, "titus": set(), "amostra": None})
        for r in linhas:
            d = R.dono(r.get("nome_profissional"), r.get("nome_profissional_solicitante"))
            if not d:
                continue
            k = (d, str(r.get("orca_id")), str(r.get("proc_tx_nome")), f(r.get("valor_total_proc")))
            g = grupos[k]
            g["n"] += 1
            g["titus"].add(str(r.get("titu_id")))
            g["amostra"] = r

        # 2) monta os atendimentos, um por OS
        por_os: dict = defaultdict(lambda: {"procedimentos": [], "valor": 0.0})
        for (dono, os_id, proc, valor), g in grupos.items():
            oc = max(1, round(g["n"] / max(1, len(g["titus"]))))
            r = g["amostra"]
            cat, _ = CAT.categoria_de(proc, os_id, catalogo)
            # Filtrar ANTES de tocar em `por_os`: é defaultdict, e só de ler a
            # chave a OS já nasceria vazia no ambiente errado, contando como
            # atendimento sem nenhum procedimento dentro.
            if not aceita(inst, cat):
                continue
            a = por_os[(dono, os_id)]
            a["procedimentos"].append({
                "nome": proc, "qtd": oc, "valor": round(valor * oc, 2),
                "categoria": cat or "",           # vazio = precisa classificar
                "tabela": str(r.get("tpre_tx_descricao") or ""),
            })
            a["valor"] += valor * oc
            a.setdefault("paciente", str(r.get("nome_cliente") or ""))
            a.setdefault("data", data_br(r.get("baix_dt_pagamento")))
            a.setdefault("data_iso", data_iso(r.get("baix_dt_pagamento")))
            a.setdefault("pagamento", str(r.get("tipa_tx_descricao") or ""))
            a.setdefault("tabela", str(r.get("tpre_tx_descricao") or ""))
            a.setdefault("os", os_id)
            a["parcelas"] = max(a.get("parcelas", 1), len(g["titus"]))

        # 3) resumo por profissional
        por_prof: dict = defaultdict(list)
        for (dono, os_id), a in por_os.items():
            a["valor"] = round(a["valor"], 2)
            a["procedimentos"].sort(key=lambda p: -p["valor"])
            por_prof[dono].append(a)

        for dono, atends in por_prof.items():
            atends.sort(key=lambda a: a.get("data_iso") or "")
            pag: dict = defaultdict(lambda: {"valor": 0.0, "qtd": 0})
            cat_: dict = defaultdict(lambda: {"valor": 0.0, "qtd": 0})
            tab_: dict = defaultdict(lambda: {"valor": 0.0, "qtd": 0})
            for a in atends:
                p = a.get("pagamento") or "Outros"
                pag[p]["valor"] += a["valor"]
                pag[p]["qtd"] += 1
                for pr in a["procedimentos"]:
                    c = pr["categoria"] or "(sem categoria)"
                    cat_[c]["valor"] += pr["valor"]
                    cat_[c]["qtd"] += pr["qtd"]
                    t = pr["tabela"] or "(sem tabela)"
                    tab_[t]["valor"] += pr["valor"]
                    tab_[t]["qtd"] += pr["qtd"]
            saida[dono][pid] = {
                "label": f"{MESES[pid[5:7]]}/{pid[:4]}",
                "total": round(sum(a["valor"] for a in atends), 2),
                "n_atend": len(atends),
                "n_pacientes": len({a["paciente"] for a in atends}),
                "por_pagamento": {k: {"valor": round(v["valor"], 2), "qtd": v["qtd"]}
                                  for k, v in sorted(pag.items())},
                "por_categoria": {k: {"valor": round(v["valor"], 2), "qtd": v["qtd"]}
                                  for k, v in sorted(cat_.items())},
                "por_tabela": {k: {"valor": round(v["valor"], 2), "qtd": v["qtd"]}
                               for k, v in sorted(tab_.items())},
                "atendimentos": atends,
            }
    return dict(saida)


def main(inst: str, salvar: bool):
    catalogo = CAT.carregar()
    dados = montar(inst, catalogo)
    print(f"=== Produtividade · {EMPRESA[inst]} · gerada do #560 ===")
    print(f"  catálogo: {len(catalogo)} procedimentos")
    periodos = sorted({p for v in dados.values() for p in v})
    print(f"  {len(dados)} profissionais · períodos {periodos}\n")

    print(f"  {'mês':10s} {'atend':>6s} {'pacientes':>10s} {'total':>15s} {'s/ categoria':>14s}")
    for pid in periodos:
        at = sum(v[pid]["n_atend"] for v in dados.values() if pid in v)
        pa = sum(v[pid]["n_pacientes"] for v in dados.values() if pid in v)
        tt = sum(v[pid]["total"] for v in dados.values() if pid in v)
        sc = sum(v[pid]["por_categoria"].get("(sem categoria)", {}).get("valor", 0)
                 for v in dados.values() if pid in v)
        print(f"  {pid:10s} {at:6d} {pa:10d} {tt:15,.2f} {sc:14,.2f}")

    faltando: dict = defaultdict(float)
    for v in dados.values():
        for p in v.values():
            for a in p["atendimentos"]:
                for pr in a["procedimentos"]:
                    if not pr["categoria"]:
                        faltando[pr["nome"]] += pr["valor"]
    if faltando:
        print(f"\n  procedimentos SEM categoria ({len(faltando)}):")
        for nome, v in sorted(faltando.items(), key=lambda x: -x[1])[:15]:
            print(f"     R$ {v:>10,.2f}  {nome[:70]}")

    if salvar:
        destino = REPO / "db" / f"produtividade_{inst}.json"
        destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        print(f"\n  salvo: {destino.relative_to(REPO)} ({destino.stat().st_size/1024:.0f} KB)")
    else:
        print("\n  [dry-run] nada salvo.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--instituicao", default="endo", choices=list(EMPRESA))
    ap.add_argument("--salvar", action="store_true")
    a = ap.parse_args()
    main(a.instituicao, a.salvar)
