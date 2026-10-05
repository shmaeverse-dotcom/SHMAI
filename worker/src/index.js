// ---------------------------------------------------------------------------
// shmAI backend Worker - entry point and router.
//
// Endpoints (all need the X-App-Token header):
//   GET    /health                 quick "is the server up?" check
//   POST   /songwriter/chat        Song Writer (Claude)
//   POST   /melody/generate        start a MusicGen job (Replicate)
//   GET    /melody/status/:id      poll a MusicGen job; saves audio to R2
//   GET    /audio/:key             download/stream audio from R2
//   DELETE /audio/:key             delete audio from R2
// ---------------------------------------------------------------------------
import { HttpError, checkAuth, checkRateLimit, json, jsonError } from "./http.js";
import { handleSongwriterChat } from "./songwriter.js";
import { handleMelodyGenerate, handleMelodyStatus } from "./melody.js";
import { handleAudioGet, handleAudioDelete } from "./audio.js";

async function route(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = request.method.toUpperCase();

  // Rate limit first (also slows down anyone guessing the token),
  // then require the app token: every endpoint is private.
  await checkRateLimit(request, env);
  checkAuth(request, env);

  if (path === "/health" && method === "GET") {
    return json({ ok: true, service: "shmai-worker", model: env.MODEL_NAME });
  }
  if (path === "/songwriter/chat") {
    if (method !== "POST") throw new HttpError(405, "method_not_allowed", "Use POST.");
    return handleSongwriterChat(request, env);
  }
  if (path === "/melody/generate") {
    if (method !== "POST") throw new HttpError(405, "method_not_allowed", "Use POST.");
    return handleMelodyGenerate(request, env);
  }
  if (path.startsWith("/melody/status/")) {
    if (method !== "GET") throw new HttpError(405, "method_not_allowed", "Use GET.");
    return handleMelodyStatus(decodeURIComponent(path.slice("/melody/status/".length)), env);
  }
  if (path.startsWith("/audio/")) {
    const key = decodeURIComponent(path.slice("/audio/".length));
    if (method === "GET" || method === "HEAD") return handleAudioGet(key, request, env);
    if (method === "DELETE") return handleAudioDelete(key, env);
    throw new HttpError(405, "method_not_allowed", "Use GET or DELETE.");
  }
  throw new HttpError(404, "not_found", `Unknown endpoint: ${method} ${path}`);
}

export default {
  async fetch(request, env) {
    try {
      return await route(request, env);
    } catch (err) {
      if (err instanceof HttpError) return jsonError(err.status, err.code, err.message);
      // Unexpected bug: log it for `wrangler tail`, but don't leak internals.
      console.error("Unhandled error:", err && err.stack ? err.stack : err);
      return jsonError(500, "server_error", "Something went wrong on the server. Please try again.");
    }
  },
};
