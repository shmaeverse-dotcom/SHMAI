"""
Sound: the retro Xbox-style selection "blip" and a simple audio player.

Selection sound
    Plays assets/sounds/select.wav when you click/select something.
    To keep your existing sound, copy your .wav file over
    assets/sounds/select.wav (or set "select_sound" in config.json).
    If no file exists, we generate a retro blip the first time.

Audio player
    Uses pygame (pip install pygame) to play WAV/MP3/OGG. If pygame isn't
    installed, files open in your computer's default music player instead.
"""
import math
import os
import struct
import subprocess
import sys
import threading
import wave
from pathlib import Path

from .config import ASSETS_DIR

SOUND_DIR = ASSETS_DIR / "sounds"
DEFAULT_SELECT = SOUND_DIR / "select.wav"

try:
    import pygame  # optional
except Exception:  # ImportError, or broken SDL install
    pygame = None


def _make_retro_blip(path):
    """Create a short two-tone 'blip' like the original Xbox dashboard."""
    rate = 44100
    samples = []
    # Two quick rising tones with a soft square-ish timbre and fast decay.
    for freq, dur in ((990, 0.045), (1480, 0.085)):
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            env = math.exp(-t * 38)
            tone = math.sin(2 * math.pi * freq * t)
            tone += 0.3 * math.sin(2 * math.pi * freq * 3 * t)  # adds bite
            tone += 0.15 * math.sin(2 * math.pi * freq * 0.5 * t)  # adds body
            samples.append(0.28 * env * tone)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples))


def _open_with_system(path):
    """Open a file with the computer's default app. Returns True if it worked."""
    path = str(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606 (Windows only)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, AttributeError) as e:
        print(f"[shmAI] Couldn't open {path}: {e}")
        return False


class SoundSystem:
    def __init__(self, cfg):
        self.cfg = cfg
        self.mixer_ok = False
        self._select_sound = None
        if pygame is not None:
            try:
                pygame.mixer.init()
                self.mixer_ok = True
            except Exception as e:
                print(f"[shmAI] Audio device not available ({e}); using system player.")
        self.reload_select_sound()

    # ---- selection sound --------------------------------------------------
    def reload_select_sound(self):
        custom = (self.cfg.get("select_sound") or "").strip()
        path = Path(custom).expanduser() if custom else DEFAULT_SELECT
        if not path.exists():
            if custom:
                print(f"[shmAI] select_sound not found: {path}; using default.")
            path = DEFAULT_SELECT
            if not path.exists():
                try:
                    _make_retro_blip(path)
                except OSError:
                    return
        self.select_path = path
        self._select_sound = None
        if self.mixer_ok:
            try:
                self._select_sound = pygame.mixer.Sound(str(path))
            except Exception:
                self._select_sound = None

    def play_select(self):
        if not self.cfg.get("sound_enabled", True):
            return
        if self._select_sound is not None:
            self._select_sound.play()  # its own channel: music keeps playing
            return
        path = str(getattr(self, "select_path", ""))
        if not path:
            return
        # Fallbacks that don't need pygame. Run in a thread so clicks never lag.
        def run():
            try:
                if sys.platform.startswith("win"):
                    import winsound
                    winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                elif sys.platform == "darwin":
                    subprocess.run(["afplay", path], capture_output=True, timeout=5)
                else:
                    for cmd in (["paplay", path], ["aplay", "-q", path]):
                        try:
                            subprocess.run(cmd, capture_output=True, timeout=5)
                            break
                        except FileNotFoundError:
                            continue
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    # ---- music / previews -------------------------------------------------
    def play_file(self, path):
        """Play an audio file. Returns 'internal', 'external' or 'failed'."""
        path = str(path)
        if self.mixer_ok:
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.play()
                return "internal"
            except Exception as e:
                print(f"[shmAI] pygame couldn't play {path}: {e}")
        return "external" if _open_with_system(path) else "failed"

    def stop(self):
        if self.mixer_ok:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass

    def is_playing(self):
        if self.mixer_ok:
            try:
                return bool(pygame.mixer.music.get_busy())
            except Exception:
                return False
        return False


def open_folder(path):
    """Show a folder in Explorer / Finder / the file manager."""
    _open_with_system(path)
