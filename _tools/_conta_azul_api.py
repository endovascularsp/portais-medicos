# -*- coding: utf-8 -*-
r"""
_conta_azul_api.py — porta de entrada da API do Conta Azul.

Todo script que for falar com o Conta Azul passa por aqui, por um motivo só: o
refresh_token é de USO ÚNICO. Cada renovação devolve outro e invalida o anterior.
Se dois scripts renovarem por conta própria, o segundo derruba o primeiro e a
autorização inteira tem de ser refeita à mão, com o Thiago presente. Então a
renovação mora num lugar só, e grava o token novo ANTES de devolver a resposta.

Prazos que valem a pena ter na cabeça:
  access_token   1 hora
  refresh_token  2 semanas — se ninguém usar a API por 2 semanas, a autorização
                 morre e é preciso refazer com `_conta_azul_trocar_codigo.py`.

Uso como biblioteca:
    from _conta_azul_api import get, post
    dados = get("/v1/pessoa", tamanho_pagina=100)

Uso na mão, para espiar um endereço:
    python _tools/_conta_azul_api.py /v1/pessoa
"""
from __future__ import annotations
import base64
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Só ajusta a saída quando este arquivo é o programa. Como biblioteca ele não
# mexe no stdout de quem importou: trocar o wrapper de fora fecha o de dentro e
# o script chamador morre com "I/O operation on closed file".
if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENV = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\.env")
TOKENS = ENV.parent / "conta_azul_tokens.json"
TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
BASE = "https://api-v2.contaazul.com"


def _cred() -> tuple:
    txt = ENV.read_text(encoding="utf-8", errors="replace")
    def pega(n):
        m = re.search(rf"^\s*{n}\s*=\s*(.+)$", txt, re.M)
        return m.group(1).strip().strip('"').strip("'") if m else None
    cid, seg = pega("CONTA_AZUL_CLIENT_ID"), pega("CONTA_AZUL_CLIENT_SECRET")
    if not cid or not seg:
        raise SystemExit("ABORTADO: CONTA_AZUL_CLIENT_ID/SECRET não estão no .env")
    return cid, seg


def _renovar(t: dict) -> dict:
    """Troca o refresh_token por um par novo e GRAVA antes de devolver.

    A ordem importa: gravar depois de usar significa que uma queda no meio do
    caminho deixa o arquivo com um token já queimado, e aí só refazendo à mão.
    """
    cid, seg = _cred()
    if not t.get("refresh_token"):
        raise SystemExit("ABORTADO: não há refresh_token — refaça a autorização.")
    dados = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": t["refresh_token"],
    }).encode()
    basic = base64.b64encode(f"{cid}:{seg}".encode()).decode()
    req = urllib.request.Request(TOKEN_URL, data=dados, method="POST", headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            novo = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:300]
        raise SystemExit(
            f"ABORTADO: não deu para renovar (HTTP {e.code}) — {corpo}\n"
            "  Se passou de 2 semanas sem uso, a autorização venceu: refaça com\n"
            "  _conta_azul_trocar_codigo.py.")
    # o Cognito às vezes devolve só o access_token; nesse caso o refresh continua valendo
    t.update({k: v for k, v in novo.items() if v})
    t["obtido_em"] = datetime.now(timezone.utc).isoformat()
    t["expira_em"] = (datetime.now(timezone.utc)
                      + timedelta(seconds=int(novo.get("expires_in", 3600)))).isoformat()
    TOKENS.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
    return t


def token() -> str:
    if not TOKENS.exists():
        raise SystemExit(f"ABORTADO: {TOKENS} não existe — falta autorizar.")
    t = json.loads(TOKENS.read_text(encoding="utf-8"))
    venc = datetime.fromisoformat(t.get("expira_em", "1970-01-01T00:00:00+00:00"))
    # 5 minutos de folga: uma chamada longa não pode vencer no meio dela
    if venc - timedelta(minutes=5) <= datetime.now(timezone.utc):
        t = _renovar(t)
    return t["access_token"]


def chamar(caminho: str, metodo: str = "GET", corpo=None, **params):
    url = BASE + caminho
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})
    dados = json.dumps(corpo).encode() if corpo is not None else None
    cab = {"Authorization": "Bearer " + token(), "Accept": "application/json"}
    if dados:
        cab["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                bruto = r.read().decode("utf-8", "replace")
                return json.loads(bruto) if bruto.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 2:      # limite de chamadas: espera e repete
                time.sleep(5 * (tentativa + 1))
                continue
            raise
    return {}


def get(caminho: str, **params):
    return chamar(caminho, "GET", None, **params)


def post(caminho: str, corpo, **params):
    return chamar(caminho, "POST", corpo, **params)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("uso: python _tools/_conta_azul_api.py /v1/algum-caminho")
    print(json.dumps(get(sys.argv[1]), indent=2, ensure_ascii=False)[:6000])
