// Edge Function: honorarios-atualizar-base
// É o que o botão "Atualizar base" do card de Fechamento chama.
//
// Não calcula nada: confere quem está pedindo, abre uma linha em
// honorarios_execucoes e acorda o GitHub Actions, que roda os mesmos scripts
// que hoje rodam no terminal do Thiago (_honorarios_fechar.py --so-base).
//
// Por que passar pelo GitHub e não fazer aqui: o cálculo é Python com pandas e
// as regras de repasse moram em `_tools/`. Reescrever isso em TypeScript seria
// manter duas verdades sobre dinheiro de médico — a pior coisa possível.
//
// A rotina NÃO publica portal. Publicar é passo à parte, deliberado.
//
// Secrets necessários (Dashboard → Edge Functions → Manage secrets):
//   GITHUB_TOKEN  — PAT fine-grained do repo endovascularsp/portais-medicos,
//                   permissão "Contents: Read and write" (é o que libera o
//                   repository_dispatch). Fica só aqui, nunca no navegador.
//   GITHUB_REPO   — opcional. Padrão: endovascularsp/portais-medicos
// (SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY já vêm da plataforma.)
//
// Endpoint: POST {SUPABASE_URL}/functions/v1/honorarios-atualizar-base
// Body:     { "periodo": "auto" }            (ou "2026-08")
// Resposta: { "execucao_id": 12, "periodo": "auto" }

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const GITHUB_TOKEN = Deno.env.get("GITHUB_TOKEN") ?? "";
const GITHUB_REPO = Deno.env.get("GITHUB_REPO") ?? "endovascularsp/portais-medicos";

// Duas pessoas clicando no mesmo minuto não podem virar duas rodadas: o
// concurrency do Actions enfileiraria, mas a tela mostraria duas execuções e
// ninguém entenderia. Uma execução recente ainda viva basta.
const JANELA_EM_ANDAMENTO_MIN = 20;

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
// O JWT diz quem é; o banco diz se essa pessoa manda no fechamento. As duas
// perguntas são separadas de propósito: ter conta não é ter permissão.
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
  // Mesmo critério da tela: o card próprio ou o guarda-chuva da gestão.
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
    const periodo = String(corpo?.periodo ?? "auto");

    // Já tem uma rodando? Devolve ela, em vez de abrir outra.
    const desde = new Date(Date.now() - JANELA_EM_ANDAMENTO_MIN * 60_000).toISOString();
    const vivas = await db(
      `honorarios_execucoes?tipo=eq.base&status=in.(enfileirado,rodando)` +
      `&iniciado_em=gte.${desde}&select=id&order=id.desc&limit=1`,
    );
    if (Array.isArray(vivas) && vivas.length) {
      return json({ execucao_id: vivas[0].id, periodo, ja_rodando: true });
    }

    const criada = await db("honorarios_execucoes", {
      method: "POST",
      headers: { Prefer: "return=representation" },
      body: JSON.stringify({
        tipo: "base",
        periodo_id: periodo,
        status: "enfileirado",
        disparado_por: email,
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
          event_type: "atualizar-base",
          client_payload: { periodo, execucao_id, disparado_por: email },
        }),
      },
    );

    if (!disparo.ok) {
      const detalhe = await disparo.text();
      // Sem isto a linha ficaria "enfileirado" para sempre e a tela mentiria
      // dizendo que está rodando.
      if (execucao_id) {
        await db(`honorarios_execucoes?id=eq.${execucao_id}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: "erro",
            terminado_em: new Date().toISOString(),
            mensagem: `não consegui acionar a rotina (GitHub ${disparo.status})`,
          }),
        });
      }
      return json({ erro: "falha ao acionar a rotina", detalhe }, 502);
    }

    return json({ execucao_id, periodo });
  } catch (e) {
    return json({ erro: String(e) }, 500);
  }
});
