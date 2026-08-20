# -*- coding: utf-8 -*-
"""
_honorarios_publicar.py — escreve o PDATA nos portais, lendo do Supabase.

Fase 3A. Substitui `gerar_pdata_*.py`, que lia do Excel. A montagem do JSON vem de
`_honorarios_gerar_pdata.py`; aqui fica só a parte de criptografar e injetar nos
HTMLs — lógica reaproveitada do gerador antigo, que já resolveu:

  - PBKDF2-SHA256 600k + AES-GCM, empacotado como salt16|nonce12|ct
  - a chave de cada médico VALIDADA contra o portal atual antes de usar
    (se não decriptar o período que já está lá, o portal é PULADO —
     melhor não publicar do que cifrar com chave errada e trancar o médico fora)
  - as três convenções diferentes dos admins
  - cache-busting dos Hubs

Uso:
    python _tools/_honorarios_publicar.py --periodo 2026-06 --validar
    python _tools/_honorarios_publicar.py --periodo 2026-07 --piloto Igor
    python _tools/_honorarios_publicar.py --periodo 2026-07
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_gerar_pdata as G  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SQL_CHAVES = Path(r"C:\Users\thiag\Documents\Endovascular_Farmer\honorarios_auto\_fase_b_user_secrets.sql")
ITERACOES = 600_000

PDATA_RE = re.compile(r"(/\*PDATA\*/)(\{.*?\})(/\*PDATA\*/)", re.DOTALL)

EMAIL = {
    "Andrea Ostaszewski Klepacz": "andreaklepacz@gmail.com", "Carolina Mardegan": "carolmardegan88@gmail.com",
    "Christiane Sayuri Lopes Inoue": "christiane.lopess@gmail.com", "Clara Silva Freitas": "sfreitasclara@gmail.com",
    "Daniela Viese Roth": "daniellaroth@gmail.com", "Eduardo Araujo Pires": "dreduardoaraujopires@gmail.com",
    "Fernanda Liporaci Villela Zuchi": "fer31liporaci@gmail.com", "João Fukuda": "jtfukuda@gmail.com",
    "Jonathan Batista Souza": "jbatisouza2012@gmail.com", "Julia do Valle Bargieri": "juliabargieri@gmail.com",
    "Manoel Augusto Lobato": "lobatocirurgiavascular@gmail.com", "Maria Fernanda R Fernandes": "contatofefenutri@gmail.com",
    "Mateus Antunes Nogueira": "dr@mateusnogueira.com.br", "Simone Matsuda Torricelli": "simone.matsuda@gmail.com",
}
CHAVES_EXTRAS = {
    "Igor Rafael Sincos": "fjJtiWVRAwYpGx6Z3XY9xv5qDPg6no6c",
    "Nicole Tenenbaum Szajubok": "v8IjSyPxD3NUiUyU2WO2KRIFehv21y0-",
}

# Quem enxerga, dentro do PRÓPRIO portal, também os dados de outro profissional.
#   {quem vê: [quem é visto]}
# O portal continua cifrado com a chave de quem vê — quem é visto não ganha
# acesso nenhum em troca, e o portal dele não muda. Na tela aparece um menu
# "Profissional" para alternar entre os nomes, um de cada vez.
# Simone x Nicole: pedido do Thiago em 20/08/2026.
VISIBILIDADE_EXTRA = {
    "Simone Matsuda Torricelli": ["Nicole Tenenbaum Szajubok"],
}


def profs_do_blob(obj: dict, prof: str, emp: str) -> dict:
    """O conteúdo do blob individual: o dono primeiro, depois quem ele enxerga.

    A ORDEM importa: o portal trata a primeira chave como o dono da tela."""
    fonte = obj["profs"]
    dentro = {}
    meu = next((v for v in fonte.values()
                if v["profissional"] == prof and v["empresa"] == emp), None)
    if meu:
        dentro[G.slugify(prof)] = interno_individual(meu)
    for outro in VISIBILIDADE_EXTRA.get(prof, []):
        v = next((x for x in fonte.values()
                  if x["profissional"] == outro and x["empresa"] == emp), None)
        if v:
            dentro[G.slugify(outro)] = interno_individual(v)
    return dentro


# --------------------------------------------------------------------------
# Cripto
# --------------------------------------------------------------------------
def _kdf(senha: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=ITERACOES).derive(senha.encode())


def cifrar(obj: dict, senha: str) -> str:
    salt, nonce = os.urandom(16), os.urandom(12)
    payload = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ct = AESGCM(_kdf(senha, salt)).encrypt(nonce, payload, None)
    return base64.b64encode(salt + nonce + ct).decode()


def decifrar(b64: str, senha: str) -> dict:
    p = base64.b64decode(b64)
    return json.loads(AESGCM(_kdf(senha, p[:16])).decrypt(p[16:28], p[28:], None).decode())


def validar_cripto() -> None:
    obj = {"t": {"v": 123.45, "m": "Validação Açaí"}}
    assert decifrar(cifrar(obj, "abc"), "abc") == obj
    print("  [OK] round-trip da criptografia")


# --------------------------------------------------------------------------
# Alvos e chaves
# --------------------------------------------------------------------------
def interno_individual(inner: dict) -> dict:
    """O objeto que vai DENTRO do blob do portal individual.

    Duas diferenças em relação ao objeto do admin, herdadas do gerador antigo e
    mantidas para não quebrar o que os portais já leem:
      - `empresa` é "Endovascular SP" também nos portais de cirurgia; só os
        admins usam o rótulo "Cirurgias";
      - `periodo_id` só existe no portal da raiz (Endovascular SP).
    """
    emp = inner["empresa"]
    out = dict(inner)
    out["empresa"] = "Oxy Recovery" if emp == "Oxy Recovery" else "Endovascular SP"
    if emp != "Endovascular SP":
        out.pop("periodo_id", None)
    return out


def alvo_individual(prof: str, emp: str) -> Path:
    slug = G.slugify(prof)
    if emp == "Oxy Recovery":
        return REPO / "oxy" / f"{slug}_Oxy_Recovery.html"
    if emp == "Cirurgias":
        return REPO / "cirurgias" / f"{slug}.html"
    return REPO / f"{slug}.html"


def _pdata_individual(path: Path):
    if not path.exists():
        return None
    m = PDATA_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        return None
    try:
        return json.loads(m.group(2))
    except json.JSONDecodeError:
        return None


def carregar_chaves() -> dict:
    """Chave por profissional, VALIDADA decriptando o último período que já está
    publicado no portal dele. Quem não validar fica de fora — cifrar com chave
    errada tranca o médico fora do próprio portal.

    A fonte é a tabela `user_secrets` do Supabase, que é onde o cadastro vive
    hoje. Antes eu lia de `_fase_b_user_secrets.sql`, um arquivo de rotação de
    junho — e por isso quem entrou depois (Gustavo, cadastrado em 20/07)
    aparecia como "sem chave" mesmo já tendo uma. O SQL e o dicionário EMAIL
    ficam só como reserva, para o caso de o banco estar fora do ar."""
    cand = dict(CHAVES_EXTRAS)
    try:
        import _honorarios_db as DB
        users = {u["email"]: u.get("name") for u in DB.buscar("users", "email,name")}
        for s in DB.buscar("user_secrets", "email,legacy_password"):
            nome = users.get(s["email"])
            if nome and s.get("legacy_password"):
                cand[nome] = s["legacy_password"]
    except SystemExit as e:
        print(f"  [CHAVES] Supabase indisponível ({e}); usando o SQL de reserva")
    if SQL_CHAVES.exists():
        sql = SQL_CHAVES.read_text(encoding="utf-8")
        e2k = {e: k for k, e in re.findall(
            r"set legacy_password = '([^']+)' where email = '([^']+)'", sql)}
        for nome, em in EMAIL.items():
            if em in e2k:
                cand.setdefault(nome, e2k[em])

    # Duas situações MUITO diferentes:
    #   - existe portal e a chave não abre  -> PULA (cifrar com ela trancaria o médico fora)
    #   - não existe portal nenhum          -> aceita (não há o que quebrar; é o caso
    #                                          de quem está sendo criado agora)
    ok, erradas, sem_portal = {}, [], []
    for nome, chave in cand.items():
        slug = G.slugify(nome)
        candidatos = [alvo_individual(nome, e) for e in ("Endovascular SP", "Cirurgias", "Oxy Recovery")]
        candidatos += [REPO / "produtividade" / f"{slug}_Produtividade.html",
                       REPO / "oxy-produtividade" / f"{slug}_Oxy_Produtividade.html"]
        existentes, validou = 0, False
        for p in candidatos:
            if not p.exists():
                continue
            existentes += 1
            data = _pdata_individual(p)
            blobs = ([v["blob"] for v in data.values() if isinstance(v, dict) and v.get("blob")]
                     if data else [])
            if not blobs:                       # produtividade guarda o blob solto
                m = re.search(r"/\*PDATA\*/'([A-Za-z0-9+/=]+)'/\*PDATA\*/", p.read_text(encoding="utf-8"))
                blobs = [m.group(1)] if m else []
            for b in blobs[-1:]:
                try:
                    decifrar(b, chave)
                    validou = True
                    break
                except Exception:
                    pass
            if validou:
                break
        if validou:
            ok[nome] = chave
        elif existentes:
            erradas.append(nome)
        else:
            ok[nome] = chave
            sem_portal.append(nome)
    print(f"  [CHAVES] validadas: {len(ok) - len(sem_portal)} · sem portal ainda: {len(sem_portal)}"
          f" · não abrem o portal: {len(erradas)}")
    for n in sem_portal:
        print(f"     [NOVO]   {n}: ainda não tem portal — chave aceita")
    for n in erradas:
        print(f"     [PULADO] {n}: a chave não abre o portal atual")
    return ok


# --------------------------------------------------------------------------
# Injeção
# --------------------------------------------------------------------------
def json_balanceado(html: str, i: int):
    if i >= len(html) or html[i] != "{":
        return None
    d, k, ins, esc = 0, i, False, False
    while k < len(html):
        c = html[k]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        else:
            if c == '"': ins = True
            elif c == "{": d += 1
            elif c == "}":
                d -= 1
                if d == 0:
                    return (i, k + 1)
        k += 1
    return None


def injetar_individual(path: Path, periodo_id: str, label: str, blob: str, escrever: bool) -> str:
    if not path.exists():
        return "SEM PORTAL"
    html = path.read_text(encoding="utf-8")
    m = PDATA_RE.search(html)
    if not m:
        return "MARCADOR NÃO ENCONTRADO"
    try:
        data = json.loads(m.group(2))
    except json.JSONDecodeError as e:
        return f"JSON INVÁLIDO: {e}"
    acao = "SUBSTITUI" if periodo_id in data else "ADICIONA"
    data[periodo_id] = {"label": label, "blob": blob}
    novo = json.dumps({k: data[k] for k in sorted(data)}, ensure_ascii=False, separators=(",", ":"))
    if escrever:
        path.write_text(html[:m.start(2)] + novo + html[m.end(2):], encoding="utf-8")
    return acao


def injetar_admin(path: Path, periodo_id: str, obj: dict, escrever: bool) -> str:
    if not path.exists():
        return "NÃO EXISTE"
    html = path.read_text(encoding="utf-8")
    i = html.find("/*PDATA*/")
    if i < 0:
        return "MARCADOR NÃO ENCONTRADO"
    j = i + len("/*PDATA*/")
    while html[j] in " \n\r\t":
        j += 1
    b = json_balanceado(html, j)
    if not b:
        return "JSON NÃO BALANCEADO"
    try:
        data = json.loads(html[b[0]:b[1]])
    except json.JSONDecodeError as e:
        return f"JSON INVÁLIDO: {e}"
    acao = "SUBSTITUI" if periodo_id in data else "ADICIONA"
    data[periodo_id] = obj
    novo = json.dumps({k: data[k] for k in sorted(data)}, ensure_ascii=False, separators=(",", ":"))
    if escrever:
        path.write_text(html[:b[0]] + novo + html[b[1]:], encoding="utf-8")
    return acao


# --------------------------------------------------------------------------
# Validação: o que o injetor produziria x o que já está publicado
# --------------------------------------------------------------------------
def validar(periodo_id: str, chaves: dict) -> int:
    obj = G.montar(periodo_id)
    print(f"\n=== VALIDAÇÃO DOS PORTAIS INDIVIDUAIS · {periodo_id} ===")
    iguais = difs = sem = 0
    for slug, inner in sorted(obj["profs"].items()):
        prof, emp = inner["profissional"], inner["empresa"]
        path = alvo_individual(prof, emp)
        if prof not in chaves or not path.exists():
            sem += 1
            continue
        data = _pdata_individual(path)
        if not data or periodo_id not in data:
            print(f"  [{path.name}] período ainda não publicado")
            sem += 1
            continue
        try:
            atual = decifrar(data[periodo_id]["blob"], chaves[prof])
        except Exception as e:
            print(f"  [{path.name}] não decriptou: {type(e).__name__}")
            difs += 1
            continue
        # Os campos novos (Regra aplicada, % Aplicado, ISS, Taxa comercial) só
        # existem em período publicado por este gerador. Comparando contra um
        # período antigo, é preciso tirá-los do lado esperado — senão a
        # diferença aparece em toda linha e esconde as de verdade. Já num
        # período novo eles TÊM que estar lá, e aí a comparação é completa.
        # o blob pode trazer mais de um profissional (VISIBILIDADE_EXTRA);
        # a comparação é sempre com o dono do portal
        atual_inner = atual.get(G.slugify(prof)) or list(atual.values())[0]
        ja_tem_novos = bool((atual_inner.get("atendimentos") or [{}])[0].get("Regra aplicada"))
        esperado = interno_individual(inner)
        if not ja_tem_novos:
            esperado["atendimentos"] = [
                {k: v for k, v in at.items() if k not in G.CAMPOS_NOVOS}
                for at in esperado["atendimentos"]]
        ruins = comparar(atual_inner, esperado)
        if not ruins:
            iguais += 1
        else:
            difs += 1
            for r in ruins[:6]:
                print(f"  [{path.name}] {r}")
    print(f"\n  idênticos: {iguais} · divergentes: {difs} · sem base de comparação: {sem}")
    if centavos["n"]:
        print(f"  (ignoradas {centavos['n']} diferenças de arredondamento somando "
              f"R$ {centavos['total']:.2f} — o Excel somava com precisão total, "
              f"o banco guarda 4 casas)")
    return 1 if difs else 0


# tolerância de arredondamento: o Excel somava valores de precisão total; o banco
# guarda 4 casas. Subtotal pode fechar 1 centavo diferente.
TOL = 0.011
centavos = {"n": 0, "total": 0.0}


def _num_igual(a, b) -> bool:
    if abs(a - b) < 1e-9:
        return True
    if abs(a - b) <= TOL:
        centavos["n"] += 1
        centavos["total"] += abs(a - b)
        return True
    return False


def _chave_at(a: dict) -> tuple:
    return (str(a.get("Nº OS")), str(a.get("Data compensação")), str(a.get("Procedimento")),
            f"{a.get('Valor recebido', 0):.2f}", str(a.get("Paciente")),
            f"{a.get('Repasse Profissional (R$)', 0):.2f}")


def comparar(pub: dict, ger: dict) -> list:
    """Diferenças reais entre o publicado e o gerado. A ORDEM das listas não conta:
    o gerador antigo ordenava pelo texto dd/mm/aaaa, o novo ordena pela data real."""
    ruins = []
    for campo in ("profissional", "empresa", "mes", "ano", "periodo_id"):
        if pub.get(campo) != ger.get(campo):
            ruins.append(f"{campo}: publicado {pub.get(campo)!r} x gerado {ger.get(campo)!r}")
    for campo, vp in (pub.get("resumo") or {}).items():
        vg = (ger.get("resumo") or {}).get(campo)
        if isinstance(vp, (int, float)) and isinstance(vg, (int, float)):
            if not _num_igual(vg, vp):
                ruins.append(f"resumo · {campo}: {vg:,.2f} (banco) x {vp:,.2f} (portal)")
        elif vp != vg:
            ruins.append(f"resumo · {campo}: {vg!r} x {vp!r}")
    for lista in ("por_categoria", "por_pagamento", "por_tabela", "atendimentos"):
        lp, lg = pub.get(lista) or [], ger.get(lista) or []
        if len(lp) != len(lg):
            ruins.append(f"{lista}: {len(lg)} itens (banco) x {len(lp)} (portal)")
            continue
        ordena = _chave_at if lista == "atendimentos" else (
            lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        for ip, ig in zip(sorted(lp, key=ordena), sorted(lg, key=ordena)):
            for c in set(ip) | set(ig):
                vp, vg = ip.get(c), ig.get(c)
                if isinstance(vp, (int, float)) and isinstance(vg, (int, float)):
                    if not _num_igual(vg, vp):
                        ruins.append(f"{lista} · OS {ip.get('Nº OS', '-')} · {c}: {vg} x {vp}")
                elif str(vp) != str(vg):
                    ruins.append(f"{lista} · {c}: {vg!r} x {vp!r}")
    return ruins


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--piloto", help="só o portal individual de quem casar com este texto")
    ap.add_argument("--somente-admins", action="store_true",
                    help="atualiza só os 3 admins; não toca em portal de médico")
    ap.add_argument("--escrever", action="store_true", help="sem isto, nada é gravado")
    a = ap.parse_args()

    print("Preparando...")
    validar_cripto()
    chaves = carregar_chaves()
    if not chaves:
        raise SystemExit("ABORTADO: nenhuma chave validada.")

    if a.validar:
        sys.exit(validar(a.periodo, chaves))

    obj = G.montar(a.periodo)
    label = obj["label"]
    print(f"\n=== {a.periodo} ({label}) · escrever={a.escrever} ===")

    if a.somente_admins:
        print("\n(--somente-admins: nenhum portal de médico será tocado)")
    print("\n--- Portais individuais (criptografados) ---" if not a.somente_admins else "")
    for slug, inner in sorted(obj["profs"].items() if not a.somente_admins else []):
        prof, emp = inner["profissional"], inner["empresa"]
        if a.piloto and a.piloto.lower() not in prof.lower():
            continue
        path = alvo_individual(prof, emp)
        if prof not in chaves:
            print(f"  [SEM CHAVE] {emp:16s} {prof}")
            continue
        dentro = profs_do_blob(obj, prof, emp)
        blob = cifrar(dentro, chaves[prof])
        extras = len(dentro) - 1
        res = injetar_individual(path, a.periodo, label, blob, a.escrever)
        print(f"  {emp:16s} {prof[:30]:32s} {len(inner['atendimentos']):4d}ln  "
              f"-> {str(path.relative_to(REPO)):46s} {res}"
              + (f"  (+{extras} visível)" if extras > 0 else ""))

    if a.piloto:
        print("\n(piloto: admins não tocados)")
        return

    print("\n--- Admin unificado: recebimento.html ---")
    res = injetar_admin(REPO / "recebimento.html", a.periodo,
                        {"label": label, "profs": obj["profs"]}, a.escrever)
    print(f"  {len(obj['profs'])} chaves -> {res}")

    print("\n--- Admin Oxy: oxy/index.html ---")
    oxy = {G.slugify(v["profissional"]) + "_Oxy_Recovery":
           {k: x for k, x in v.items() if k != "periodo_id"}
           for v in obj["profs"].values()
           if v["empresa"] == "Oxy Recovery" and alvo_individual(v["profissional"], "Oxy Recovery").exists()}
    res = injetar_admin(REPO / "oxy" / "index.html", a.periodo, {"label": label, "profs": oxy}, a.escrever)
    print(f"  {len(oxy)} chaves -> {res}")

    print("\n--- Admin Cirurgias: cirurgias/index.html ---")
    cir = {G.slugify(v["profissional"]): {k: x for k, x in v.items() if k != "periodo_id"}
           for v in obj["profs"].values() if v["empresa"] == "Cirurgias"}
    res = injetar_admin(REPO / "cirurgias" / "index.html", a.periodo, {"label": label, "profs": cir}, a.escrever)
    print(f"  {len(cir)} chaves -> {res}")

    if not a.escrever:
        print("\n[simulação] nada foi gravado. Rode com --escrever.")


if __name__ == "__main__":
    main()
