// ---------------------------------------------------------------------------
// GET / DELETE /audio/:key  - serve or remove generated audio stored in R2.
// ---------------------------------------------------------------------------
import { HttpError, json } from "./http.js";

// Accept "audio/<id>.wav" or just "<id>.wav" (we add the folder for you).
// Only these simple names are allowed, so nobody can read other bucket files.
function normalizeKey(raw) {
  const key = raw.startsWith("audio/") ? raw : `audio/${raw}`;
  if (!/^audio\/[A-Za-z0-9_-]{1,80}\.(wav|mp3)$/.test(key)) {
    throw new HttpError(400, "bad_request", "That audio file name doesn't look right.");
  }
  return key;
}

export async function handleAudioGet(rawKey, request, env) {
  const key = normalizeKey(rawKey);
  const object = await env.AUDIO_BUCKET.get(key);
  if (!object) throw new HttpError(404, "not_found", "That audio file doesn't exist (it may have been deleted).");

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("content-length", String(object.size));
  headers.set("content-disposition", `attachment; filename="${key.split("/").pop()}"`);
  if (!headers.has("content-type")) headers.set("content-type", "application/octet-stream");

  return new Response(request.method === "HEAD" ? null : object.body, { headers });
}

export async function handleAudioDelete(rawKey, env) {
  const key = normalizeKey(rawKey);
  await env.AUDIO_BUCKET.delete(key);
  return json({ deleted: key });
}
