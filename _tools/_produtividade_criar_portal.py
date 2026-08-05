# -*- coding: utf-8 -*-
"""
_produtividade_criar_portal.py — cria o portal individual de Produtividade de um
profissional, a partir dos dados que já estão no admin.

Diferente do Insights (que busca os portais em tempo real) e do Recebimento (que
lê do Supabase), a Produtividade guarda os dados DENTRO do próprio arquivo, num
blob criptografado com a chave do profissional:

    { "Nome": { profissional, empresa, periodos: { "2026-05": {label, resumo,
                                                               atendimentos} } } }

A fonte é o `const DADOS` do admin — que é texto puro e já tem tudo.

Uso:
    python _tools/_produtividade_criar_portal.py --prof "Nicole Tenenbaum Szajubok" --dry-run
    python _tools/_produtividade_criar_portal.py --prof "Nicole Tenenbaum Szajubok"
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_publicar as P  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
VER = "20260805"
PDATA_RE = re.compile(r"/\*PDATA\*/'([A-Za-z0-9+/=]+)'/\*PDATA\*/")

AMBIENTE = {
    "Endovascular SP": ("produtividade", "_Produtividade", "🏥 Endovascular SP"),
    "Oxy Recovery":    ("oxy-produtividade", "_Oxy_Produtividade", "💊 Oxy Recovery"),
}

CARD = """
          <div class="hub-card prod" id="card-prod">
            <div class="hub-card-icon">&#x1F4CA;</div>
            <div class="hub-card-title">Produtividade</div>
            <div class="hub-card-desc">Atendimentos realizados<br>e procedimentos por período</div>
            <div class="hub-card-links">
                <a href="../{pasta}/{slug}{sufixo}.html?v={ver}" onclick="navegar(this,event)" class="hub-sub-btn prod-btn">
                  {rotulo}
                </a>
            </div>
          </div>"""


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


def json_apos(t: str, i: int) -> str:
    d, k, ins, esc = 0, i, False, False
    while k < len(t):
        c = t[k]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        else:
            if c == '"': ins = True
            elif c == "{": d += 1
            elif c == "}":
                d -= 1
                if d == 0: return t[i:k + 1]
        k += 1
    raise SystemExit("ABORTADO: JSON não balanceado no admin.")


def main(prof: str, empresa: str, dry_run: bool):
    pasta, sufixo, rotulo = AMBIENTE[empresa]
    slug = slugify(prof)
    dir_alvo = REPO / pasta
    alvo = dir_alvo / f"{slug}{sufixo}.html"
    hub = REPO / "hub" / f"{slug}_Hub.html"
    print(f"=== Produtividade · {prof} · {empresa} ===")
    if alvo.exists():
        raise SystemExit(f"ABORTADO: {alvo.relative_to(REPO)} já existe.")
    if not hub.exists():
        raise SystemExit(f"ABORTADO: Hub não existe ({hub.name}).")

    chaves = P.carregar_chaves()
    if prof not in chaves:
        raise SystemExit(f"ABORTADO: sem chave para {prof!r}.")
    chave = chaves[prof]

    # --- dados, do admin ---
    at = (dir_alvo / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const DADOS\s*=\s*(\{)", at)
    dados = json.loads(json_apos(at, m.start(1)))
    if prof not in dados:
        raise SystemExit(f"ABORTADO: {prof} não está no admin de {pasta}.")
    periodos = {pid: v for pid, v in dados[prof].items() if (v or {}).get("n_atend")}
    if not periodos:
        raise SystemExit(f"ABORTADO: {prof} não tem atendimento em nenhum período.")
    interno = {"profissional": prof, "empresa": empresa, "periodos": {}}
    for pid in sorted(periodos):
        v = periodos[pid]
        interno["periodos"][pid] = {
            "label": v.get("label"),
            "resumo": {"total": v.get("total", 0), "n_atend": v.get("n_atend", 0),
                       "n_pacientes": v.get("n_pacientes", 0),
                       "por_pagamento": v.get("por_pagamento", {})},
            "atendimentos": v.get("atendimentos", []),
        }
        print(f"  {pid} {v.get('label'):16s} {v.get('n_atend'):3d} atend · "
              f"{v.get('n_pacientes')} pacientes · R$ {v.get('total', 0):>10,.2f}")

    # --- portal, clonando outro da mesma pasta ---
    cand = [p for p in sorted(dir_alvo.glob(f"*{sufixo}.html"))
            if p.name != "index.html" and p != alvo
            and (REPO / "hub" / f"{p.name[:-len(sufixo + '.html')]}_Hub.html").exists()]
    if not cand:
        raise SystemExit("ABORTADO: nenhum portal-modelo na pasta.")
    tmpl = min(cand, key=lambda p: p.stat().st_size)
    t_slug = tmpl.name[:-len(sufixo + ".html")]
    t_nome = t_slug.replace("_", " ")
    print(f"\n  modelo: {tmpl.relative_to(REPO)}  ({t_nome})")

    html = tmpl.read_text(encoding="utf-8")
    mm = PDATA_RE.search(html)
    if not mm:
        raise SystemExit("ABORTADO: modelo sem blob PDATA.")
    html = html[:mm.start(1)] + "__BLOB__" + html[mm.end(1):]
    html = html.replace(t_nome, prof).replace(t_slug, slug)
    if t_nome.split()[0] != prof.split()[0]:
        html = html.replace(t_nome.split()[0], prof.split()[0])
    html = html.replace("__BLOB__", P.cifrar({prof: interno}, chave))
    if t_nome.split()[0] in html:
        raise SystemExit(f"ABORTADO: sobrou {t_nome.split()[0]!r} do modelo.")
    volta = P.decifrar(PDATA_RE.search(html).group(1), chave)
    if prof not in volta or sorted(volta[prof]["periodos"]) != sorted(interno["periodos"]):
        raise SystemExit("ABORTADO: o portal gerado não devolve os mesmos períodos.")
    print(f"  portal .....: {alvo.relative_to(REPO)} ({len(html):,} chars) OK")

    # --- Hub: card de Produtividade + portais.prod ---
    ht = hub.read_text(encoding="utf-8")
    mb = re.search(r'const BLOB = "([^"]+)"', ht)
    dados_hub = P.decifrar(mb.group(1), chave)
    antes = dict(dados_hub.get("portais") or {})
    novo = dict(dados_hub)
    novo["portais"] = dict(antes)
    novo["portais"]["prod"] = f"../{pasta}/{slug}{sufixo}.html"
    ht = re.sub(r'const BLOB = "[^"]+"', 'const BLOB = "' + P.cifrar(novo, chave) + '"', ht, count=1)

    if 'id="card-prod"' not in ht:
        # A ordem dos cards nos outros Hubs é Recebimento -> Produtividade ->
        # Insights. Entra logo depois do de Recebimento; se não houver, depois do
        # último card, para não ficar fora do padrão.
        ancora = re.search(r'<div class="hub-card rec" id="card-rec">', ht)
        if not ancora:
            for x in re.finditer(r'<div class="hub-card [a-z]+" id="card-[a-z]+">', ht):
                ancora = x
        if not ancora:
            raise SystemExit("ABORTADO: Hub sem card algum para me orientar.")
        d, k = 0, ancora.start()
        while k < len(ht):
            if ht.startswith("<div", k): d += 1; k += 4
            elif ht.startswith("</div>", k):
                d -= 1; k += 6
                if d == 0: break
            else: k += 1
        ht = ht[:k] + CARD.format(pasta=pasta, slug=slug, sufixo=sufixo, ver=VER, rotulo=rotulo) + ht[k:]
        if ht.count("<div") != ht.count("</div>"):
            raise SystemExit("ABORTADO: divs desbalanceadas no Hub.")
        if ht.count('id="card-prod"') != 1:
            raise SystemExit("ABORTADO: card de Produtividade duplicado.")
        print("  hub ........: card 📊 Produtividade inserido")
    conf = P.decifrar(re.search(r'const BLOB = "([^"]+)"', ht).group(1), chave)
    perdidos = [k2 for k2, v2 in antes.items() if v2 and not conf["portais"].get(k2)]
    if perdidos:
        raise SystemExit(f"ABORTADO: o Hub perderia {perdidos}")
    print(f"  hub ........: portais {[k2 for k2, v2 in conf['portais'].items() if v2]}")

    if dry_run:
        print("\n[dry-run] nada gravado.")
        return
    alvo.write_text(html, encoding="utf-8")
    hub.write_text(ht, encoding="utf-8")
    print("\nCriado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prof", required=True)
    ap.add_argument("--empresa", default="Endovascular SP", choices=list(AMBIENTE))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.prof, a.empresa, a.dry_run)
