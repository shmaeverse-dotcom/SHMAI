# shmAI Worker (Cloudflare backend)

This small server runs on Cloudflare and holds your secret keys, so the
desktop app never has to. It does three things:

| Endpoint | What it does |
|---|---|
| `POST /songwriter/chat` | Song Writer: talks to Claude (`claude-sonnet-4-6`) with the Grammy-winning-songwriter persona |
| `POST /melody/generate` | Starts a MusicGen job on Replicate (instrumental only) and returns `{ id }` |
| `GET /melody/status/:id` | Checks the job; when done, copies the audio into R2 and returns `{ status, audioKey }` |
| `GET /audio/:key` · `DELETE /audio/:key` | Streams or deletes a generated file from R2 |
| `GET /health` | Quick "is it working?" check |

Every request must send the header `X-App-Token: <your APP_TOKEN>`, or it gets
`401`. Each IP is limited to 60 requests per minute (`429` after that).
Errors always look like `{ "error": { "code": "...", "message": "..." } }`.

---

## What you need first (one time)

1. **Node.js 20 or newer**: https://nodejs.org (pick "LTS"). Check it's installed:
   `node --version`
2. **A Cloudflare account** (free): https://dash.cloudflare.com/sign-up
   R2 storage must be turned on once in the dashboard: **R2 → Purchase/Enable R2**.
   The free tier is generous, but R2 asks for a payment method.
3. **An Anthropic API key**: https://console.anthropic.com → *API Keys* → *Create Key*
4. **A Replicate API token**: https://replicate.com/account/api-tokens
   (add a little credit under Billing; MusicGen costs a few cents per clip)
5. **An App Token you invent**: any long random password, e.g. from
   https://passwordsgenerator.net (32+ characters, letters and numbers).
   You'll paste the same value into the desktop app's Settings.

---

## Deploy, step by step

Open a terminal **in this `worker` folder** and run these one at a time:

```bash
# 1. install the tools this project uses
npm install

# 2. log in to Cloudflare (opens your browser)
npx wrangler login

# 3. create the storage bucket for generated audio
npx wrangler r2 bucket create shmai-audio

# 4. add your three secrets (each command asks you to paste the value)
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler secret put REPLICATE_API_TOKEN
npx wrangler secret put APP_TOKEN

# 5. publish it
npx wrangler deploy
```

Step 5 prints your Worker's address, something like
`https://shmai-worker.YOUR-SUBDOMAIN.workers.dev`. **Copy it.**

Then in shmAI: **Settings (gear, top-right) → Worker URL** = that address,
**App Token** = the APP_TOKEN you invented → **Test Connection** → **Save**.

> If step 4 says the Worker doesn't exist yet, run step 5 first, then
> step 4, then step 5 again.

### Updating later
Change code or `wrangler.toml`, then run `npx wrangler deploy` again.
To change a key: `npx wrangler secret put NAME` (then no redeploy needed).
To watch live logs: `npx wrangler tail`.

### Settings in `wrangler.toml` (not secret)
| Name | Default | Meaning |
|---|---|---|
| `MODEL_NAME` | `claude-sonnet-4-6` | Claude model for the Song Writer |
| `MAX_TOKENS` | `8000` | Longest songwriter reply |
| `MUSICGEN_VERSION` | (a version id) | Pinned MusicGen version. If Replicate ever rejects it, copy the newest id from https://replicate.com/meta/musicgen/versions, or set it to `""` to use the model's latest |
| `MUSICGEN_CHECKPOINT` | `stereo-large` | MusicGen size/flavor |
| `MAX_DURATION` | `30` | Longest clip in seconds |
| `[[ratelimits]] simple.limit` | `60` per 60s | Requests per IP per minute |

---

## Test locally first (optional, recommended)

1. Create a file named `.dev.vars` in this folder (it is git-ignored):
   ```
   APP_TOKEN=test-token
   ANTHROPIC_API_KEY=sk-ant-...your key...
   REPLICATE_API_TOKEN=r8_...your token...
   ```
2. Start the local server:
   ```bash
   npx wrangler dev
   ```
   It runs at `http://localhost:8787` and uses a local, fake R2 bucket.
3. In a second terminal, try these (macOS/Linux; on Windows use Git Bash or WSL):

```bash
# health check -> {"ok":true,...}
curl -s -H "X-App-Token: test-token" http://localhost:8787/health

# wrong token -> 401 error
curl -s http://localhost:8787/health

# Song Writer (freeform)
curl -s -X POST http://localhost:8787/songwriter/chat \
  -H "X-App-Token: test-token" -H "Content-Type: application/json" \
  -d '{"mode":"freeform","options":{"explicit":false},
       "messages":[{"role":"user","content":"Write a short upbeat pop chorus about a road trip."}]}'

# Start a melody -> {"id":"abc123..."}
curl -s -X POST http://localhost:8787/melody/generate \
  -H "X-App-Token: test-token" -H "Content-Type: application/json" \
  -d '{"genre":"Lo-fi","mood":"Dreamy","instrument":["Rhodes Piano","Upright Bass"],
       "style":"dusty vinyl","bpm":82,"key":"F minor","duration":10}'

# Poll it (repeat every few seconds until "succeeded")
curl -s -H "X-App-Token: test-token" http://localhost:8787/melody/status/PASTE_ID_HERE

# Download the audio (use the audioKey from the status reply, with / written as %2F)
curl -s -H "X-App-Token: test-token" -o melody.wav \
  "http://localhost:8787/audio/audio%2FPASTE_ID_HERE.wav"

# Delete it from R2
curl -s -X DELETE -H "X-App-Token: test-token" \
  "http://localhost:8787/audio/audio%2FPASTE_ID_HERE.wav"
```

Unit tests for the MusicGen prompt builder: `npm test`.

To point the desktop app at your local Worker: Settings → Worker URL
`http://localhost:8787`, App Token `test-token`.

---

## Request / response reference

**POST /songwriter/chat**
```json
{ "messages": [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}, ...],
  "mode": "freeform" | "guided",
  "options": { "explicit": false, "bars": 64, "genre": "...", "mood": "...", "topic": "...",
               "structure": "...", "artist_style": "..." },
  "user_id": "optional, for future personalization" }
→ { "reply": "...lyrics + writer's notes...", "stop_reason": "end_turn" }
```
The app sends the whole conversation every time (that's what makes revisions work).

**POST /melody/generate**
```json
{ "prompt": "", "instrument": "Piano" | ["Piano","Synth Pad"], "genre": "", "style": "", "mood": "",
  "reference": "", "bpm": 90, "key": "A minor", "duration": 15, "format": "wav" | "mp3", "seed": 123 }
→ { "id": "...", "status": "starting", "prompt": "<the MusicGen prompt that was built>", "duration": 15 }
```

**GET /melody/status/:id** → `{ "status": "starting" | "processing" }`, or
`{ "status": "succeeded", "audioKey": "audio/<id>.wav" }`, or
`{ "status": "failed", "error": "..." }`

**GET /audio/:key** → the audio file. **DELETE /audio/:key** → `{ "deleted": "audio/<id>.wav" }`.
The desktop app deletes each file from R2 right after downloading it, to keep storage tidy.
