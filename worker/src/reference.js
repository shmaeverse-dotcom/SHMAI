// ---------------------------------------------------------------------------
// Reference audio for "make something similar" (Melody Generator drop zone).
//
//   POST /melody/reference      (app token required) upload a short clip
//                               -> { reference_id }
//   GET  /ref/<reference_id>.wav  PUBLIC, but only for whoever knows the long
//                               random id: this is how Replicate downloads
//                               the clip. Links expire after REF_TTL_HOURS
//                               and are deleted once the melody is done.
// ---------------------------------------------------------------------------
import { HttpError, json } from "./http.js";

export const REF_TTL_HOURS = 6;
const MAX_BYTES = 12 * 1024 * 1024; // ~12 MB (the app sends a 30 s clip, ~1.5 MB)
const TYPES = { "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/mpeg": "mp3", "audio/mp3": "mp3" };

function newId() {
  // 64 hex characters of randomness: impossible to guess
  return (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "");
}

export function refKey(id, ext) {
  return `refs/${id}.${ext}`;
}

export async function handleReferenceUpload(request, env) {
  const type = (request.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
  const ext = TYPES[type];
  if (!ext) throw new HttpError(415, "bad_type", "Send the reference as audio/wav or audio/mpeg.");
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > MAX_BYTES) throw new HttpError(413, "too_large", "Reference clip is too big (max 12 MB).");
  const bytes = await request.arrayBuffer();
  if (bytes.byteLength === 0) throw new HttpError(400, "bad_request", "The reference clip was empty.");
  if (bytes.byteLength > MAX_BYTES) throw new HttpError(413, "too_large", "Reference clip is too big (max 12 MB).");

  const id = newId();
  await env.AUDIO_BUCKET.put(refKey(id, ext), bytes, {
    httpMetadata: { contentType: ext === "mp3" ? "audio/mpeg" : "audio/wav" },
    customMetadata: { createdAt: String(Date.now()) },
  });
  return json({ reference_id: id, ext, bytes: bytes.byteLength });
}

/** Find an uploaded reference; returns { key, ext } or null. */
export async function findReference(id, env) {
  if (typeof id !== "string" || !/^[a-f0-9]{64}$/.test(id)) return null;
  for (const ext of ["wav", "mp3"]) {
    const head = await env.AUDIO_BUCKET.head(refKey(id, ext));
    if (head) return { key: refKey(id, ext), ext, createdAt: Number(head.customMetadata?.createdAt || 0) };
  }
  return null;
}

/** Public GET /ref/<id>.<ext> (no token: the random id IS the password). */
export async function handleReferenceGet(file, env) {
  const m = /^([a-f0-9]{64})\.(wav|mp3)$/.exec(file);
  if (!m) throw new HttpError(404, "not_found", "Not found.");
  const object = await env.AUDIO_BUCKET.get(refKey(m[1], m[2]));
  const created = Number(object?.customMetadata?.createdAt || 0);
  if (!object || Date.now() - created > REF_TTL_HOURS * 3600 * 1000) {
    throw new HttpError(404, "not_found", "Not found.");
  }
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("content-length", String(object.size));
  headers.set("cache-control", "private, no-store");
  return new Response(object.body, { headers });
}
