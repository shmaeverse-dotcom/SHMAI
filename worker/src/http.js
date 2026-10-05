// ---------------------------------------------------------------------------
// Small helpers shared by every endpoint: JSON replies, errors, auth checks
// and rate limiting.
// ---------------------------------------------------------------------------

/** Send a JSON reply. */
export function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...extraHeaders },
  });
}

/**
 * Send a JSON error the desktop app can show to the user.
 * Shape is always: { error: { code, message } }
 */
export function jsonError(status, code, message) {
  return json({ error: { code, message } }, status);
}

/** An error we throw on purpose; the router turns it into a clean JSON reply. */
export class HttpError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Read the request body as JSON, or explain clearly what's wrong. */
export async function readJson(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    throw new HttpError(400, "bad_json", "The request body must be valid JSON.");
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    throw new HttpError(400, "bad_json", "The request body must be a JSON object.");
  }
  return body;
}

/**
 * Compare two strings in constant time so attackers can't guess the token
 * one character at a time by measuring response speed.
 */
function safeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a);
  const y = enc.encode(b);
  let diff = x.length ^ y.length;
  const len = Math.max(x.length, y.length);
  for (let i = 0; i < len; i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

/** Every request must carry the shared app token in the X-App-Token header. */
export function checkAuth(request, env) {
  if (!env.APP_TOKEN) {
    throw new HttpError(500, "not_configured",
      "Server is missing APP_TOKEN. Run: npx wrangler secret put APP_TOKEN");
  }
  const sent = request.headers.get("X-App-Token") || "";
  if (!sent || !safeEqual(sent, env.APP_TOKEN)) {
    throw new HttpError(401, "unauthorized",
      "Missing or wrong app token. Check the App Token in shmAI Settings.");
  }
}

// Fallback limiter used only when the Cloudflare RATE_LIMITER binding is not
// available (for example in some local `wrangler dev` setups). It counts per
// Worker instance, so it is "best effort" rather than exact.
const memoryHits = new Map();
const MEMORY_LIMIT = 60; // requests
const MEMORY_WINDOW_MS = 60_000; // per minute

/** Basic per-IP rate limiting. Throws a 429 error when someone goes too fast. */
export async function checkRateLimit(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "local";

  if (env.RATE_LIMITER && typeof env.RATE_LIMITER.limit === "function") {
    const { success } = await env.RATE_LIMITER.limit({ key: ip });
    if (!success) {
      throw new HttpError(429, "rate_limited",
        "Too many requests. Please wait a minute and try again.");
    }
    return;
  }

  const now = Date.now();
  const hits = (memoryHits.get(ip) || []).filter((t) => now - t < MEMORY_WINDOW_MS);
  hits.push(now);
  memoryHits.set(ip, hits);
  if (hits.length > MEMORY_LIMIT) {
    throw new HttpError(429, "rate_limited",
      "Too many requests. Please wait a minute and try again.");
  }
}
