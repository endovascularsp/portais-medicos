# -*- coding: utf-8 -*-
"""
_honorarios_refazer_morpheus_oxy.py — aplica a decisão do Morpheus da Oxy aos
lançamentos de Junho e Julho.

Contexto: em 11/08/2026 o Thiago decidiu que todo Morpheus da Dra. Christiane
foi feito na clínica (e todo o do Dr. Igor, no hospital). "Cirurgia - Clínica"
é sempre 80/20 — não passa pela regra de lead —, e essas 3 linhas saíram a 90%.

São 3 linhas, em 2 OS (a 14982742 é parcelada e volta em Julho):

    Junho  OS 14982742  líquido  1.925,00   90% → 80%   −192,50
    Junho  OS 15337957  líquido 12.000,00   90% → 80%  −1.200,00
    Julho  OS 14982742  líquido  1.925,00   90% → 80%   −192,50

Por que uma edição cirúrgica e não recalcular o mês inteiro pelo motor: o motor
leria os CSVs do SVN de novo e poderia mexer em linha que ninguém pediu para
mexer. Aqui o alvo é declarado, a conta é uma só, e o script confere depois de
gravar se o banco aceitou (UPDATE bloqueado por RLS não dá erro — só não grava).

Depois deste script:
    python _tools/_honorarios_publicar.py --periodo 2026-06 --validar
    python _tools/_honorarios_publicar.py --periodo 2026-07 --validar
    (e de novo com --escrever)

Uso:
    python _tools/_honorarios_refazer_morpheus_oxy.py
    python _tools/_honorarios_refazer_morpheus_oxy.py --aplicar
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as db

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUEM = "thiago.luiz@endovascularsp.com.br"
CAT_NOVA = "Cirurgia - Clínica"
PCT_NOVO = 0.8
REGRA = "R2 cirurgia em clínica particular"
OBS = ("Recalculado em 11/08/2026: o Morpheus da Dra. Christiane foi feito na "
       "clínica, não no hospital. Cirurgia - Clínica é sempre 80/20 e não passa "
       "pela regra de lead — a linha saía a 90%. Decisão do Thiago, registrada "
       "em honorarios_categoria_os para as OS 14982742 e 15337957.")


def alvos():
    return [x for x in db.buscar("honorarios_lancamentos")
            if str(x.get("procedimento") or "").strip().lower() == "morpheus"
            and x.get("empresa") == "Oxy Recovery"
            and x.get("periodo_id") in ("2026-06", "2026-07")]


def novos_valores(x):
    liq = float(x.get("valor_liquido") or 0)
    prof = round(liq * PCT_NOVO, 4)
    # A clínica fica com o que sobra do líquido; o indicador não entra nesta regra.
    clin = round(liq - prof - float(x.get("repasse_indicador") or 0), 4)
    return prof, clin


def main():
    aplicar = "--aplicar" in sys.argv
    linhas = alvos()
    print(f"{len(linhas)} lançamento(s) alvo\n")

    dif_total = 0.0
    for x in sorted(linhas, key=lambda y: (y["periodo_id"], y["os_numero"])):
        prof, clin = novos_valores(x)
        antes = float(x.get("repasse_profissional") or 0)
        dif_total += prof - antes
        print(f"  {x['periodo_id']} | OS {x['os_numero']} | {x.get('paciente')}")
        print(f"     categoria {x.get('categoria')} -> {CAT_NOVA}")
        print(f"     pct {x.get('pct_aplicado')} -> {PCT_NOVO}")
        print(f"     repasse profissional {antes:,.2f} -> {prof:,.2f}   ({prof-antes:+,.2f})")
        print(f"     repasse clínica {float(x.get('repasse_clinica') or 0):,.2f} -> {clin:,.2f}")
    print(f"\n  Efeito total no repasse da profissional: R$ {dif_total:,.2f}")

    if not aplicar:
        print("\n(nada gravado — rode com --aplicar)")
        return

    for x in linhas:
        prof, clin = novos_valores(x)
        db.atualizar("honorarios_lancamentos", x["id"], {
            "categoria": CAT_NOVA,
            "pct_aplicado": PCT_NOVO,
            "repasse_profissional": prof,
            "repasse_clinica": clin,
            "regra_aplicada": REGRA,
            "observacao": OBS,
            "revisado_em": "2026-08-11",
            "revisado_por": QUEM,
        })

    # Conferência: no Supabase, UPDATE barrado por RLS não levanta erro — só não
    # grava. Sem esta releitura, "deu certo" seria chute.
    print("\nConferindo o que ficou gravado:")
    ok = True
    for x in sorted(alvos(), key=lambda y: (y["periodo_id"], y["os_numero"])):
        esperado, _ = novos_valores(x)
        bateu = (x.get("categoria") == CAT_NOVA
                 and abs(float(x.get("repasse_profissional") or 0) - esperado) < 0.005
                 and abs(float(x.get("pct_aplicado") or 0) - PCT_NOVO) < 1e-9)
        ok = ok and bateu
        print(f"  {'OK ' if bateu else 'NAO'} {x['periodo_id']} OS {x['os_numero']}: "
              f"{x.get('categoria')} | pct {x.get('pct_aplicado')} | "
              f"repasse {float(x.get('repasse_profissional') or 0):,.2f}")
    print("\nGravado." if ok else "\nATENÇÃO: alguma linha não persistiu — ver policy de escrita.")


if __name__ == "__main__":
    main()
