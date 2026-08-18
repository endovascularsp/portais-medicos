# -*- coding: utf-8 -*-
r"""
_auditar_filtros_botoes.py — varre TODOS os portais e responde três perguntas:

1. **Os filtros se acumulam?** Categoria, Tabela e Profissional têm de conviver.
   Em 18/08/2026 o Thiago descobriu que Profissional não era filtro, era atalho
   de navegação: filtrar "Simone Matsuda + Produtos" mostrava a soma dos três
   profissionais. Corrigido nos 3 dashboards do Gestor; esta varredura existe
   para achar onde mais ficou faltando.

2. **Os botões funcionam?** Um `onclick="fn()"` cuja função não existe no arquivo
   é um botão que não faz nada — e não dá erro visível, só não responde.

3. **O código procura elemento que não existe?** `getElementById('x')` sem o id
   `x` no HTML devolve null; a atribuição de innerHTML estoura e a função morre
   ANTES de fazer qualquer coisa, sem mensagem na tela. Foi assim que a aba
   Catálogo abriu inteiramente vazia em 11/08/2026 e pareceu problema de
   permissão por horas.

Só leitura. Não altera nenhum arquivo.

Uso:
    python _tools/_auditar_filtros_botoes.py
    python _tools/_auditar_filtros_botoes.py --detalhe    # lista item a item
"""
from __future__ import annotations
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = Path(__file__).resolve().parent.parent

# Funções que o navegador fornece — não são "órfãs" quando não achamos a
# definição no arquivo.
NATIVAS = {
    "alert", "confirm", "print", "open", "close", "reload", "focus", "blur",
    "history", "location", "window", "document", "event", "return", "this",
    # palavras-chave que aparecem em `onclick="if(...)"` e não são função
    "if", "for", "while", "switch", "typeof", "new", "delete", "void",
}

# Ids que só existem depois que o JS cria o elemento, ou que vêm de biblioteca.
IDS_DINAMICOS = re.compile(r"^(sb-|chart-|tab-|aba-|painel-|view-)")


def grupos():
    """Os portais, por ambiente. O que não existir é ignorado sem reclamar."""
    def html(pasta, excluir=()):
        p = REPO / pasta if pasta else REPO
        if not p.is_dir():
            return []
        return [f for f in sorted(p.glob("*.html")) if f.name not in excluir]

    return [
        ("Recebimento — Endovascular SP", html("", excluir=("index.html", "recebimento.html"))),
        ("Recebimento — Oxy", html("oxy", excluir=("index.html",))),
        ("Recebimento — Cirurgias", html("cirurgias", excluir=("index.html",))),
        ("Produtividade — Endo", html("produtividade")),
        ("Produtividade — Oxy", html("oxy-produtividade")),
        ("Produtividade — Cirurgias", html("cirurgias-produtividade")),
        ("Dashboards do Gestor", [REPO / "recebimento.html", REPO / "oxy" / "index.html",
                                  REPO / "cirurgias" / "index.html"]),
        ("Hubs", html("hub")),
    ]


def js_de(txt: str) -> str:
    """Junta o JavaScript embutido, ignorando <script src=...>."""
    return "\n".join(m.group(1) for m in
                     re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", txt, re.S))


def analisar(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf-8", errors="replace")
    js = js_de(txt)

    # ── botões órfãos ────────────────────────────────────────────────────
    chamadas = set(re.findall(r'on(?:click|change|input|submit)\s*=\s*["\']([A-Za-z_$][\w$]*)\s*\(',
                              txt))
    definidas = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", js))
    definidas |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()", js))
    definidas |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", js))
    orfas = sorted(c for c in chamadas if c not in definidas and c not in NATIVAS)

    # ── ids procurados que não existem no HTML ───────────────────────────
    procurados = set(re.findall(r"getElementById\(\s*['\"]([^'\"]+)['\"]", js))
    existentes = set(re.findall(r"""\bid\s*=\s*['"]([^'"]+)['"]""", txt))
    # ids criados dentro de strings de template pelo próprio JS
    existentes |= set(re.findall(r"""id=[\\]?['"]?\+?\s*['"]?([a-zA-Z0-9\-_]+)""", js))
    sumidos = sorted(i for i in procurados
                     if i not in existentes and not IDS_DINAMICOS.match(i))

    # ── filtros ──────────────────────────────────────────────────────────
    tem_barra = bool(re.search(r"cat-filtro|tab-filtro|prof-filtro", txt))
    filtros = {
        "categoria": "cat-filtro" in txt,
        "tabela": "tab-filtro" in txt,
        "profissional": "prof-filtro" in txt,
    }
    # DUAS CONVENÇÕES CONVIVEM, e ignorar isso gera falso positivo em massa:
    #   Recebimento  -> filtro vazio ('') significa "sem filtro"
    #   Produtividade-> a sentinela é a string 'todas'
    # A pergunta é a mesma nos dois: categoria e tabela entram no MESMO teste,
    # ligadas por &&? Se entram, os filtros se somam.
    combina_cat_tab = bool(re.search(
        r"(!FILTRO_CATEGORIA\s*\|\||FILTRO_CATEGORIA\s*===\s*'todas'\s*\|\|)"
        r".{0,160}&&.{0,80}FILTRO_TABELA", js, re.S))

    # Profissional: ou é filtro que convive (Recebimento, depois de 18/08), ou é
    # navegação que RELÊ o select a cada render — que na prática também acumula,
    # porque mudar a categoria mantém a pessoa escolhida (Produtividade).
    acumula_filtro = bool(re.search(r"_soDoProfFiltrado", js))
    acumula_navegando = bool(re.search(
        r"getElementById\('prof-filtro'\)[^\n]*\n?[^\n]*value", js)) and \
        bool(re.search(r"function render\(\)", js))
    acumula = acumula_filtro or acumula_navegando

    # Navegação que NÃO relê: escolher a pessoa troca de tela e a próxima
    # mudança de filtro devolve para a visão geral, perdendo a seleção. Era o
    # caso do Recebimento até 18/08 — o defeito que o Thiago achou.
    navega = (bool(re.search(r"function filtrarPorProf\([^)]*\)\s*\{\s*if\(!profKey\)", js))
              and not acumula_filtro)

    return {"orfas": orfas, "sumidos": sumidos, "tem_barra": tem_barra,
            "filtros": filtros, "acumula": acumula, "combina": combina_cat_tab,
            "navega": navega}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    a = ap.parse_args()

    problemas = 0
    for titulo, arquivos in grupos():
        arquivos = [f for f in arquivos if f.exists()]
        if not arquivos:
            continue
        print(f"\n{'='*92}\n{titulo}  ({len(arquivos)} arquivos)\n{'='*92}")
        resumo = {"orfas": {}, "sumidos": {}, "sem_acumular": [], "navega": [], "sem_combinar": []}
        for f in arquivos:
            r = analisar(f)
            rel = str(f.relative_to(REPO)).replace("\\", "/")
            for o in r["orfas"]:
                resumo["orfas"].setdefault(o, []).append(rel)
            for s in r["sumidos"]:
                resumo["sumidos"].setdefault(s, []).append(rel)
            if r["filtros"]["profissional"]:
                if r["navega"]:
                    resumo["navega"].append(rel)
                elif not r["acumula"]:
                    resumo["sem_acumular"].append(rel)
            if r["filtros"]["categoria"] and r["filtros"]["tabela"] and not r["combina"]:
                resumo["sem_combinar"].append(rel)

        um = arquivos[0]
        r0 = analisar(um)
        ativos = [k for k, v in r0["filtros"].items() if v]
        print(f"  filtros presentes: {', '.join(ativos) if ativos else '(nenhum)'}")

        if resumo["navega"]:
            problemas += len(resumo["navega"])
            print(f"\n  [!] Profissional ainda é NAVEGAÇÃO, não filtro — {len(resumo['navega'])} arquivo(s)")
            for x in resumo["navega"][:6]:
                print(f"        {x}")
            if len(resumo["navega"]) > 6:
                print(f"        … e mais {len(resumo['navega'])-6}")
        elif resumo["sem_acumular"]:
            problemas += len(resumo["sem_acumular"])
            print(f"\n  [!] tem filtro de Profissional mas NÃO acumula — {len(resumo['sem_acumular'])} arquivo(s)")
            for x in resumo["sem_acumular"][:6]:
                print(f"        {x}")

        if resumo["sem_combinar"]:
            problemas += len(resumo["sem_combinar"])
            print(f"\n  [!] Categoria e Tabela não se combinam — {len(resumo['sem_combinar'])} arquivo(s)")

        if resumo["orfas"]:
            problemas += sum(len(v) for v in resumo["orfas"].values())
            print(f"\n  [!] BOTÕES que chamam função inexistente:")
            for fn, arqs in sorted(resumo["orfas"].items(), key=lambda kv: -len(kv[1])):
                print(f"        {fn}()  em {len(arqs)} arquivo(s)"
                      + (f"  ex.: {arqs[0]}" if not a.detalhe else ""))
                if a.detalhe:
                    for x in arqs:
                        print(f"            {x}")

        if resumo["sumidos"]:
            print(f"\n  [·] ids procurados e não encontrados (pode ser falso positivo "
                  f"quando o JS cria o elemento):")
            for i, arqs in sorted(resumo["sumidos"].items(), key=lambda kv: -len(kv[1]))[:8]:
                print(f"        '{i}' em {len(arqs)} arquivo(s)")

        if not any([resumo["navega"], resumo["sem_acumular"], resumo["sem_combinar"],
                    resumo["orfas"]]):
            print("  tudo certo.")

    print(f"\n{'='*92}\nproblemas encontrados: {problemas}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
