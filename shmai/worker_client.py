"""
Talks to your Cloudflare Worker over HTTPS.

The desktop app NEVER holds the Anthropic or Replicate keys. It only knows:
  - worker_url : where your Worker lives
  - app_token  : the shared password sent in the X-App-Token header

Every method raises WorkerError with a friendly, plain-English message the
UI can show directly. These calls are slow (network), so the pages always
run them on a background thread (see App.run_async).
"""
from pathlib import Path
from urllib.parse import quote

import requests

from .errors import FriendlyError

TIMEOUT_FAST = 20      # seconds, for quick calls
TIMEOUT_CHAT = 180     # the songwriter can take a while to think
TIMEOUT_DOWNLOAD = 120


class WorkerError(FriendlyError):
    """An error with a message that's safe and friendly to show the user."""


class WorkerClient:
    def __init__(self, cfg):
        self.cfg = cfg

    # ---- plumbing ------------------------------------------------------------
    def _base(self):
        url = (self.cfg.get("worker_url") or "").strip().rstrip("/")
        if not url:
            raise WorkerError(
                "The shmAI server isn't set up yet.\n\n"
                "Open Settings (gear, top-right) and paste your Worker URL and App Token.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    def _headers(self):
        token = (self.cfg.get("app_token") or "").strip()
        if not token:
            raise WorkerError("No App Token set. Open Settings and paste the App Token.")
        return {"X-App-Token": token, "User-Agent": "shmAI-desktop/1.0"}

    def _request(self, method, path, timeout=TIMEOUT_FAST, extra_headers=None, **kwargs):
        url = self._base() + path
        headers = self._headers()
        headers.update(extra_headers or {})
        try:
            res = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except requests.exceptions.Timeout:
            raise WorkerError("The shmAI server took too long to answer. Please try again.") from None
        except requests.exceptions.SSLError:
            raise WorkerError("Secure connection to the server failed. Check the Worker URL.") from None
        except requests.exceptions.ConnectionError:
            raise WorkerError(
                "Can't reach the shmAI server.\n\n"
                "• Check your internet connection\n"
                "• Check the Worker URL in Settings\n"
                "• Make sure the Worker is deployed") from None
        except requests.exceptions.RequestException as e:
            raise WorkerError(f"Network problem: {e}") from None

        if res.ok:
            return res
        raise WorkerError(self._explain(res))

    @staticmethod
    def _explain(res):
        message = ""
        try:
            message = res.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        if res.status_code == 401:
            return message or "The server rejected the App Token. Check it in Settings."
        if res.status_code == 404 and not message:
            return "That server address doesn't have shmAI on it. Check the Worker URL in Settings."
        if res.status_code == 429:
            return message or "Slow down a little. Too many requests. Wait a minute and try again."
        if res.status_code >= 500 and not message:
            return f"The shmAI server had a problem (error {res.status_code}). Try again shortly."
        return message or f"Unexpected server reply (error {res.status_code})."

    # ---- endpoints -----------------------------------------------------------
    def health(self):
        return self._request("GET", "/health").json()

    def songwriter_chat(self, messages, mode="freeform", options=None):
        payload = {
            "messages": messages,
            "mode": mode,
            "options": options or {},
            # Hooks for later stages (memory/personalization). Unused for now.
            "user_id": self.cfg.get("user_id", ""),
            "settings": {},
        }
        data = self._request("POST", "/songwriter/chat", timeout=TIMEOUT_CHAT, json=payload).json()
        reply = data.get("reply")
        if not reply:
            raise WorkerError("The songwriter returned an empty reply. Try again.")
        return reply

    def melody_generate(self, params):
        payload = dict(params)
        payload["user_id"] = self.cfg.get("user_id", "")
        data = self._request("POST", "/melody/generate", json=payload).json()
        if not data.get("id"):
            raise WorkerError("The server didn't return a job id.")
        return data

    def upload_reference(self, clip_path):
        """Upload a short reference clip ("make something similar"). Returns its id."""
        with open(clip_path, "rb") as f:
            data = f.read()
        res = self._request("POST", "/melody/reference", timeout=TIMEOUT_DOWNLOAD, data=data,
                            extra_headers={"Content-Type": "audio/wav"})
        ref_id = res.json().get("reference_id")
        if not ref_id:
            raise WorkerError("The server didn't accept the reference song.")
        return ref_id

    def melody_status(self, job_id):
        return self._request("GET", "/melody/status/" + quote(job_id, safe="")).json()

    def download_audio(self, key, dest_path, progress=None):
        """Stream an audio file from R2 (via the Worker) to dest_path."""
        res = self._request("GET", "/audio/" + quote(key, safe=""), timeout=TIMEOUT_DOWNLOAD, stream=True)
        total = int(res.headers.get("content-length") or 0)
        done = 0
        dest_path = Path(dest_path)
        tmp = dest_path.with_suffix(dest_path.suffix + ".part")
        try:
            with open(tmp, "wb") as f:
                for chunk in res.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
                        done += len(chunk)
                        if progress and total:
                            progress(done / total)
            tmp.replace(dest_path)
        except requests.exceptions.RequestException:
            raise WorkerError("The download was interrupted. Please try again.") from None
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        return dest_path

    def delete_audio(self, key):
        return self._request("DELETE", "/audio/" + quote(key, safe="")).json()
