# -*- coding: utf-8 -*-
"""
_honorarios_motor.py — calcula o repasse de um período a partir dos CSVs do SVN.

Lê os exports do relatório #560 (um por instituição: Endovascular SP e Oxy
Recovery), resolve a categoria pelo catálogo de procedimentos, aplica as regras
de `_honorarios_regras.py` e gera o SQL de carga do período.

O motor NUNCA chuta. O que ele não souber resolver vira uma linha na fila de
exceções (`honorarios_excecoes`), com contexto suficiente para decidir.

Uso:
    python _tools/_honorarios_motor.py --periodo 2026-07 \
        --endo "C:\\...\\560_endo.csv" --oxy "C:\\...\\560_oxy.csv" [--dry-run]
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _honorarios_regras as R      # noqa: E402
import _honorarios_catalogo as _cat  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
# Onde `_svn_puxar_560.py` grava o que baixa da API do SVN.
CACHE_SVN = Path.home() / "Documents" / "Endovascular_Farmer" / "svn_560_cache"
# A constante da planilha saiu em 07/08/2026: o motor não abre mais o Excel.
# O catálogo vem do Supabase (ver _honorarios_catalogo.carregar).

CHAVE_NATURAL = ["empresa", "os_numero", "procedimento", "data_compensacao",
                 "valor_recebido", "profissional"]


# --------------------------------------------------------------------------
# Leitura do CSV do SVN
# --------------------------------------------------------------------------
def num_br(v):
    """'2.000,00' -> 2000.00"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return 0.0
    return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s.replace(".", ""))


def data_br(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return pd.to_datetime(str(v).strip(), dayfirst=True).strftime("%Y-%m-%d")
    except Exception:
        return None


def ler_csv(caminho: str, empresa: str) -> pd.DataFrame:
    txt = open(caminho, "rb").read().decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(txt), sep=";")
    out = pd.DataFrame({
        "empresa":          empresa,
        "os_numero":        df["N° OS"].astype(str).str.strip(),
        "profissional":     df["Profissional"],
        "solicitante":      df["Profissional solicitante"],
        "paciente":         df["Nome cliente"],
        "indicacao":        df["Indicado Por"],
        "tabela":           df["Tabela"],
        "procedimento":     df["Procedimento"],
        "conta_pagamento":  df["Conta de pagamento"],
        "data_emissao":     df["Data emissão"].map(data_br),
        "data_compensacao": df["Data compensação"].map(data_br),
        "tipo_pagamento":   df["Tipo de pagamento"],
        "valor_recebido":   df["Valor recebido"].map(num_br),
        # O custo NÃO entra no cálculo. O SVN preenche "Custo proporcional" com o
        # custo do PROCEDIMENTO INTEIRO, enquanto "Valor recebido" é o da PARCELA —
        # subtrair um do outro produz líquido negativo (uma sessão de R$ 106 com
        # custo de R$ 106). Na prática a clínica sempre fechou com custo zero
        # (4.763 linhas de Jan–Jun, todas zeradas). Guardamos o que o SVN informou
        # em `custo_svn` só para conferência, e calculamos com custo = 0.
        "custo":            0.0,
        "custo_svn":        df["Custo proporcional"].map(num_br),
        "situacao":         df["Situação Agendamento"],
    })
    return out


# --------------------------------------------------------------------------
# Mesma leitura, direto da API do SVN — sem CSV exportado à mão
# --------------------------------------------------------------------------
# O mapa abaixo NÃO foi deduzido pelos nomes. Foi provado em 07/08/2026 casando
# o CSV de Julho/2026 exportado à mão (722 linhas) com o retorno da API do mesmo
# período e filtro, e comparando campo a campo. Nas 329 linhas em que o par
# (OS, procedimento) é único — e portanto o casamento é certo — os 14 campos
# bateram em 329/329. Ver o registro em `reference_svn_api_mapa_560`.
API_PARA_CSV = {
    "os_numero":        "orca_id",
    "profissional":     "nome_profissional",
    "solicitante":      "nome_profissional_solicitante",
    "paciente":         "nome_cliente",
    "indicacao":        "pein_tx_indicado_por",
    "tabela":           "tpre_tx_descricao",
    "procedimento":     "proc_tx_nome",
    "conta_pagamento":  "cofi_tx_descricao",
    "data_emissao":     "cont_dt_emissao",
    "data_compensacao": "baix_dt_recebimento",
    "tipo_pagamento":   "tipa_tx_descricao",
    "valor_recebido":   "valor_recebido_prop",
    "custo_svn":        "custo_prop",
    "situacao":         "siag_id_label",
}

# ATENÇÃO ao nome do filtro: os rótulos da API são o OPOSTO dos da tela.
# Honorário é o que a clínica REALMENTE recebeu — a tela chama de "Compensação",
# e na API isso é `baix_dt_recebimento`.
FILTRO_COMPENSACAO = "baix_dt_recebimento"


def _data_iso(v):
    """Data da API -> datetime.

    A API mistura dois formatos: a maioria dos campos vem em DD/MM/AAAA, mas
    alguns (orca_dt_orcamento) vêm em AAAA-MM-DD. Ler tudo com o padrão do
    pandas trocava dia por mês: '07/06/2026' (7 de junho) virava 6 de julho.
    Isso corrompia a data de compensação, que além de aparecer para o médico
    faz parte da chave que identifica a linha no banco — 390 linhas de Julho
    deixaram de casar com as já gravadas por causa disso.
    """
    s = str(v or "").strip()
    if not s or s.lower() in ("none", "nan"):
        return pd.NaT
    s = s[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return pd.to_datetime(s, errors="coerce")           # já é ISO
    return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")


def ler_api(instituicao: str, periodo: str, empresa: str) -> pd.DataFrame:
    """Mesmo DataFrame que `ler_csv`, montado a partir do cache da API.

    O cache é gravado por `_svn_puxar_560.py`. Se o arquivo do período não
    existir, aborta dizendo o comando — nunca busca sozinho, para não disparar
    dezenas de requisições ao SVN sem o operador saber.
    """
    arq = CACHE_SVN / f"560_{instituicao}_{periodo}_{FILTRO_COMPENSACAO}.json"
    if not arq.exists():
        raise SystemExit(
            f"ABORTADO: {arq.name} não existe.\n"
            f"  Baixe antes:  python _tools/_svn_puxar_560.py --instituicao {instituicao} "
            f"--de {periodo} --ate {periodo} --filtro-data {FILTRO_COMPENSACAO}")
    dados = json.loads(arq.read_text(encoding="utf-8"))
    if not dados:
        raise SystemExit(f"ABORTADO: {arq.name} está vazio.")
    bruto = pd.DataFrame(dados)
    faltam = [c for c in API_PARA_CSV.values() if c not in bruto.columns]
    if faltam:
        raise SystemExit(f"ABORTADO: a API não trouxe {faltam} — o relatório #560 mudou de forma.")
    out = pd.DataFrame({destino: bruto[origem] for destino, origem in API_PARA_CSV.items()})
    out["empresa"] = empresa
    out["os_numero"] = out["os_numero"].astype(str).str.strip()
    out["data_emissao"] = out["data_emissao"].map(_data_iso)
    out["data_compensacao"] = out["data_compensacao"].map(_data_iso)
    for c in ("valor_recebido", "custo_svn"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    out["custo"] = 0.0        # mesma decisão do ler_csv: custo não entra na conta
    return out


# --------------------------------------------------------------------------
# Catálogo de procedimentos (mesma fonte que alimentou o banco)
# --------------------------------------------------------------------------
def carregar_catalogo() -> dict:
    """Catálogo procedimento -> categoria, lido do Supabase.
    Fonte única em `_honorarios_catalogo.py`, compartilhada com o gerador do seed.
    Até 07/08/2026 isto abria a aba "Apoio" do Excel de fechamento — era o
    último ponto do motor que dependia da planilha."""
    return _cat.carregar()


# --------------------------------------------------------------------------
# Motor
# --------------------------------------------------------------------------
def nf_propria(profissional, conta) -> bool:
    c = R.chave(conta)
    if not c:
        return False
    if c in R.CONTA_PROPRIA_LITERAL:
        return True
    return any(t in c for t in R.chave(profissional).split() if len(t) > 3)


def resolver_dono(df) -> pd.DataFrame:
    """Executante em branco -> o dono é o SOLICITANTE (decisão do Thiago, 03/08/2026).
    No SVN o executante só é preenchido quando alguém de fato executou.

    TEM que rodar ANTES do cálculo do `seq`. Se o seq for calculado com o campo
    ainda em branco, uma linha herdada recebe seq 1 dentro do grupo "sem dono" e
    colide com uma linha que já era daquele profissional e também tem seq 1 —
    mesma OS, mesmo procedimento, mesma data, mesmo valor. O banco então descarta
    uma de cada par no ON CONFLICT. Foi o que tirou 12 lançamentos de Julho."""
    vazio = df["profissional"].isna() | (df["profissional"].astype(str).str.strip().isin(["", "nan"]))
    tem_sol = df["solicitante"].notna() & (df["solicitante"].astype(str).str.strip() != "")
    df["via_solicitante"] = vazio & tem_sol
    df.loc[df["via_solicitante"], "profissional"] = df.loc[df["via_solicitante"], "solicitante"]
    return df


def nomes_profissionais(df) -> set:
    """Sobrenomes dos profissionais que aparecem no período, para reconhecer quando
    o campo "Indicado Por" traz o nome de alguém da casa."""
    out = set()
    for col in ("profissional", "solicitante"):
        for v in df[col].dropna().unique():
            for t in R.chave(v).split():
                if len(t) > 4:
                    out.add(t)
    return out


def calcular(row, periodo_id, catalogo, nomes_prof=()):
    """Devolve (valores, excecao). `excecao` = None quando o motor resolveu."""
    ctx = dict(row)
    prof, empresa = row["profissional"], row["empresa"]
    bruto = float(row["valor_recebido"] or 0)
    custo = float(row["custo"] or 0)

    # pd.isna, não `not prof`: o campo vem como NaN quando está vazio no SVN, e
    # bool(NaN) é True — 40 linhas de Julho passavam direto e recebiam repasse
    # calculado sem dono (R$ 6.634,36).
    # O dono já vem resolvido de `resolver_dono()`, que roda ANTES do seq.
    prof_k = R.chave(prof) if not pd.isna(prof) else ""
    via_solicitante = bool(row.get("via_solicitante"))

    if prof_k in R.IGNORAR_PROFISSIONAL:
        # Regra conhecida, não dúvida: Enfermagem, Paulo Laredo, Agendamento
        # Cirúrgico e afins não são corpo clínico. Sai do cálculo sem ir para a
        # fila — senão a fila enche de ruído todo mês e ninguém mais a lê.
        return None, ("__ignorar__", prof_k, None)
    if not prof_k:
        return None, ("profissional_invalido",
                      "Profissional em branco no SVN",
                      "Linha não gera repasse enquanto não tiver dono definido.")

    categoria, origem_cat = _cat.categoria_de(row["procedimento"], row["os_numero"], catalogo)
    if not categoria:
        return None, ("procedimento_sem_categoria", origem_cat,
                      "Classificar a categoria para o motor calcular.")
    ctx["categoria"] = categoria
    por_os = origem_cat == "categoria definida por OS"
    cat_k = R.chave(categoria)

    # --- Regra 3A: NF na conta do profissional ---
    if nf_propria(prof, row["conta_pagamento"]):
        ctx.update(imposto=0.0, taxa_comercial=0.0, taxa_cartao=0.0, valor_liquido=0.0,
                   repasse_profissional=-R.REPASSE_CLINICA_NF_PROPRIA * bruto,
                   repasse_indicador=0.0,
                   repasse_clinica=R.REPASSE_CLINICA_NF_PROPRIA * bruto,
                   pct_aplicado=-R.REPASSE_CLINICA_NF_PROPRIA, papel="executor",
                   nf_propria=True, regra_aplicada="R3A NF do profissional")
        return ctx, None

    # --- impostos e taxas ---
    iss = R.ISS * bruto
    tcom = R.TAXA_COMERCIAL * bruto if R.tem_taxa_comercial(categoria, periodo_id) else 0.0
    tcar = R.TAXA_CARTAO * bruto if R.chave(row["tipo_pagamento"]) in R.TIPOS_COM_TAXA_CARTAO else 0.0
    liquido = bruto - iss - tcom - tcar - custo
    ctx.update(imposto=iss, taxa_comercial=tcom, taxa_cartao=tcar,
               valor_liquido=liquido, nf_propria=False)

    # --- cirurgias ---
    if cat_k == "cirurgia - clinica":
        pct, regra = R.CIRURGIA_CLINICA, "R2 cirurgia em clínica particular"
        papel = "executor"
    elif cat_k == "cirurgia - hospital":
        papel = "executor"
        if R.eh_plano(row["tabela"]):
            pct, regra = R.CIRURGIA_PLANO, "R1 cirurgia por plano de saúde"
        else:
            pct, regra = R.origem_lead(row["indicacao"], nomes_prof)
    else:
        papel = R.papel_de(empresa, categoria, prof)
        pct, regra = R.percentual(empresa, categoria, prof, papel)
        if pct is None:
            return None, ("sem_regra", regra, "Cadastrar o percentual da categoria.")

    rep_prof = pct * liquido
    if via_solicitante:
        regra += " (dono via solicitante)"
    if por_os:
        regra += " (categoria por OS)"
    ctx.update(papel=papel, pct_aplicado=pct, regra_aplicada=regra,
               repasse_profissional=rep_prof if papel == "executor" else 0.0,
               repasse_indicador=rep_prof if papel == "indicador" else 0.0)
    ctx["repasse_clinica"] = liquido - ctx["repasse_profissional"] - ctx["repasse_indicador"]
    return ctx, None


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------
def lit(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "NULL"
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def n(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "0"
    return "0" if pd.isna(f) else f"{f:.4f}"


COLS_LANC = ["periodo_id", "empresa", "os_numero", "profissional", "solicitante", "paciente",
             "indicacao", "tabela", "procedimento", "categoria", "conta_pagamento",
             "data_emissao", "data_compensacao", "tipo_pagamento", "valor_recebido", "custo",
             "seq", "imposto", "taxa_comercial", "taxa_cartao", "valor_liquido",
             "repasse_profissional", "repasse_indicador", "repasse_clinica",
             "pct_aplicado", "regra_aplicada", "papel", "nf_propria", "origem", "congelado"]

COLS_EXC = ["periodo_id", "tipo", "empresa", "os_numero", "profissional", "paciente",
            "procedimento", "categoria", "tabela", "indicacao", "valor_recebido",
            "data_compensacao", "descricao", "sugestao"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--periodo", required=True)
    ap.add_argument("--da-api", action="store_true",
                    help="lê do cache da API do SVN em vez dos CSVs exportados à mão")
    ap.add_argument("--endo", help="CSV do Endovascular (dispensável com --da-api)")
    ap.add_argument("--oxy", help="CSV da Oxy Recovery (dispensável com --da-api)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    catalogo = carregar_catalogo()
    if a.da_api:
        df = pd.concat([ler_api("endo", a.periodo, R.ENDO),
                        ler_api("oxy",  a.periodo, R.OXY)], ignore_index=True)
        fonte = "API do SVN"
    else:
        if not a.endo or not a.oxy:
            raise SystemExit("ABORTADO: informe --endo e --oxy, ou use --da-api.")
        df = pd.concat([ler_csv(a.endo, R.ENDO), ler_csv(a.oxy, R.OXY)], ignore_index=True)
        fonte = "CSVs exportados à mão"
    print(f"=== MOTOR DE REPASSE — {a.periodo} ===")
    print(f"Catálogo ..........: {len(catalogo)} procedimentos (do Supabase)")
    print(f"Fonte .............: {fonte}")
    print(f"Linhas lidas ......: {len(df)}  (Endo {sum(df.empresa == R.ENDO)} / Oxy {sum(df.empresa == R.OXY)})")

    df = resolver_dono(df)
    n_herdadas = int(df["via_solicitante"].sum())
    if n_herdadas:
        print(f"Sem executante ....: {n_herdadas} linhas herdaram o solicitante como dono")

    # seq dentro do grupo da chave natural (pacotes e parcelas geram linhas idênticas).
    # O map explícito é necessário: no pandas 3 o `.astype(str)` PRESERVA o vazio como
    # nulo em vez de virar "nan", e aí o groupby descarta esses grupos — as 43 linhas
    # sem executante saíam com seq vazio e quebravam a geração do SQL.
    chaves = [df[c].map(lambda v: "" if pd.isna(v) else str(v)) for c in CHAVE_NATURAL]
    df["seq"] = df.groupby(chaves).cumcount() + 1
    assert df["seq"].notna().all(), "seq vazio — chave natural com valor nulo"
    dup = df.duplicated(subset=CHAVE_NATURAL + ["seq"]).sum()
    assert dup == 0, f"{dup} linhas colidem na chave natural — o banco descartaria essas"

    nomes_prof = nomes_profissionais(df)
    ok, exc, ignorados = [], [], Counter()
    for _, row in df.iterrows():
        val, e = calcular(row, a.periodo, catalogo, nomes_prof)
        if e:
            tipo, desc, sug = e
            if tipo == "__ignorar__":
                ignorados[desc] += 1
                continue
            exc.append({**row, "tipo": tipo, "descricao": desc, "sugestao": sug,
                        "categoria": catalogo.get(R.chave(row["procedimento"]))})
        else:
            ok.append(val)

    if ignorados:
        print(f"\nFora do corpo clínico (excluídos por regra): {sum(ignorados.values())}")
        for k, q in ignorados.most_common():
            print(f"    {k:44s} {q:4d}")
    print(f"\nCalculados ........: {len(ok)}  ({100*len(ok)/max(len(df),1):.1f}% dos {len(df)})")
    print(f"Fila de exceções ..: {len(exc)}")
    for t, q in Counter(x["tipo"] for x in exc).most_common():
        print(f"    {t:28s} {q:4d}")

    svn_custo = df[df["custo_svn"] > 0]
    if len(svn_custo):
        print(f"\n[aviso] o SVN informou custo em {len(svn_custo)} linhas "
              f"(R$ {svn_custo['custo_svn'].sum():,.2f}), ignorado no cálculo — é custo do"
              " procedimento inteiro, não da parcela. Confirmar com o Thiago se algum dia entrar.")

    if ok:
        s = pd.DataFrame(ok)
        neg = s[s["valor_liquido"] < -0.01]
        if len(neg):
            print(f"\n[ALERTA] {len(neg)} linhas com líquido negativo — investigar antes de subir.")
        print(f"\nRecebido ..........: R$ {s['valor_recebido'].sum():>14,.2f}")
        print(f"ISS ...............: R$ {s['imposto'].sum():>14,.2f}")
        print(f"Taxa comercial 2% .: R$ {s['taxa_comercial'].sum():>14,.2f}")
        print(f"Taxa cartão .......: R$ {s['taxa_cartao'].sum():>14,.2f}")
        print(f"Líquido ...........: R$ {s['valor_liquido'].sum():>14,.2f}")
        print(f"Repasse profissional R$ {s['repasse_profissional'].sum():>14,.2f}")
        print(f"Repasse indicador .: R$ {s['repasse_indicador'].sum():>14,.2f}")
        print(f"Repasse clínica ...: R$ {s['repasse_clinica'].sum():>14,.2f}")
        cir = s[s["regra_aplicada"].astype(str).str.startswith(("R3B", "R3C"))]
        if len(cir):
            print("\n--- cirurgia em hospital particular: como o lead foi classificado ---")
            gc = cir.groupby("regra_aplicada").agg(
                linhas=("os_numero", "size"), recebido=("valor_recebido", "sum"),
                repasse=("repasse_profissional", "sum"))
            for regra, r in gc.iterrows():
                print(f"  {regra:64s} {int(r['linhas']):3d}ln  R$ {r['repasse']:>12,.2f}")
            print("  origens que caíram em cada lado:")
            for regra, grp in cir.groupby("regra_aplicada"):
                vals = grp["indicacao"].fillna("(vazio)").replace("", "(vazio)").value_counts()
                print(f"    [{regra[:44]}] {dict(list(vals.items())[:8])}")

        print("\n--- repasse por profissional ---")
        g = s.groupby(["empresa", "profissional"]).agg(
            linhas=("os_numero", "size"),
            repasse=("repasse_profissional", "sum"),
            indicacao=("repasse_indicador", "sum")).sort_values("repasse", ascending=False)
        for (emp, prof), r in g.iterrows():
            extra = f"  (+ind {r['indicacao']:>9,.2f})" if r["indicacao"] else ""
            print(f"  {emp[:12]:12s} {str(prof)[:32]:32s} {int(r['linhas']):4d}ln  R$ {r['repasse']:>12,.2f}{extra}")

    if exc:
        print("\n--- fila de exceções (agrupada) ---")
        ge = pd.DataFrame(exc).groupby(["tipo", "descricao"]).size().sort_values(ascending=False)
        for (t, d), q in ge.items():
            print(f"  {q:4d}x [{t}] {d[:96]}")

    if a.dry_run:
        print("\n[dry-run] nada foi escrito.")
        return

    destino = REPO / "db" / f"carga_{a.periodo.replace('-', '_')}_honorarios.sql"
    partes = [
        f"-- Carga do período {a.periodo} — gerada por _tools/_honorarios_motor.py\n"
        f"-- {len(ok)} lançamentos calculados + {len(exc)} exceções para decisão.\n"
        "-- Reexecutável: ON CONFLICT nas duas tabelas.\n"
    ]
    if ok:
        vals = ",\n  ".join(
            "(" + ", ".join([
                lit(a.periodo), lit(r["empresa"]), lit(r["os_numero"]), lit(r["profissional"]),
                lit(r["solicitante"]), lit(r["paciente"]), lit(r["indicacao"]), lit(r["tabela"]),
                lit(r["procedimento"]), lit(r["categoria"]), lit(r["conta_pagamento"]),
                lit(r["data_emissao"]), lit(r["data_compensacao"]), lit(r["tipo_pagamento"]),
                n(r["valor_recebido"]), n(r["custo"]), str(int(r["seq"])),
                n(r["imposto"]), n(r["taxa_comercial"]), n(r["taxa_cartao"]), n(r["valor_liquido"]),
                n(r["repasse_profissional"]), n(r["repasse_indicador"]), n(r["repasse_clinica"]),
                n(r["pct_aplicado"]), lit(r["regra_aplicada"]), lit(r["papel"]),
                "true" if r["nf_propria"] else "false", "'csv_svn'", "false",
            ]) + ")" for r in ok)
        partes.append(
            f"INSERT INTO public.honorarios_lancamentos ({', '.join(COLS_LANC)}) VALUES\n  {vals}\n"
            "ON CONFLICT (empresa, os_numero, procedimento, data_compensacao,"
            " valor_recebido, profissional, seq) DO NOTHING;\n")
    if exc:
        vals = ",\n  ".join(
            "(" + ", ".join([
                lit(a.periodo), lit(r["tipo"]), lit(r["empresa"]), lit(r["os_numero"]),
                lit(r["profissional"]), lit(r["paciente"]), lit(r["procedimento"]),
                lit(r.get("categoria")), lit(r["tabela"]), lit(r["indicacao"]),
                n(r["valor_recebido"]), lit(r["data_compensacao"]),
                lit(r["descricao"]), lit(r["sugestao"]),
            ]) + ")" for r in exc)
        partes.append(
            f"INSERT INTO public.honorarios_excecoes ({', '.join(COLS_EXC)}) VALUES\n  {vals}\n"
            "ON CONFLICT DO NOTHING;\n")
    partes.append(
        "\n-- Conferência:\n"
        f"-- SELECT count(*), round(sum(repasse_profissional),2) FROM public.honorarios_lancamentos WHERE periodo_id = '{a.periodo}';\n"
        f"-- SELECT tipo, count(*) FROM public.honorarios_excecoes WHERE periodo_id = '{a.periodo}' AND status='aberta' GROUP BY tipo;\n")
    destino.write_text("\n".join(partes), encoding="utf-8")
    print(f"\nGerado: {destino}  ({destino.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
