# -*- coding: utf-8 -*-
"""
_hub_prod_cirurgias.py — acerta o card 📊 Produtividade dos Hubs para os 3
ambientes (Endovascular SP · Oxy Recovery · Cirurgias).

Companheiro do `_onboard_prod_cirurgias.py`. Refaz os sub-botões do card a
partir do que EXISTE em disco, então serve para as três coisas de uma vez:
adicionar o 🔬 Cirurgias a quem passou a ter, remover o 🏥 de quem deixou de ter
(o Mateus, que é 100% cirurgia) e corrigir botão que aponta para arquivo que
nunca existiu.

Também mexe no `Gestor_Hub.html`, que lista os três admins.

O BLOB criptografado do Hub guarda um mapa `portais` que hoje NENHUMA tela lê em
tempo de execução — os cards são HTML fixo. Ele é metadado usado pelos scripts
de criação de portal, e por isso é atualizado junto: se ficar mentindo, o
próximo script que criar portal decide errado.

Uso:
    python _tools/_hub_prod_cirurgias.py             # simula
    python _tools/_hub_prod_cirurgias.py --escrever
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_publicar as P   # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# O console do Windows abre em cp1252 e morre no primeiro emoji do relatório.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:      # stdout redirecionado por outro script
    pass

# (chave no `portais`, pasta, sufixo, classe do botão, rótulo)
AMB = [
    ("prod",     "produtividade",           "_Produtividade",           "prod-btn", "🏥 Endovascular SP"),
    ("prod_oxy", "oxy-produtividade",       "_Oxy_Produtividade",       "oxy-prod", "💊 Oxy Recovery"),
    ("prod_cir", "cirurgias-produtividade", "_Cirurgias_Produtividade", "cir",      "🔬 Cirurgias"),
]

LINK = ('              <a href="../{pasta}/{slug}{sufixo}.html" onclick="navegar(this,event)" '
        'class="hub-sub-btn {cls}">\n                {rotulo}\n              </a>')


def slugify(nome: str) -> str:
    return unicodedata.normalize("NFC", nome).replace(" ", "_")


_CACHE_CHAVES = {}


def _chaves() -> dict:
    """Uma leitura só: `carregar_chaves` valida tudo e imprime um relatório
    inteiro a cada chamada — 20 vezes seguidas era só ruído."""
    if not _CACHE_CHAVES:
        _CACHE_CHAVES.update(P.carregar_chaves())
    return _CACHE_CHAVES


def bloco_links(t: str, card_id: str) -> tuple:
    """Devolve (inicio, fim) do <div class="hub-card-links"> do card pedido."""
    i = t.find(f'id="{card_id}"')
    if i < 0:
        return None
    j = t.find('<div class="hub-card-links">', i)
    if j < 0:
        return None
    k = t.find("</div>", j)
    return (t.index(">", j) + 1, k)


def arrumar_hub(path: Path, escrever: bool) -> str:
    slug = path.name[:-len("_Hub.html")]
    t = velho = path.read_text(encoding="utf-8")
    pos = bloco_links(t, "card-prod")
    if not pos:
        return "sem card de Produtividade"

    tem = [(k, pasta, sufixo, cls, rot) for k, pasta, sufixo, cls, rot in AMB
           if (REPO / pasta / f"{slug}{sufixo}.html").exists()]
    if not tem:
        return "nenhum portal de Produtividade — card não mexido"

    links = "\n" + "\n".join(
        LINK.format(pasta=pasta, slug=slug, sufixo=sufixo, cls=cls, rotulo=rot)
        for _k, pasta, sufixo, cls, rot in tem) + "\n          "
    t = t[:pos[0]] + links + t[pos[1]:]

    # o mapa `portais` do blob acompanha o que existe
    chaves = _chaves()
    nome = slug.replace("_", " ")
    if nome in chaves:
        m = re.search(r'const BLOB = "([^"]+)"', t)
        d = P.decifrar(m.group(1), chaves[nome])
        portais = dict(d.get("portais") or {})
        for k, pasta, sufixo, _c, _r in AMB:
            caminho = f"../{pasta}/{slug}{sufixo}.html"
            if (REPO / pasta / f"{slug}{sufixo}.html").exists():
                portais[k] = caminho
            else:
                portais.pop(k, None)
        d = dict(d, portais=portais)
        t = re.sub(r'const BLOB = "[^"]+"', 'const BLOB = "' + P.cifrar(d, chaves[nome]) + '"',
                   t, count=1)

    if t.count("<div") != t.count("</div>"):
        raise SystemExit(f"ABORTADO: divs desbalanceadas em {path.name}")
    if t == velho:
        return "sem mudança"
    if escrever:
        path.write_text(t, encoding="utf-8")
    return " + ".join(r for *_x, r in tem)


def arrumar_gestor(escrever: bool) -> str:
    path = REPO / "hub" / "Gestor_Hub.html"
    t = velho = path.read_text(encoding="utf-8")
    # o href carrega o ?v= do cache-bust, que muda a cada publicação — por isso
    # a âncora é por regex, não por texto fixo.
    m = re.search(r'<a href="\.\./oxy-produtividade/[^"]*"[^>]*>\s*💊 Oxy Recovery\s*</a>', t)
    if not m:
        return "âncora do card de Produtividade não encontrada"
    if "cirurgias-produtividade/" in t:
        return "já tem o link de Cirurgias"
    novo = m.group(0) + ("\n          <a href=\"../cirurgias-produtividade/\" onclick=\"navegar(this,event)\" "
                         "class=\"hub-sub-btn prod-cir\">\n            🔬 Cirurgias\n          </a>")
    t = t[:m.start()] + novo + t[m.end():]
    if ".hub-sub-btn.prod-cir{" not in t:
        m = re.search(r"\.hub-sub-btn\.prod-oxy\{[^}]*\}", t)
        if not m:
            return "não achei o CSS do botão de Produtividade Oxy"
        t = (t[:m.end()] +
             "\n    .hub-sub-btn.prod-cir{color:#f5a623;border-color:rgba(245,166,35,0.35);"
             "background:rgba(245,166,35,0.08)}"
             "\n    .hub-sub-btn.prod-cir:hover{background:rgba(245,166,35,0.20);border-color:#f5a623}"
             + t[m.end():])
    if t == velho:
        return "sem mudança"
    if escrever:
        path.write_text(t, encoding="utf-8")
    return "link 🔬 Cirurgias inserido"


def main(escrever: bool):
    print(f"\n=== Hubs · card de Produtividade com 3 ambientes · escrever={escrever} ===\n")
    for path in sorted((REPO / "hub").glob("*_Hub.html")):
        if path.name == "Gestor_Hub.html":
            continue
        res = arrumar_hub(path, escrever)
        if res in ("sem mudança", "sem card de Produtividade"):
            continue
        print(f"  {path.name[:-9][:32]:34s} {res}")
    print(f"\n  Gestor_Hub.html: {arrumar_gestor(escrever)}")
    if not escrever:
        print("\n[simulação] nada gravado. Rode com --escrever.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    main(ap.parse_args().escrever)
