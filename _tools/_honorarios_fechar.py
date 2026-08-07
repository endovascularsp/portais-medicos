# -*- coding: utf-8 -*-
"""
_honorarios_fechar.py — fecha um mês de honorários com um comando só.

Substitui a sequência que antes era feita à mão:

    _svn_puxar_560.py  (duas vezes, uma por instituição)
    _honorarios_motor.py
    _honorarios_sincronizar.py
    _honorarios_publicar.py

E, principalmente: quando aparece divergência, ele PARA e manda para o portal
de Fechamento. Antes isso significava abrir o código e editar um arquivo de
regras — o processo pertencia a quem programa.

    python _tools/_honorarios_fechar.py --periodo 2026-08              # simula
    python _tools/_honorarios_fechar.py --periodo 2026-08 --escrever

Sem --escrever nada é gravado nem publicado: mostra o que faria.
Com --pular-download usa o que já está no cache, sem bater no SVN de novo.
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(AQUI))

PORTAL = "https://portalendovascularsp.com.br/fechamento/"


def passo(n: int, titulo: str):
    # flush explícito: sem ele a saída do subprocesso, que escreve direto no
    # terminal, aparece ANTES dos títulos deste script — e quem está rodando
    # perde a sequência dos passos.
    print(f"\n{'─'*66}\n{n}. {titulo}\n{'─'*66}", flush=True)


def rodar(cmd: list) -> int:
    """Roda um dos tools e deixa a saída aparecer na hora."""
    sys.stdout.flush()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    return subprocess.run([sys.executable] + cmd, cwd=str(REPO), env=env).returncode


def main(periodo: str, escrever: bool, pular_download: bool) -> int:
    import _honorarios_db as DB
    import _honorarios_fila as FILA

    # O terminal do Windows abre em cp1252 e quebra em qualquer acento. Quem vai
    # rodar isto não deveria precisar saber configurar codificação de terminal.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    titulo = f"FECHAMENTO DE HONORÁRIOS · {periodo}" + ("" if escrever else "  (simulação)")
    print(f"\n╔{'═'*64}╗")
    print(f"║  {titulo:<62}║")
    print(f"╚{'═'*64}╝", flush=True)

    # ---- trava: mês congelado não se mexe -----------------------------------
    per = [p for p in DB.buscar("honorarios_periodos", "periodo_id,label,status,congelado")
           if p["periodo_id"] == periodo]
    if not per:
        print(f"\nABORTADO: o período {periodo} não existe na tabela de períodos.")
        return 1
    if per[0]["congelado"]:
        print(f"\nABORTADO: {per[0]['label']} está fechado e não aceita alteração.")
        print("  Reabrir é decisão da Gestão Administrativa.")
        return 1

    # ---- 1. buscar no SVN ---------------------------------------------------
    passo(1, "Buscar o movimento no Saudevianet")
    if pular_download:
        print("  (pulado — usando o que já está no cache)")
    else:
        for inst in ("endo", "oxy"):
            print(f"\n  · {inst}")
            rc = rodar(["_tools/_svn_puxar_560.py", "--instituicao", inst,
                        "--de", periodo, "--ate", periodo,
                        "--filtro-data", "baix_dt_recebimento"])
            if rc:
                print(f"\nABORTADO: falhou ao buscar {inst} no SVN.")
                return 1

    # ---- 2 e 3. calcular, e parar se houver divergência ---------------------
    passo(2, "Calcular o repasse e conferir as divergências")
    rc = rodar(["_tools/_honorarios_sincronizar.py", "--periodo", periodo]
               + (["--escrever"] if escrever else []))

    if rc:
        # O sincronizar devolve 1 quando há divergência aberta — que não é erro,
        # é o processo pedindo uma decisão humana.
        ab = FILA.abertas(periodo)
        if ab:
            passo(3, "Decisão necessária")
            print(f"  {len(ab)} divergência(s) esperando alguém decidir.\n")
            for e in ab[:10]:
                print(f"   · {e['paciente'] or '—'} — {e['procedimento'] or '—'}")
                print(f"     {e['descricao']}")
            if len(ab) > 10:
                print(f"   ... e mais {len(ab)-10}")
            print(f"\n  Decida no portal:  {PORTAL}")
            print(f"  Depois rode de novo:  python _tools/_honorarios_fechar.py "
                  f"--periodo {periodo} --escrever --pular-download")
        return 1

    if not escrever:
        print(f"\n{'─'*66}")
        print("  [simulação] nada foi gravado nem publicado.")
        print(f"  Para valer:  python _tools/_honorarios_fechar.py --periodo {periodo} --escrever")
        return 0

    # ---- 4. publicar --------------------------------------------------------
    passo(4, "Publicar nos portais")
    rc = rodar(["_tools/_honorarios_publicar.py", "--periodo", periodo, "--escrever"])
    if rc:
        print("\nABORTADO na publicação. O banco já está atualizado; os portais não.")
        return 1

    passo(5, "Atualizar os links dos Hubs")
    rodar(["_tools/_cache_bust_hubs.py"])

    # ---- resumo -------------------------------------------------------------
    l = DB.buscar("honorarios_lancamentos",
                  "valor_recebido,repasse_profissional,repasse_clinica,profissional",
                  filtros={"periodo_id": f"eq.{periodo}"})
    soma = lambda c: sum(float(r[c] or 0) for r in l)          # noqa: E731
    profs = {r["profissional"] for r in l if r["profissional"]}
    print(f"\n{'═'*66}")
    print(f"  {per[0]['label']} fechado")
    print(f"{'═'*66}")
    print(f"  lançamentos .........: {len(l):>14,}".replace(",", "."))
    print(f"  profissionais .......: {len(profs):>14}")
    print(f"  recebido ............: R$ {soma('valor_recebido'):>14,.2f}")
    print(f"  repasse aos médicos .: R$ {soma('repasse_profissional'):>14,.2f}")
    print(f"  receita da clínica ..: R$ {soma('repasse_clinica'):>14,.2f}")
    print(f"\n  Falta você: conferir no portal, publicar no GitHub e limpar o cache")
    print(f"  do Cloudflare. Os portais já estão escritos aqui na sua máquina.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True, help="AAAA-MM")
    ap.add_argument("--escrever", action="store_true",
                    help="grava no banco e escreve os portais")
    ap.add_argument("--pular-download", action="store_true",
                    help="usa o cache do SVN em vez de buscar de novo")
    a = ap.parse_args()
    raise SystemExit(main(a.periodo, a.escrever, a.pular_download))
