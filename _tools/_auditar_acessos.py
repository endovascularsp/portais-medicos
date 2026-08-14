# -*- coding: utf-8 -*-
"""
_auditar_acessos.py — acha quem abre uma tela e não enxerga os dados dela.

O BURACO QUE ISTO PROCURA (14/08/2026)
Abrir a página e ler os dados são duas permissões diferentes: a página confere
`cards.includes(...)` no JavaScript; o banco confere `has_card(...)` na RLS. Quem
tem a primeira e não a segunda entra normalmente e vê **tudo vazio, sem
mensagem de erro** — foi o caso da Micaele no card de Fechamento, que precisa de
`gestor_fechamento` (tela) E `honorarios` (dados).

Não há como adivinhar esse par: ele é descoberto lendo, de cada página, quais
tabelas ela consulta, e de cada tabela, qual card a RLS exige. É o que este
script faz — nada é escrito à mão aqui.

  1. de cada `*.html`: os `sb.from('tabela')` e os `cards.includes('card')`;
  2. de cada `db/*.sql`: o `has_card('card')` das policies de cada tabela;
  3. de cada usuário: se ele abre a tela e não tem o card que os dados exigem.

`role='admin'` passa por tudo (`is_admin_user()`), então não entra no relatório.

Uso:
    python _tools/_auditar_acessos.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "_tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

import _honorarios_db as DB   # noqa: E402

IGNORAR = {".git", "_tools", "assets", "db", "supabase", ".github", "__pycache__"}
TABELA_RE = re.compile(r"\.from\(\s*['\"]([a-z0-9_]+)['\"]")
GATE_RE = re.compile(r"cards\.includes\(\s*['\"]([a-z0-9_]+)['\"]")


def paginas() -> dict:
    """página -> (cards que abrem, tabelas que ela consulta)"""
    out = {}
    for p in sorted(REPO.rglob("*.html")):
        if any(x in IGNORAR for x in p.relative_to(REPO).parts[:-1]):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        gates = set(GATE_RE.findall(t))
        tabelas = set(TABELA_RE.findall(t))
        if gates and tabelas:
            out[p.relative_to(REPO).as_posix()] = (gates, tabelas)
    return out


def cards_da_rls() -> dict:
    """tabela -> cards aceitos pela RLS. Lê as policies do próprio repositório.

    Cobre os dois jeitos como as migrations escrevem: policy por tabela e o
    laço que aplica a mesma policy a uma lista de tabelas (migration_009)."""
    out: dict = {}
    for sql in sorted((REPO / "db").glob("*.sql")):
        txt = sql.read_text(encoding="utf-8", errors="replace")

        # 1) policies escritas uma a uma
        for m in re.finditer(r"CREATE POLICY[^;]+?ON\s+public\.([a-z0-9_]+)(.*?);", txt, re.S | re.I):
            tabela, corpo = m.group(1), m.group(2)
            for c in re.findall(r"has_card\(\s*'+([a-z0-9_]+)'+\s*\)", corpo):
                out.setdefault(tabela, set()).add(c)

        # 2) laço `FOREACH t IN ARRAY [...]` com o EXECUTE format(...)
        for m in re.finditer(r"ARRAY\s*\[([^\]]+)\](.*?)END LOOP", txt, re.S | re.I):
            tabelas = re.findall(r"'([a-z0-9_]+)'", m.group(1))
            cards = re.findall(r"has_card\(\s*''+([a-z0-9_]+)''+\s*\)", m.group(2))
            for t in tabelas:
                for c in cards:
                    out.setdefault(t, set()).add(c)
    return out


def main() -> int:
    pags = paginas()
    rls = cards_da_rls()
    usuarios = [u for u in DB.buscar("users", select="email,role,cards")
                if (u.get("role") or "") != "admin"]

    print(f"\n=== Varredura de acesso · {len(pags)} páginas com portão · "
          f"{len(rls)} tabelas com RLS por card · {len(usuarios)} usuários não-admin ===")

    furos: list = []
    for pag, (gates, tabelas) in sorted(pags.items()):
        exigidos: dict = {}
        for t in tabelas:
            for c in rls.get(t, ()):
                exigidos.setdefault(c, set()).add(t)
        if not exigidos:
            continue
        for u in usuarios:
            cards = set(u.get("cards") or [])
            if not (cards & gates):
                continue                      # não abre a página; não é furo
            faltando = {c: ts for c, ts in exigidos.items() if c not in cards}
            # Se QUALQUER card exigido ele tem, a tabela já abre — o furo é só
            # quando falta todo mundo que dá acesso àquela tabela.
            tabelas_mortas = {t for c, ts in faltando.items() for t in ts
                              if not (cards & rls.get(t, set()))}
            if tabelas_mortas:
                furos.append((u["email"], pag, sorted(cards & gates),
                              sorted({c for c in faltando}), sorted(tabelas_mortas)))

    print(f"\n--- Abre a tela e NÃO enxerga os dados: {len(furos)} ---")
    for email, pag, por, falta, tabs in furos:
        print(f"\n  {email}")
        print(f"     página : {pag}   (entra por {', '.join(por)})")
        print(f"     falta  : {', '.join(falta)}")
        print(f"     vazio  : {', '.join(tabs[:6])}{' …' if len(tabs) > 6 else ''}")

    # O contrário também merece uma olhada: card de dados sem a tela.
    print("\n--- Tem o card de dados e nenhuma tela que o use ---")
    todos_gates = set().union(*[g for g, _ in pags.values()]) if pags else set()
    cards_dados = set().union(*rls.values()) if rls else set()
    n = 0
    for u in usuarios:
        cards = set(u.get("cards") or [])
        sobrando = (cards & cards_dados) - todos_gates
        # só reporta quem não abre NENHUMA tela que leia aquilo
        sobrando = {c for c in sobrando
                    if not any(c in g for g, _ in pags.values())}
        if sobrando:
            n += 1
            print(f"  {u['email']:46s} {', '.join(sorted(sobrando))}")
    if not n:
        print("  (nenhum)")

    # Honestidade sobre o alcance: tabela consultada por página com portão e sem
    # policy por card encontrada aqui. Ou ela não usa card (só admin, ou aberta a
    # qualquer autenticado), ou a policy não está no repositório — nos dois casos
    # este script não tem o que conferir, e é melhor dizer do que fingir cobertura.
    sem_regra = sorted({t for _p, (_g, ts) in pags.items() for t in ts if t not in rls})
    print(f"\n--- Fora do alcance desta varredura: {len(sem_regra)} tabela(s) ---")
    print("  " + (", ".join(sem_regra) if sem_regra else "(nenhuma)"))

    return 1 if furos else 0


if __name__ == "__main__":
    raise SystemExit(main())
