"""
_onboard_andrea_cirurgias.py — Onboarding da Dra. Andrea no portal Cirurgias.

A cirurgia de Abril dela (Cirurgia - Hospital, R$ 19.000 / repasse R$ 14.022)
entrou na planilha depois da ultima geracao. Como o individual dela em
cirurgias/ nao existia, o gerador a pulou (NAO_EXISTE) e o reconstrutor de
admin nunca a achou. Resultado: some do portal Cirurgias inteiro.

Este script (idempotente, --dry-run disponivel):
  1. Monta o objeto _Cir da Andrea (Abril) reaproveitando montar_objeto_prof.
  2. VALIDA a senha canonica 'and2026' decriptando o portal Endo existente dela.
  3. Cria cirurgias/Andrea_Ostaszewski_Klepacz.html clonando o template da
     Carolina (troca title/nav/PROF_FIXO + injeta so o periodo 2026-04 cifrado).
  4. Injeta a entrada dela (chave SEM sufixo) no admin cirurgias/index.html.
  5. Adiciona o card "Cirurgias" no Hub dela (ao lado do Endo).

NAO commita. NAO faz push. Validar visualmente antes.
"""
from __future__ import annotations
import argparse, json, re, sys, os
from pathlib import Path

REPO = Path(r"C:\Users\thiag\Documents\portais-medicos")
HONOR = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\honorarios_auto")
sys.path.insert(0, str(HONOR))
import gerar_pdata_abril as g  # montar_objeto_prof, encrypt_blob, decrypt_blob, is_cirurgia, slugify

PROF = "Andrea Ostaszewski Klepacz"
SLUG = "Andrea_Ostaszewski_Klepacz"
SENHA = "and2026"
TEMPLATE = REPO / "cirurgias" / "Carolina_Mardegan.html"
TEMPLATE_SLUG = "Carolina_Mardegan"
TEMPLATE_NOME = "Carolina Mardegan"
ALVO_INDIV = REPO / "cirurgias" / f"{SLUG}.html"
ADMIN = REPO / "cirurgias" / "index.html"
HUB = REPO / "hub" / f"{SLUG}_Hub.html"
PDATA_RE = re.compile(r"(/\*PDATA\*/)(\{.*?\})(/\*PDATA\*/)", re.DOTALL)


def validar_senha_endo():
    """Confirma que 'and2026' decripta o portal Endo existente da Andrea.
    Garante que o blob de Cirurgias sera decriptavel com a mesma senha que ela ja usa."""
    p = REPO / f"{SLUG}.html"
    if not p.exists():
        raise SystemExit(f"ABORT: portal Endo da Andrea nao encontrado: {p}")
    m = PDATA_RE.search(p.read_text(encoding="utf-8"))
    enc = json.loads(m.group(2))
    pid, ent = next(iter(enc.items()))
    obj = g.decrypt_blob(ent["blob"], SENHA)
    assert SLUG in obj, f"decriptou mas slug {SLUG} ausente"
    print(f"  [OK] senha '{SENHA}' decripta o portal Endo da Andrea (periodo {pid})")


def montar():
    df = g.pd.read_excel(g.PLANILHA, sheet_name="Base Compensação")
    df = df[(df["Profissional"] == PROF) & (df["Mês"] == "Abril") &
            (df["Categoria"].apply(g.is_cirurgia))]
    if df.empty:
        raise SystemExit("ABORT: nenhuma cirurgia da Andrea em Abril na planilha")
    obj = g.montar_objeto_prof(PROF, df, "Endovascular SP", com_periodo_id=False)
    inner = obj[SLUG]
    print(f"  Cirurgias Abril: {len(df)} linha(s) | recebido R$ {inner['resumo']['Valor recebido']:,.2f} "
          f"| repasse prof R$ {inner['resumo']['Repasse Profissional (R$)']:,.2f}")
    for a in inner["atendimentos"]:
        print(f"    - {a['Paciente']} | {a['Procedimento'][:50]} | R$ {a['Repasse Profissional (R$)']:,.2f}")
    return obj, inner


def criar_individual(obj, dry):
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace(TEMPLATE_NOME, PROF).replace(TEMPLATE_SLUG, SLUG)
    blob = g.encrypt_blob(obj, SENHA)
    novo_pdata = json.dumps({"2026-04": {"label": "Abril/2026", "blob": blob}},
                            ensure_ascii=False, separators=(",", ":"))
    m = PDATA_RE.search(html)
    html = html[:m.start(2)] + novo_pdata + html[m.end(2):]
    # round-trip de seguranca
    chk = g.decrypt_blob(blob, SENHA)
    assert SLUG in chk and chk[SLUG]["resumo"]["Valor recebido"] == obj[SLUG]["resumo"]["Valor recebido"]
    if not dry:
        ALVO_INDIV.write_text(html, encoding="utf-8")
    print(f"  [{'DRY' if dry else 'OK'}] individual criado: {ALVO_INDIV.relative_to(REPO)} ({len(html):,} bytes)")


def injetar_admin(inner, dry):
    html = ADMIN.read_text(encoding="utf-8")
    m = PDATA_RE.search(html)
    data = json.loads(m.group(2))
    profs = data["2026-04"]["profs"]
    acao = "REPLACE" if SLUG in profs else "ADD"
    profs[SLUG] = inner
    novo = json.dumps(data, ensure_ascii=False)
    html = html[:m.start(2)] + novo + html[m.end(2):]
    if not dry:
        ADMIN.write_text(html, encoding="utf-8", newline="")
    print(f"  [{'DRY' if dry else 'OK'}] admin {acao} -> {sorted(profs.keys())}")


def add_hub_card(dry):
    html = HUB.read_text(encoding="utf-8")
    # ancora unica: link Endo do card Recebimento (raiz, nao /produtividade/)
    anchor = re.search(
        r'(<a href="\.\./' + re.escape(SLUG) +
        r'\.html\?v=\d+" onclick="navegar\(this,event\)" class="hub-sub-btn endo">\s*'
        r'🏥 Endovascular SP\s*</a>)', html)
    if not anchor:
        print("  [WARN] ancora do card Recebimento nao encontrada no Hub — pulando card")
        return
    if "cirurgias/" + SLUG in html:
        print("  [SKIP] Hub ja tem card de Cirurgias")
        return
    cir_btn = ('\n              <a href="../cirurgias/' + SLUG +
               '.html?v=20260601" onclick="navegar(this,event)" class="hub-sub-btn cir">\n'
               '                🔬 Cirurgias\n'
               '              </a>')
    html = html[:anchor.end(1)] + cir_btn + html[anchor.end(1):]
    if not dry:
        HUB.write_text(html, encoding="utf-8")
    print(f"  [{'DRY' if dry else 'OK'}] card Cirurgias adicionado no Hub da Andrea")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dry = a.dry_run
    print(f"\n=== Onboarding Andrea — Cirurgias ({'DRY-RUN' if dry else 'ESCRITA'}) ===")
    print("\n[1] Validar senha canonica:")
    validar_senha_endo()
    print("\n[2] Montar objeto:")
    obj, inner = montar()
    print("\n[3] Criar individual:")
    criar_individual(obj, dry)
    print("\n[4] Injetar no admin:")
    injetar_admin(inner, dry)
    print("\n[5] Card no Hub:")
    add_hub_card(dry)
    print("\nFeito." + (" (nada escrito)" if dry else " Validar visualmente antes do commit."))


if __name__ == "__main__":
    main()
