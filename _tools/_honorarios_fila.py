# -*- coding: utf-8 -*-
"""
_honorarios_fila.py — a ponte entre o motor e o portal de Fechamento.

Antes, o motor listava as divergências no terminal e quem decidisse tinha que
abrir o código para registrar a classificação. Este módulo põe a fila no banco,
para o portal mostrar, e lê de volta o que foi decidido lá.

Duas direções:

    subir(periodo, excecoes)  motor -> banco : o que o motor não soube resolver
    decisoes(periodo)         banco -> motor : o que foi decidido no portal

Como cada tipo de divergência é resolvido:

  procedimento_sem_categoria  A decisão é a CATEGORIA, e ela vale para sempre:
                              o portal grava direto em honorarios_procedimentos.
                              Na rodada seguinte o catálogo já sabe, e a
                              divergência não volta.

  cirurgia_sem_origem_lead    A decisão é o PERCENTUAL (80% da clínica ou 90% do
                              médico) e vale só para aquela linha — a indicação
                              de uma cirurgia não diz nada sobre a próxima.
                              Fica em `resolucao`.

  profissional_invalido       A decisão é o DONO do atendimento, ou excluir a
                              linha do fechamento. Vale só para aquela linha.

  sem_regra                   Falta regra de repasse cadastrada para a
  divergencia_valor           categoria, ou o valor não fecha. Não se resolve por
                              clique: o portal mostra e manda falar com quem
                              cuida das regras.

A fila é reescrita a cada rodada: divergência que o motor deixou de acusar
(porque foi resolvida, ou porque a linha sumiu do SVN) é fechada sozinha, para
a fila não virar um cemitério que ninguém lê.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB       # noqa: E402
import _honorarios_regras as R    # noqa: E402

# Tipos que o portal resolve por clique. Os demais são mostrados como aviso.
RESOLVIVEIS = {"procedimento_sem_categoria", "cirurgia_sem_origem_lead",
               "profissional_invalido"}

CAMPOS = ["periodo_id", "tipo", "empresa", "os_numero", "profissional", "paciente",
          "procedimento", "categoria", "tabela", "indicacao", "valor_recebido",
          "data_compensacao", "descricao", "sugestao"]


def _chave(e: dict) -> tuple:
    """Identifica a divergência. Não usa o texto da descrição: ele muda de
    redação sem que o caso mude, e a fila encheria de duplicata."""
    return (str(e.get("tipo")), str(e.get("os_numero") or "").strip(),
            str(e.get("procedimento") or "").strip(),
            str(e.get("empresa") or ""))


def _limpo(v):
    """NaN/NaT do pandas viram null; datas viram texto ISO."""
    try:
        import pandas as pd
        if v is None:
            return None
        if isinstance(v, pd.Timestamp):
            return v.strftime("%Y-%m-%d")
        if not isinstance(v, (str, bool, list, dict)) and pd.isna(v):
            return None
        if hasattr(v, "item"):
            return v.item()
    except ImportError:
        pass
    return v


def subir(periodo: str, excecoes: list, escrever: bool = True) -> dict:
    """Põe no banco as divergências desta rodada e fecha as que sumiram.

    Devolve um resumo: {novas, mantidas, fechadas, abertas}.
    """
    atuais = DB.buscar("honorarios_excecoes", "*",
                       filtros={"periodo_id": f"eq.{periodo}"})
    por_chave = {_chave(e): e for e in atuais}
    vistas = set()
    novas = []

    for e in excecoes:
        k = _chave(e)
        vistas.add(k)
        if k in por_chave:
            continue                      # já está na fila (aberta ou resolvida)
        novas.append({c: _limpo(e.get(c)) for c in CAMPOS} | {"periodo_id": periodo})

    # Divergência que o motor não acusa mais: ou foi resolvida, ou a linha saiu
    # do SVN. Nos dois casos não deve continuar pedindo decisão.
    sumidas = [e for k, e in por_chave.items()
               if k not in vistas and e["status"] == "aberta"]

    if escrever:
        for e in novas:
            DB.inserir("honorarios_excecoes", e)
        for e in sumidas:
            DB.atualizar("honorarios_excecoes", e["id"],
                         {"status": "ignorada",
                          "resolucao": {"motivo": "não apareceu na rodada seguinte"}})

    abertas = [e for k, e in por_chave.items()
               if e["status"] == "aberta" and k in vistas] + novas
    return {"novas": len(novas), "mantidas": len(abertas) - len(novas),
            "fechadas": len(sumidas), "abertas": len(abertas)}


def decisoes(periodo: str) -> dict:
    """O que foi decidido no portal, no formato que o motor consome.

        {(os_numero, procedimento_normalizado): {"pct": .9, "profissional": "..."}}

    Só devolve as resolvidas. O catálogo não entra aqui: quando a decisão é
    categoria, o portal grava em honorarios_procedimentos e o motor a enxerga
    pelo caminho normal.
    """
    out = {}
    for e in DB.buscar("honorarios_excecoes", "*",
                       filtros={"periodo_id": f"eq.{periodo}", "status": "eq.resolvida"}):
        r = e.get("resolucao") or {}
        if not r:
            continue
        k = (str(e.get("os_numero") or "").strip(),
             R.chave(e.get("procedimento")))
        out[k] = r
    return out


def abertas(periodo: str) -> list:
    return DB.buscar("honorarios_excecoes", "*",
                     filtros={"periodo_id": f"eq.{periodo}", "status": "eq.aberta"},
                     ordem="valor_recebido.desc")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Mostra a fila de um período.")
    ap.add_argument("--periodo", required=True)
    a = ap.parse_args()
    ab = abertas(a.periodo)
    print(f"\n=== fila de {a.periodo}: {len(ab)} divergência(s) aberta(s) ===\n")
    for e in ab:
        print(f"  [{e['tipo']}] OS {e['os_numero']} · {e['paciente']}")
        print(f"      {e['procedimento']}  ·  R$ {float(e['valor_recebido'] or 0):,.2f}")
        print(f"      {e['descricao']}")
    d = decisoes(a.periodo)
    if d:
        print(f"\n  {len(d)} decisão(ões) já tomada(s) no portal.")
