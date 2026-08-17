// Edge Function: honorarios-republicar-ajuste
//
// É o que a aba "Descontos e acréscimos" chama sozinha, sempre que alguém grava,
// edita ou exclui um lançamento. Acorda o workflow `republicar-ajuste.yml`, que
// reescreve o portal daquele médico com o valor novo.
//
// Por que existe: o portal do médico é arquivo gerado. Em 17/08/2026 a Angelina
// lançou um desconto de R$ 9.335,99 no Dr. Igor num Julho publicado em 10/08 — o
// banco passou a dizer R$ 55.763,79 e o portal continuou dizendo R$ 65.099,78.
// Sem esta função, corrigir isso dependia de alguém rodar Python com token no
// terminal, e era o último passo do fechamento que ainda pedia isso.
//
// Espelha `honorarios-atualizar-base`: mesma checagem de quem pede, mesma tabela
// de execuções, mesmo caminho de disparo. A diferença é o event_type e o fato de
// ESTA publicar em portal de médico (a outra, de propósito, não).
//
// Secrets (Dashboard → Edge Functions → Manage secrets) — os mesmos da outra
// função, já configurados no projeto:
//   GITHUB_TOKEN  — PAT fine-grained de endovascularsp/portais-medicos com
//                   "Contents: Read and write". Fica só aqui, nunca no navegador.
//   GITHUB_REPO   — opcional. Padrão: endovascularsp/portais-medicos
//
// Endpoint: POST {SUPABASE_URL}/functions/v1/honorarios-republicar-ajuste
// Body:     { "periodo": "2026-07", "profissional": "Igor Rafael Sincos",
//             "empresa": "Endovascular SP" }
// Resposta: { "execucao_id": 12 } ou { "execucao_id": 12, "ja_rodando": true }

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const GITHUB_TOKEN = Deno.env.get("GITHUB_TOKEN") ?? "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") ?? "endovascularsp/portais-medicos";

// Quem edita um desconto normalmente edita dois ou três seguidos. Cada gravação
// pedindo sua própria publicação encheria a fila de rodadas quase iguais. Uma
// publicação recente do MESMO médico no MESMO mês serve para as seguintes: o
// workflow lê o banco na hora que roda, então ele já vai levar as edições
// posteriores. Curto de propósito — não é para engolir um lançamento de 10
// minutos depois.
const JANELA_AGRUPAMENTO_MIN = 3;

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });

/* ---------- banco com service_role (passa por cima da RLS) ---------- */
async function db(path: string, init: RequestInit = {}) {
  const r = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...init,
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!r.ok) throw new Error(`DB ${path}: ${r.status} ${await r.text()}`);
  const txt = await r.text();
  return txt ? JSON.parse(txt) : null;
}

/* ---------- quem está pedindo ---------- */
// O JWT diz quem é; o banco diz se essa pessoa manda no fechamento. Ter conta
// não é ter permissão — e aqui o efeito é escrever no portal de um médico.
async function quemChamou(req: Request): Promise<string | null> {
  const auth = req.headers.get("Authorization") ?? "";
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const r = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: { apikey: SERVICE_KEY, Authorization: auth },
  });
  if (!r.ok) return null;
  const u = await r.json();
  return (u?.email ?? "").toLowerCase() || null;
}

async function podeFechar(email: string): Promise<boolean> {
  const us = await db(
    `users?email=eq.${encodeURIComponent(email)}&select=role,cards`,
  );
  const u = Array.isArray(us) ? us[0] : null;
  if (!u) return false;
  if (u.role === "admin") return true;
  const cards: string[] = Array.isArray(u.cards) ? u.cards : [];
  return cards.includes("honorarios") || cards.includes("gestor_fechamento") ||
    cards.includes("gestor");
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS_HEADERS });
  if (req.method !== "POST") return json({ erro: "método não permitido" }, 405);

  try {
    const email = await quemChamou(req);
    if (!email) return json({ erro: "não autenticado" }, 401);
    if (!(await podeFechar(email))) return json({ erro: "sem permissão" }, 403);

    if (!GITHUB_TOKEN) {
      return json({ erro: "GITHUB_TOKEN não configurado nesta função" }, 500);
    }

    const corpo = await req.json().catch(() => ({}));
    const periodo = String(corpo?.periodo ?? "").trim();
    const profissional = String(corpo?.profissional ?? "").trim();
    const empresa = String(corpo?.empresa ?? "").trim();

    if (!/^\d{4}-\d{2}$/.test(periodo)) {
      return json({ erro: "período inválido (esperado AAAA-MM)" }, 400);
    }
    if (!profissional) return json({ erro: "profissional é obrigatório" }, 400);

    // Já tem uma publicação recente deste médico neste mês? Reaproveita.
    const desde = new Date(Date.now() - JANELA_AGRUPAMENTO_MIN * 60_000).toISOString();
    const vivas = await db(
      `honorarios_execucoes?tipo=eq.publicacao&status=in.(enfileirado,rodando)` +
      `&periodo_id=eq.${encodeURIComponent(periodo)}` +
      `&iniciado_em=gte.${desde}&select=id,mensagem&order=id.desc&limit=5`,
    );
    const mesmoProf = (Array.isArray(vivas) ? vivas : []).find(
      (v: { mensagem?: string }) => (v.mensagem ?? "").includes(profissional),
    );
    if (mesmoProf) {
      return json({ execucao_id: mesmoProf.id, ja_rodando: true });
    }

    const criada = await db("honorarios_execucoes", {
      method: "POST",
      headers: { Prefer: "return=representation" },
      body: JSON.stringify({
        tipo: "publicacao",
        periodo_id: periodo,
        status: "enfileirado",
        disparado_por: email,
        // A mensagem já nasce dizendo de quem é: é por ela que a chamada
        // seguinte, dentro da janela, reconhece que já tem uma na fila.
        mensagem: `${profissional}${empresa ? ` · ${empresa}` : ""} · aguardando`,
      }),
    });
    const execucao_id = Array.isArray(criada) ? criada[0]?.id : criada?.id;

    const disparo = await fetch(
      `https://api.github.com/repos/${GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          event_type: "republicar-ajuste",
          client_payload: {
            periodo, profissional, empresa, execucao_id, disparado_por: email,
          },
        }),
      },
    );

    if (!disparo.ok) {
      const detalhe = await disparo.text();
      // Sem isto a linha ficaria "enfileirado" para sempre e a tela mentiria.
      if (execucao_id) {
        await db(`honorarios_execucoes?id=eq.${execucao_id}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: "erro",
            terminado_em: new Date().toISOString(),
            mensagem: `não consegui acionar a publicação (GitHub ${disparo.status})`,
          }),
        });
      }
      return json({ erro: "falha ao acionar a publicação", detalhe }, 502);
    }

    return json({ execucao_id });
  } catch (e) {
    return json({ erro: String(e) }, 500);
  }
});
