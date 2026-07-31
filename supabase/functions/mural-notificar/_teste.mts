// Banco de provas da Edge Function mural-notificar.
// Roda a funcao de verdade com Deno, fetch e Resend dublados — nenhum e-mail sai
// e nenhum banco e tocado. Use antes de qualquer deploy da funcao.
//
// Uso (a partir desta pasta):  node --experimental-strip-types _teste.mts
import { readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const AVISO = '11111111-2222-3333-4444-555555555555';
let CALLER = 'autor@endovascularsp.com.br';
let st: any = {};

function reset() {
  st = {
    aviso: {
      id: AVISO, titulo: 'Reunião geral na sexta às 8h',
      corpo: 'TEXTO SECRETO QUE NAO PODE VAZAR NO EMAIL',
      equipes: ['enfermagem'],
      autor_email: 'autor@endovascularsp.com.br', autor_nome: 'Ana Autora',
      notificar_email: true,
    },
    perfil: { email: CALLER, name: 'Ana Autora', role: 'funcionario' },
    destinatarios: [
      { email: 'a@endovascularsp.com.br', nome: 'Maria Silva' },
      { email: 'b@endovascularsp.com.br', nome: 'José Souza' },
    ],
    naoLeram: [{ email: 'b@endovascularsp.com.br', nome: 'José Souza' }],
    emails: [] as any[],
    resend: [] as any[],
  };
}

const R = (b: any, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { 'Content-Type': 'application/json' } });

(globalThis as any).Deno = {
  env: { get: (k: string) => ({
    SUPABASE_URL: 'https://proj.supabase.co',
    SUPABASE_SERVICE_ROLE_KEY: 'service-key',
    RESEND_API_KEY: 're_teste',
  } as any)[k] },
  serve: (h: any) => { (globalThis as any).__handler = h; },
};

(globalThis as any).fetch = async (url: any, init: any = {}) => {
  const u = String(url);
  if (u.includes('/auth/v1/user')) {
    if (!init.headers?.Authorization?.includes('valido')) return R({}, 401);
    return R({ email: CALLER });
  }
  if (u.includes('/rest/v1/mural_avisos')) return R([st.aviso]);
  if (u.includes('/rest/v1/users')) return R([st.perfil]);
  if (u.includes('/rest/v1/rpc/mural_destinatarios_aviso')) return R(st.destinatarios);
  if (u.includes('/rest/v1/rpc/mural_nao_leram')) return R(st.naoLeram);
  if (u.includes('/rest/v1/mural_emails')) {
    if (init.method === 'POST') { st.emails.push(...JSON.parse(init.body)); return new Response(null, { status: 201 }); }
    const tipo = /tipo=eq\.(\w+)/.exec(u)?.[1];
    const desde = /created_at=gte\.([^&]+)/.exec(u)?.[1];
    return R(st.emails.filter((e: any) =>
      e.tipo === tipo && e.status === 'enviado' &&
      (!desde || new Date(e.created_at ?? Date.now()) >= new Date(decodeURIComponent(desde)))));
  }
  if (u.includes('api.resend.com')) { st.resend.push(...JSON.parse(init.body)); return R({ data: st.resend.map((_: any, i: number) => ({ id: 'msg' + i })) }); }
  throw new Error('fetch não dublado: ' + u);
};

// Deno.serve e chamado na importacao. Copia pra .mts porque o Node so
// remove tipos de arquivos com extensao de modulo.
const alvo = process.argv[2] ?? new URL('./index.ts', import.meta.url);
const copia = join(tmpdir(), 'mural_notificar_teste.mts');
writeFileSync(copia, readFileSync(alvo, 'utf8'));
await import(pathToFileURL(copia).href);
const handler = (globalThis as any).__handler;

const chamar = (body: any, auth = 'Bearer token-valido') =>
  handler(new Request('https://x/functions/v1/mural-notificar', {
    method: 'POST', headers: { Authorization: auth, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }));

let falhas = 0;
function ok(nome: string, cond: boolean, extra = '') {
  console.log((cond ? '  OK   ' : '  FALHA') + ' ' + nome + (cond ? '' : '  <<< ' + extra));
  if (!cond) falhas++;
}

/* ---------------- casos ---------------- */
console.log('\n1. Aviso novo publicado pelo autor');
reset(); CALLER = 'autor@endovascularsp.com.br'; st.perfil.email = CALLER;
let r = await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' });
let b = await r.json();
ok('envia para os 2 destinatários', b.enviados === 2, JSON.stringify(b));
ok('uma mensagem por pessoa (sem cópia oculta)', st.resend.length === 2 && st.resend.every((m: any) => m.to.length === 1));
ok('o corpo do aviso NÃO vai no e-mail', !JSON.stringify(st.resend).includes('SECRETO'));
ok('o título vai no e-mail', st.resend[0].html.includes('Reunião geral'));
ok('assunto certo', st.resend[0].subject.startsWith('📣 Novo aviso:'));
ok('trata cada pessoa pelo primeiro nome', st.resend[0].html.includes('Olá, Maria') && st.resend[1].html.includes('Olá, José'));
ok('registra os 2 envios no log', st.emails.length === 2 && st.emails.every((e: any) => e.status === 'enviado'));

console.log('\n2. Não repete o envio se clicar duas vezes');
r = await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' });
b = await r.json();
ok('segunda chamada não envia nada', b.enviados === 0 && b.motivo === 'ja_notificado', JSON.stringify(b));
ok('nenhum e-mail extra saiu', st.resend.length === 2);

console.log('\n3. Quem não é o autor não notifica o aviso dos outros');
reset(); CALLER = 'intruso@endovascularsp.com.br'; st.perfil = { email: CALLER, name: 'Intruso', role: 'funcionario' };
r = await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' });
ok('403', r.status === 403);
ok('nada enviado', st.resend.length === 0);

console.log('\n4. Checkbox desmarcado = nenhum e-mail');
reset(); CALLER = 'autor@endovascularsp.com.br'; st.aviso.notificar_email = false;
r = await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' });
b = await r.json();
ok('respeita a escolha de não notificar', b.enviados === 0 && b.motivo === 'notificacao_desligada', JSON.stringify(b));

console.log('\n5. Comentário avisa o autor do aviso');
reset(); CALLER = 'a@endovascularsp.com.br'; st.perfil = { email: CALLER, name: 'Maria Silva', role: 'funcionario' };
r = await chamar({ aviso_id: AVISO, tipo: 'comentario' });
b = await r.json();
ok('1 e-mail, para o autor', b.enviados === 1 && st.resend[0].to[0] === 'autor@endovascularsp.com.br', JSON.stringify(b));
ok('diz quem comentou', st.resend[0].html.includes('Maria Silva'));
ok('não repete comentário logo em seguida', (await (await chamar({ aviso_id: AVISO, tipo: 'comentario' })).json()).motivo === 'avisado_ha_pouco');

console.log('\n6. Quem está fora da equipe não consegue disparar e-mail pelo aviso');
reset(); CALLER = 'forasteiro@endovascularsp.com.br'; st.perfil = { email: CALLER, name: 'Forasteiro', role: 'funcionario' };
r = await chamar({ aviso_id: AVISO, tipo: 'comentario' });
ok('403', r.status === 403);

console.log('\n7. Cobrança de quem não leu');
reset(); CALLER = 'autor@endovascularsp.com.br';
r = await chamar({ aviso_id: AVISO, tipo: 'cobranca' });
b = await r.json();
ok('cobra só quem falta', b.enviados === 1 && st.resend[0].to[0] === 'b@endovascularsp.com.br', JSON.stringify(b));
ok('assunto de lembrete', st.resend[0].subject.startsWith('🔔 Lembrete'));
ok('não cobra de novo no mesmo dia', (await (await chamar({ aviso_id: AVISO, tipo: 'cobranca' })).json()).motivo === 'cobrado_nas_ultimas_24h');

console.log('\n8. Cobrança quando todo mundo já leu');
reset(); CALLER = 'autor@endovascularsp.com.br'; st.naoLeram = [];
b = await (await chamar({ aviso_id: AVISO, tipo: 'cobranca' })).json();
ok('não envia nada', b.enviados === 0 && b.motivo === 'todos_leram', JSON.stringify(b));

console.log('\n9. Cobrança por quem não é autor nem admin');
reset(); CALLER = 'outro@endovascularsp.com.br'; st.perfil = { email: CALLER, name: 'Outro', role: 'funcionario' };
r = await chamar({ aviso_id: AVISO, tipo: 'cobranca' });
ok('403', r.status === 403);

console.log('\n10. Admin pode cobrar aviso alheio');
reset(); CALLER = 'chefe@endovascularsp.com.br'; st.perfil = { email: CALLER, name: 'Chefe', role: 'admin' };
b = await (await chamar({ aviso_id: AVISO, tipo: 'cobranca' })).json();
ok('envia', b.enviados === 1, JSON.stringify(b));

console.log('\n11. Entradas inválidas');
reset(); CALLER = 'autor@endovascularsp.com.br';
ok('sem token → 401', (await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' }, 'Bearer podre')).status === 401);
ok('tipo desconhecido → 400', (await chamar({ aviso_id: AVISO, tipo: 'hackear' })).status === 400);
ok('aviso_id não-uuid → 400', (await chamar({ aviso_id: 'x&role=eq.admin', tipo: 'novo_aviso' })).status === 400);
ok('OPTIONS (preflight do navegador) → 204',
  (await handler(new Request('https://x', { method: 'OPTIONS' }))).status === 204);

console.log('\n12. Falha do provedor de e-mail');
reset(); CALLER = 'autor@endovascularsp.com.br';
const fetchBom = (globalThis as any).fetch;
(globalThis as any).fetch = async (u: any, i: any) =>
  String(u).includes('resend') ? new Response('quota exceeded', { status: 429 }) : fetchBom(u, i);
r = await chamar({ aviso_id: AVISO, tipo: 'novo_aviso' });
b = await r.json();
ok('devolve 502 com o motivo', r.status === 502 && /429/.test(b.detalhe || ''), JSON.stringify(b));
ok('registra a falha no log', st.emails.length === 2 && st.emails.every((e: any) => e.status === 'erro'));
(globalThis as any).fetch = fetchBom;

console.log(falhas ? `\n${falhas} FALHA(S)\n` : '\nTodos os casos passaram.\n');
process.exit(falhas ? 1 : 0);
