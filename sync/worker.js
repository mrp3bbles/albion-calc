// Settings sync for the calculator.
//   GET/PUT /<sync-code>          whoever knows the code can read and write it
//   POST /account/register|login  {user, key, code?} -> {code}
// `key` is PBKDF2(password) computed in the browser; we store only sha256(salt + key).
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,PUT,POST,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};
const reply = (body, status = 200) => new Response(body, { status, headers: { ...CORS, 'Content-Type': 'application/json' } });
const error = (msg, status) => reply(JSON.stringify({ error: msg }), status);
const CODE = /^[A-Za-z0-9_-]{20,64}$/;

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

async function handleAccount(kind, req, env) {
  let body;
  try { body = await req.json(); } catch { return error('not json', 400); }
  const { user, key, code } = body;
  if (!/^[a-z0-9_]{3,24}$/.test(user || '') || !/^[0-9a-f]{64}$/.test(key || '')) return error('bad username or password', 400);
  const rec = await env.KV.get('user:' + user, 'json');
  if (kind === 'register') {
    if (rec) return error('That username is taken', 409);
    const salt = crypto.randomUUID();
    const syncCode = CODE.test(code || '') ? code : crypto.randomUUID().replaceAll('-', '');
    await env.KV.put('user:' + user, JSON.stringify({ salt, hash: await sha256(salt + key), code: syncCode }));
    return reply(JSON.stringify({ code: syncCode }));
  }
  if (!rec || (await sha256(rec.salt + key)) !== rec.hash) return error('Wrong username or password', 401);
  return reply(JSON.stringify({ code: rec.code }));
}

export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
    const path = new URL(req.url).pathname.slice(1);
    const acct = path.match(/^account\/(register|login)$/);
    if (acct) return req.method === 'POST' ? handleAccount(acct[1], req, env) : error('method', 405);
    if (!CODE.test(path)) return error('bad sync code', 400);
    if (req.method === 'GET') return reply((await env.KV.get(path)) ?? 'null');
    if (req.method === 'PUT') {
      const body = await req.text();
      if (body.length > 1000000) return error('too big', 413);
      try { JSON.parse(body); } catch { return error('not json', 400); }
      await env.KV.put(path, body);
      return reply('{"ok":true}');
    }
    return error('method', 405);
  },
};
