# -*- coding: utf-8 -*-
r"""
_conta_azul_autorizar.py — primeira autorização na API do Conta Azul (OAuth2).

Roda UMA vez, com o Thiago presente: abre o navegador, ele autoriza com a conta
da clínica, e o script guarda os tokens. Depois disso a renovação é automática
(ver `_conta_azul_api.py`).

Como funciona, e por que precisa de gente:
  1. o script sobe um servidor local só para receber a resposta;
  2. abre o navegador na tela de autorização do Conta Azul;
  3. ele entra e autoriza;
  4. o Conta Azul devolve um CÓDIGO no endereço local — que vale 3 MINUTOS;
  5. o script troca esse código por access_token + refresh_token e grava.

Endereços da API nova (a de 2025; a antiga está sendo desativada):
  autorizar : https://auth.contaazul.com/oauth2/authorize
  token     : https://auth.contaazul.com/oauth2/token   (Basic client_id:secret)
  api       : https://api-v2.contaazul.com/v1/
O escopo é fixo — não se escolhe mais por assunto como na versão legada.

ATENÇÃO ao refresh_token: vale 2 semanas e é de USO ÚNICO. Cada renovação
devolve outro, que tem de ser gravado na hora. Perder um significa refazer esta
autorização à mão.

Uso:
    python _tools/_conta_azul_autorizar.py --redirect http://localhost:8765/callback
"""
from __future__ import annotations
import argparse
import base64
import http.server
import io
import json
import re
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENV = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\.env")
TOKENS = ENV.parent / "conta_azul_tokens.json"
AUTORIZAR = "https://auth.contaazul.com/oauth2/authorize"
TOKEN = "https://auth.contaazul.com/oauth2/token"
ESCOPO = "openid profile aws.cognito.signin.user.admin"

_codigo = {"valor": None, "erro": None}


def cred() -> tuple:
    txt = ENV.read_text(encoding="utf-8", errors="replace")
    def pega(n):
        m = re.search(rf"^\s*{n}\s*=\s*(.+)$", txt, re.M)
        return m.group(1).strip().strip('"').strip("'") if m else None
    cid, seg = pega("CONTA_AZUL_CLIENT_ID"), pega("CONTA_AZUL_CLIENT_SECRET")
    if not cid or not seg:
        raise SystemExit("ABORTADO: CONTA_AZUL_CLIENT_ID/SECRET não estão no .env")
    return cid, seg


class Ouvinte(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _codigo["valor"] = (q.get("code") or [None])[0]
        _codigo["erro"] = (q.get("error_description") or q.get("error") or [None])[0]
        ok = bool(_codigo["valor"])
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"""<!DOCTYPE html><html lang=pt-BR><meta charset=UTF-8>
<body style="font-family:Segoe UI,Arial;background:#EEF2F6;color:#0D1E30;
 display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="background:#fff;padding:36px 44px;border-radius:14px;text-align:center;
 box-shadow:0 6px 20px rgba(11,31,58,.12)">
<div style="font-size:34px">{'✅' if ok else '⚠️'}</div>
<h1 style="font-size:17px;color:#0B1F3A;margin:10px 0 6px">
{'Autorizado' if ok else 'Não deu certo'}</h1>
<p style="font-size:13px;color:#4A6278;margin:0">
{'Pode fechar esta aba e voltar para a conversa.' if ok
 else 'Volte para a conversa: o motivo apareceu no terminal.'}</p>
</div></body></html>""".encode("utf-8"))

    def log_message(self, *a):
        pass          # sem ruído de servidor no terminal


def trocar(codigo, redirect, cid, seg) -> dict:
    dados = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": codigo,
        "redirect_uri": redirect,
    }).encode()
    basic = base64.b64encode(f"{cid}:{seg}".encode()).decode()
    req = urllib.request.Request(TOKEN, data=dados, method="POST", headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redirect", required=True,
                    help="EXATAMENTE a URL cadastrada no Portal do Desenvolvedor")
    a = ap.parse_args()
    cid, seg = cred()

    porta = urllib.parse.urlparse(a.redirect).port or 80
    servidor = http.server.HTTPServer(("localhost", porta), Ouvinte)
    threading.Thread(target=servidor.handle_request, daemon=True).start()

    url = AUTORIZAR + "?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid,
        "redirect_uri": a.redirect, "scope": ESCOPO, "state": "endovascular",
    })
    print("Abrindo o navegador para você autorizar com a conta da clínica…")
    print(f"Se não abrir, cole este endereço:\n\n{url}\n")
    webbrowser.open(url)

    print("Esperando a autorização (o código vale 3 minutos)…")
    for _ in range(180):
        if _codigo["valor"] or _codigo["erro"]:
            break
        threading.Event().wait(1)
    servidor.server_close()

    if _codigo["erro"]:
        raise SystemExit(f"ABORTADO: o Conta Azul recusou — {_codigo['erro']}")
    if not _codigo["valor"]:
        raise SystemExit("ABORTADO: ninguém autorizou em 3 minutos.")

    print("Código recebido. Trocando por token…")
    t = trocar(_codigo["valor"], a.redirect, cid, seg)
    t["obtido_em"] = datetime.now(timezone.utc).isoformat()
    t["expira_em"] = (datetime.now(timezone.utc)
                      + timedelta(seconds=int(t.get("expires_in", 3600)))).isoformat()
    t["redirect_uri"] = a.redirect
    TOKENS.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nGRAVADO: {TOKENS}")
    print(f"  access_token  vale até {t['expira_em'][:19]} (1 hora)")
    print(f"  refresh_token {'presente' if t.get('refresh_token') else 'AUSENTE — problema'}"
          " (2 semanas, uso único)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
