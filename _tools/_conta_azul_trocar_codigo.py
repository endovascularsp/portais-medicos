# -*- coding: utf-8 -*-
r"""
_conta_azul_trocar_codigo.py — troca o código de autorização por tokens.

Por que existe em vez do fluxo automático: a aplicação da clínica está
cadastrada com `redirect_uri=https://contaazul.com`, um endereço do próprio
Conta Azul. Não dá para escutar ali, então o código volta na BARRA DE ENDEREÇO
do navegador e é copiado a mão. Se um dia a redirect for trocada para
`http://localhost:8765/callback`, o `_conta_azul_autorizar.py` faz tudo sozinho.

O código vale 3 MINUTOS. Entre copiar e rodar isto, não dá para almoçar.

Uso:
    python _tools/_conta_azul_trocar_codigo.py --codigo COLE_AQUI
    python _tools/_conta_azul_trocar_codigo.py --url "https://contaazul.com/?code=...&state=..."
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ENV = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\.env")
TOKENS = ENV.parent / "conta_azul_tokens.json"
TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
REDIRECT = "https://contaazul.com"


def cred() -> tuple:
    txt = ENV.read_text(encoding="utf-8", errors="replace")
    def pega(n):
        m = re.search(rf"^\s*{n}\s*=\s*(.+)$", txt, re.M)
        return m.group(1).strip().strip('"').strip("'") if m else None
    cid, seg = pega("CONTA_AZUL_CLIENT_ID"), pega("CONTA_AZUL_CLIENT_SECRET")
    if not cid or not seg:
        raise SystemExit("ABORTADO: CONTA_AZUL_CLIENT_ID/SECRET não estão no .env")
    return cid, seg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codigo")
    ap.add_argument("--url", help="cole a barra de endereço inteira, se preferir")
    ap.add_argument("--redirect", default=REDIRECT)
    a = ap.parse_args()

    codigo = a.codigo
    if a.url and not codigo:
        # aceita tanto ?code= quanto #code=, porque o Conta Azul usa hash em
        # parte do fluxo e o navegador mostra os dois formatos
        m = re.search(r"[?&#]code=([^&\s]+)", a.url)
        if not m:
            raise SystemExit("ABORTADO: não achei 'code=' nesse endereço.")
        codigo = m.group(1)
    if not codigo:
        raise SystemExit("ABORTADO: informe --codigo ou --url")
    codigo = urllib.parse.unquote(codigo.strip())

    cid, seg = cred()
    dados = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": codigo,
        "redirect_uri": a.redirect,
    }).encode()
    basic = base64.b64encode(f"{cid}:{seg}".encode()).decode()
    req = urllib.request.Request(TOKEN_URL, data=dados, method="POST", headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:400]
        print(f"HTTP {e.code} — {corpo}")
        if "invalid_grant" in corpo:
            print("\n  'invalid_grant' quase sempre é uma destas três:")
            print("   · o código passou dos 3 minutos;")
            print("   · o código já foi usado (cada um serve uma vez só);")
            print("   · a redirect_uri daqui não é idêntica à que gerou o código.")
        return 1

    t["obtido_em"] = datetime.now(timezone.utc).isoformat()
    t["expira_em"] = (datetime.now(timezone.utc)
                      + timedelta(seconds=int(t.get("expires_in", 3600)))).isoformat()
    t["redirect_uri"] = a.redirect
    TOKENS.write_text(json.dumps(t, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"GRAVADO: {TOKENS}")
    print(f"  access_token  vale até {t['expira_em'][:19]} (1 hora)")
    print(f"  refresh_token {'presente' if t.get('refresh_token') else 'AUSENTE — problema'}"
          " (2 semanas, uso único)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
