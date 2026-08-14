# -*- coding: utf-8 -*-
"""
_onboard_prod_cirurgias.py — cria o 3º ambiente da Produtividade: Cirurgias.

Pedido do Thiago em 14/08/2026: a Produtividade tem de ter os mesmos 3
ambientes do Recebimento (Endovascular SP · Oxy Recovery · Cirurgias). Só ficou
possível quando a Produtividade passou a ler o relatório #560 do SVN, que traz
CATEGORIA por procedimento — a base antiga não tinha, e por isso a cirurgia
ficava misturada dentro da Endovascular.

Metade da Produtividade da Endovascular é cirurgia (R$ 2,34 mi de R$ 4,70 mi
entre Jan e Jul/2026), então este script MUDA MUITO o número que os 8
profissionais com cirurgia veem no portal Endo. Isso é o esperado.

O que faz (tudo idempotente — rodar de novo não duplica nada):
  1. cria `cirurgias-produtividade/index.html` a partir do admin do Endo;
  2. cria um portal individual por profissional com cirurgia, clonando o portal
     Endo DO PRÓPRIO profissional (mesmo nome dentro do arquivo — nenhuma troca
     de nome, que é a parte que costuma dar errado ao clonar de terceiros);
  3. refaz a barra "Meus Portais" dos 3 ambientes, mostrando só os que existem.

Não injeta dados: quem faz isso é
    python _tools/_produtividade_publicar.py --instituicao cir --escrever
    python _tools/_produtividade_publicar.py --instituicao endo --escrever

Uso:
    python _tools/_onboard_prod_cirurgias.py             # simula
    python _tools/_onboard_prod_cirurgias.py --escrever
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_catalogo as CAT       # noqa: E402
import _produtividade_gerar as G         # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# (chave, pasta, sufixo, emoji, rótulo quando há mais de um, classe do link)
AMBIENTES = [
    ("endo", "produtividade",           "_Produtividade",           "📊", "Prod. Endo",      "prod-endo"),
    ("oxy",  "oxy-produtividade",       "_Oxy_Produtividade",       "💊", "Prod. Oxy",       "prod-oxy"),
    ("cir",  "cirurgias-produtividade", "_Cirurgias_Produtividade", "🔬", "Prod. Cirurgias", "prod-cir"),
]
PASTA = {a[0]: a[1] for a in AMBIENTES}
SUFIXO = {a[0]: a[2] for a in AMBIENTES}

# Mesmo âmbar do 🔬 Cirurgias do Recebimento — o médico já associa a cor ao
# ambiente. Ver a memória sobre identidade visual de cada ambiente.
CSS_CIR = (".portais-nav-btn.prod-cir{color:#f5a623;border-color:rgba(245,166,35,0.40);"
           "background:rgba(245,166,35,0.08);}\n"
           ".portais-nav-btn.prod-cir:hover{background:rgba(245,166,35,0.22);border-color:#f5a623;}\n")
CSS_CIR_ADMIN = (".admin-nav-btn.prod-cir{color:#f5a623;border-color:rgba(245,166,35,0.35);"
                 "background:rgba(245,166,35,0.08);}\n"
                 ".admin-nav-btn.prod-cir:hover{background:rgba(245,166,35,0.20);border-color:#f5a623;}\n")

NAV_RE = re.compile(r"<div class='portais-nav'>.*?</div>", re.S)
ADMIN_NAV_RE = re.compile(r"<nav class='admin-nav'>.*?</nav>", re.S)


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


def existe(amb: str, slug: str) -> bool:
    return (REPO / PASTA[amb] / f"{slug}{SUFIXO[amb]}.html").exists()


# ── 1) admin ────────────────────────────────────────────────────────────────
def criar_admin(escrever: bool) -> str:
    origem = REPO / "produtividade" / "index.html"
    destino = REPO / "cirurgias-produtividade" / "index.html"
    if destino.exists():
        return "já existe"
    t = origem.read_text(encoding="utf-8")

    t = t.replace("<title>Admin — Produtividade Endovascular SP</title>",
                  "<title>Admin — Produtividade Cirurgias</title>", 1)
    # os 2 links "Abrir portal" da tela apontam para o arquivo do profissional
    if t.count("_Produtividade.html") != 2:
        raise SystemExit(f"ABORTADO: esperava 2 links de portal, achei {t.count('_Produtividade.html')}")
    t = t.replace("_Produtividade.html", "_Cirurgias_Produtividade.html")

    # o admin novo nasce vazio: quem enche é o _produtividade_publicar.py
    t = re.sub(r"(const DADOS_RAW\s*=\s*)\{.*?\};", r"\1{};", t, count=1, flags=re.S)
    t = re.sub(r"(const PORDER\s*=\s*)\[.*?\];", r"\1[];", t, count=1, flags=re.S)

    m = ADMIN_NAV_RE.search(t)
    if not m:
        raise SystemExit("ABORTADO: admin sem <nav class='admin-nav'>")
    t = t[:m.start()] + nav_admin("cir") + t[m.end():]
    t = injeta_css(t, CSS_CIR_ADMIN, ".admin-nav-btn.")

    if escrever:
        destino.parent.mkdir(exist_ok=True)
        destino.write_text(t, encoding="utf-8")
    return f"criado ({len(t):,} chars)"


def nav_admin(atual: str) -> str:
    """Barra de navegação entre os 3 admins de Produtividade."""
    partes = ["<nav class='admin-nav'>", "<span class='admin-nav-label'>Meus Portais</span>"]
    rotulos = {"endo": "🏥 Endovascular SP", "oxy": "💊 Oxy Recovery", "cir": "🔬 Cirurgias"}
    classes = {"endo": "prod", "oxy": "prod-oxy", "cir": "prod-cir"}
    for k, pasta, _s, _e, _r, _c in AMBIENTES:
        if k == atual:
            partes.append(f"<a href='#' class='admin-nav-btn {classes[k]} active'>{rotulos[k]}</a>")
        else:
            partes.append(f"<a href='../{pasta}/' class='admin-nav-btn {classes[k]}'>{rotulos[k]}</a>")
    partes.append("</nav>")
    return "\n".join(partes)


def injeta_css(t: str, css: str, prefixo: str) -> str:
    if css.split("{")[0] in t:
        return t
    ult = None
    for m in re.finditer(re.escape(prefixo) + r"[a-z-]+(?::hover)?\{[^}]*\}\n?", t):
        ult = m
    if not ult:
        raise SystemExit(f"ABORTADO: não achei onde encaixar o CSS de {prefixo}")
    return t[:ult.end()] + css + t[ult.end():]


# ── 2) portais individuais ──────────────────────────────────────────────────
def criar_portais(profs: list, escrever: bool) -> list:
    out = []
    for prof in profs:
        slug = slugify(prof)
        origem = REPO / "produtividade" / f"{slug}_Produtividade.html"
        destino = REPO / "cirurgias-produtividade" / f"{slug}_Cirurgias_Produtividade.html"
        if destino.exists():
            out.append((prof, "já existe"))
            continue
        if not origem.exists():
            out.append((prof, "SEM PORTAL ENDO PARA CLONAR"))
            continue
        t = origem.read_text(encoding="utf-8")
        # o nome do profissional é o mesmo: nada de troca de nome aqui.
        n = t.count("<div class='header-sub'>Endovascular SP</div>")
        if n != 1:
            out.append((prof, f"header-sub aparece {n}x — não mexi"))
            continue
        t = t.replace("<div class='header-sub'>Endovascular SP</div>",
                      "<div class='header-sub'>Cirurgias</div>", 1)
        if escrever:
            destino.parent.mkdir(exist_ok=True)
            destino.write_text(t, encoding="utf-8")
        out.append((prof, f"criado ({len(t):,} chars)"))
    return out


# ── 3) barra "Meus Portais" dos portais individuais ─────────────────────────
def nav_individual(slug: str, atual: str, t: str) -> str:
    """Refaz a barra mostrando só os ambientes que o profissional TEM.

    O botão do ambiente atual é reaproveitado como está no arquivo — cada pasta
    tem o seu (o Oxy, por exemplo, roda em tema claro invertido e não usa a
    classe `active`). Só o texto muda: com um ambiente só, o rótulo é
    "Produtividade"; com mais de um, "Prod. Endo"/"Prod. Oxy"/"Prod. Cirurgias".
    """
    m = NAV_RE.search(t)
    if not m:
        return t
    barra = m.group(0)
    atuais = re.findall(r"<a (?![^>]*href)[^>]*>.*?</a>", barra, re.S)
    if len(atuais) != 1:
        return t
    botao = atuais[0]

    tenho = [k for k, *_ in AMBIENTES if k == atual or existe(k, slug)]
    emoji = {k: e for k, _p, _s, e, _r, _c in AMBIENTES}
    rot = {k: r for k, _p, _s, _e, r, _c in AMBIENTES}
    cls = {k: c for k, _p, _s, _e, _r, c in AMBIENTES}

    texto = f"{emoji[atual]} {rot[atual] if len(tenho) > 1 else 'Produtividade'}"
    botao = re.sub(r">[^<]*</a>$", f">{texto}</a>", botao)
    # O portal de Cirurgias nasceu clonado do Endo e veio com a classe do Endo.
    # Fica igual ao Recebimento, onde o botão do ambiente atual é `cir active`.
    if atual == "cir":
        botao = re.sub(r"class='portais-nav-btn[^']*'",
                       "class='portais-nav-btn prod-cir active'", botao)

    partes = ["<div class='portais-nav'>",
              "<span class='portais-nav-label'>Meus Portais</span>"]
    for k, pasta, sufixo, e, r, c in AMBIENTES:
        if k not in tenho:
            continue
        if k == atual:
            partes.append(botao)
        else:
            partes.append(f"<a href='../{pasta}/{slug}{sufixo}.html' "
                          f"class='portais-nav-btn {c}'>{e} {r}</a>")
    nova = "".join(partes) + "</div>"
    return t[:m.start()] + nova + t[m.end():]


def arrumar_navs(escrever: bool) -> list:
    out = []
    for amb, pasta, sufixo, _e, _r, _c in AMBIENTES:
        dir_ = REPO / pasta
        if not dir_.exists():
            continue
        for path in sorted(dir_.glob(f"*{sufixo}.html")):
            if path.name == "index.html":
                continue
            slug = path.name[:-len(sufixo + ".html")]
            t = velho = path.read_text(encoding="utf-8")
            t = injeta_css(t, CSS_CIR, ".portais-nav-btn.")
            t = nav_individual(slug, amb, t)
            if t == velho:
                continue
            if escrever:
                path.write_text(t, encoding="utf-8")
            out.append(str(path.relative_to(REPO)))
    # os 2 admins antigos ganham o 3º botão
    for amb in ("endo", "oxy"):
        path = REPO / PASTA[amb] / "index.html"
        t = velho = path.read_text(encoding="utf-8")
        m = ADMIN_NAV_RE.search(t)
        if not m:
            continue
        t = t[:m.start()] + nav_admin(amb) + t[m.end():]
        t = injeta_css(t, CSS_CIR_ADMIN, ".admin-nav-btn.")
        if t == velho:
            continue
        if escrever:
            path.write_text(t, encoding="utf-8")
        out.append(str(path.relative_to(REPO)))
    return out


def main(escrever: bool):
    profs = sorted(G.montar("cir", CAT.carregar()))
    print(f"\n=== Produtividade · 3º ambiente (Cirurgias) · escrever={escrever} ===")
    print(f"\n  {len(profs)} profissionais com cirurgia: {', '.join(p.split()[0] for p in profs)}")

    print(f"\n--- admin ---\n  cirurgias-produtividade/index.html: {criar_admin(escrever)}")

    print("\n--- portais individuais ---")
    for prof, res in criar_portais(profs, escrever):
        print(f"  {prof[:34]:36s} {res}")

    print("\n--- barra 'Meus Portais' ---")
    for p in arrumar_navs(escrever):
        print(f"  {p}")

    if not escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")
    else:
        print("\nAgora rode:\n"
              "  python _tools/_produtividade_publicar.py --instituicao cir  --escrever\n"
              "  python _tools/_produtividade_publicar.py --instituicao endo --escrever")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    main(ap.parse_args().escrever)
