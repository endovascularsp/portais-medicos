# -*- coding: utf-8 -*-
"""
_honorarios_criar_insights.py — cria o Dashboard de Insights de um médico.

Diferente dos portais de Recebimento, o Insights NÃO carrega dados próprios: ele
busca os portais do médico (`FONTES`) e decripta na hora, com a senha que o médico
digita. Por isso criar um é clonagem + troca de identidade, sem injetar PDATA.

Também acrescenta o card 💡 Dashboard de Insights ao Hub, quando falta.

Uso:
    python _tools/_honorarios_criar_insights.py --prof "Simone Denise David" --dry-run
    python _tools/_honorarios_criar_insights.py --prof "Simone Denise David"
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO = Path(__file__).resolve().parent.parent
PASTA = REPO / "dashboard-insights"
VER = "20260805"


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


CARD = """
          <div class="hub-card insights" id="card-insights">
            <div class="hub-card-icon">&#x1F4A1;</div>
            <div class="hub-card-title">Dashboard de Insights</div>
            <div class="hub-card-desc">Top pacientes, top procedimentos<br>e indicadores de performance</div>
            <div class="hub-card-links">
                <a href="../dashboard-insights/{slug}_Insights.html?v={ver}" onclick="navegar(this,event)" class="hub-sub-btn insights">
                  &#x1F4C8; Acessar Insights
                </a>
            </div>
          </div>"""


def main(prof: str, modelo: str, dry_run: bool):
    slug = slugify(prof)
    alvo = PASTA / f"{slug}_Insights.html"
    hub = REPO / "hub" / f"{slug}_Hub.html"
    print(f"=== Insights · {prof} ===")
    if alvo.exists():
        raise SystemExit(f"ABORTADO: {alvo.relative_to(REPO)} já existe.")
    if not hub.exists():
        raise SystemExit(f"ABORTADO: Hub não existe ({hub.name}).")

    tmpl = PASTA / f"{slugify(modelo)}_Insights.html"
    if not tmpl.exists():
        raise SystemExit(f"ABORTADO: modelo não existe ({tmpl.name}).")
    t_slug, t_nome = slugify(modelo), modelo

    html = tmpl.read_text(encoding="utf-8")
    html = html.replace(t_nome, prof).replace(t_slug, slug)
    if t_nome.split()[0] != prof.split()[0]:
        html = html.replace(t_nome.split()[0], prof.split()[0])
    resto = t_nome.split()[0]
    if resto in html:
        raise SystemExit(f"ABORTADO: sobrou {resto!r} do modelo.")

    # as FONTES têm que apontar para portais deste médico
    fontes = re.findall(r"url:\s*'([^']+)'", html)
    if not fontes or any(slug not in f for f in fontes):
        raise SystemExit(f"ABORTADO: FONTES não ficaram no nome certo: {fontes}")
    existem = [f for f in fontes if (PASTA / f).resolve().exists()]
    print(f"  fontes .....: {len(fontes)} declaradas · {len(existem)} existem hoje")
    for f in fontes:
        print(f"      {'OK ' if (PASTA / f).resolve().exists() else '-- '} {f}")
    if not existem:
        raise SystemExit("ABORTADO: nenhum portal do médico existe; o Insights abriria vazio.")

    ht = hub.read_text(encoding="utf-8")
    add_card = 'id="card-insights"' not in ht
    if add_card:
        cont = re.search(r'(<div class="hub-card [a-z]+" id="card-(?:rec|prod)">)', ht)
        if not cont:
            raise SystemExit("ABORTADO: Hub sem card de Recebimento ou Produtividade "
                             "para me orientar onde inserir o de Insights.")
        # entra depois do ÚLTIMO card existente
        ult = None
        for m in re.finditer(r'<div class="hub-card [a-z]+" id="card-[a-z]+">', ht):
            ult = m
        i, prof_div, k = ult.start(), 0, ult.start()
        while k < len(ht):
            if ht.startswith("<div", k):
                prof_div += 1; k += 4
            elif ht.startswith("</div>", k):
                prof_div -= 1; k += 6
                if prof_div == 0:
                    break
            else:
                k += 1
        ht = ht[:k] + CARD.format(slug=slug, ver=VER) + ht[k:]
        if ht.count("<div") != ht.count("</div>"):
            raise SystemExit("ABORTADO: o Hub ficaria com as divs desbalanceadas.")
        if ht.count('id="card-insights"') != 1:
            raise SystemExit("ABORTADO: card de Insights duplicado.")
        print("  hub ........: card 💡 Insights inserido")
    else:
        print("  hub ........: já tinha o card de Insights")

    print(f"  portal .....: {alvo.relative_to(REPO)} ({len(html):,} chars)")
    if dry_run:
        print("\n[dry-run] nada gravado.")
        return
    alvo.write_text(html, encoding="utf-8")
    if add_card:
        hub.write_text(ht, encoding="utf-8")
    print("\nCriado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prof", required=True)
    ap.add_argument("--modelo", default="João Fukuda")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.prof, a.modelo, a.dry_run)
