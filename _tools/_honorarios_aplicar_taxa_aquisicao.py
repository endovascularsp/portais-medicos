# -*- coding: utf-8 -*-
r"""
_honorarios_aplicar_taxa_aquisicao.py — recalcula um período já fechado com as
regras novas de lead, SEM reimportar nada do Saudevianet.

Por que não usar `_honorarios_fechar.py`: ele repuxa a base do SVN e recalcula
tudo. A um dia do pagamento isso traria movimento que ninguém pediu (lançamento
novo, valor corrigido na origem). Aqui só os PERCENTUAIS mudam — a base fica
exatamente como foi conferida (27 idênticos / 0 divergentes em 17/08).

O que muda em cada linha: `pct_aplicado`, `regra_aplicada`,
`repasse_profissional`, `repasse_indicador` e `repasse_clinica`. Valor recebido,
impostos, taxas e valor líquido **não são tocados**.

Não mexe em:
  · Oxy Recovery — a Taxa de Aquisição não vale lá (decisão do Thiago)
  · linhas com percentual 0 ou negativo — profissional da casa sem repasse e
    NF própria seguem as próprias regras
  · decisão de lead tomada no portal — se alguém decidiu a mão, o motor não discute

Uso:
    python _tools/_honorarios_aplicar_taxa_aquisicao.py --periodo 2026-07
    python _tools/_honorarios_aplicar_taxa_aquisicao.py --periodo 2026-07 --escrever
"""
from __future__ import annotations
import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB       # noqa: E402
import _honorarios_regras as R    # noqa: E402


def nomes_da_casa(linhas) -> list:
    """Nomes completos (conjunto de tokens por pessoa) de quem aparece no período.
    Mesma construção do motor — sobrenome solto colide."""
    vistos, out = set(), []
    for x in linhas:
        for c in ("profissional", "solicitante"):
            toks = frozenset(t for t in R.chave(x.get(c)).split() if len(t) > 3)
            if toks and toks not in vistos:
                vistos.add(toks)
                out.append(toks)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()

    per = DB.buscar("honorarios_periodos", filtros={"periodo_id": f"eq.{a.periodo}"})
    if not per:
        raise SystemExit(f"ABORTADO: período {a.periodo} não existe.")
    congelado = per[0].get("congelado")
    print(f"período {a.periodo}: status={per[0].get('status')} congelado={congelado}")

    linhas = DB.buscar("honorarios_lancamentos", filtros={"periodo_id": f"eq.{a.periodo}"})
    print(f"{len(linhas)} lançamentos lidos")
    nomes = nomes_da_casa(linhas)

    mudancas, por_prof = [], defaultdict(lambda: [0, 0.0, 0.0])
    for x in linhas:
        p0 = x.get("pct_aplicado")
        if p0 is None or p0 <= 0:
            continue                      # 0% e NF própria não entram
        if x.get("empresa") == R.OXY:
            continue                      # Oxy está fora da regra
        cat = R.chave(x.get("categoria"))
        lado, _ = R.lado_do_lead(x.get("indicacao"), nomes, x.get("profissional"))
        if cat in ("cirurgia - clinica", "cirurgia - hospital"):
            p1, regra = R.origem_lead(x.get("indicacao"), nomes, x.get("profissional"))
        else:
            p1, sufixo = R.com_taxa_aquisicao(p0, lado, x.get("empresa"))
            regra = (x.get("regra_aplicada") or "").split(" + taxa de aquisição")[0] + sufixo
        if abs(float(p1) - float(p0)) < 1e-9:
            continue
        liq = float(x.get("valor_liquido") or 0)
        novo = round(p1 * liq, 4)
        indicador = (x.get("papel") == "indicador")
        campos = {
            "pct_aplicado": p1,
            "regra_aplicada": regra[:200],
            "repasse_profissional": 0.0 if indicador else novo,
            "repasse_indicador": novo if indicador else 0.0,
            "repasse_clinica": round(liq - novo, 4),
        }
        mudancas.append((x["id"], campos))
        d = por_prof[x.get("profissional")]
        d[0] += 1
        d[1] += float(x.get("repasse_profissional") or 0) + float(x.get("repasse_indicador") or 0)
        d[2] += novo

    print(f"\n{len(mudancas)} linhas mudam de percentual\n")
    print(f"{'PROFISSIONAL':28} {'ln':>4} {'hoje':>13} {'novo':>13} {'diferença':>13}")
    print("-" * 78)
    for k, v in sorted(por_prof.items(), key=lambda kv: kv[1][2] - kv[1][1]):
        print(f"  {str(k)[:26]:26} {v[0]:4} {v[1]:13,.2f} {v[2]:13,.2f} {v[2]-v[1]:+13,.2f}")
    t = [sum(v[i] for v in por_prof.values()) for i in (0, 1, 2)]
    print(f"  {'TOTAL':26} {int(t[0]):4} {t[1]:13,.2f} {t[2]:13,.2f} {t[2]-t[1]:+13,.2f}")
    print(f"\n  a clínica passa a reter R$ {t[1]-t[2]:,.2f} a mais")

    if not a.escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
        return 0

    # ── grava ────────────────────────────────────────────────────────────
    # NÃO é preciso descongelar. `congelado` é marcador lógico: impede o motor de
    # recalcular o mês sozinho no próximo fechamento — não bloqueia escrita. Este
    # script é uma correção deliberada e autorizada, então o mês continua
    # congelado o tempo todo, e a proteção contra recálculo automático fica de pé.
    print("\nperíodo permanece congelado — a escrita aqui é deliberada.")
    feitas = 0
    for rid, campos in mudancas:
        DB.atualizar("honorarios_lancamentos", rid, campos)
        feitas += 1
        if feitas % 50 == 0:
            print(f"  {feitas}/{len(mudancas)}")
    print(f"  {feitas}/{len(mudancas)} gravadas")
    # ── confere relendo do banco ─────────────────────────────────────────
    depois = DB.buscar("honorarios_lancamentos", filtros={"periodo_id": f"eq.{a.periodo}"},
                       select="empresa,profissional,repasse_profissional,repasse_indicador")
    tot = sum((x.get("repasse_profissional") or 0) + (x.get("repasse_indicador") or 0)
              for x in depois if x.get("empresa") != R.OXY)
    print(f"\nCONFERÊNCIA (lida do banco): repasse Endo+Cirurgias = R$ {tot:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
