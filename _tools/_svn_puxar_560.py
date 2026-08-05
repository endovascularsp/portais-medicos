# -*- coding: utf-8 -*-
"""
_svn_puxar_560.py — baixa o relatório #560 do SVN pela API, por período.

Descoberta de 05/08/2026: a API aceita `filtro_data` com o NOME TÉCNICO da coluna
de data. Os nomes amigáveis ("recebimento", "compensacao") devolvem HTTP 570.

    filtro_data=baix_dt_pagamento     -> o que a TELA chama de "Recebimento"
                                         (data da venda / pagamento do cliente)
    filtro_data=baix_dt_recebimento   -> data em que a clínica recebeu

Sim, os nomes são o oposto do rótulo da tela. Confirmado contra o CSV exportado à
mão de Julho/2026: 722 linhas, 322 OS, R$ 750.929,62 — bate exatamente.

O mês inteiro estoura o tempo do servidor (HTTP 524); por isso a busca é quebrada
em janelas de poucos dias.

ATENÇÃO: o token é da instituição Endovascular SP. Para a Oxy Recovery é preciso
um segundo token, gerado com a instituição trocada no SVN.

Uso:
    python _tools/_svn_puxar_560.py --de 2026-01 --ate 2026-07
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\.env")
SAIDA = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\svn_560_cache")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
JANELA = 5   # dias por requisição


def token() -> str:
    m = re.search(r"SVN_TOKEN\s*=\s*(.+)", ENV.read_text(encoding="utf-8", errors="replace"))
    if not m:
        raise SystemExit("ABORTADO: SVN_TOKEN não encontrado no .env")
    return m.group(1).strip().strip("\"'")


def puxar(tok: str, ini: str, fim: str, filtro_data: str, tentativas: int = 3) -> list:
    q = {"codigo": 560, "inicio": ini, "fim": fim,
         "inst_tx_token": tok, "filtro_data": filtro_data}
    url = "http://apps.saudevianet.com.br/api/dashboard/getRelatorio?" + urllib.parse.urlencode(q)
    for t in range(tentativas):
        try:
            raw = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": UA}), timeout=300).read()
            return json.loads(raw.decode("utf-8", "replace")).get("dados", [])
        except urllib.error.HTTPError as e:
            if e.code == 524 and t < tentativas - 1:
                continue          # servidor demorou; tenta de novo
            raise SystemExit(f"ABORTADO: HTTP {e.code} em {ini[:10]}..{fim[:10]}")
        except Exception as e:
            if t == tentativas - 1:
                raise SystemExit(f"ABORTADO: {type(e).__name__} em {ini[:10]}..{fim[:10]}")
    return []


def meses(de: str, ate: str):
    a = dt.date(int(de[:4]), int(de[5:7]), 1)
    b = dt.date(int(ate[:4]), int(ate[5:7]), 1)
    while a <= b:
        prox = dt.date(a.year + (a.month == 12), a.month % 12 + 1, 1)
        yield a.strftime("%Y-%m"), a, prox - dt.timedelta(days=1)
        a = prox


def main(de: str, ate: str, filtro_data: str):
    tok = token()
    SAIDA.mkdir(exist_ok=True)
    for pid, ini, fim in meses(de, ate):
        alvo = SAIDA / f"560_{pid}_{filtro_data}.json"
        if alvo.exists():
            n = len(json.loads(alvo.read_text(encoding="utf-8")))
            print(f"  {pid}  já em cache ({n} registros)")
            continue
        linhas, d = [], ini
        while d <= fim:
            f = min(d + dt.timedelta(days=JANELA - 1), fim)
            linhas += puxar(tok, f"{d} 00:00:00", f"{f} 23:59:59", filtro_data)
            d = f + dt.timedelta(days=1)
        alvo.write_text(json.dumps(linhas, ensure_ascii=False), encoding="utf-8")
        oss = len({str(r.get("orca_id")) for r in linhas})
        print(f"  {pid}  {len(linhas):5d} registros · {oss:4d} OS  -> {alvo.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--de", required=True)
    ap.add_argument("--ate", required=True)
    ap.add_argument("--filtro-data", default="baix_dt_pagamento")
    a = ap.parse_args()
    print(f"Relatório #560 · {a.de} a {a.ate} · filtro_data={a.filtro_data}")
    main(a.de, a.ate, a.filtro_data)
