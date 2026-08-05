# -*- coding: utf-8 -*-
"""
_honorarios_criar_portal.py — cria o portal individual de um profissional numa
empresa em que ele ainda não tem, com TODOS os períodos que existem na base.

Substitui os scripts `_onboard_*.py` antigos, que liam do Excel. Este lê do
Supabase e reaproveita a criptografia já validada.

O que faz, nesta ordem:
  1. monta o PDATA de todos os períodos do profissional naquela empresa;
  2. clona um portal existente da mesma pasta, troca a identidade e injeta o PDATA;
  3. insere o sub-botão no card de Recebimento do Hub e religa `portais.<sub>`
     dentro do BLOB do Hub (que é criptografado com a mesma chave do profissional);
  4. adiciona o profissional ao LINKS do admin, para aparecer o "Abrir Portal".

Cada passo é verificado antes de gravar: o portal novo é decriptado de volta, o
BLOB do Hub é conferido para garantir que os outros portais não se perderam, e
aborta se sobrar qualquer resíduo do nome do modelo.

Uso:
    python _tools/_honorarios_criar_portal.py --prof "João Fukuda" --empresa Cirurgias --dry-run
    python _tools/_honorarios_criar_portal.py --prof "João Fukuda" --empresa Cirurgias
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_gerar_pdata as G  # noqa: E402
import _honorarios_publicar as P     # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PDATA_RE = re.compile(r"(/\*PDATA\*/)(\{.*?\})(/\*PDATA\*/)", re.DOTALL)
VER = "20260805"

# empresa -> (pasta, sufixo do arquivo, chave em portais{}, classe do botão, rótulo)
DESTINO = {
    "Cirurgias":       ("cirurgias", "",              "cir",  "cir",  "🔬 Cirurgias"),
    "Oxy Recovery":    ("oxy",       "_Oxy_Recovery", "oxy",  "oxy",  "💊 Oxy Recovery"),
    "Endovascular SP": ("",          "",              "endo", "endo", "🏥 Endovascular SP"),
}


def periodos_do_prof(prof: str, empresa: str) -> dict:
    """{periodo_id: objeto interno} — todos os meses que o profissional tem."""
    out = {}
    for pid in sorted(G.pdata_publicado(P.REPO / "recebimento.html")):
        obj = G.montar(pid)
        for inner in obj["profs"].values():
            if inner["profissional"] == prof and inner["empresa"] == empresa:
                out[pid] = (obj["label"], inner)
    return out


def main(prof: str, empresa: str, modelo: str | None, dry_run: bool):
    pasta, sufixo, chave_portal, classe, rotulo = DESTINO[empresa]
    slug = G.slugify(prof)
    dir_alvo = REPO / pasta if pasta else REPO
    alvo = dir_alvo / f"{slug}{sufixo}.html"
    hub = REPO / "hub" / f"{slug}_Hub.html"
    admin = dir_alvo / "index.html" if pasta else REPO / "recebimento.html"

    print(f"=== {prof} · {empresa} ===")
    if alvo.exists():
        raise SystemExit(f"ABORTADO: {alvo.relative_to(REPO)} já existe.")
    if not hub.exists():
        raise SystemExit(f"ABORTADO: Hub não existe ({hub.relative_to(REPO)}). "
                         "Este script não cria Hub do zero.")

    chaves = P.carregar_chaves()
    if prof not in chaves:
        raise SystemExit(f"ABORTADO: sem chave validada para {prof!r}.")
    chave = chaves[prof]

    # --- 1) dados ---
    pers = periodos_do_prof(prof, empresa)
    if not pers:
        raise SystemExit(f"ABORTADO: {prof} não tem lançamento de {empresa} em nenhum período.")
    pdata = {}
    for pid, (label, inner) in sorted(pers.items()):
        blob = P.cifrar({slug: P.interno_individual(inner)}, chave)
        pdata[pid] = {"label": label, "blob": blob}
        r = inner["resumo"]
        print(f"  {pid} {label:16s} {len(inner['atendimentos']):3d} atend · "
              f"receb R$ {r['Valor recebido']:>11,.2f} · repasse R$ {r['Repasse Profissional (R$)']:>11,.2f}")

    # --- 2) portal a partir de um modelo da mesma pasta ---
    # Só serve de modelo o portal de um profissional que TEM Hub — assim não
    # clonamos arquivos internos como "Agendamento Cirúrgico" ou "Enfermagem",
    # que existem na raiz mas não são portal de médico.
    candidatos = [p for p in sorted(dir_alvo.glob(f"*{sufixo}.html"))
                  if p.name != "index.html" and p != alvo
                  and (REPO / "hub" / f"{p.name[:-len(sufixo + '.html')] if sufixo else p.stem}_Hub.html").exists()
                  and (modelo is None or modelo.lower() in p.name.lower())]
    if not candidatos:
        raise SystemExit("ABORTADO: nenhum portal-modelo encontrado na pasta.")
    tmpl = min(candidatos, key=lambda p: p.stat().st_size)
    t_slug = tmpl.name[:-len(sufixo + ".html")] if sufixo else tmpl.stem
    t_nome = t_slug.replace("_", " ")
    print(f"\n  modelo: {tmpl.relative_to(REPO)}  ({t_nome})")

    html = tmpl.read_text(encoding="utf-8")
    m = PDATA_RE.search(html)
    if not m:
        raise SystemExit("ABORTADO: modelo sem marcador PDATA.")
    # tira o PDATA ANTES de trocar nomes, para não mexer nos dados do modelo
    html = html[:m.start(2)] + "__PDATA__" + html[m.end(2):]
    html = (html.replace(t_nome, prof)
                .replace(t_slug, slug)
                .replace(t_nome.split()[0], prof.split()[0]))
    html = html.replace("__PDATA__", json.dumps(pdata, ensure_ascii=False, separators=(",", ":")))

    resto = t_nome.split()[0]
    if resto in html:
        raise SystemExit(f"ABORTADO: sobrou {resto!r} do modelo no portal novo.")
    conferido = P.decifrar(json.loads(PDATA_RE.search(html).group(2))[max(pdata)]["blob"], chave)
    if slug not in conferido:
        raise SystemExit("ABORTADO: o portal gerado não decripta para o profissional certo.")
    print(f"  portal .....: {alvo.relative_to(REPO)}  ({len(html):,} chars, {len(pdata)} períodos) OK")

    # --- 3) Hub: sub-botão + portais.<chave> no BLOB ---
    ht = hub.read_text(encoding="utf-8")
    mb = re.search(r'const BLOB = "([^"]+)"', ht)
    if not mb:
        raise SystemExit("ABORTADO: Hub sem BLOB.")
    dados_hub = P.decifrar(mb.group(1), chave)
    antes = dict(dados_hub.get("portais") or {})
    if antes.get(chave_portal):
        print(f"  hub ........: portais.{chave_portal} já apontava para {antes[chave_portal]}")
    href = (f"../{pasta}/{slug}{sufixo}.html" if pasta else f"../{slug}.html")
    novo_hub = dict(dados_hub)
    novo_hub["portais"] = dict(antes)
    novo_hub["portais"][chave_portal] = href
    ht = re.sub(r'const BLOB = "[^"]+"', 'const BLOB = "' + P.cifrar(novo_hub, chave) + '"', ht, count=1)

    botao = (f'\n              <a href="{href}?v={VER}" onclick="navegar(this,event)" '
             f'class="hub-sub-btn {classe}">\n                {rotulo}\n              </a>')

    if f'class="hub-sub-btn {classe}"' not in ht:
        ancora = re.search(r'(<a href="[^"]*"[^>]*class="hub-sub-btn (?:endo|oxy|cir)">\s*[^<]*</a>)', ht)
        if ancora:
            # já existe o card de Recebimento: só entra mais um sub-botão nele
            ht = ht[:ancora.end()] + botao + ht[ancora.end():]
        else:
            # Hub sem card de Recebimento (caso de quem só tinha Produtividade):
            # o card inteiro é criado antes do card de Produtividade.
            prod = re.search(r'(\s*)<div class="hub-card prod" id="card-prod">', ht)
            if not prod:
                raise SystemExit("ABORTADO: Hub não tem card-prod para me orientar; "
                                 "não sei onde colocar o card de Recebimento.")
            card = (f'{prod.group(1)}<div class="hub-card rec" id="card-rec">'
                    f'{prod.group(1)}  <div class="hub-card-icon">💰</div>'
                    f'{prod.group(1)}  <div class="hub-card-title">Recebimento</div>'
                    f'{prod.group(1)}  <div class="hub-card-desc">Honorários e repasses'
                    f'<br>por competência</div>'
                    f'{prod.group(1)}  <div class="hub-card-links">{botao}'
                    f'{prod.group(1)}  </div>'
                    f'{prod.group(1)}</div>')
            ht = ht[:prod.start()] + card + ht[prod.start():]
            print("  hub ........: card de Recebimento não existia — criado")

    conf = P.decifrar(re.search(r'const BLOB = "([^"]+)"', ht).group(1), chave)
    perdidos = [k for k, v in antes.items() if v and not conf["portais"].get(k)]
    if perdidos:
        raise SystemExit(f"ABORTADO: o Hub perderia os portais {perdidos}")
    if ht.count(f'class="hub-sub-btn {classe}"') != 1:
        raise SystemExit("ABORTADO: sub-botão duplicado no Hub.")
    print(f"  hub ........: sub-botão {rotulo} + portais.{chave_portal} · "
          f"preservados {[k for k, v in conf['portais'].items() if v]}")

    # --- 4) LINKS do admin ---
    at = admin.read_text(encoding="utf-8")
    ml = re.search(r"const LINKS = (\{[^;]*\})", at)
    at_novo = at
    if ml:
        links = json.loads(ml.group(1))
        links[slug] = f"{slug}{sufixo}.html"
        links = {k: links[k] for k in sorted(links)}
        at_novo = at[:ml.start(1)] + json.dumps(links, ensure_ascii=False) + at[ml.end(1):]
        print(f"  admin ......: {admin.relative_to(REPO)} · LINKS agora com {len(links)} portais")
    else:
        print(f"  admin ......: {admin.relative_to(REPO)} não tem LINKS (nada a fazer)")

    if dry_run:
        print("\n[dry-run] nada gravado.")
        return
    alvo.write_text(html, encoding="utf-8")
    hub.write_text(ht, encoding="utf-8")
    if ml:
        admin.write_text(at_novo, encoding="utf-8")
    print("\nCriado.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prof", required=True)
    ap.add_argument("--empresa", required=True, choices=list(DESTINO))
    ap.add_argument("--modelo")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    main(a.prof, a.empresa, a.modelo, a.dry_run)
