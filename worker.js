const JSON_HEADERS = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
let jwksCache = null;
let jwksFetchedAt = 0;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}
function decodeBase64Url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((value.length + 3) % 4);
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
}
async function accessClaims(request, env) {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const header = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[0])));
    const claims = JSON.parse(new TextDecoder().decode(decodeBase64Url(parts[1])));
    const now = Math.floor(Date.now() / 1000);
    const issuer = "https://" + env.ACCESS_TEAM_DOMAIN.replace(/^https?:\/\//, "").replace(/\/$/, "");
    if (claims.iss !== issuer || Number(claims.exp) <= now || Number(claims.nbf || 0) > now) return null;
    const audiences = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    if (!audiences.includes(env.ACCESS_AUD)) return null;
    if (!jwksCache || Date.now() - jwksFetchedAt > 3600000) {
      const response = await fetch(issuer + "/cdn-cgi/access/certs", { cf: { cacheTtl: 3600 } });
      if (!response.ok) return null;
      jwksCache = await response.json();
      jwksFetchedAt = Date.now();
    }
    const jwk = (jwksCache.keys || []).find(key => key.kid === header.kid && key.kty === "RSA");
    if (!jwk) return null;
    const publicKey = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const signed = new TextEncoder().encode(parts[0] + "." + parts[1]);
    const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", publicKey, decodeBase64Url(parts[2]), signed);
    if (!valid) return null;
    return { email: String(claims.email || claims.sub || "usuario").slice(0, 254) };
  } catch (_) {
    return null;
  }
}
function validData(data) {
  if (!data || !Array.isArray(data.zones) || !Array.isArray(data.supervisors) || !Array.isArray(data.aircraft)) return false;
  if (data.zones.length > 20 || data.supervisors.length > 200 || data.aircraft.length > 100) return false;
  const rows = [...data.zones.flatMap(z => Array.isArray(z.resources) ? z.resources : []), ...data.supervisors, ...data.aircraft];
  if (rows.length > 1000) return false;
  return rows.every(row => row && typeof row === "object" &&
    Object.entries(row).every(([key, value]) => typeof value === "string" && value.length <= 500));
}
async function handleApi(request, env) {
  if (!env.DB) return json({ error: "Base de datos no configurada." }, 503);
  const claims = await accessClaims(request, env);
  if (!claims) return json({ error: "Acceso no autorizado. Inicia sesión mediante el acceso corporativo." }, 401);
  if (request.method === "GET") {
    const row = await env.DB.prepare("SELECT data_json, version, updated_at, updated_by FROM operational_state WHERE id = 1").first();
    if (!row) return json({ data: null, version: 0, updatedAt: null, updatedBy: null });
    return json({ data: JSON.parse(row.data_json), version: row.version, updatedAt: row.updated_at, updatedBy: row.updated_by });
  }
  if (request.method !== "PUT") return json({ error: "Método no permitido." }, 405);
  const length = Number(request.headers.get("content-length") || 0);
  if (length > 1000000) return json({ error: "El archivo de datos supera el tamaño permitido." }, 413);
  let body;
  try { body = await request.json(); } catch (_) { return json({ error: "JSON inválido." }, 400); }
  if (!validData(body.data) || !Number.isInteger(body.expectedVersion) || body.expectedVersion < 0) {
    return json({ error: "Estructura de datos o versión inválida." }, 400);
  }
  const serialized = JSON.stringify(body.data);
  const updatedAt = new Date().toISOString();
  const updatedBy = claims.email;
  if (body.expectedVersion === 0) {
    const result = await env.DB.prepare(
      "INSERT OR IGNORE INTO operational_state (id, data_json, version, updated_at, updated_by) VALUES (1, ?, 1, ?, ?)"
    ).bind(serialized, updatedAt, updatedBy).run();
    if (!result.meta.changes) return json({ error: "Otra persona ya publicó la primera versión. Recarga los datos." }, 409);
  } else {
    const result = await env.DB.prepare(
      "UPDATE operational_state SET data_json = ?, version = version + 1, updated_at = ?, updated_by = ? WHERE id = 1 AND version = ?"
    ).bind(serialized, updatedAt, updatedBy, body.expectedVersion).run();
    if (!result.meta.changes) return json({ error: "Los datos fueron modificados por otra persona. Recarga antes de guardar." }, 409);
  }
  const current = await env.DB.prepare("SELECT version FROM operational_state WHERE id = 1").first();
  await env.DB.prepare(
    "INSERT INTO operational_audit (version, updated_at, updated_by, data_json) VALUES (?, ?, ?, ?)"
  ).bind(current.version, updatedAt, updatedBy, serialized).run();
  return json({ ok: true, version: current.version, updatedAt, updatedBy });
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      if (url.pathname === "/api/operational/resources") return handleApi(request, env);
      return json({ error: "Ruta no encontrada." }, 404);
    }
    return env.ASSETS.fetch(request);
  }
};
