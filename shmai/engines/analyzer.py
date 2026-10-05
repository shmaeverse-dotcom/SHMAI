"""
Audio Analyzer + Key Finder engine (runs locally, needs numpy).

analyze(path) -> dict with:
    duration, bpm, key ("A minor"), camelot ("8A"), relative key,
    key confidence (0-1), top alternative keys, peak/RMS loudness (dBFS),
    and a small waveform outline for drawing.

How it works (plain English):
    Key:  the song's energy is folded into the 12 notes (a "chromagram"),
          then compared against the classic Krumhansl-Kessler key profiles.
          The best match wins.
    BPM:  we measure moments where the sound suddenly gets louder ("onsets")
          and look for the repeating gap between them.

Opens WAV directly. MP3/M4A/FLAC/OGG need ffmpeg installed (or the optional
soundfile/librosa packages).
"""
import shutil
import subprocess
import wave
from pathlib import Path

from ..errors import FriendlyError

try:
    import numpy as np
except ImportError:
    np = None

SR = 22050          # analysis sample rate
MAX_SECONDS = 240   # analyze up to 4 minutes (plenty for key + tempo)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DISPLAY_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

# Key profiles (Albrecht & Shanahan 2013): how often each scale note is
# used in major / minor music. Tested better than the older Krumhansl set.
MAJOR = [0.238, 0.006, 0.111, 0.006, 0.137, 0.094, 0.016, 0.214, 0.009, 0.080, 0.008, 0.081]
MINOR = [0.220, 0.006, 0.104, 0.123, 0.019, 0.103, 0.012, 0.214, 0.062, 0.022, 0.061, 0.052]

CAMELOT_MAJOR = {0: "8B", 7: "9B", 2: "10B", 9: "11B", 4: "12B", 11: "1B", 6: "2B", 1: "3B", 8: "4B", 3: "5B",
                 10: "6B", 5: "7B"}
CAMELOT_MINOR = {9: "8A", 4: "9A", 11: "10A", 6: "11A", 1: "12A", 8: "1A", 3: "2A", 10: "3A", 5: "4A", 0: "5A",
                 7: "6A", 2: "7A"}


class AnalyzerError(FriendlyError):
    pass


def key_label(root, mode):
    return f"{DISPLAY_NAMES[root]} {mode}"


# ---------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------
def load_audio(path):
    """Return (mono float32 samples at SR, original duration in seconds)."""
    if np is None:
        raise AnalyzerError("The analyzer needs numpy. Run:  python3 -m pip install numpy")
    path = Path(path)
    if not path.exists():
        raise AnalyzerError(f"File not found: {path}")

    if path.suffix.lower() == ".wav":
        try:
            return _load_wav(path)
        except (wave.Error, EOFError, ValueError):
            pass  # unusual WAV flavor (e.g. float): try the other loaders

    if shutil.which("ffmpeg"):
        return _load_ffmpeg(path)
    try:
        import soundfile as sf  # optional
        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        return _resample(mono, sr), len(mono) / sr
    except Exception:
        pass
    try:
        import librosa  # optional
        y, _sr = librosa.load(str(path), sr=SR, mono=True, duration=MAX_SECONDS)
        return y.astype("float32"), librosa.get_duration(path=str(path))
    except Exception:
        pass
    raise AnalyzerError(
        f"Can't open {path.suffix or 'this'} files yet. Install ffmpeg (free) to analyze MP3/M4A/FLAC,\n"
        "or convert the file to WAV.")


def _load_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        frames = w.readframes(min(n, sr * MAX_SECONDS))
    if width == 1:
        data = (np.frombuffer(frames, dtype=np.uint8).astype("float32") - 128) / 128
    elif width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype("float32") / 32768
    elif width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        ints = (raw[:, 0].astype(np.int32) | (raw[:, 1].astype(np.int32) << 8) | (raw[:, 2].astype(np.int32) << 16))
        ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
        data = ints.astype("float32") / 8388608
    elif width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype("float32") / 2147483648
    else:
        raise ValueError("unsupported sample width")
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return _resample(data, sr), n / float(sr)


def _load_ffmpeg(path):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-t", str(MAX_SECONDS), "-ac", "1", "-ar", str(SR),
           "-f", "s16le", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise AnalyzerError("Decoding took too long.") from None
    if proc.returncode != 0 or not proc.stdout:
        msg = proc.stderr.decode(errors="replace").strip().splitlines()
        raise AnalyzerError(f"Couldn't read this audio file.\n{msg[-1] if msg else ''}")
    data = np.frombuffer(proc.stdout, dtype="<i2").astype("float32") / 32768
    # ask ffprobe for the full length (we only decoded the first few minutes)
    duration = len(data) / SR
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(path)], capture_output=True, text=True, timeout=30).stdout.strip()
            duration = float(out)
        except (ValueError, subprocess.TimeoutExpired):
            pass
    return data, duration


def _resample(data, sr):
    if sr == SR:
        return data.astype("float32")
    n_out = int(len(data) * SR / sr)
    x_old = np.linspace(0, 1, len(data), endpoint=False)
    x_new = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_new, x_old, data).astype("float32")


# ---------------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------------
def _stft_mag(y, n_fft, hop):
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    frames = 1 + (len(y) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    win = np.hanning(n_fft).astype("float32")
    return np.abs(np.fft.rfft(y[idx] * win, axis=1))


def detect_key(y):
    n_fft, hop = 8192, 2048
    mag = _stft_mag(y, n_fft, hop) ** 2               # power spectrum
    freqs = np.fft.rfftfreq(n_fft, 1.0 / SR)
    # 1) group FFT bins into real notes (semitones) from C2 to C7
    notes = np.arange(36, 97)
    note_energy = np.zeros((mag.shape[0], len(notes)))
    for i, midi in enumerate(notes):
        lo = 440.0 * 2 ** ((midi - 0.5 - 69) / 12)
        hi = 440.0 * 2 ** ((midi + 0.5 - 69) / 12)
        sel = (freqs >= lo) & (freqs < hi)
        if sel.any():
            note_energy[:, i] = mag[:, sel].mean(axis=1)
    # 2) loudness-compress, then remove broadband noise (drums, hiss) by
    #    subtracting each frame's median note level
    level = np.log1p(note_energy / (note_energy.mean() + 1e-12))
    level = np.maximum(0, level - np.median(level, axis=1, keepdims=True))
    # 3) fold octaves into 12 pitch classes
    chroma = np.zeros(12)
    for i, midi in enumerate(notes):
        chroma[midi % 12] += level[:, i].sum()
    if chroma.sum() <= 0:
        raise AnalyzerError("Couldn't hear any musical notes in this file (is it silent or drums only?).")
    chroma = chroma / chroma.max()

    scores = []
    for root in range(12):
        for mode, prof in (("major", MAJOR), ("minor", MINOR)):
            r = np.corrcoef(chroma, np.roll(prof, root))[0, 1]
            scores.append((float(r), root, mode))
    scores.sort(reverse=True)
    best, second = scores[0], scores[1]
    # A relative major/minor pair sharing all notes is the usual runner-up,
    # so confidence looks at the gap to the next DIFFERENT scale too.
    confidence = max(0.0, min(1.0, best[0] * 0.6 + (best[0] - second[0]) * 4))
    return best[1], best[2], confidence, scores[:5], chroma.tolist()


def detect_bpm(y):
    n_fft, hop = 2048, 512
    mag = _stft_mag(y, n_fft, hop)
    logmag = np.log1p(mag * 100)
    flux = np.maximum(0, np.diff(logmag, axis=0)).sum(axis=1)
    if flux.size < 16 or flux.max() <= 0:
        return None
    flux = flux - np.convolve(flux, np.ones(16) / 16, mode="same")  # remove slow loudness changes
    flux = np.maximum(flux, 0)
    fps = SR / hop
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    ac = ac / (ac[0] + 1e-9)

    def at(lag):
        i = int(lag)
        if i + 1 >= len(ac):
            return 0.0
        f = lag - i
        return ac[i] * (1 - f) + ac[i + 1] * f

    best_bpm, best_score = None, -1.0
    for bpm in np.arange(60.0, 200.0, 0.25):
        lag = fps * 60.0 / bpm
        # a real tempo repeats at 1, 2, 3 and 4 beats
        val = at(lag) + 0.6 * at(2 * lag) + 0.4 * at(3 * lag) + 0.5 * at(4 * lag)
        # prefer typical tempos (75-150) when half/double time are equally likely
        prior = np.exp(-0.5 * (np.log2(bpm / 112.0) / 0.45) ** 2)
        score = val * (0.25 + 0.75 * prior)
        if score > best_score:
            best_bpm, best_score = bpm, score
    return round(float(best_bpm) * 2) / 2 if best_bpm else None


def tempo_alternatives(bpm):
    """Half- and double-time readings: a 174 BPM track can feel like 87."""
    if not bpm:
        return []
    return [b for b in (bpm / 2, bpm * 2) if 50 <= b <= 220]


def analyze(path):
    y, duration = load_audio(path)
    if len(y) < SR:
        raise AnalyzerError("The file is too short to analyze (under 1 second).")
    root, mode, conf, top, chroma = detect_key(y)
    bpm = detect_bpm(y)
    peak = float(np.max(np.abs(y)))
    rms = float(np.sqrt(np.mean(y ** 2)))
    to_db = lambda v: round(20 * np.log10(max(v, 1e-9)), 1)  # noqa: E731
    rel_root, rel_mode = ((root + 9) % 12, "minor") if mode == "major" else ((root + 3) % 12, "major")
    n = 600
    chunk = max(1, len(y) // n)
    wave_env = np.abs(y[: chunk * n]).reshape(-1, chunk).max(axis=1) if len(y) >= n else np.abs(y)
    return {
        "path": str(path),
        "name": Path(path).name,
        "duration": duration,
        "bpm": bpm,
        "bpm_alternatives": tempo_alternatives(bpm),
        "key": key_label(root, mode),
        "root": root,
        "mode": mode,
        "camelot": (CAMELOT_MAJOR if mode == "major" else CAMELOT_MINOR)[root],
        "relative": key_label(rel_root, rel_mode),
        "confidence": conf,
        "alternatives": [key_label(r, m) for _s, r, m in top[1:4]],
        "chroma": chroma,
        "peak_db": to_db(peak),
        "rms_db": to_db(rms),
        "waveform": (wave_env / (wave_env.max() or 1)).tolist(),
    }
