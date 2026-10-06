// ---------------------------------------------------------------------------
// Accurate drum copying: separate the drums from a song with Demucs.
//
//   POST /drums/separate      { reference_id }  (the song uploaded with
//                             POST /melody/reference)  -> { id }
//   GET  /drums/status/:id    poll; when done the drums-only track is in R2
//                             -> { status, audioKey }
//
// Demucs is an AI "stem splitter" on Replicate. The model and its inputs can
// be changed in wrangler.toml (DEMUCS_MODEL / DEMUCS_VERSION / DEMUCS_INPUT)
// without touching code.
// ---------------------------------------------------------------------------
import { HttpError, json, readJson } from "./http.js";
import { api, predictionStatus, replicateError, replicateHeaders, safeFetch } from "./melody.js";
import { REF_TTL_HOURS, findReference } from "./reference.js";

/** Which Replicate model version to run: pinned, or the model's latest. */
async function demucsVersion(env) {
  if (env.DEMUCS_VERSION) return env.DEMUCS_VERSION;
  const model = env.DEMUCS_MODEL || "ryan5453/demucs";
  const res = await safeFetch(`${api(env)}/models/${model}`, { headers: replicateHeaders(env) }, "Replicate");
  if (!res.ok) throw await replicateError(res);
  const info = await res.json();
  const id = info?.latest_version?.id;
  if (!id) throw new HttpError(502, "upstream_error", `Replicate didn't list a version for ${model}.`);
  return id;
}

function extraInput(env) {
  try {
    return JSON.parse(env.DEMUCS_INPUT || '{"stem": "drums", "output_format": "wav"}');
  } catch {
    throw new HttpError(500, "not_configured", "DEMUCS_INPUT in wrangler.toml isn't valid JSON.");
  }
}

export async function handleDrumSeparate(request, env) {
  const body = await readJson(request);
  const ref = await findReference(body.reference_id, env);
  if (!ref || Date.now() - ref.createdAt > REF_TTL_HOURS * 3600 * 1000) {
    throw new HttpError(400, "reference_missing", "The uploaded song expired or wasn't found. Drop it in again.");
  }
  const origin = new URL(request.url).origin;
  const input = { ...extraInput(env), audio: `${origin}/ref/${body.reference_id}.${ref.ext}` };
  const res = await safeFetch(`${api(env)}/predictions`, {
    method: "POST",
    headers: replicateHeaders(env),
    body: JSON.stringify({ version: await demucsVersion(env), input }),
  }, "Replicate");
  if (!res.ok) throw await replicateError(res);
  const prediction = await res.json();
  if (prediction.id) {
    await env.AUDIO_BUCKET.put(`jobs/${prediction.id}`, ref.key); // delete the song when done
  }
  return json({ id: prediction.id, status: prediction.status });
}

/** Demucs may return {drums: url, ...}, a list of urls, or one url. Keep the drums. */
export function pickDrums(output) {
  if (typeof output === "string") return output;
  if (Array.isArray(output)) {
    return output.find((u) => typeof u === "string" && /drums/i.test(u) && !/no_drums|no-drums/i.test(u))
      || output.find((u) => typeof u === "string" && /drums/i.test(u));
  }
  if (output && typeof output === "object") {
    return output.drums || Object.entries(output).find(([k]) => /drum/i.test(k) && !/no/i.test(k))?.[1];
  }
  return undefined;
}

export function handleDrumStatus(id, env) {
  return predictionStatus(id, env, { suffix: "-drums", pick: pickDrums, what: "Drum separation" });
}
