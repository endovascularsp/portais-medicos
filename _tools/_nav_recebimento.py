# -*- coding: utf-8 -*-
"""
_nav_recebimento.py — refaz a barra "Meus Portais" dos portais de Recebimento.

Irmão do `_onboard_prod_cirurgias.py`, que faz o mesmo na Produtividade. A barra
é montada a partir do que EXISTE em disco, então resolve os dois defeitos que a
varredura de 14/08/2026 encontrou:

  - **botão que falta**: Andrea, Eduardo e João Fukuda tinham portal de
    Cirurgias, mas o portal Endo deles não trazia o 🔬 — dava para entrar em
    Cirurgias pelo Hub e não dava para voltar por dentro;
  - **botão que sobra**: Mateus apontava para um portal Endo que não existe, e
    Gustavo e Simone Denise David para portais Oxy que nunca existiram. Em
    produção o UX6-HIDE-404 esconde esses botões, então ninguém reclamava — mas
    o link errado ficava lá.

Regra de ouro da classe do botão (o mesmo tropeço já aconteceu no admin da
Produtividade): a classe do ambiente ATUAL leva `active`, que tem
`pointer-events:none`. Um LINK nunca pode nascer com ela.

Uso:
    python _tools/_nav_recebimento.py             # simula
    python _tools/_nav_recebimento.py --escrever
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# (chave, pasta, sufixo, classe, rótulo)
AMB = [
    ("endo", "",          "",              "endo", "🏥 Endovascular SP"),
    ("oxy",  "oxy",       "_Oxy_Recovery", "oxy",  "💊 Oxy Recovery"),
    ("cir",  "cirurgias", "",              "cir",  "🔬 Cirurgias"),
]
NAV_RE = re.compile(r"<div class='portais-nav'>.*?</div>", re.S)


def arquivo(amb: str, slug: str) -> Path:
    _k, pasta, sufixo, _c, _r = next(a for a in AMB if a[0] == amb)
    return REPO / pasta / f"{slug}{sufixo}.html" if pasta else REPO / f"{slug}.html"


def barra(slug: str, atual: str) -> str:
    tem = [a for a in AMB if arquivo(a[0], slug).exists()]
    partes = ["<div class='portais-nav'>",
              "<span class='portais-nav-label'>Meus Portais</span>"]
    for k, pasta, sufixo, cls, rot in tem:
        if k == atual:
            partes.append(f"<a class='portais-nav-btn {cls} active'>{rot}</a>")
        else:
            prefixo = "../" if atual != "endo" else ""
            destino = f"{pasta}/{slug}{sufixo}.html" if pasta else f"{slug}.html"
            partes.append(f"<a href='{prefixo}{destino}' class='portais-nav-btn {cls}'>{rot}</a>")
    return "".join(partes) + "</div>"


def alvos() -> list:
    """Portais de médico do Recebimento: MODO_MEDICO = true e barra de portais."""
    out = []
    for amb, pasta, sufixo, _c, _r in AMB:
        base = REPO / pasta if pasta else REPO
        for p in sorted(base.glob("*.html")):
            if p.name == "index.html" or p.parent != base:
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            if not re.search(r"MODO_MEDICO\s*=\s*true", t):
                continue
            slug = p.name[:-len(sufixo + ".html")] if sufixo else p.stem
            # É portal de médico quem tem Hub. Sem esse teste entram arquivos
            # internos da raiz (Agendamento Cirúrgico, Enfermagem), que também
            # rodam com senha mas não pertencem a ninguém.
            if not (REPO / "hub" / f"{slug}_Hub.html").exists():
                continue
            out.append((amb, p, slug))
    return out


def main(escrever: bool) -> int:
    print(f"\n=== Barra 'Meus Portais' do Recebimento · escrever={escrever} ===\n")
    n = 0
    for amb, path, slug in alvos():
        t = velho = path.read_text(encoding="utf-8")
        nova = barra(slug, amb)
        m = NAV_RE.search(t)
        if not m:
            # Portal sem a barra (só a Dra. Daniela na Oxy, em 14/08/2026): ela
            # entra logo depois do cabeçalho, que é onde vive nos outros.
            k = t.find("</header>")
            if k < 0:
                print(f"  [PULADO] {path.relative_to(REPO)} — sem barra e sem </header>")
                continue
            k += len("</header>")
            t = t[:k] + "\n" + nova + t[k:]
            if escrever:
                path.write_text(t, encoding="utf-8")
            n += 1
            print(f"  {str(path.relative_to(REPO))[:52]:54s} barra criada "
                  f"({len(re.findall(r'<a ', nova))} botões)")
            continue
        if nova == m.group(0):
            continue
        t = t[:m.start()] + nova + t[m.end():]
        antes = len(re.findall(r"<a ", m.group(0)))
        depois = len(re.findall(r"<a ", nova))
        if escrever:
            path.write_text(t, encoding="utf-8")
        n += 1
        print(f"  {str(path.relative_to(REPO))[:52]:54s} {antes} -> {depois} botões")
    print(f"\n  {n} arquivo(s)")
    if not escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(main(ap.parse_args().escrever))
