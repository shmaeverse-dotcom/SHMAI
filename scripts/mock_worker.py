#!/usr/bin/env python3
"""
A FAKE shmAI Worker for testing the desktop app offline: no Cloudflare,
no API keys, no cost. It answers the same endpoints with canned data.

    python3 scripts/mock_worker.py            # listens on http://127.0.0.1:8799
Then in shmAI Settings use:
    Worker URL: http://127.0.0.1:8799
    App Token:  test-token

Song Writer replies with placeholder lyrics; Melody Generator "renders" a
short synth tone after a few seconds so the whole download/play flow can
be tested.
"""
import io
import json
import math
import struct
import sys
import time
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

TOKEN = "test-token"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
JOBS = {}    # id -> {"start": time, "params": {...}}
FILES = {}   # key -> bytes
REFS = set()  # uploaded reference clip ids


def tone_wav(seconds=4, freq=220.0):
    rate = 22050
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(int(rate * seconds)):
            t = i / rate
            note = freq * (1.5 if int(t * 2) % 2 else 1.0)
            v = 0.3 * math.sin(2 * math.pi * note * t) * (1 - (t * 2 % 1) * 0.7)
            frames += struct.pack("<h", int(v * 32767))
        w.writeframes(bytes(frames))
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, data, ctype="application/json"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, status, code, msg):
        self._send(status, {"error": {"code": code, "message": msg}})

    def _auth(self):
        if self.headers.get("X-App-Token") != TOKEN:
            self._err(401, "unauthorized", "Missing or wrong app token. Check the App Token in shmAI Settings.")
            return False
        return True

    def _body(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n)
        if self.headers.get("content-type", "").startswith("audio/"):
            return {"_bytes": len(raw)}  # reference upload: just count it
        return json.loads(raw or b"{}")

    def do_GET(self):
        if not self._auth():
            return
        path = self.path.rstrip("/")
        if path == "/health":
            return self._send(200, {"ok": True, "service": "mock-worker", "model": "mock-model"})
        if path.startswith("/melody/status/"):
            job_id = unquote(path.split("/")[-1])
            job = JOBS.get(job_id)
            if not job:
                return self._err(404, "not_found", "No generation job with that id.")
            if time.time() - job["start"] < 4:
                return self._send(200, {"status": "processing"})
            key = f"audio/{job_id}.wav"
            if key not in FILES:
                FILES[key] = tone_wav(min(6, job["params"].get("duration", 4)))
            return self._send(200, {"status": "succeeded", "audioKey": key})
        if path.startswith("/audio/"):
            key = unquote(path[len("/audio/"):])
            key = key if key.startswith("audio/") else "audio/" + key
            if key not in FILES:
                return self._err(404, "not_found", "That audio file doesn't exist.")
            return self._send(200, FILES[key], "audio/wav")
        self._err(404, "not_found", f"Unknown endpoint: GET {path}")

    def do_DELETE(self):
        if not self._auth():
            return
        key = unquote(self.path[len("/audio/"):])
        FILES.pop(key if key.startswith("audio/") else "audio/" + key, None)
        self._send(200, {"deleted": key})

    def do_POST(self):
        if not self._auth():
            return
        try:
            body = self._body()
        except ValueError:
            return self._err(400, "bad_json", "The request body must be valid JSON.")
        if self.path == "/songwriter/chat":
            msgs = body.get("messages") or []
            if not msgs or msgs[-1].get("role") != "user":
                return self._err(400, "bad_request", "The last message must come from the user.")
            time.sleep(1.0)
            turn = sum(1 for m in msgs if m["role"] == "user")
            rating = "EXPLICIT" if (body.get("options") or {}).get("explicit") else "CLEAN"
            reply = (f"[Verse 1]\nMock lyric line one for turn {turn}\nMock lyric line two, {rating} version\n\n"
                     f"[Chorus]\nThis is a placeholder hook ({body.get('mode')})\n\n"
                     "Writer's notes:\n- Mock reply from scripts/mock_worker.py\n"
                     f"- You said: {msgs[-1]['content'][:80]!r}")
            return self._send(200, {"reply": reply, "stop_reason": "end_turn"})
        if self.path == "/melody/reference":
            REFS.add(uuid.uuid4().hex + uuid.uuid4().hex)
            ref_id = sorted(REFS)[-1]
            return self._send(200, {"reference_id": ref_id, "ext": "wav"})
        if self.path == "/melody/generate":
            if body.get("reference_id") and body["reference_id"] not in REFS:
                return self._err(400, "reference_missing", "The reference clip expired or wasn't found.")
            job_id = uuid.uuid4().hex[:20]
            JOBS[job_id] = {"start": time.time(), "params": body}
            return self._send(200, {"id": job_id, "status": "starting", "prompt": "mock", "duration": 8})
        self._err(404, "not_found", f"Unknown endpoint: POST {self.path}")

    def log_message(self, fmt, *args):
        sys.stderr.write("[mock] " + fmt % args + "\n")


if __name__ == "__main__":
    print(f"Mock shmAI Worker on http://127.0.0.1:{PORT}  (App Token: {TOKEN})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
