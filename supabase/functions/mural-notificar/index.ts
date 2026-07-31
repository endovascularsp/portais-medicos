// Edge Function: mural-notificar
// Dispara os e-mails do Mural de Avisos. Chamada pelo portal (mural/index.html)
// logo depois de publicar um aviso, de comentar, ou ao clicar em "cobrar quem não leu".
//
// Secrets necessários no Supabase (Dashboard → Edge Functions → Manage secrets):
//   RESEND_API_KEY   — chave da conta Resend (re_...)
//   MURAL_FROM       — opcional. Padrão: "Mural Endovascular SP <avisos@portalendovascularsp.com.br>"
//                      Sai do domínio DOS PORTAIS, não do corporativo: o DNS de
//                      portalendovascularsp.com.br é do Thiago (Cloudflare), enquanto
//                      endovascularsp.com.br fica na Locaweb e carrega os registros do
//                      Google Workspace — melhor não encostar neles.
//   MURAL_URL        — opcional. Padrão: "https://portalendovascularsp.com.br/mural/index.html"
// (SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY já vêm injetados pela plataforma.)
//
// Endpoint: POST {SUPABASE_URL}/functions/v1/mural-notificar
// Body:     { "aviso_id": "uuid", "tipo": "novo_aviso" | "comentario" | "cobranca" }
// Resposta: { "enviados": 5, "motivo": "..." }
//
// REGRA DE CONTEÚDO: o e-mail leva TÍTULO + botão pro Mural. Nunca o corpo do
// aviso, nunca o anexo, nunca o texto do comentário. Motivo em
// db/migration_008_mural_notificacoes.sql.

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") ?? "";
const FROM = Deno.env.get("MURAL_FROM") ?? "Mural Endovascular SP <avisos@portalendovascularsp.com.br>";
const MURAL_URL = Deno.env.get("MURAL_URL") ?? "https://portalendovascularsp.com.br/mural/index.html";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// Resend aceita até 100 mensagens por chamada do endpoint /emails/batch.
// Com ~43 pessoas na clínica, um aviso "pra Todos" cabe numa chamada só —
// importante porque o plano gratuito limita a 2 requisições por segundo.
const LOTE = 100;

// Janela anti-enxurrada dos comentários: numa discussão animada o autor
// receberia um e-mail por comentário. Ele vê todos ao abrir o Mural.
const JANELA_COMENTARIO_MIN = 15;

// Cobrança manual: no máximo uma por aviso por dia, pra não virar perseguição.
const JANELA_COBRANCA_H = 24;

type Pessoa = { email: string; nome: string | null };

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });

/* ---------- acesso ao banco com service_role (passa por cima da RLS) ---------- */
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
  // INSERT com Prefer: return=minimal responde 201 sem corpo — r.json() estouraria.
  const txt = await r.text();
  return txt ? JSON.parse(txt) : null;
}

const rpc = (fn: string, args: unknown) =>
  db(`rpc/${fn}`, { method: "POST", body: JSON.stringify(args) });

/* ---------- identidade de quem chamou ---------- */
// verify_jwt já barra token inválido, mas precisamos do e-mail pra autorizar a
// ação (só o autor notifica o próprio aviso, só autor/admin cobram).
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

/* ---------- e-mail ---------- */
function esc(s: unknown) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

// HTML de e-mail é conservador de propósito: tabela, largura fixa, estilo inline.
// Outlook e Gmail ignoram <style> em <head> e boa parte de flex/grid.
function montarHtml(o: {
  chamada: string;      // linha acima do título ("Novo aviso para a Enfermagem")
  titulo: string;
  rodape: string;
  saudacao: string;
}) {
  return `<!doctype html>
<html lang="pt-BR"><body style="margin:0;padding:0;background:#0d1b2e;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1b2e;padding:28px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#132540;border:1px solid rgba(255,255,255,0.14);border-radius:16px;">
      <tr><td style="padding:26px 28px 8px;">
        <div style="font:700 15px 'Segoe UI',Arial,sans-serif;color:#f5c842;">📣 Mural de Avisos</div>
        <div style="font:400 12px 'Segoe UI',Arial,sans-serif;color:rgba(255,255,255,0.45);margin-top:2px;">Endovascular SP</div>
      </td></tr>
      <tr><td style="padding:14px 28px 0;">
        <div style="font:400 14px 'Segoe UI',Arial,sans-serif;color:rgba(255,255,255,0.72);">${o.saudacao}</div>
        <div style="font:600 13px 'Segoe UI',Arial,sans-serif;color:#a9cdf7;margin-top:14px;">${o.chamada}</div>
        <div style="font:700 20px/1.35 'Segoe UI',Arial,sans-serif;color:#ffffff;margin-top:6px;">${o.titulo}</div>
      </td></tr>
      <tr><td style="padding:24px 28px 6px;">
        <a href="${MURAL_URL}" style="display:inline-block;background:#f5a623;color:#1a1206;font:700 14px 'Segoe UI',Arial,sans-serif;text-decoration:none;padding:13px 26px;border-radius:10px;">Abrir no Mural →</a>
      </td></tr>
      <tr><td style="padding:18px 28px 26px;">
        <div style="border-top:1px solid rgba(255,255,255,0.09);padding-top:14px;font:400 11.5px/1.55 'Segoe UI',Arial,sans-serif;color:rgba(255,255,255,0.38);">
          ${o.rodape}<br/>
          O conteúdo do aviso fica no portal — este e-mail traz só o título. Mensagem automática, não responda.
        </div>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>`;
}

const primeiroNome = (p: Pessoa) =>
  String(p.nome ?? p.email.split("@")[0]).trim().split(/\s+/)[0];

// Envia em lotes e devolve o id do Resend por destinatário (mesma ordem).
async function enviar(msgs: { to: string; subject: string; html: string }[]) {
  const ids: (string | null)[] = [];
  for (let i = 0; i < msgs.length; i += LOTE) {
    const lote = msgs.slice(i, i + LOTE);
    const r = await fetch("https://api.resend.com/emails/batch", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      // Uma mensagem por pessoa (nada de cópia oculta) — assim ninguém
      // descobre pela lista de destinatários quem mais está na equipe.
      body: JSON.stringify(lote.map((m) => ({ from: FROM, to: [m.to], subject: m.subject, html: m.html }))),
    });
    const txt = await r.text();
    if (!r.ok) throw new Error(`Resend ${r.status}: ${txt}`);
    const data = JSON.parse(txt)?.data ?? [];
    lote.forEach((_, k) => ids.push(data[k]?.id ?? null));
  }
  return ids;
}

async function logar(
  avisoId: string,
  tipo: string,
  pessoas: Pessoa[],
  ids: (string | null)[],
  erro?: string,
) {
  if (!pessoas.length) return;
  await db("mural_emails", {
    method: "POST",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify(pessoas.map((p, i) => ({
      aviso_id: avisoId,
      tipo,
      destinatario_email: p.email,
      destinatario_nome: p.nome,
      status: erro ? "erro" : "enviado",
      erro: erro ?? null,
      provider_id: erro ? null : (ids[i] ?? null),
    }))),
  });
}

// Já houve envio desse tipo pra esse aviso dentro da janela? (janela 0 = "alguma vez")
async function jaEnviou(avisoId: string, tipo: string, minutos: number) {
  let q = `mural_emails?select=created_at&aviso_id=eq.${avisoId}&tipo=eq.${tipo}&status=eq.enviado&limit=1`;
  if (minutos > 0) {
    const desde = new Date(Date.now() - minutos * 60_000).toISOString();
    q += `&created_at=gte.${desde}`;
  }
  return (await db(q)).length > 0;
}

/* ---------- handler ---------- */
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS_HEADERS });
  if (req.method !== "POST") return json({ error: "Use POST" }, 405);
  if (!RESEND_API_KEY) return json({ error: "RESEND_API_KEY não configurada" }, 500);

  try {
    const caller = await quemChamou(req);
    if (!caller) return json({ error: "Não autenticado" }, 401);

    const { aviso_id, tipo } = await req.json().catch(() => ({}));
    if (!aviso_id || !["novo_aviso", "comentario", "cobranca"].includes(tipo)) {
      return json({ error: "aviso_id e tipo são obrigatórios" }, 400);
    }
    // aviso_id entra direto na querystring do PostgREST — se não for um UUID de
    // verdade, dá pra pendurar outros filtros no meio ("&role=eq.admin&...").
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(aviso_id)) {
      return json({ error: "aviso_id inválido" }, 400);
    }

    const avisos = await db(
      `mural_avisos?select=id,titulo,equipes,autor_email,autor_nome,notificar_email&id=eq.${aviso_id}&limit=1`,
    );
    const aviso = avisos[0];
    if (!aviso) return json({ error: "Aviso não encontrado" }, 404);
    const autor = String(aviso.autor_email).toLowerCase();

    // Perfil de quem chamou (nome pro corpo do e-mail, role pra autorização)
    const perfil = (await db(`users?select=email,name,role&email=eq.${encodeURIComponent(caller)}&limit=1`))[0];
    const isAdmin = perfil?.role === "admin";

    let pessoas: Pessoa[] = [];
    let assunto = "";
    let chamada = "";
    let rodape = "";

    if (tipo === "novo_aviso") {
      if (caller !== autor) return json({ error: "Só o autor notifica o próprio aviso" }, 403);
      if (!aviso.notificar_email) return json({ enviados: 0, motivo: "notificacao_desligada" });
      if (await jaEnviou(aviso_id, "novo_aviso", 0)) {
        return json({ enviados: 0, motivo: "ja_notificado" });
      }
      pessoas = await rpc("mural_destinatarios_aviso", { p_aviso_id: aviso_id });
      const alvo = (aviso.equipes ?? []).includes("todos") ? "toda a clínica" : "sua equipe";
      assunto = `📣 Novo aviso: ${aviso.titulo}`;
      chamada = `Novo aviso para ${alvo}`;
      rodape = `Publicado por ${esc(aviso.autor_nome ?? autor)}.`;

    } else if (tipo === "comentario") {
      // Quem comentou precisa ser alguém que enxerga o aviso.
      const podem: Pessoa[] = await rpc("mural_destinatarios_aviso", { p_aviso_id: aviso_id });
      const podeComentar = isAdmin || caller === autor || podem.some((p) => p.email === caller);
      if (!podeComentar) return json({ error: "Sem acesso a este aviso" }, 403);
      if (caller === autor) return json({ enviados: 0, motivo: "autor_comentou_o_proprio" });
      if (await jaEnviou(aviso_id, "comentario", JANELA_COMENTARIO_MIN)) {
        return json({ enviados: 0, motivo: "avisado_ha_pouco" });
      }
      pessoas = [{ email: autor, nome: aviso.autor_nome ?? null }];
      assunto = `💬 Comentaram no seu aviso: ${aviso.titulo}`;
      chamada = "Novo comentário no seu aviso";
      rodape = `Comentário de ${esc(perfil?.name ?? caller)}. O texto está no Mural.`;

    } else {
      if (!isAdmin && caller !== autor) {
        return json({ error: "Só o autor ou um admin podem cobrar" }, 403);
      }
      if (await jaEnviou(aviso_id, "cobranca", JANELA_COBRANCA_H * 60)) {
        return json({ enviados: 0, motivo: "cobrado_nas_ultimas_24h" });
      }
      pessoas = await rpc("mural_nao_leram", { p_aviso_id: aviso_id });
      if (!pessoas.length) return json({ enviados: 0, motivo: "todos_leram" });
      assunto = `🔔 Lembrete — você ainda não leu: ${aviso.titulo}`;
      chamada = "Lembrete: este aviso ainda não foi lido por você";
      rodape = `Aviso publicado por ${esc(aviso.autor_nome ?? autor)}.`;
    }

    if (!pessoas.length) return json({ enviados: 0, motivo: "sem_destinatarios" });

    const msgs = pessoas.map((p) => ({
      to: p.email,
      subject: assunto,
      html: montarHtml({
        saudacao: `Olá, ${esc(primeiroNome(p))} 👋`,
        chamada: esc(chamada),
        titulo: esc(aviso.titulo),
        rodape,
      }),
    }));

    try {
      const ids = await enviar(msgs);
      await logar(aviso_id, tipo, pessoas, ids);
      return json({ enviados: pessoas.length });
    } catch (e) {
      // Registra a falha antes de devolver — senão o erro some e ninguém
      // descobre que o aviso saiu sem e-mail.
      const msg = e instanceof Error ? e.message : String(e);
      await logar(aviso_id, tipo, pessoas, [], msg).catch(() => {});
      return json({ error: "Falha ao enviar os e-mails", detalhe: msg }, 502);
    }
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
