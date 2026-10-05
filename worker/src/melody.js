// ---------------------------------------------------------------------------
// Melody generation with MusicGen on Replicate.
//   POST /melody/generate     -> starts a job, returns { id }
//   GET  /melody/status/:id   -> checks the job; when finished, copies the
//                                audio into R2 and returns { status, audioKey }
// ---------------------------------------------------------------------------
import { HttpError, json, readJson } from "./http.js";

const REPLICATE_API = "https://api.replicate.com/v1";

/** Trim a text field and cap its length so prompts stay sensible. */
function text(value, max = 200) {
  if (value === undefined || value === null) return "";
  if (Array.isArray(value)) value = value.filter(Boolean).join(", ");
  return String(value).replace(/\s+/g, " ").trim().slice(0, max);
}

/**
 * Turn the app's selections into one descriptive MusicGen prompt.
 * MusicGen works best with comma-separated musical descriptors.
 */
export function buildMusicGenPrompt(body) {
  const parts = [];
  const genre = text(body.genre, 60);
  const style = text(body.style, 200);
  const mood = text(body.mood, 60);
  const instrument = text(body.instrument, 160);
  const reference = text(body.reference, 200);
  const prompt = text(body.prompt, 400);
  const bpm = Number(body.bpm);
  const key = text(body.key, 20);

  if (genre) parts.push(`${genre} instrumental`);
  if (mood) parts.push(`${mood} mood`);
  if (instrument) parts.push(`featuring ${instrument}`);
  if (style) parts.push(style);
  if (reference) parts.push(`vibe like ${reference}`);
  if (Number.isFinite(bpm) && bpm >= 40 && bpm <= 240) parts.push(`${Math.round(bpm)} bpm`);
  if (key) parts.push(`in the key of ${key}`);
  if (prompt) parts.push(prompt);
  // Always instrumental: MusicGen can't sing words, but we steer it away from
  // vocal-like sounds too.
  parts.push("instrumental only, no vocals, no singing, high quality studio mix");
  return parts.join(", ");
}

/** fetch() that turns "no internet / host down" into a friendly error. */
async function safeFetch(url, init, what) {
  try {
    return await fetch(url, init);
  } catch {
    throw new HttpError(502, "upstream_unreachable", `Couldn't reach ${what}. Try again shortly.`);
  }
}

function replicateHeaders(env) {
  if (!env.REPLICATE_API_TOKEN) {
    throw new HttpError(500, "not_configured",
      "Server is missing REPLICATE_API_TOKEN. Run: npx wrangler secret put REPLICATE_API_TOKEN");
  }
  return {
    Authorization: `Bearer ${env.REPLICATE_API_TOKEN}`,
    "Content-Type": "application/json",
  };
}

/** Turn a failed Replicate reply into a clear error for the app. */
async function replicateError(res) {
  let detail = "";
  try {
    const data = await res.json();
    detail = data.detail || data.title || JSON.stringify(data);
  } catch {
    detail = await res.text().catch(() => "");
  }
  if (res.status === 401) {
    return new HttpError(502, "upstream_auth",
      "The server's Replicate token was rejected. The owner needs to update REPLICATE_API_TOKEN.");
  }
  if (res.status === 402) {
    return new HttpError(502, "upstream_billing", "Replicate billing problem: add credit to the Replicate account.");
  }
  if (res.status === 429) {
    return new HttpError(429, "upstream_busy", "Replicate is busy. Try again in a minute.");
  }
  return new HttpError(502, "upstream_error", `Replicate error (${res.status}): ${detail}`.slice(0, 400));
}

export async function handleMelodyGenerate(request, env) {
  const body = await readJson(request);
  const maxDuration = Number(env.MAX_DURATION) || 30;
  let duration = Math.round(Number(body.duration ?? 15));
  if (!Number.isFinite(duration) || duration < 1) duration = 15;
  duration = Math.min(duration, maxDuration);

  const prompt = buildMusicGenPrompt(body);
  const format = body.format === "mp3" ? "mp3" : "wav";

  const input = {
    prompt,
    duration,
    model_version: env.MUSICGEN_CHECKPOINT || "stereo-large",
    output_format: format,
    normalization_strategy: "peak",
  };
  // Optional extra: a fixed seed lets users re-create a result.
  if (Number.isInteger(body.seed) && body.seed >= 0) input.seed = body.seed;

  // If a version id is set we pin it; otherwise use the model's latest.
  const url = env.MUSICGEN_VERSION
    ? `${REPLICATE_API}/predictions`
    : `${REPLICATE_API}/models/${env.MUSICGEN_MODEL || "meta/musicgen"}/predictions`;
  const payload = env.MUSICGEN_VERSION ? { version: env.MUSICGEN_VERSION, input } : { input };

  const res = await safeFetch(url, {
    method: "POST",
    headers: replicateHeaders(env),
    body: JSON.stringify(payload),
  }, "Replicate");
  if (!res.ok) throw await replicateError(res);
  const prediction = await res.json();

  return json({ id: prediction.id, status: prediction.status, prompt, duration, format });
}

export async function handleMelodyStatus(id, env) {
  if (!/^[a-z0-9]{6,64}$/i.test(id)) {
    throw new HttpError(400, "bad_request", "That job id doesn't look right.");
  }

  // Already copied to R2 on an earlier poll? Answer straight away.
  for (const ext of ["wav", "mp3"]) {
    const key = `audio/${id}.${ext}`;
    if (await env.AUDIO_BUCKET.head(key)) {
      return json({ status: "succeeded", audioKey: key });
    }
  }

  const res = await safeFetch(`${REPLICATE_API}/predictions/${id}`, { headers: replicateHeaders(env) }, "Replicate");
  if (res.status === 404) throw new HttpError(404, "not_found", "No generation job with that id.");
  if (!res.ok) throw await replicateError(res);
  const prediction = await res.json();

  if (prediction.status === "failed" || prediction.status === "canceled") {
    return json({
      status: prediction.status,
      error: prediction.error ? String(prediction.error).slice(0, 400) : "Generation did not finish.",
    });
  }
  if (prediction.status !== "succeeded") {
    // "starting" or "processing": tell the app to keep polling.
    return json({ status: prediction.status });
  }

  // Output is a single file URL (some versions return a list).
  const outputUrl = Array.isArray(prediction.output) ? prediction.output[0] : prediction.output;
  if (typeof outputUrl !== "string" || !outputUrl.startsWith("https://")) {
    throw new HttpError(502, "upstream_error", "Replicate finished but returned no audio file.");
  }
  const ext = outputUrl.toLowerCase().includes(".mp3") ? "mp3" : "wav";
  const key = `audio/${id}.${ext}`;

  const audio = await safeFetch(outputUrl, {}, "Replicate's file storage");
  if (!audio.ok) {
    throw new HttpError(502, "upstream_error", "Couldn't download the finished audio from Replicate.");
  }
  // Clips are at most a few MB, so reading into memory is fine and avoids
  // R2's "stream must have a known length" rule.
  const bytes = await audio.arrayBuffer();
  await env.AUDIO_BUCKET.put(key, bytes, {
    httpMetadata: { contentType: ext === "mp3" ? "audio/mpeg" : "audio/wav" },
    customMetadata: { prediction: id, createdAt: new Date().toISOString() },
  });

  return json({ status: "succeeded", audioKey: key });
}
