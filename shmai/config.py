"""
Settings for shmAI, stored in config.json next to muse.py.

You can edit them inside the app (Settings button, top-right) or by hand.
Environment variables override the file, handy for testing:
    SHMAI_WORKER_URL   -> worker_url
    SHMAI_APP_TOKEN    -> app_token

No secret API keys live here. The Anthropic and Replicate keys stay on
your Cloudflare Worker. This file only knows the Worker's address and the
shared app token.
"""
import json
import os
import uuid
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = APP_DIR / "config.json"
ASSETS_DIR = APP_DIR / "assets"

DEFAULTS = {
    # --- Cloudflare Worker connection (fill these in!) ---
    "worker_url": "",          # e.g. https://shmai-worker.YOUR-NAME.workers.dev
    "app_token": "",           # the same value you gave `wrangler secret put APP_TOKEN`
    # --- Future hook: identifies this install for memory/personalization later ---
    "user_id": "",
    # --- Look & feel (the adjustable size/spacing option) ---
    "ui_scale": 1.0,           # text size multiplier (0.8 - 1.6)
    "ui_spacing": 1.0,         # padding/spacing multiplier (0.6 - 1.8)
    "animations": True,        # starfield, dancers, transitions
    "sound_enabled": True,     # selection "blip" sound
    "select_sound": "",        # optional path to your own .wav selection sound
    # --- Where downloads and generated files go ---
    "output_dir": str(Path.home() / "Music" / "shmAI"),
}


def load_config():
    """Read config.json (creating it on first run) and apply env overrides."""
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
        except (OSError, ValueError):
            # A broken config file shouldn't stop the app from opening.
            print("[shmAI] config.json could not be read; using defaults.")

    first_run = not cfg.get("user_id")
    if first_run:
        cfg["user_id"] = uuid.uuid4().hex
    if first_run or not CONFIG_PATH.exists():
        save_config(cfg)

    # Environment variables win (not saved back to the file).
    if os.environ.get("SHMAI_WORKER_URL"):
        cfg["worker_url"] = os.environ["SHMAI_WORKER_URL"]
    if os.environ.get("SHMAI_APP_TOKEN"):
        cfg["app_token"] = os.environ["SHMAI_APP_TOKEN"]
    return cfg


def save_config(cfg):
    """Write settings to config.json (pretty-printed so it's easy to edit)."""
    data = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        print(f"[shmAI] Could not save config.json: {e}")


def output_dir(cfg, sub=""):
    """Folder for saved files, created if needed. `sub` is a page name."""
    path = Path(cfg.get("output_dir") or DEFAULTS["output_dir"]).expanduser()
    if sub:
        path = path / sub
    path.mkdir(parents=True, exist_ok=True)
    return path
