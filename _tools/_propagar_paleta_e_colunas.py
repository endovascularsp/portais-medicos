# -*- coding: utf-8 -*-
"""
_propagar_paleta_e_colunas.py — leva duas mudanças aprovadas em 06/08/2026 para
todos os portais de Recebimento e Produtividade.

1. PALETA (só cor, nenhum cálculo)
   O visual do admin de Produtividade da Oxy, aprovado pelo Thiago:
     - barra de filtros navy escura, campos claros, "Aplicar" dourado;
     - dos cartões de indicador, só o PRIMEIRO fica escuro; os demais brancos.
   O primeiro cartão é sempre o número principal (Total Recebido / Valor
   Recebido / Total Produzido) — conferido em cada família antes de escrever.

2. COLUNA DO EXPORT
   A coluna do .xlsx chamada "Imposto (18%)" carregava ISS + taxa comercial
   somados. Nas linhas com a taxa de 2% o valor é 20% do recebido, sob um
   cabeçalho que promete 18% — quem confere na calculadora não fecha.
   Vira duas colunas: "ISS (18%)" e "Taxa comercial (2%)".

   Até Maio/2026 a taxa comercial não existia (conferido: toda linha desses
   meses é exatamente 18% do recebido), e o detalhe não vem gravado. Nesses
   casos o total inteiro cai em ISS e a taxa fica zerada — o que é o fato.
   As duas colunas sempre somam o que a coluna única mostrava: nenhum total,
   líquido ou repasse muda.

Três famílias, com vocabulário de classes diferente:
   recebimento  → .kpi-row .kpi          (raiz, oxy/, cirurgias/)
   prod-admin   → .kpi.kpi-accent        (produtividade/index.html)
   prod-indiv   → .cards .card           (portais individuais de produtividade)

Uso:
    python _tools/_propagar_paleta_e_colunas.py            # simula
    python _tools/_propagar_paleta_e_colunas.py --escrever
"""
from __future__ import annotations
import argparse
import io
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 1. Coluna do export
# ---------------------------------------------------------------------------
COL_VELHA = "{h:'Imposto (18%)',     t:'m', w:15, get:a=>a['Imposto (18%)']},"
COL_NOVA = (
    "  // Ate Maio/2026 a taxa comercial nao existia e o total era so ISS; por\n"
    "  // isso, quando o detalhe nao vem gravado, o total inteiro cai em ISS e a\n"
    "  // taxa fica zerada. As duas colunas sempre somam o antigo 'Imposto (18%)'.\n"
    "{h:'ISS (18%)',         t:'m', w:14,\n"
    "   // Derivado do total, nao do ISS gravado: cada parte foi arredondada\n"
    "   // separadamente, entao em 26 linhas do semestre a soma das duas dava\n"
    "   // 1 centavo a mais ou a menos que o total que gerou o Valor Liquido.\n"
    "   // Assim as colunas sempre fecham com o liquido, sem centavo fantasma.\n"
    "   get:a=>Math.round(((a['Imposto (18%)']||0)-(a['Taxa comercial (2%)']||0))*100)/100},\n"
    "{h:'Taxa comercial (2%)', t:'m', w:19, get:a=>a['Taxa comercial (2%)']||0},"
)

# ---------------------------------------------------------------------------
# 2. Paleta — o miolo comum (barra de filtros) e a parte que muda por família
# ---------------------------------------------------------------------------
CABECALHO = """<style id="paleta-unificada">
/* ============================================================================
   Paleta unificada — 06/08/2026, a pedido do Thiago.

   Mesmo visual do admin de Produtividade da Oxy, que ele aprovou:
     1. a barra de filtros vira navy escura, com os campos claros e o botão
        Aplicar em dourado — ela passa a ser a faixa de comando da página;
     2. dos cartões de indicador, só o PRIMEIRO fica escuro. Os demais ficam
        brancos, o que faz o número principal saltar em vez de ter quatro
        blocos escuros competindo.

   Este bloco vem depois de todo o CSS original de propósito: em CSS, entre
   regras de mesmo peso, vence a última. Inserido antes, não faria efeito.

   Só cor. Nenhuma conta, valor, filtro ou regra foi tocada.
   ============================================================================ */
body{background:#EEF2F6;}
"""

BARRA = """
/* Barra de filtros escura */
.periodo-bloco{background:#0B1F3A;border-color:#0B1F3A;}
.periodo-label,.periodo-label-novo{color:rgba(255,255,255,0.65);}
.range-filter select{background:rgba(255,255,255,0.10);color:#fff;
  border-color:rgba(255,255,255,0.28);}
.range-filter select option{background:#0B1F3A;color:#fff;}
.range-btn.clear{background:rgba(255,255,255,0.10);color:#fff;
  border-color:rgba(255,255,255,0.28);}
.range-btn.clear:hover{background:rgba(255,255,255,0.20);}
.range-btn.apply{background:#A18960;border-color:#A18960;color:#0B1F3A;}
.range-ate{color:rgba(255,255,255,0.6);}
.range-sep{background:rgba(255,255,255,0.25);}
.tab{background:transparent;color:rgba(255,255,255,0.85);border-color:rgba(255,255,255,0.28);}
.tab:hover:not(.active){border-color:#A18960;color:#fff;}
.tab.active{background:#A18960;border-color:#A18960;color:#0B1F3A;}
</style>
</head>"""


def cartoes(seletor: str, prefixo: str) -> str:
    """As regras que clareiam todos os cartões menos o primeiro."""
    return f"""
/* Indicadores: só o primeiro continua escuro (é o número principal) */
{seletor}{{background:#fff;border-color:#D5DEE8;}}
{seletor} .{prefixo}-label{{color:#4A6278;}}
{seletor} .{prefixo}-{'val' if prefixo == 'kpi' else 'value'}{{color:#0B1F3A;}}
{seletor} .{prefixo}-foot{{color:#4A6278;}}
{seletor} .{prefixo}-ic{{background:rgba(11,31,58,0.08);}}
{seletor} .delta-pos{{color:#2D7A3C;}}
{seletor} .delta-neg{{color:#C0392B;}}
"""


FAMILIAS = {
    "recebimento": cartoes(".kpi-row .kpi:not(:first-child)", "kpi"),
    "prod-indiv":  cartoes(".cards .card:not(:first-child)", "card"),
}


class Falha(Exception):
    pass


def alvos() -> list:
    """(caminho, familia, faz_coluna) — só Recebimento e Produtividade."""
    out = []
    # Recebimento: raiz (portais individuais), oxy/, cirurgias/
    for pasta, nomes in (("", REPO.glob("*.html")),
                         ("oxy", (REPO / "oxy").glob("*.html")),
                         ("cirurgias", (REPO / "cirurgias").glob("*.html"))):
        for p in sorted(nomes):
            t = p.read_text(encoding="utf-8")
            if "periodo-bloco" not in t or "h:'Imposto (18%)'" not in t:
                continue          # não é portal de Recebimento
            out.append((p, "recebimento", True))
    # Produtividade: portais individuais das duas empresas
    for pasta in ("produtividade", "oxy-produtividade"):
        for p in sorted((REPO / pasta).glob("*.html")):
            if p.name == "index.html":
                continue          # os dois admins já estão prontos
            out.append((p, "prod-indiv", False))
    return out


def aplicar(t: str, familia: str, faz_coluna: bool) -> tuple[str, list]:
    feito = []
    # --- paleta ---
    if "paleta-unificada" in t:
        feito.append("paleta já existia")
    else:
        if t.count("</head>") != 1:
            raise Falha(f"</head> aparece {t.count('</head>')}x")
        bloco = CABECALHO + FAMILIAS[familia] + BARRA
        t = t.replace("</head>", bloco, 1)
        feito.append("paleta")
    # --- coluna do export ---
    if faz_coluna:
        if "h:'ISS (18%)'" in t:
            feito.append("coluna já existia")
        else:
            if t.count(COL_VELHA) != 1:
                raise Falha(f"coluna do export aparece {t.count(COL_VELHA)}x")
            t = t.replace(COL_VELHA, COL_NOVA, 1)
            feito.append("coluna")
    return t, feito


def main(escrever: bool) -> int:
    lista = alvos()
    print(f"\n=== Paleta + coluna do export · escrever={escrever} ===")
    print(f"    {sum(1 for _,f,_ in lista if f=='recebimento')} de Recebimento · "
          f"{sum(1 for _,f,_ in lista if f=='prod-indiv')} de Produtividade\n")
    ok, pulados = 0, 0
    for path, familia, faz_coluna in lista:
        bruto = path.read_bytes()
        fim = "\r\n" if bruto.count(b"\r\n") > bruto.count(b"\n") // 2 else "\n"
        t = io.open(path, encoding="utf-8").read()
        try:
            novo, feito = aplicar(t, familia, faz_coluna)
        except Falha as e:
            pulados += 1
            print(f"  [PULADO] {str(path.relative_to(REPO))[:52]:54s} {e}")
            continue
        if escrever and novo != t:
            io.open(path, "w", encoding="utf-8", newline=fim).write(novo)
        ok += 1
        print(f"  [OK]     {str(path.relative_to(REPO))[:52]:54s} {familia:12s} {', '.join(feito)}")
    print(f"\n  {ok} arquivo(s) · {pulados} pulado(s)")
    if not escrever:
        print("\n  [simulação] nada gravado. Rode com --escrever.")
    return pulados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escrever", action="store_true")
    raise SystemExit(1 if main(ap.parse_args().escrever) else 0)
