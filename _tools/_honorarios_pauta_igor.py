# Pauta da conversa com o Dr. Igor: procedimentos com ROTULO DE CIRURGIA e
# ticket medio baixo. O rotulo de cirurgia tira a linha do percentual fixo e
# joga na regra de lead (80/90%) — por isso ticket baixo com rotulo de cirurgia
# e o sinal de que a categoria pode estar errada.
import json, urllib.request, collections

ENV = r"C:\Users\thiag\Documents\Endovascular_Farmer\.env"
env = {}
for ln in open(ENV, encoding="utf-8", errors="replace"):
    ln = ln.strip()
    if ln and not ln.startswith("#") and "=" in ln:
        k, v = ln.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
URL = env["SUPABASE_URL"].rstrip("/"); KEY = env["SUPABASE_SERVICE_KEY"]

def q(t, params):
    req = urllib.request.Request(f"{URL}/rest/v1/{t}?{params}", headers={
        "apikey": KEY, "Authorization": f"Bearer {KEY}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))

# paginacao (o PostgREST corta em 1000)
lanc, passo, off = [], 1000, 0
while True:
    lote = q("honorarios_lancamentos",
             f"select=periodo_id,procedimento,categoria,valor_recebido,repasse_profissional,"
             f"repasse_clinica,pct_aplicado,profissional&limit={passo}&offset={off}")
    lanc += lote
    if len(lote) < passo: break
    off += passo
print(f"{len(lanc)} lancamentos lidos\n")

LIMITE = 1500.0
cir = [l for l in lanc if "cirurgia" in str(l.get("categoria") or "").lower()]

por_proc = collections.defaultdict(list)
for l in cir:
    por_proc[(l["procedimento"], l["categoria"])].append(l)

linhas = []
for (proc, cat), ls in por_proc.items():
    vals = [float(l.get("valor_recebido") or 0) for l in ls]
    n = len(vals); ticket = sum(vals) / n if n else 0
    if ticket >= LIMITE: continue
    rep = sum(float(l.get("repasse_profissional") or 0) for l in ls)
    cli = sum(float(l.get("repasse_clinica") or 0) for l in ls)
    pcts = sorted({round(float(l["pct_aplicado"]) * 100) for l in ls if l.get("pct_aplicado") is not None})
    profs = collections.Counter(l["profissional"] for l in ls)
    periodos = sorted({l["periodo_id"] for l in ls})
    linhas.append({"proc": proc, "cat": cat, "n": n, "ticket": ticket,
                   "recebido": sum(vals), "repasse": rep, "clinica": cli,
                   "pcts": pcts, "profs": profs, "periodos": periodos})

linhas.sort(key=lambda x: -x["repasse"])

print(f"{len(linhas)} procedimentos com rotulo de CIRURGIA e ticket medio < R$ {LIMITE:,.0f}\n")
print(f"{'#':>3} {'lanc':>5} {'ticket':>10} {'recebido':>12} {'repasse prof':>13} {'%':>10}  procedimento")
print("-" * 118)
for i, l in enumerate(linhas, 1):
    pcts = "/".join(str(p) for p in l["pcts"]) + "%"
    print(f"{i:>3} {l['n']:>5} {l['ticket']:>10,.2f} {l['recebido']:>12,.2f} "
          f"{l['repasse']:>13,.2f} {pcts:>10}  {l['proc'][:52]}")

print(f"\n{'':>3} {'':>5} {'':>10} {sum(l['recebido'] for l in linhas):>12,.2f} "
      f"{sum(l['repasse'] for l in linhas):>13,.2f}   TOTAL")

print("\n\n--- detalhe por procedimento ---")
for i, l in enumerate(linhas, 1):
    print(f"\n{i}. {l['proc']}  [{l['cat']}]")
    print(f"   {l['n']} lancamentos | ticket medio R$ {l['ticket']:,.2f} | "
          f"recebido R$ {l['recebido']:,.2f}")
    print(f"   repasse profissional R$ {l['repasse']:,.2f} | clinica R$ {l['clinica']:,.2f} | "
          f"percentuais {'/'.join(str(p) for p in l['pcts'])}%")
    print(f"   periodos: {', '.join(l['periodos'])}")
    print(f"   profissionais: {', '.join(f'{p} ({n})' for p, n in l['profs'].most_common())}")

json.dump(linhas, open("pauta_igor.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
