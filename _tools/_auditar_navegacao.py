# -*- coding: utf-8 -*-
"""
_auditar_navegacao.py — confere se dá para circular por todos os portais.

Varre TODO link relativo de TODA página do repositório e responde três coisas:

  1. LINK QUEBRADO — aponta para arquivo/pasta que não existe. Em produção o
     script UX6-HIDE-404 esconde esses botões, então o sintoma que o usuário
     relata não é "erro", é "o botão sumiu";
  2. SEM VOLTA — portal de médico sem link para o Hub dele (o 🏠 Home);
  3. MÃO ÚNICA — A leva a B, mas B não traz de volta para A. É o que faz o
     médico entrar num ambiente e ficar preso lá.

Uso:
    python _tools/_auditar_navegacao.py
    python _tools/_auditar_navegacao.py --so cirurgias-produtividade
"""
from __future__ import annotations
import argparse
import re
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# href de navegação — ignora âncora, mailto, http externo e data:
HREF_RE = re.compile(r"""href=['"]([^'"]+)['"]""")
PULAR = ("#", "mailto:", "tel:", "javascript:", "data:", "http://", "https://", "//")

# pastas que não são navegação de portal
IGNORAR_DIR = {".git", "_tools", "assets", "db", "supabase", ".github", "__pycache__"}

# onde moram os portais de médico — são estes que precisam de volta ao Hub
PASTAS_PORTAL = {"oxy", "cirurgias", "produtividade", "oxy-produtividade",
                 "cirurgias-produtividade", "dashboard-insights"}


def paginas() -> list:
    out = []
    for p in sorted(REPO.rglob("*.html")):
        if any(x in IGNORAR_DIR for x in p.relative_to(REPO).parts[:-1]):
            continue
        out.append(p)
    return out


def links(p: Path) -> list:
    """(href cru, destino resolvido) dos links relativos da página."""
    t = p.read_text(encoding="utf-8", errors="replace")
    out = []
    for h in HREF_RE.findall(t):
        if h.startswith(PULAR) or not h.strip():
            continue
        # href montado em JavaScript (`${slug}_Produtividade.html`): o destino
        # só existe em tempo de execução, não dá para conferir em disco.
        if "${" in h:
            continue
        limpo = urllib.parse.unquote(h.split("?")[0].split("#")[0])
        if not limpo:
            continue
        # o site é servido na raiz do domínio (portalendovascularsp.com.br),
        # então '/hub/...' sai da raiz do repositório, não da pasta do arquivo.
        alvo = ((REPO / limpo.lstrip("/")) if limpo.startswith("/")
                else (p.parent / limpo)).resolve()
        # link de pasta: o servidor entrega o index.html de dentro
        if limpo.endswith("/"):
            alvo = alvo / "index.html"
        out.append((h, alvo))
    return out


def main(so: str | None):
    quebrados, sem_volta, mao_unica = [], [], []
    mapa: dict = {}

    for p in paginas():
        rel = p.relative_to(REPO).as_posix()
        if so and so not in rel:
            continue
        destinos = set()
        for h, alvo in links(p):
            if not alvo.exists():
                quebrados.append((rel, h))
                continue
            try:
                destinos.add(alvo.relative_to(REPO).as_posix())
            except ValueError:
                pass                      # link para fora do repositório
        mapa[rel] = destinos

        # Todo portal de médico tem de ter caminho de volta ao Hub. O próprio
        # Hub é a home — não precisa apontar para si — e os módulos internos
        # (Compras, Atendimentos…) têm navegação própria, fora deste escopo.
        pasta = rel.split("/")[0] if "/" in rel else ""
        if pasta in PASTAS_PORTAL or (pasta == "" and "MODO_MEDICO = true" in
                                      p.read_text(encoding="utf-8", errors="replace")):
            if not any(d.startswith("hub/") for d in destinos):
                sem_volta.append(rel)

    # mão única só entre páginas de portal (Hub é ponto de partida, não precisa
    # ser apontado de volta por todo mundo)
    for origem, destinos in mapa.items():
        for d in destinos:
            if d not in mapa or d.startswith("hub/") or origem.startswith("hub/"):
                continue
            if d.endswith("index.html") or origem.endswith("index.html"):
                continue
            if origem not in mapa[d]:
                mao_unica.append((origem, d))

    print(f"\n=== Varredura de navegação · {len(mapa)} páginas ===")

    print(f"\n--- 1) links quebrados: {len(quebrados)} ---")
    for rel, h in quebrados:
        print(f"  {rel[:56]:58s} -> {h[:60]}")

    print(f"\n--- 2) páginas sem volta para o Hub: {len(sem_volta)} ---")
    for rel in sem_volta:
        print(f"  {rel}")

    print(f"\n--- 3) navegação de mão única: {len(mao_unica)} ---")
    for a, b in mao_unica:
        print(f"  {a[:52]:54s} -> {b[:52]}  (sem volta)")

    orfaos = portais_sem_botao(so)
    print(f"\n--- 4) portal que existe mas não tem botão no Hub: {len(orfaos)} ---")
    for hub, arq in orfaos:
        print(f"  {hub[:34]:36s} não abre {arq}")

    return 1 if (quebrados or sem_volta or mao_unica or orfaos) else 0


# um portal por ambiente, no caminho que o Hub usaria
ENVS = [
    ("{slug}.html",                                          "Recebimento Endo"),
    ("oxy/{slug}_Oxy_Recovery.html",                          "Recebimento Oxy"),
    ("cirurgias/{slug}.html",                                 "Recebimento Cirurgias"),
    ("produtividade/{slug}_Produtividade.html",               "Produtividade Endo"),
    ("oxy-produtividade/{slug}_Oxy_Produtividade.html",       "Produtividade Oxy"),
    ("cirurgias-produtividade/{slug}_Cirurgias_Produtividade.html", "Produtividade Cirurgias"),
    ("dashboard-insights/{slug}_Insights.html",               "Insights"),
]


def portais_sem_botao(so: str | None) -> list:
    """Portal que existe em disco e o Hub do dono não aponta para ele.

    Não dá link quebrado nem mão única — o portal simplesmente não é alcançável
    por quem não sabe a URL. Foi o caso do 🔬 na Produtividade antes de
    14/08/2026."""
    out = []
    for hub in sorted((REPO / "hub").glob("*_Hub.html")):
        if hub.name == "Gestor_Hub.html":
            continue
        slug = hub.name[:-len("_Hub.html")]
        if so and so not in hub.name:
            continue
        t = hub.read_text(encoding="utf-8", errors="replace")
        for molde, rotulo in ENVS:
            caminho = molde.format(slug=slug)
            if not (REPO / caminho).exists():
                continue
            if f'"../{caminho}' not in t and f"'../{caminho}" not in t:
                out.append((hub.name, f"{rotulo} ({caminho})"))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", help="filtra pelo caminho")
    raise SystemExit(main(ap.parse_args().so))
