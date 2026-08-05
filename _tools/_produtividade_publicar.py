# -*- coding: utf-8 -*-
"""
_produtividade_publicar.py — escreve a Produtividade gerada do #560 nos portais.

Duas escritas diferentes:
  - ADMIN (produtividade/index.html, oxy-produtividade/index.html):
    `const DADOS` e `const PORDER` em texto puro;
  - INDIVIDUAIS: um blob criptografado com a chave do profissional, contendo
    { "Nome": { profissional, empresa, periodos: { pid: {label, resumo,
                                                         atendimentos} } } }

Confere antes de gravar e valida depois: cada portal escrito é decriptado de
volta e comparado com o que deveria conter.

Uso:
    python _tools/_produtividade_publicar.py --instituicao endo            # simula
    python _tools/_produtividade_publicar.py --instituicao endo --piloto Clara --escrever
    python _tools/_produtividade_publicar.py --instituicao endo --escrever
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_catalogo as CAT   # noqa: E402
import _honorarios_publicar as P     # noqa: E402
import _produtividade_gerar as G     # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PDATA_RE = re.compile(r"(/\*PDATA\*/')([A-Za-z0-9+/=]+)('/\*PDATA\*/)")
AMBIENTE = {
    "endo": ("produtividade", "_Produtividade", "Endovascular SP"),
    "oxy":  ("oxy-produtividade", "_Oxy_Produtividade", "Oxy Recovery"),
}


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


def interno(prof: str, empresa: str, pers: dict) -> dict:
    """O objeto que vai dentro do blob do portal individual."""
    return {
        "profissional": prof, "empresa": empresa,
        "periodos": {
            pid: {
                "label": v["label"],
                "resumo": {"total": v["total"], "n_atend": v["n_atend"],
                           "n_pacientes": v["n_pacientes"],
                           "por_pagamento": v["por_pagamento"],
                           "por_categoria": v["por_categoria"],
                           "por_tabela": v["por_tabela"]},
                "atendimentos": v["atendimentos"],
            } for pid, v in sorted(pers.items())
        },
    }


def injetar_admin(path: Path, dados: dict, escrever: bool) -> str:
    html = path.read_text(encoding="utf-8")
    md = re.search(r"(const DADOS(?:_RAW)?\s*=\s*)(\{.*?\});", html, re.S)
    mp = re.search(r"(const PORDER\s*=\s*)(\[.*?\]);", html, re.S)
    if not md or not mp:
        return "MARCADOR NÃO ENCONTRADO"
    periodos = sorted({p for v in dados.values() for p in v})
    novo = (html[:md.start(2)] + json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
            + html[md.end(2):])
    mp2 = re.search(r"(const PORDER\s*=\s*)(\[.*?\]);", novo, re.S)
    novo = novo[:mp2.start(2)] + json.dumps(periodos, ensure_ascii=False) + novo[mp2.end(2):]
    if escrever:
        path.write_text(novo, encoding="utf-8")
    return f"{len(dados)} profissionais · períodos {periodos} · {len(novo):,} chars"


def injetar_individual(path: Path, blob: str, escrever: bool) -> str:
    if not path.exists():
        return "SEM PORTAL"
    html = path.read_text(encoding="utf-8")
    m = PDATA_RE.search(html)
    if not m:
        return "MARCADOR NÃO ENCONTRADO"
    novo = html[:m.start(2)] + blob + html[m.end(2):]
    if escrever:
        path.write_text(novo, encoding="utf-8")
    return "OK"


def main(inst: str, piloto: str | None, escrever: bool):
    pasta, sufixo, empresa = AMBIENTE[inst]
    dados = G.montar(inst, CAT.carregar())
    chaves = P.carregar_chaves()
    print(f"\n=== Produtividade · {empresa} · escrever={escrever} ===")

    print("\n--- Portais individuais (criptografados) ---")
    for prof in sorted(dados):
        if piloto and piloto.lower() not in prof.lower():
            continue
        slug = slugify(prof)
        path = REPO / pasta / f"{slug}{sufixo}.html"
        if prof not in chaves:
            print(f"  [SEM CHAVE]  {prof}")
            continue
        if not path.exists():
            tot = sum(v["total"] for v in dados[prof].values())
            print(f"  [SEM PORTAL] {prof[:32]:34s} R$ {tot:>11,.2f} — "
                  f"criar com _produtividade_criar_portal.py")
            continue
        obj = {prof: interno(prof, empresa, dados[prof])}
        blob = P.cifrar(obj, chaves[prof])
        res = injetar_individual(path, blob, escrever)
        pers = sorted(dados[prof])
        tot = sum(v["total"] for v in dados[prof].values())
        print(f"  {prof[:32]:34s} {len(pers)} meses ({pers[0][-2:]}-{pers[-1][-2:]}) "
              f"R$ {tot:>11,.2f} -> {res}")
        if escrever and res == "OK":
            volta = P.decifrar(PDATA_RE.search(path.read_text(encoding="utf-8")).group(2),
                               chaves[prof])
            if sorted(volta[prof]["periodos"]) != pers:
                raise SystemExit(f"ABORTADO: {path.name} não devolveu os mesmos períodos.")

    if piloto:
        print("\n(piloto: admin não tocado)")
        return

    print(f"\n--- Admin: {pasta}/index.html ---")
    res = injetar_admin(REPO / pasta / "index.html", dados, escrever)
    print(f"  {res}")
    if not escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--instituicao", default="endo", choices=list(AMBIENTE))
    ap.add_argument("--piloto")
    ap.add_argument("--escrever", action="store_true")
    a = ap.parse_args()
    main(a.instituicao, a.piloto, a.escrever)
