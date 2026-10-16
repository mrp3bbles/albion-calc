// Settings sync for the calculator: GET/PUT /<sync-code>. Whoever knows the code can read and write it.
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};
const reply = (body, status = 200) => new Response(body, { status, headers: { ...CORS, 'Content-Type': 'application/json' } });

export default {
  async fetch(req, env) {
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });
    const id = new URL(req.url).pathname.slice(1);
    if (!/^[A-Za-z0-9_-]{20,64}$/.test(id)) return reply('{"error":"bad sync code"}', 400);
    if (req.method === 'GET') return reply((await env.KV.get(id)) ?? 'null');
    if (req.method === 'PUT') {
      const body = await req.text();
      if (body.length > 65536) return reply('{"error":"too big"}', 413);
      try { JSON.parse(body); } catch { return reply('{"error":"not json"}', 400); }
      await env.KV.put(id, body);
      return reply('{"ok":true}');
    }
    return reply('{"error":"method"}', 405);
  },
};
