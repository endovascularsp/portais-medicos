# -*- coding: utf-8 -*-
"""
_honorarios_cadastrar_medico.py — cadastra um médico novo do zero.

Faz, nesta ordem:
  1. gera uma chave aleatória de 32 caracteres (mesmo formato das existentes);
  2. insere em `users` e `user_secrets` no Supabase;
  3. cria o Hub, clonando o de outro médico e trocando a identidade.

O portal de Recebimento/Produtividade NÃO é criado aqui — para isso existe
`_honorarios_criar_portal.py`, que roda depois e já encontra Hub e chave prontos.

ATENÇÃO: `users` é a MESMA tabela do Mural, do Compras e da Gestão de Acessos.
Por isso o script recusa qualquer e-mail que já exista, e insere um registro por
vez em vez de fazer carga em lote.

Uso:
    python _tools/_honorarios_cadastrar_medico.py --email x@y.com --nome "Fulano" --dry-run
    python _tools/_honorarios_cadastrar_medico.py --email x@y.com --nome "Fulano"
"""
from __future__ import annotations
import argparse
import re
import secrets
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_db as DB      # noqa: E402
import _honorarios_publicar as P  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEPARTAMENTO_MEDICOS = 17
CARDS = ["medico_proprio"]
VER = "20260805"


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


def nova_chave() -> str:
    """32 caracteres no mesmo alfabeto das chaves já existentes."""
    return secrets.token_urlsafe(24)


def main(email: str, nome: str, modelo_hub: str, dry_run: bool):
    email = email.strip().lower()
    slug = slugify(nome)
    hub_novo = REPO / "hub" / f"{slug}_Hub.html"
    print(f"=== cadastrar {nome} <{email}> ===")

    # --- 1) o e-mail já existe? ---
    users = DB.buscar("users", "email,name,role")
    secrets_ = DB.buscar("user_secrets", "email")
    if any(str(u["email"]).lower() == email for u in users):
        raise SystemExit(f"ABORTADO: {email} já está em `users`. Este script só cadastra do zero.")
    if any(str(s["email"]).lower() == email for s in secrets_):
        raise SystemExit(f"ABORTADO: {email} já tem chave em `user_secrets`.")
    if hub_novo.exists():
        raise SystemExit(f"ABORTADO: {hub_novo.relative_to(REPO)} já existe.")
    print(f"  e-mail inédito em users ({len(users)} hoje) e user_secrets ({len(secrets_)} hoje)")

    # --- 2) Hub a partir de um modelo ---
    tmpl = REPO / "hub" / f"{slugify(modelo_hub)}_Hub.html"
    if not tmpl.exists():
        raise SystemExit(f"ABORTADO: Hub-modelo não existe ({tmpl.name}).")
    t_slug = tmpl.stem[:-4]              # tira o "_Hub"
    t_nome = t_slug.replace("_", " ")
    ht = tmpl.read_text(encoding="utf-8")

    chave = nova_chave()
    # O BLOB do Hub é cifrado com a chave do dono; refazemos com a chave nova,
    # zerando os portais (serão religados por _honorarios_criar_portal.py).
    mb = re.search(r'const BLOB = "([^"]+)"', ht)
    if not mb:
        raise SystemExit("ABORTADO: Hub-modelo sem BLOB.")
    ht = re.sub(r'const BLOB = "[^"]+"',
                'const BLOB = "' + P.cifrar(
                    {"profissional": nome,
                     "portais": {"endo": None, "oxy": None, "cir": None, "prod": None}},
                    chave) + '"', ht, count=1)
    ht = ht.replace(t_nome, nome).replace(t_slug, slug)
    if t_nome.split()[0] != nome.split()[0]:
        ht = ht.replace(t_nome.split()[0], nome.split()[0])

    # tira os cards que apontariam para portais que ele ainda não tem
    for cid in ("card-rec", "card-prod"):
        ht = re.sub(rf'\s*<div class="hub-card [a-z]+" id="{cid}">.*?</div>\s*</div>', "",
                    ht, flags=re.S)
    resto = t_nome.split()[0]
    if resto in ht:
        raise SystemExit(f"ABORTADO: sobrou {resto!r} do modelo no Hub novo.")
    conf = P.decifrar(re.search(r'const BLOB = "([^"]+)"', ht).group(1), chave)
    if conf["profissional"] != nome:
        raise SystemExit("ABORTADO: o Hub novo não decripta para o nome certo.")
    print(f"  hub ........: {hub_novo.relative_to(REPO)} (modelo {tmpl.name}, {len(ht):,} chars)")
    print(f"  chave ......: gerada, {len(chave)} caracteres (não exibida)")

    if dry_run:
        print("\n[dry-run] nada gravado, nada inserido no banco.")
        return

    # --- 3) grava ---
    u = DB.inserir("users", {"email": email, "name": nome, "role": "medico",
                             "slug": slug, "cards": CARDS,
                             "departamento_id": DEPARTAMENTO_MEDICOS})
    print(f"  users ......: {u['email']} · {u['role']} · cards {u['cards']}")
    DB.inserir("user_secrets", {"email": email, "legacy_password": chave})
    print("  user_secrets: chave gravada")
    hub_novo.write_text(ht, encoding="utf-8")
    print(f"  hub ........: gravado")
    print(f"\nPronto. Agora rode _honorarios_criar_portal.py para dar os portais a {nome}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--nome", required=True)
    ap.add_argument("--modelo-hub", default="Eduardo Araujo Pires")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.email, a.nome, a.modelo_hub, a.dry_run)
