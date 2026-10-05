// ---------------------------------------------------------------------------
// POST /songwriter/chat
// Talks to Claude (Anthropic Messages API) with a pro-songwriter persona.
// The desktop app sends the WHOLE conversation every time (multi-turn).
// ---------------------------------------------------------------------------
import Anthropic from "@anthropic-ai/sdk";
import { HttpError, json, readJson } from "./http.js";

const MAX_MESSAGES = 60; // longest conversation we accept
const MAX_CHARS_PER_MESSAGE = 20_000;

// The core persona. Kept as one constant so it never changes between
// requests (that lets Anthropic cache it, which is faster and cheaper).
const PERSONA = `You are a Grammy-winning songwriter and topline writer with more than 20 years of professional experience across pop, hip-hop, R&B, rock, country, electronic and film/TV sync. You have written hits for major artists and you mentor younger writers.

How you work:
- You analyze songs like a pro: structure, rhyme schemes, meter and syllable counts, hook placement, prosody (how the words sit on the rhythm), point of view and emotional arc.
- You build ORIGINAL songs to the user's description. Every lyric you write is new. Never reproduce, quote at length, or lightly rewrite the lyrics of existing songs, even if asked; you may describe an artist's style (themes, flow, rhyme density, vocabulary, cadence) and write something original in that spirit.
- You write with real craft, not generic AI lyrics: concrete, specific imagery over abstractions; fresh metaphors instead of cliches ("heart of gold", "fire inside", "dancing in the rain" etc. are banned unless subverted); internal rhymes, multisyllabic rhymes and slant rhymes where the genre calls for them; consistent meter inside each section so lines are singable; a hook that is short, repeatable and lands on the title.
- Label every section clearly, e.g. [Intro], [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Outro].
- When the user gives a length in bars, respect it: in most popular music one lyric line is roughly 2 bars (rap: often 1 line per bar). Say briefly how you mapped bars to lines.
- After the lyrics, add a short "Writer's notes" section (3-6 bullet points): the concept, rhyme/flow choices, suggested melody or delivery ideas, and one or two optional alternate lines.
- When asked for revisions, change only what was asked and keep everything else, unless the user wants a full rewrite.
- If the request is vague, make confident creative choices and mention them in the notes rather than asking lots of questions.`;

function contentRule(explicit) {
  return explicit
    ? "CONTENT SETTING: EXPLICIT. Mature themes and strong language are allowed when they serve the song. Never include hate speech or sexual content involving minors."
    : "CONTENT SETTING: CLEAN. No profanity, slurs, graphic sex or graphic drug references. Keep it radio-edit safe, using clever wording instead of censored swear words.";
}

function modeRule(mode) {
  return mode === "guided"
    ? "MODE: GUIDED. The user's first message is a structured brief from a form. Follow every field in it exactly (length, structure, genre, mood, topic, style)."
    : "MODE: FREEFORM CHAT. The user describes what they want in plain language. Hold a natural conversation like a studio session.";
}

/** Check the incoming messages and return a clean copy. */
function validateMessages(messages) {
  if (!Array.isArray(messages) || messages.length === 0) {
    throw new HttpError(400, "bad_request", "'messages' must be a non-empty list.");
  }
  if (messages.length > MAX_MESSAGES) {
    throw new HttpError(400, "too_long",
      `Conversation is too long (max ${MAX_MESSAGES} messages). Start a new song.`);
  }
  const clean = messages.map((m, i) => {
    if (!m || (m.role !== "user" && m.role !== "assistant")) {
      throw new HttpError(400, "bad_request", `Message ${i + 1} needs role "user" or "assistant".`);
    }
    if (typeof m.content !== "string" || !m.content.trim()) {
      throw new HttpError(400, "bad_request", `Message ${i + 1} needs some text content.`);
    }
    if (m.content.length > MAX_CHARS_PER_MESSAGE) {
      throw new HttpError(400, "too_long", `Message ${i + 1} is too long.`);
    }
    return { role: m.role, content: m.content };
  });
  if (clean[0].role !== "user") {
    throw new HttpError(400, "bad_request", "The first message must come from the user.");
  }
  if (clean[clean.length - 1].role !== "user") {
    throw new HttpError(400, "bad_request", "The last message must come from the user.");
  }
  return clean;
}

export async function handleSongwriterChat(request, env) {
  if (!env.ANTHROPIC_API_KEY) {
    throw new HttpError(500, "not_configured",
      "Server is missing ANTHROPIC_API_KEY. Run: npx wrangler secret put ANTHROPIC_API_KEY");
  }
  const body = await readJson(request);
  const messages = validateMessages(body.messages);
  const mode = body.mode === "guided" ? "guided" : "freeform";
  const options = body.options && typeof body.options === "object" ? body.options : {};
  const explicit = options.explicit === true;

  // Future hook: body.user_id / body.settings will drive memory and
  // personalization in a later stage. For now we only forward the id so
  // usage can be told apart in the Anthropic console.
  const userId = typeof body.user_id === "string" ? body.user_id.slice(0, 64) : undefined;

  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY, maxRetries: 2 });

  let response;
  try {
    response = await client.messages.create({
      model: env.MODEL_NAME || "claude-sonnet-4-6",
      max_tokens: Number(env.MAX_TOKENS) || 8000,
      thinking: { type: "adaptive" },
      system: [
        // Stable persona first (cached), per-request rules after it.
        { type: "text", text: PERSONA, cache_control: { type: "ephemeral" } },
        { type: "text", text: `${modeRule(mode)}\n${contentRule(explicit)}` },
      ],
      messages,
      ...(userId ? { metadata: { user_id: userId } } : {}),
    });
  } catch (err) {
    // Most specific first. APIConnectionError is a subclass of APIError.
    if (err instanceof Anthropic.AuthenticationError) {
      throw new HttpError(502, "upstream_auth",
        "The server's Anthropic API key was rejected. The owner needs to update ANTHROPIC_API_KEY.");
    }
    if (err instanceof Anthropic.NotFoundError) {
      throw new HttpError(502, "upstream_model", `Model "${env.MODEL_NAME}" was not found. Check MODEL_NAME in wrangler.toml.`);
    }
    if (err instanceof Anthropic.RateLimitError) {
      throw new HttpError(429, "upstream_busy", "The songwriter is busy right now. Try again in a minute.");
    }
    if (err instanceof Anthropic.APIConnectionError) {
      throw new HttpError(502, "upstream_unreachable", "Couldn't reach Anthropic. Try again shortly.");
    }
    if (err instanceof Anthropic.APIError) {
      throw new HttpError(502, "upstream_error", `Anthropic error (${err.status ?? "?"}): ${err.message}`);
    }
    throw err;
  }

  if (response.stop_reason === "refusal") {
    return json({ reply: "I can't write that one. Try changing the topic or wording and I'll take another pass.", stop_reason: "refusal" });
  }

  const reply = response.content
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("\n")
    .trim();

  return json({
    reply: response.stop_reason === "max_tokens"
      ? `${reply}\n\n[Reply was cut off for length. Ask me to "continue".]`
      : reply,
    stop_reason: response.stop_reason,
  });
}
