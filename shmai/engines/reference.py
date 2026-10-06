"""
Prepares a dropped song for "make something similar" (Melody Generator).

prepare(path) -> dict with:
    name, bpm, key   (measured locally with the Audio Analyzer engine)
    clip             path of a 30-second mono WAV cut from the song. That's
                     what gets uploaded to your Worker for MusicGen to follow.
                     Small (~1.3 MB), and taken from 25% into the song to
                     skip quiet intros.
"""
import tempfile
import wave
from pathlib import Path

from . import analyzer as an

CLIP_SECONDS = 30


def _musical_bpm(bpm):
    """Fold tempos into 60-200 (e.g. 210 -> 105, 52 -> 104)."""
    if not bpm:
        return None
    while bpm > 200:
        bpm /= 2
    while bpm < 60:
        bpm *= 2
    return int(round(bpm))


def prepare(path):
    path = Path(path)
    result = an.analyze(path)
    y, _duration = an.load_audio(path)
    np = an.np
    n = int(CLIP_SECONDS * an.SR)
    start = int(len(y) * 0.25)
    if start + n > len(y):
        start = max(0, len(y) - n)
    clip = y[start:start + n]
    peak = float(np.max(np.abs(clip))) or 1.0
    pcm = (clip / peak * 0.9 * 32767).astype("<i2")
    out = Path(tempfile.gettempdir()) / f"shmai_reference_{abs(hash(str(path))) % 10**8}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(an.SR)
        w.writeframes(pcm.tobytes())
    return {
        "name": path.name,
        "source": str(path),
        "clip": str(out),
        "bpm": _musical_bpm(result.get("bpm")),
        "key": result.get("key"),
        "camelot": result.get("camelot"),
    }
