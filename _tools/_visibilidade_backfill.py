# -*- coding: utf-8 -*-
"""
_visibilidade_backfill.py — leva para os meses JÁ PUBLICADOS a visibilidade
extra configurada em `_honorarios_publicar.VISIBILIDADE_EXTRA`.

O publicador mensal já monta o blob com o dono + quem ele enxerga, mas só do
mês que está sendo publicado. Os meses antigos continuariam com um nome só.
Este script resolve isso SEM tocar no banco: abre o blob de quem é visto com a
chave dele, junta ao blob de quem vê e regrava cifrado com a chave de quem vê.
Assim o que aparece na tela é exatamente o que já está no ar — nenhum número é
recalculado.

Mexe em dois lugares por par de profissionais:
  - Recebimento (raiz, cirurgias/, oxy/): um blob por mês;
  - Produtividade (produtividade/, oxy-produtividade/, cirurgias-produtividade/):
    um blob só, com todos os meses dentro.

Uso:
    python _tools/_visibilidade_backfill.py              # simula
    python _tools/_visibilidade_backfill.py --escrever
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_publicar as P  # noqa: E402

REPO = P.REPO
PROD_RE = re.compile(r"(/\*PDATA\*/')([A-Za-z0-9+/=]+)('/\*PDATA\*/)")
AMBIENTES_PROD = [
    ("produtividade", "_Produtividade"),
    ("oxy-produtividade", "_Oxy_Produtividade"),
    ("cirurgias-produtividade", "_Cirurgias_Produtividade"),
]


def _recebimento(ve: str, vistos: list, chaves: dict, escrever: bool) -> None:
    for emp in ("Endovascular SP", "Cirurgias", "Oxy Recovery"):
        path = P.alvo_individual(ve, emp)
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        m = P.PDATA_RE.search(html)
        if not m:
            print(f"  [{path.name}] marcador não encontrado"); continue
        data = json.loads(m.group(2))

        # o que cada visto tem publicado, por mês
        deles = {}
        for outro in vistos:
            p2 = P.alvo_individual(outro, emp)
            if not p2.exists():
                continue
            m2 = P.PDATA_RE.search(p2.read_text(encoding="utf-8"))
            if not m2:
                continue
            for pid, blk in json.loads(m2.group(2)).items():
                try:
                    dec = P.decifrar(blk["blob"], chaves[outro])
                except Exception:
                    print(f"  [{p2.name}] {pid}: não abriu com a chave de {outro}")
                    continue
                deles.setdefault(pid, {}).update(dec)

        # Só regrava o que muda: mês em que ninguém foi somado fica como está,
        # para não encher o diff de blob novo com o mesmo conteúdo.
        tocados = 0
        for pid in sorted(data):
            try:
                dono = P.decifrar(data[pid]["blob"], chaves[ve])
            except Exception:
                print(f"  [{path.name}] {pid}: não abriu com a chave de {ve} — PULADO")
                continue
            # o dono primeiro; o portal usa a primeira chave como dono da tela
            dentro = {P.G.slugify(ve): dono[P.G.slugify(ve)]} if P.G.slugify(ve) in dono else dict(dono)
            for k, v in dono.items():
                dentro.setdefault(k, v)
            novos = {k: v for k, v in (deles.get(pid) or {}).items() if k not in dentro}
            if not novos:
                continue
            dentro.update(novos)
            data[pid] = {"label": data[pid]["label"], "blob": P.cifrar(dentro, chaves[ve])}
            tocados += 1
            print(f"    {pid}: {', '.join(dentro)}")
        if escrever and tocados:
            novo = json.dumps({k: data[k] for k in sorted(data)},
                              ensure_ascii=False, separators=(",", ":"))
            path.write_text(html[:m.start(2)] + novo + html[m.end(2):], encoding="utf-8")
        print(f"  [{emp}] {path.name}: {tocados} meses"
              + ("" if escrever else "  (simulação)"))


def _produtividade(ve: str, vistos: list, chaves: dict, escrever: bool) -> None:
    for pasta, sufixo in AMBIENTES_PROD:
        path = REPO / pasta / f"{P.G.slugify(ve)}{sufixo}.html"
        if not path.exists():
            continue
        html = path.read_text(encoding="utf-8")
        m = PROD_RE.search(html)
        if not m:
            print(f"  [{path.name}] marcador não encontrado"); continue
        try:
            dentro = P.decifrar(m.group(2), chaves[ve])
        except Exception:
            print(f"  [{path.name}] não abriu com a chave de {ve} — PULADO"); continue
        mudou = False
        for outro in vistos:
            p2 = REPO / pasta / f"{P.G.slugify(outro)}{sufixo}.html"
            if not p2.exists():
                continue
            m2 = PROD_RE.search(p2.read_text(encoding="utf-8"))
            if not m2:
                continue
            try:
                vindo = P.decifrar(m2.group(2), chaves[outro])
            except Exception:
                print(f"  [{p2.name}] não abriu com a chave de {outro}")
                continue
            for k, v in vindo.items():
                if k not in dentro:
                    dentro[k] = v
                    mudou = True
        if not mudou:
            print(f"  [{pasta}] {path.name}: nada a somar")
            continue
        blob = P.cifrar(dentro, chaves[ve])
        if escrever:
            path.write_text(html[:m.start(2)] + blob + html[m.end(2):], encoding="utf-8")
            volta = P.decifrar(PROD_RE.search(path.read_text(encoding="utf-8")).group(2), chaves[ve])
            if list(volta) != list(dentro):
                raise SystemExit(f"ABORTADO: {path.name} não devolveu os mesmos nomes.")
        print(f"  [{pasta}] {path.name}: {', '.join(dentro)}"
              + ("" if escrever else "  (simulação)"))


def main(escrever: bool) -> None:
    chaves = P.carregar_chaves()
    for ve, vistos in P.VISIBILIDADE_EXTRA.items():
        faltando = [n for n in [ve] + list(vistos) if n not in chaves]
        if faltando:
            print(f"[SEM CHAVE] {', '.join(faltando)} — par {ve} pulado")
            continue
        print(f"\n=== {ve} enxerga: {', '.join(vistos)} ===")
        print("--- Recebimento ---")
        _recebimento(ve, list(vistos), chaves, escrever)
        print("--- Produtividade ---")
        _produtividade(ve, list(vistos), chaves, escrever)
    if not escrever:
        print("\n[simulação] nada foi gravado. Rode com --escrever.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    main(ap.parse_args().escrever)
