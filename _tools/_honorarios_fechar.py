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

Sem --escrever nenhum lançamento é gravado nem publicado: mostra o que faria.
A ÚNICA exceção é a fila de divergências, que sobe para o banco de qualquer
jeito — é ela que o portal mostra, e ficar só no terminal era justamente o que
prendia a decisão a quem programa (ver _honorarios_sincronizar.py).
Com --pular-download usa o que já está no cache, sem bater no SVN de novo.

MODO SÓ BASE (--so-base), usado pela rotina automática de 13/08/2026
--------------------------------------------------------------------
Faz os passos 1 a 3 e PARA: põe o banco em dia com o Saudevianet e manda as
dúvidas para a fila do portal, sem encostar no portal de médico nenhum. É o que
roda toda madrugada e o que o botão "Atualizar base" dispara.

A separação é de propósito: mês em aberto é verdade parcial — compensação ainda
está chegando — e o médico não pode ver número mudando sozinho. Publicar
continua sendo um ato deliberado.

    python _tools/_honorarios_fechar.py --periodo auto --so-base --escrever
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
sys.path.insert(0, str(AQUI))

PORTAL = "https://portalendovascularsp.com.br/fechamento/"

MES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
          "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolver_periodo(DB, pedido: str, abrir_se_preciso: bool, escrever: bool):
    """Traduz --periodo auto para o mês que está aberto.

    Regra: aberto é o período NÃO congelado de maior id. Se não houver nenhum —
    caso do dia 1º, quando o mês novo ainda não existe — a rotina pode abrir o
    mês corrente, mas só com --abrir-se-preciso. Abrir mês não publica nada:
    é só criar a linha onde os lançamentos vão cair.
    """
    if pedido != "auto":
        return pedido, None

    ps = DB.buscar("honorarios_periodos", "periodo_id,label,congelado")
    abertos = sorted([p for p in ps if not p["congelado"]],
                     key=lambda p: p["periodo_id"])
    if abertos:
        return abertos[-1]["periodo_id"], None

    hoje = date.today()
    pid = f"{hoje.year}-{hoje.month:02d}"
    if any(p["periodo_id"] == pid for p in ps):
        return None, (f"o período {pid} existe mas está congelado, e não há "
                      "nenhum outro mês aberto — nada a atualizar.")
    if not abrir_se_preciso:
        return None, (f"nenhum mês aberto e {pid} não existe. Abra o mês no "
                      "portal, ou rode com --abrir-se-preciso.")
    if not escrever:
        print(f"  [simulação] abriria o período {pid}.")
        return pid, None

    DB.inserir("honorarios_periodos", {
        "periodo_id": pid,
        "label": f"{MES_PT[hoje.month]}/{hoje.year}",
        "status": "aberto",
        "congelado": False,
        "observacao": "Aberto pela rotina automática de atualização da base.",
    })
    print(f"  período {pid} aberto agora.")
    return pid, None


# ---------------------------------------------------------------------------
# Registro da execução — é o que a tela do portal lê para mostrar o andamento
# ---------------------------------------------------------------------------
# Nunca derruba o fechamento: se a tabela ainda não existir, avisa e segue. O
# valor está em atualizar a base, não em registrar que atualizou.
_EXEC_ATUAL = None      # para o tratador de erro lá embaixo saber o que fechar


def exec_iniciar(DB, tipo: str, periodo: str, disparado_por: str, exec_id=None):
    global _EXEC_ATUAL
    campos = {"status": "rodando", "periodo_id": periodo, "iniciado_em": _agora()}
    try:
        if exec_id:
            DB.atualizar("honorarios_execucoes", exec_id, campos)
            _EXEC_ATUAL = exec_id
            return exec_id
        r = DB.inserir("honorarios_execucoes",
                       dict(campos, tipo=tipo, disparado_por=disparado_por))
        _EXEC_ATUAL = r.get("id") if isinstance(r, dict) else None
        return _EXEC_ATUAL
    # SystemExit, e não só Exception: é assim que _honorarios_db aborta, e
    # SystemExit não descende de Exception. Sem os dois, a falta da tabela de
    # registro derrubava o fechamento inteiro — foi o que aconteceu na
    # primeira rodada de Agosto.
    except (Exception, SystemExit) as e:
        print(f"  (aviso: não consegui registrar a execução — {e})")
        return None


def exec_terminar(DB, exec_id, status: str, mensagem: str, **campos):
    if not exec_id:
        return
    try:
        DB.atualizar("honorarios_execucoes", exec_id,
                     dict(campos, status=status, mensagem=mensagem[:2000],
                          terminado_em=_agora()))
    except (Exception, SystemExit) as e:
        print(f"  (aviso: não consegui fechar o registro da execução — {e})")


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


def main(periodo: str, escrever: bool, pular_download: bool,
         so_base: bool = False, abrir_se_preciso: bool = False,
         exec_id=None, disparado_por: str = "rotina") -> int:
    import _honorarios_db as DB
    import _honorarios_fila as FILA

    # O terminal do Windows abre em cp1252 e quebra em qualquer acento. Quem vai
    # rodar isto não deveria precisar saber configurar codificação de terminal.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    periodo, erro = resolver_periodo(DB, periodo, abrir_se_preciso, escrever)
    if erro:
        print(f"\nNADA A FAZER: {erro}")
        return 0

    titulo = (("ATUALIZAÇÃO DA BASE" if so_base else "FECHAMENTO DE HONORÁRIOS")
              + f" · {periodo}" + ("" if escrever else "  (simulação)"))
    print(f"\n╔{'═'*64}╗")
    print(f"║  {titulo:<62}║")
    print(f"╚{'═'*64}╝", flush=True)

    if escrever:
        exec_id = exec_iniciar(DB, "base" if so_base else "publicacao",
                               periodo, disparado_por, exec_id)

    # ---- trava: mês congelado não se mexe -----------------------------------
    per = [p for p in DB.buscar("honorarios_periodos", "periodo_id,label,status,congelado")
           if p["periodo_id"] == periodo]
    if not per and not escrever and abrir_se_preciso:
        # Simulação do primeiro dia do mês: o período ainda não existe porque
        # quem criaria seria esta mesma rodada, se fosse para valer.
        per = [{"label": periodo, "congelado": False}]
    if not per:
        print(f"\nABORTADO: o período {periodo} não existe na tabela de períodos.")
        exec_terminar(DB, exec_id, "erro", f"período {periodo} não existe")
        return 1
    if per[0]["congelado"]:
        print(f"\nABORTADO: {per[0]['label']} está fechado e não aceita alteração.")
        print("  Reabrir é decisão da Gestão Administrativa.")
        exec_terminar(DB, exec_id, "erro", f"{per[0]['label']} está congelado")
        return 1

    # ---- 1. buscar no SVN ---------------------------------------------------
    passo(1, "Buscar o movimento no Saudevianet")
    if pular_download:
        print("  (pulado — usando o que já está no cache)")
    else:
        for inst in ("endo", "oxy"):
            print(f"\n  · {inst}")
            # O SVN cai sozinho de vez em quando (HTTP 524, conexão derrubada).
            # O script já tenta 3x por janela; esta é a segunda camada, para a
            # rotina automática não amanhecer vermelha por instabilidade de
            # servidor. --refazer porque o mês em aberto muda todo dia.
            for tentativa in (1, 2):
                rc = rodar(["_tools/_svn_puxar_560.py", "--instituicao", inst,
                            "--de", periodo, "--ate", periodo,
                            "--filtro-data", "baix_dt_recebimento", "--refazer"])
                if not rc:
                    break
                if tentativa == 1:
                    print(f"    (o SVN não respondeu para {inst}; tentando de novo)")
            if rc:
                print(f"\nABORTADO: falhou ao buscar {inst} no SVN.")
                exec_terminar(DB, exec_id, "erro",
                              f"falha ao buscar {inst} no Saudevianet")
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
            # Divergência não é falha da rotina: é o processo pedindo decisão.
            # Por isso o registro sai como 'divergencias', e no modo só base o
            # código de saída é 0 — senão a rotina automática ficaria vermelha
            # todo dia em que alguém precisa decidir alguma coisa.
            exec_terminar(DB, exec_id, "divergencias",
                          f"{len(ab)} divergência(s) esperando decisão",
                          divergencias_abertas=len(ab))
            return 0 if so_base else 1
        exec_terminar(DB, exec_id, "erro", "o cálculo falhou — ver o log da execução")
        return 1

    if not escrever:
        print(f"\n{'─'*66}")
        print("  [simulação] nada foi gravado nem publicado.")
        print(f"  Para valer:  python _tools/_honorarios_fechar.py --periodo {periodo} --escrever")
        return 0

    if so_base:
        l = DB.buscar("honorarios_lancamentos", "id",
                      filtros={"periodo_id": f"eq.{periodo}"})
        print(f"\n{'═'*66}")
        print(f"  Base de {per[0]['label']} em dia — {len(l)} lançamento(s), "
              "nenhuma divergência aberta.")
        print(f"{'═'*66}")
        print("  Os portais NÃO foram tocados: publicar é um passo à parte.")
        exec_terminar(DB, exec_id, "ok", "base atualizada, sem divergências",
                      divergencias_abertas=0, lancamentos=len(l))
        return 0

    # ---- 4. publicar --------------------------------------------------------
    passo(4, "Publicar nos portais")
    rc = rodar(["_tools/_honorarios_publicar.py", "--periodo", periodo, "--escrever"])
    if rc:
        print("\nABORTADO na publicação. O banco já está atualizado; os portais não.")
        exec_terminar(DB, exec_id, "erro", "falhou ao escrever os portais")
        return 1

    passo(5, "Atualizar a aba de Regras e os links dos Hubs")
    # A aba de Regras mostra percentuais e impostos lidos do banco, mas as regras
    # de cirurgia, NF do médico e exclusões moram no código. Reinjetar aqui evita
    # que a tela mostre número velho depois de alguém mudar uma regra — e é
    # justamente essa tela que o Dr. Igor vai abrir para conferir.
    rodar(["_tools/_honorarios_publicar_regras.py", "--escrever"])
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
    exec_terminar(DB, exec_id, "ok", f"{per[0]['label']} publicado nos portais",
                  divergencias_abertas=0, lancamentos=len(l))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True,
                    help="AAAA-MM, ou 'auto' para o mês que está aberto")
    ap.add_argument("--escrever", action="store_true",
                    help="grava no banco e escreve os portais")
    ap.add_argument("--pular-download", action="store_true",
                    help="usa o cache do SVN em vez de buscar de novo")
    ap.add_argument("--so-base", action="store_true",
                    help="para depois da fila: não publica nada nos portais")
    ap.add_argument("--abrir-se-preciso", action="store_true",
                    help="com --periodo auto, abre o mês corrente se não existir")
    ap.add_argument("--execucao-id", default=None,
                    help="linha de honorarios_execucoes criada pelo portal")
    ap.add_argument("--disparado-por", default="rotina",
                    help="quem pediu: e-mail de quem clicou, ou 'rotina'")
    a = ap.parse_args()

    import _honorarios_db as _DB
    try:
        rc = main(a.periodo, a.escrever, a.pular_download, a.so_base,
                  a.abrir_se_preciso, a.execucao_id, a.disparado_por)
    except Exception:
        # Erro inesperado não pode deixar a execução "rodando" para sempre na
        # tela do portal — quem olhar amanhã tem de ver o que aconteceu.
        traceback.print_exc()
        exec_terminar(_DB, _EXEC_ATUAL or a.execucao_id, "erro",
                      "erro inesperado: " + traceback.format_exc()[-500:])
        rc = 1
    raise SystemExit(rc)
