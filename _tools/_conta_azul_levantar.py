# -*- coding: utf-8 -*-
r"""
_conta_azul_levantar.py — retrato do que existe no Conta Azul, antes de construir.

A pergunta que este script responde não é "a API funciona" (funciona), é "o dado
está preenchido". O portal de custos só consegue separar despesa por ambiente
(Endovascular / Oxy / Oxy Prime) se quem lança preenche o CENTRO DE CUSTO, e só
consegue agrupar por natureza se preenche a CATEGORIA. Nada disso é obrigatório
no Conta Azul: o campo pode ficar vazio e o lançamento entra do mesmo jeito.

Então antes de desenhar tela nenhuma, medimos: de cada 100 reais que saíram, em
quantos dá para dizer de que ambiente saíram. Se a resposta for baixa, o
caminho não é técnico — é combinar o preenchimento com quem lança.

Uso:
    python _tools/_conta_azul_levantar.py                    # ano corrente
    python _tools/_conta_azul_levantar.py --de 2026-01-01 --ate 2026-07-31
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import urllib.error
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _conta_azul_api import get                                   # noqa: E402

PAGAR = "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
RECEBER = "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"
SAIDA = Path(__file__).resolve().parent.parent / "_saida" / "conta_azul_levantamento.json"


def paginar(caminho: str, de: str, ate: str) -> list:
    """Puxa mês a mês. A busca aceita intervalo livre, mas fatiar por mês evita
    página gigante e deixa o progresso visível em vez de um silêncio de minutos."""
    tudo, pagina = [], 1
    while True:
        r = get(caminho, data_vencimento_de=de, data_vencimento_ate=ate,
                pagina=pagina, tamanho_pagina=100)
        itens = r.get("itens", []) if isinstance(r, dict) else []
        tudo += itens
        if len(itens) < 100:
            break
        pagina += 1
        if pagina > 60:                        # trava de segurança contra laço infinito
            print("    AVISO: parei na página 60 — o intervalo pode estar truncado.")
            break
    return tudo


def meses(de: str, ate: str):
    a, m = int(de[:4]), int(de[5:7])
    fim = (int(ate[:4]), int(ate[5:7]))
    while (a, m) <= fim:
        ultimo = 31
        while True:
            try:
                date(a, m, ultimo); break
            except ValueError:
                ultimo -= 1
        yield f"{a}-{m:02d}-01", f"{a}-{m:02d}-{ultimo:02d}"
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)


def um_nome(lista, campo="nome"):
    """centros_de_custo e categorias vêm como lista (um lançamento pode ser
    rateado). Para o retrato basta saber se está vazio e quem é o principal."""
    if not lista:
        return None
    p = lista[0]
    return p.get(campo) or p.get("descricao") or str(p)[:40]


def retratar(nome, itens):
    total = sum(float(i.get("total") or 0) for i in itens)
    sem_cc = [i for i in itens if not i.get("centros_de_custo")]
    sem_cat = [i for i in itens if not i.get("categorias")]
    v_sem_cc = sum(float(i.get("total") or 0) for i in sem_cc)
    v_sem_cat = sum(float(i.get("total") or 0) for i in sem_cat)
    print(f"\n{'='*70}\n{nome}: {len(itens)} lançamentos, R$ {total:,.2f}"
          .replace(",", "@").replace(".", ",").replace("@", "."))
    def linha(rot, qtd, val):
        pq = 100 * qtd / len(itens) if itens else 0
        pv = 100 * val / total if total else 0
        print(f"  {rot:34} {qtd:5} ({pq:5.1f}%)   R$ {val:14,.2f} ({pv:5.1f}%)"
              .replace(",", "@").replace(".", ",").replace("@", "."))
    linha("SEM centro de custo", len(sem_cc), v_sem_cc)
    linha("SEM categoria", len(sem_cat), v_sem_cat)

    por_cc = defaultdict(float)
    for i in itens:
        por_cc[um_nome(i.get("centros_de_custo")) or "(em branco)"] += float(i.get("total") or 0)
    print("\n  por centro de custo:")
    for k, v in sorted(por_cc.items(), key=lambda kv: -kv[1])[:14]:
        print(f"    {k[:44]:46} R$ {v:14,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))

    por_cat = defaultdict(float)
    for i in itens:
        por_cat[um_nome(i.get("categorias")) or "(em branco)"] += float(i.get("total") or 0)
    print(f"\n  categorias distintas: {len(por_cat)}  — as 12 maiores:")
    for k, v in sorted(por_cat.items(), key=lambda kv: -kv[1])[:12]:
        print(f"    {k[:44]:46} R$ {v:14,.2f}".replace(",", "@").replace(".", ",").replace("@", "."))
    return {"qtd": len(itens), "total": round(total, 2),
            "sem_centro_custo": len(sem_cc), "sem_categoria": len(sem_cat),
            "por_centro_custo": {k: round(v, 2) for k, v in por_cc.items()},
            "por_categoria": {k: round(v, 2) for k, v in por_cat.items()}}


def main() -> int:
    hoje = date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", default=f"{hoje.year}-01-01")
    ap.add_argument("--ate", default=hoje.isoformat())
    a = ap.parse_args()

    resultado = {"periodo": [a.de, a.ate]}
    for nome, cam in (("CONTAS A PAGAR", PAGAR), ("CONTAS A RECEBER", RECEBER)):
        itens = []
        for d, t in meses(a.de, a.ate):
            try:
                p = paginar(cam, d, min(t, a.ate))
            except urllib.error.HTTPError as e:
                print(f"  {d[:7]}: ERRO {e.code}")
                continue
            itens += p
            print(f"  {nome[9:].lower()} {d[:7]}: {len(p)}")
        resultado[nome] = retratar(nome, itens)

    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGRAVADO: {SAIDA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
