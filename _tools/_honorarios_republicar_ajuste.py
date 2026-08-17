# -*- coding: utf-8 -*-
r"""
_honorarios_republicar_ajuste.py — republica o portal de UM profissional depois de
um desconto/acréscimo ser lançado, editado ou excluído.

Por que existe: o portal do médico é arquivo gerado. Quando a Micaele lança um
desconto num mês já publicado, o banco passa a dizer uma coisa e o portal
continua dizendo outra — foi exatamente o que aconteceu em 17/08/2026, com o
desconto de R$ 9.335,99 do Dr. Igor num Julho publicado em 10/08. O médico abriria
o portal, veria o repasse cheio, receberia menos na conta e ligaria. É o
telefonema que a aba de descontos foi criada para evitar.

O que ele faz de diferente de `_honorarios_publicar.py --periodo X --escrever`:

  · toca UM profissional numa UMA empresa (a do centro de custo do lançamento),
    não os 38 arquivos. Republicar tudo por causa de um desconto seria ~25 MB de
    commit e reescreveria portais que não mudaram — cada rodada gera salt e nonce
    novos, então o arquivo muda mesmo quando o conteúdo é igual;
  · registra em `honorarios_execucoes` (tipo 'publicacao'), que é de onde a tela
    tira o "última atualização";
  · devolve na saída padrão os arquivos que mudaram, para o workflow commitar só
    esses.

NÃO recalcula nada: mês congelado continua congelado. Publicar é copiar para o
portal o que o banco já diz.

Uso:
    python _tools/_honorarios_republicar_ajuste.py --periodo 2026-07 \
        --profissional "Igor Rafael Sincos" --empresa "Endovascular SP" --escrever

    # sem --empresa, republica o profissional em todas as empresas em que ele
    # aparece no período (usar só quando não se sabe o centro de custo)
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB          # noqa: E402
import _honorarios_gerar_pdata as G  # noqa: E402
import _honorarios_publicar as P     # noqa: E402


def chave(s) -> str:
    s = unicodedata.normalize("NFD", str(s or "").strip())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def cache_bust(slug: str, arquivos: list, escrever: bool) -> list:
    """Renova o ?v= APENAS no Hub deste médico, e só nos links dos portais que
    mudaram.

    `_cache_bust_hubs.py` faz os 20 Hubs de uma vez — certo no fechamento
    mensal, exagerado aqui: um desconto viraria 20 arquivos no commit. E ele
    carimba só a data, então duas publicações no mesmo dia deixariam o segundo
    médico com a versão velha em cache (gotcha registrado em 11/08/2026). Aqui a
    versão tem minuto.
    """
    from datetime import datetime
    hub = P.REPO / "hub" / f"{slug}_Hub.html"
    if not hub.exists():
        print(f"  [aviso] Hub não encontrado: {hub.name} — sem cache-busting")
        return []
    versao = datetime.now().strftime("%Y%m%d%H%M")
    html = original = hub.read_text(encoding="utf-8")
    for rel in arquivos:
        # No Hub os links são relativos a hub/, ou seja "../Igor.html"
        alvo = "../" + rel
        html = re.sub(
            r'href="' + re.escape(alvo) + r'(\?v=\d+)?"',
            f'href="{alvo}?v={versao}"', html)
    if html == original:
        return []
    if escrever:
        hub.write_text(html, encoding="utf-8")
    print(f"  cache-bust  {hub.name:44s} ?v={versao}")
    return [str(hub.relative_to(P.REPO)).replace("\\", "/")]


def marcar(execucao_id, **campos) -> None:
    """Atualiza a linha de execução. Falha aqui não pode derrubar a publicação:
    o portal do médico é o que importa; o registro na tela é secundário."""
    if not execucao_id:
        return
    try:
        DB.atualizar("honorarios_execucoes", str(execucao_id), campos)
    except Exception as e:                                    # noqa: BLE001
        print(f"  [aviso] não consegui atualizar a execução {execucao_id}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--profissional", required=True)
    ap.add_argument("--empresa", default="",
                    help="centro de custo do lançamento; vazio = todas")
    ap.add_argument("--execucao-id", type=int)
    ap.add_argument("--escrever", action="store_true",
                    help="sem isto, nada é gravado — só mostra o que faria")
    a = ap.parse_args()

    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc).isoformat()
    marcar(a.execucao_id, status="rodando", iniciado_em=agora)

    try:
        P.validar_cripto()
        chaves = P.carregar_chaves()
        if not chaves:
            raise SystemExit("nenhuma chave validada — não publico às cegas")

        obj = G.montar(a.periodo)
        label = obj["label"]

        alvos = [
            inner for inner in obj["profs"].values()
            if chave(inner["profissional"]) == chave(a.profissional)
            and (not a.empresa or chave(inner["empresa"]) == chave(a.empresa))
        ]
        if not alvos:
            # Não é erro: o profissional pode não ter movimento no mês, e um
            # desconto sem repasse não tem portal onde aparecer.
            msg = (f"{a.profissional} não tem lançamento em {a.periodo}"
                   + (f" / {a.empresa}" if a.empresa else "") + " — nada a publicar")
            print(msg)
            marcar(a.execucao_id, status="ok", terminado_em=agora, mensagem=msg)
            return 0

        prof = alvos[0]["profissional"]
        if prof not in chaves:
            raise SystemExit(f"{prof} não tem chave validada — publicar cifraria "
                             "com chave errada e trancaria o médico fora")

        mudados, detalhes = [], []
        for inner in alvos:
            emp = inner["empresa"]
            path = P.alvo_individual(prof, emp)
            blob = P.cifrar({G.slugify(prof): P.interno_individual(inner)},
                            chaves[prof])
            res = P.injetar_individual(path, a.periodo, label, blob, a.escrever)
            aj = inner["resumo"].get("Ajustes (R$)")
            detalhes.append(f"{emp}: {res}"
                            + (f" (ajustes {aj:+.2f})" if aj else " (sem ajustes)"))
            print(f"  {emp:16s} {path.name:44s} {res}")
            if res in ("SUBSTITUI", "ADICIONA") and a.escrever:
                mudados.append(str(path.relative_to(P.REPO)).replace("\\", "/"))

        if mudados:
            mudados += cache_bust(G.slugify(prof), mudados, a.escrever)

        msg = f"{prof} · {a.periodo} · " + " · ".join(detalhes)
        marcar(a.execucao_id, status="ok",
               terminado_em=datetime.now(timezone.utc).isoformat(), mensagem=msg[:500])

        # O workflow lê esta linha para commitar só o que mudou.
        print("ARQUIVOS_MUDADOS=" + " ".join(mudados))
        return 0

    except SystemExit as e:
        marcar(a.execucao_id, status="erro",
               terminado_em=datetime.now(timezone.utc).isoformat(),
               mensagem=str(e)[:500])
        print(f"ABORTADO: {e}")
        return 1
    except Exception as e:                                    # noqa: BLE001
        marcar(a.execucao_id, status="erro",
               terminado_em=datetime.now(timezone.utc).isoformat(),
               mensagem=f"{type(e).__name__}: {e}"[:500])
        raise


if __name__ == "__main__":
    sys.exit(main())
