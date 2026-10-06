"""
Drum pattern copier: listens to a song's drums and writes the pattern down.

How it works (plain English):
  1. Get the drums by themselves.
       Quick mode    : on this computer, a trick called "harmonic/percussive
                       separation" turns down sustained sounds (chords,
                       vocals, bass notes) so the short drum hits stand out.
       Accurate mode : the Worker uses Demucs (an AI stem splitter on
                       Replicate) to pull out a real drums-only track first.
  2. Listen in three frequency bands: kick (deep lows), snare/clap
     (mids + noise) and hi-hats (very high). Every sudden jump in a band
     is a hit.
  3. Lock onto the tempo grid: fine-tune the BPM and find where the 16th
     notes land, then find beat 1 of the bar (kick on the 1, snare on the
     backbeat). Also measures SWING, hi-hat ROLLS (1/32 notes) and OPEN hats.
  4. Find the LOOP: modern songs repeat a 4-, 8- or 16-bar drum loop (with
     fills at the end). Every possible loop length and starting bar is
     tested; the one whose repeats agree best wins (or you pick the length).

The result is a pattern you can export as MIDI, play with built-in sounds or
your own drum kit folder, layer under generated music, or feed to the MIDI
composer.
"""
import wave
from pathlib import Path

from ..errors import FriendlyError
from . import analyzer as an
from . import midi_engine as me

try:
    import numpy as np
except ImportError:
    np = None

SR = an.SR                 # 22050 Hz analysis rate
N_FFT, HOP = 1024, 256     # ~11.6 ms time resolution
FPS = SR / HOP
MAX_SECONDS = 180          # enough for two passes of a 16-bar loop at 80 BPM
LOOP_CHOICES = (4, 8, 16)
BANDS = {"kick": (30, 150), "snare": (180, 2500), "hat": (5500, 10500)}
NOTE = {"kick": 36, "snare": 38, "hat": 42, "open_hat": 46}
LANES = ("kick", "snare", "hat", "open_hat", "roll")  # roll = 1/32 hat between two 16ths


class DrumError(FriendlyError):
    pass


# ---------------------------------------------------------------------------------
# 1. Spectrogram + "keep only the hits"
# ---------------------------------------------------------------------------------
def _median_filter(x, size, axis):
    """Median filter along one axis, in chunks so memory stays small."""
    pad = size // 2
    out = np.empty_like(x)
    if axis == 1:  # across frequency, per frame
        xp = np.pad(x, ((0, 0), (pad, pad)), mode="reflect")
        for a in range(0, x.shape[0], 800):
            win = np.lib.stride_tricks.sliding_window_view(xp[a:a + 800], size, axis=1)
            out[a:a + 800] = np.median(win, axis=-1)
    else:          # across time, per frequency bin
        xp = np.pad(x, ((pad, pad), (0, 0)), mode="reflect")
        for a in range(0, x.shape[0], 800):
            win = np.lib.stride_tricks.sliding_window_view(xp[a:a + 800 + 2 * pad], size, axis=0)
            out[a:a + 800] = np.median(win, axis=-1)[: min(800, x.shape[0] - a)]
    return out


def _percussive(mag):
    """Harmonic/percussive separation: drums are 'vertical' in a spectrogram
    (short, all frequencies), notes are 'horizontal' (long, one pitch)."""
    harm = _median_filter(mag, 17, axis=0)
    perc = _median_filter(mag, 17, axis=1)
    mask = perc ** 2 / (harm ** 2 + perc ** 2 + 1e-12)
    return mag * mask


def _band_curves(mag):
    """Per band: an 'onset' curve (how suddenly it got louder) and an energy curve."""
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    onset, energy = {}, {}
    for name, (lo, hi) in BANDS.items():
        sel = (freqs >= lo) & (freqs < hi)
        band = mag[:, sel]
        # LINEAR jumps in energy: a real kick is a big low-end jump; a hi-hat's
        # faint low rumble barely registers (log scaling would exaggerate it).
        flux = np.maximum(0, np.diff(band, axis=0, prepend=band[:1])).sum(axis=1)
        e = band.sum(axis=1)
        onset[name] = flux / (np.percentile(flux, 99.5) + 1e-9)
        energy[name] = np.convolve(e, np.ones(3) / 3, mode="same")
    return onset, energy


# ---------------------------------------------------------------------------------
# 2. Tempo grid
# ---------------------------------------------------------------------------------
def _local_max(curve, radius=1):
    out = curve.copy()
    for r in range(1, radius + 1):
        out = np.maximum(out, np.roll(curve, r))
        out = np.maximum(out, np.roll(curve, -r))
    return out


def fit_grid(onset_all, bpm0, spread=0.015):
    """Fine-tune BPM around bpm0 and find where the 16th-note grid starts.
    Returns (bpm, phase_in_frames)."""
    peaks = _local_max(onset_all, 1)
    best = (bpm0, 0.0, -1.0)
    for bpm in np.arange(bpm0 * (1 - spread), bpm0 * (1 + spread), 0.02):
        step = FPS * 60.0 / bpm / 4.0
        n = int((len(peaks) - 2) / step)
        if n < 16:
            continue
        phases = np.arange(0, step, 0.5)
        idx = np.round(phases[:, None] + np.arange(n)[None, :] * step).astype(int)
        idx = np.clip(idx, 0, len(peaks) - 1)
        scores = peaks[idx].mean(axis=1)
        i = int(np.argmax(scores))
        if scores[i] > best[2]:
            best = (float(bpm), float(phases[i]), float(scores[i]))
    return best[0], best[1]


def _otsu(values):
    """Split values into 'hits' and 'not hits' automatically (Otsu's method)."""
    v = np.log1p(values * 20)
    hist, edges = np.histogram(v, bins=64)
    total = hist.sum()
    if total == 0:
        return 1.0
    w = np.cumsum(hist)
    mu = np.cumsum(hist * edges[:-1])
    mu_t = mu[-1]
    between = (mu_t * w / total - mu) ** 2 / (w * (total - w) + 1e-12)
    t = edges[int(np.argmax(between))]
    return float(np.expm1(t) / 20)


def _threshold(v):
    """Hit / no-hit cut-off for one band: automatic split, but never below a
    quarter of that band's strong hits (so faint bleed doesn't count)."""
    strong = np.percentile(v, 97) if len(v) else 1.0
    return max(_otsu(v), 0.25 * strong, 0.05)


def _tempo_candidates(curve, hint):
    """Possible tempos: the analyzer's guess and its common mix-ups (half,
    double, 3/4, 4/3, 4/5, 5/4) plus peaks of the drums' own repetition."""
    cands = {hint * f for f in (1, 2, 0.5, 1.5, 2 / 3, 1.25, 0.8, 4 / 3, 0.75)}
    ac = np.correlate(curve - curve.mean(), curve - curve.mean(), mode="full")[len(curve) - 1:]
    for bpm in np.arange(70, 180, 1.0):
        lag = int(round(FPS * 60 / bpm))
        if lag + 1 < len(ac) and ac[lag] >= ac[lag - 1] and ac[lag] >= ac[lag + 1] and ac[lag] > 0.25 * ac[0]:
            cands.add(bpm)
    return sorted(b for b in cands if 70 <= b <= 180)


def _grid_contrast(curve, bpm, phase):
    """How much more onset energy sits ON the 16th grid than halfway between."""
    peaks = _local_max(curve, 1)
    step = FPS * 60.0 / bpm / 4.0
    n = int((len(peaks) - step - 2) / step)
    on = np.round(phase + np.arange(n) * step).astype(int)
    off = np.round(phase + step / 2 + np.arange(n) * step).astype(int)
    return float(peaks[on].mean() - peaks[off].mean())


def _sample(curve, idx, radius):
    """Max of curve within ±radius frames of each index, plus where it was."""
    offs = np.arange(-radius, radius + 1)
    pos = np.clip(idx[:, None] + offs[None, :], 0, len(curve) - 1)
    vals = curve[pos]
    j = np.argmax(vals, axis=1)
    return vals[np.arange(len(idx)), j], offs[j]


# ---------------------------------------------------------------------------------
# 3. Main entry
# ---------------------------------------------------------------------------------
def extract_pattern(path, mode="quick", loop="auto", bpm_hint=None, stem_path=None, progress=None):
    """Copy the drum pattern from an audio file.

    mode      'quick' (on this computer) or 'accurate' (stem_path = drums-only
              file from Demucs)
    loop      'auto', 4, 8 or 16 (bars)
    returns   dict: bpm, bars, hits [(step, note, velocity)], swing, loop_scores,
              confidence, start_time, mode
    """
    if np is None:
        raise DrumError("Copying drums needs numpy. Run:  python3 -m pip install numpy")
    say = progress or (lambda text: None)

    say("Listening…")
    y_mix, _ = an.load_audio(path)
    y_mix = y_mix[: int(MAX_SECONDS * SR)]
    if bpm_hint is None:
        bpm_hint = an.detect_bpm(y_mix)
    if not bpm_hint:
        raise DrumError("Couldn't find a steady beat in this song.")
    bpm_hint = float(bpm_hint)
    while bpm_hint < 70:   # drum grids read best between 70 and 180 BPM
        bpm_hint *= 2
    while bpm_hint > 180:
        bpm_hint /= 2

    if stem_path:
        y, _ = an.load_audio(stem_path)
        y = y[: int(MAX_SECONDS * SR)]
        mag = an._stft_mag(y, N_FFT, HOP)
    else:
        say("Separating the drums from the music…")
        mag = _percussive(an._stft_mag(y_mix, N_FFT, HOP))

    say("Finding kicks, snares and hi-hats…")
    onset, energy = _band_curves(mag)
    onset_all = onset["kick"] + onset["snare"] + 0.6 * onset["hat"]
    # try the likely tempos; keep the one whose grid lines up best with the hits
    best = None
    for cand in _tempo_candidates(onset_all, bpm_hint):
        b, ph = fit_grid(onset_all, cand, spread=0.006)
        c = _grid_contrast(onset_all, b, ph)
        if best is None or c > best[0]:
            best = (c, b, ph)
    bpm, phase = fit_grid(onset_all, best[1], spread=0.004)
    step = FPS * 60.0 / bpm / 4.0
    n_steps = int((len(onset_all) - phase - step) / step)
    if n_steps < 32:
        raise DrumError("The song is too short to find a drum loop (need at least 2 bars).")
    grid = np.round(phase + np.arange(n_steps) * step).astype(int)
    radius = max(1, int(step * 0.3))

    vals, offsets, hits, norm = {}, {}, {}, {}
    for band in BANDS:
        v, o = _sample(onset[band], grid, radius)
        vals[band], offsets[band] = v, o
        hits[band] = v > _threshold(v)
        norm[band] = v / (np.percentile(v, 97) + 1e-9)  # 1.0 = a typical strong hit in this band
    # Each drum spills a little into the other bands (a kick's click reaches the
    # snare band, a snare's body reaches the lows). Count a kick only when the
    # low end dominates, a snare only when the mids do, or both if both are
    # strong (layered kick + snare).
    nk, ns = norm["kick"], norm["snare"]
    hits["kick"] &= (nk >= 0.75 * ns) | (nk > 0.85)
    hits["snare"] &= (ns >= 0.75 * nk) | (ns > 0.85)
    # open vs closed hats: does the high band keep ringing half a step after the hit?
    hit_frame = np.clip(grid + offsets["hat"], 0, len(energy["hat"]) - 1)
    e0, _ = _sample(energy["hat"], hit_frame, 1)
    later = np.clip(hit_frame + int(step * 0.6), 0, len(energy["hat"]) - 1)
    # subtract whatever was already ringing just before the hit (e.g. the
    # previous open hat), so only THIS hat's own ring counts
    before = np.min(np.stack([energy["hat"][np.clip(hit_frame - k, 0, None)] for k in (2, 3, 4)]), axis=0)
    rise = e0 - before
    clear = rise > 0.5 * e0             # the hat clearly stands out from what was ringing
    ring = np.where(clear, (energy["hat"][later] - before) / (rise + 1e-9), 0.0)  # unclear -> closed (more common)
    open_hat = hits["hat"] & (ring > 0.3)   # closed hats are nearly silent by then; open ones still ring
    closed_hat = hits["hat"] & ~open_hat
    # 1/32 rolls: a hat hit halfway between two hat hits
    mid = np.clip(np.round(grid + step / 2).astype(int), 0, len(onset["hat"]) - 1)
    mv, _ = _sample(onset["hat"], mid, max(1, int(step * 0.15)))
    hat_thr = _threshold(vals["hat"])
    roll = (mv > hat_thr * 0.9) & hits["hat"] & np.roll(hits["hat"], -1)

    lanes = {"kick": hits["kick"], "snare": hits["snare"], "hat": closed_hat, "open_hat": open_hat, "roll": roll}
    vel = {"kick": vals["kick"], "snare": vals["snare"], "hat": vals["hat"], "open_hat": vals["hat"],
           "roll": mv}

    say("Finding beat 1…")
    start = _find_bar_start(lanes)
    say("Looking for the 4 / 8 / 16-bar loop…")
    result = _find_loop(lanes, vel, start, loop)

    # swing: how late the off-beat 16ths land, as a fraction of a 16th
    hit_any = lanes["kick"] | lanes["snare"] | lanes["hat"]
    pos = (np.arange(n_steps) - start) % 2          # count from beat 1 of the bar
    odd = hit_any & (pos == 1)
    even = hit_any & (pos == 0)
    off_all = np.where(lanes["hat"], offsets["hat"], np.where(lanes["snare"], offsets["snare"], offsets["kick"]))
    swing = 0.0
    if odd.sum() >= 4 and even.sum() >= 4:
        swing = float(np.median(off_all[odd]) - np.median(off_all[even])) / step
        swing = round(min(0.33, max(0.0, swing)), 3)

    loop_start_step = start + result["offset_bars"] * 16
    return {
        "bpm": round(bpm, 2),
        "bars": result["bars"],
        "hits": result["hits"],
        "swing": swing,
        "loop_scores": result["scores"],
        "confidence": round(result["score"], 3),
        "start_time": round((phase + loop_start_step * step) / FPS, 3),
        "mode": "accurate" if stem_path else "quick",
        "analyzed_bars": (n_steps - start) // 16,
    }


def _find_bar_start(lanes):
    """Which of the 16 grid positions is beat 1? Kick on the 1, snare/clap on
    the backbeat (or on beat 3 in half-time), rarely a snare on the 1."""
    k, s = lanes["kick"], lanes["snare"]
    best, best_score = 0, -9.0
    for st in range(16):
        nb = (len(k) - st) // 16
        if nb < 2:
            continue
        K = k[st:st + nb * 16].reshape(nb, 16).astype(float)
        S = s[st:st + nb * 16].reshape(nb, 16).astype(float)
        back = np.maximum(S[:, 4], S[:, 12])
        score = (K[:, 0] + 0.35 * K[:, 8] + 0.5 * back + 0.35 * S[:, 8] * (1 - back) - 0.6 * S[:, 0]).mean()
        if score > best_score:
            best, best_score = st, score
    return best


def _sim(a, b):
    return 2 * (a & b).sum() / (a.sum() + b.sum() + 1e-9)


def _loop_score(B, busy, L, o):
    """How well the bars repeat as an L-bar loop starting at bar o. Each copy
    is compared with the OTHER copies, so a long loop with only two copies
    can't simply agree with itself."""
    nb = len(B)
    reps = (nb - o) // L
    if reps < 2:
        return None
    R = B[o:o + reps * L].reshape(reps, L * B.shape[1])
    ok = busy[o:o + reps * L].reshape(reps, L).mean(axis=1) > 0.7
    if ok.sum() < 2:
        return None
    Rk = R[ok]
    sims = [_sim(Rk[i], np.delete(Rk, i, axis=0).mean(axis=0) >= 0.5) for i in range(len(Rk))]
    return float(np.mean(sims)), ok, reps


def _fill_periods(B, busy):
    """Find regular switch-ups: bars that break the groove every 8 or 16 bars
    (a fill, a drop-out, a turnaround). Judged on kick + snare + open hat
    only (busy hi-hats would drown it out). Returns candidates, best first:
    [(period, start_bar), ...] where start_bar is the bar after the fill."""
    nb = len(B)
    if nb < 12:
        return []
    core = np.concatenate([B[:, LANES.index(l) * 16:(LANES.index(l) + 1) * 16] for l in ("kick", "snare", "open_hat")],
                          axis=1)
    dev = np.array([1 - _sim(core[b], core[b - 4]) if (busy[b] and busy[b - 4]) else np.nan for b in range(4, nb)])
    idx = np.arange(4, nb)
    cands = []
    for P in (8, 16):
        for ph in range(P):
            at = (idx % P) == ph
            vals, rest = dev[at], dev[~at]
            vals, rest = vals[~np.isnan(vals)], rest[~np.isnan(rest)]
            if len(vals) < 2 or len(rest) < 4:
                continue
            gap = float(np.mean(vals) - np.mean(rest))
            # every occurrence must stand out, not just the average (noise-proof)
            if gap > 0.15 and np.min(vals) > np.mean(rest) + 0.08:
                # a 16-bar cycle must be clearly stronger than an 8-bar one to win
                cands.append((gap - (0.05 if P == 16 else 0.0), P, (ph + 1) % P))
    cands.sort(reverse=True)
    return [(P, o) for _g, P, o in cands]


def _find_loop(lanes, vel, start, loop):
    """Pick the loop: 4, 8 or 16 bars (or the length you chose)."""
    nb = (len(lanes["kick"]) - start) // 16
    if nb < 1:
        raise DrumError("Couldn't find a full bar of drums.")
    B = np.concatenate([lanes[l][start:start + nb * 16].reshape(nb, 16) for l in LANES], axis=1)
    V = np.concatenate([vel[l][start:start + nb * 16].reshape(nb, 16) for l in LANES], axis=1)
    # bars with almost nothing in them (breakdowns, intro) shouldn't vote
    busy = B.sum(axis=1) >= max(2, np.median(B.sum(axis=1)) * 0.4)

    lengths = LOOP_CHOICES if loop == "auto" else (int(loop),)
    scores, found = {}, {}
    for L in lengths:
        best = None
        for o in range(min(L, max(1, nb - L))):
            r = _loop_score(B, busy, L, o)
            if r and (best is None or r[0] > best[0]):
                best = (r[0], o, r[1], r[2])
        if best:
            scores[L] = round(best[0], 3)
            found[L] = best

    choice = None
    if loop == "auto":
        for P, o in _fill_periods(B, busy):
            r = _loop_score(B, busy, P, o)
            if r:                       # needs at least two full copies in the song
                found[P] = (r[0], o, r[1], r[2])
                scores[P] = round(r[0], 3)
                choice = P              # regular fills decide the loop length
                break
        if choice is None and found:
            choice = min(found)         # otherwise: shortest loop...
            for L in sorted(found):
                if L > choice and scores[L] >= scores[choice] + 0.04:
                    choice = L          # ...unless a longer one clearly repeats better
    elif found:
        choice = int(loop)

    if choice is None:
        # too short for two copies: use what we have as a single loop
        L = min(4 if loop == "auto" else int(loop), nb)
        found[L] = (0.5, 0, np.array([True]), 1)
        scores[L] = 0.5
        choice = L
    score, o, ok, reps = found[choice]
    L = choice
    R = B[o:o + reps * L].reshape(reps, L, B.shape[1])[ok]
    RV = V[o:o + reps * L].reshape(reps, L, V.shape[1])[ok]
    cons = R.mean(axis=0) >= 0.5
    hits = []
    vmax = {l: float(np.percentile(vel[l], 98)) + 1e-9 for l in LANES}
    for bar in range(L):
        for li, lane in enumerate(LANES):
            for s16 in range(16):
                col = li * 16 + s16
                if not cons[bar, col]:
                    continue
                strength = RV[:, bar, col][R[:, bar, col]].mean()
                velocity = int(np.clip(55 + 72 * strength / vmax[lane], 40, 127))
                step = bar * 16 + s16 + (0.5 if lane == "roll" else 0.0)
                note = NOTE["hat"] if lane == "roll" else NOTE[lane]
                hits.append((step, note, velocity))
    hits.sort()
    return {"bars": L, "hits": hits, "score": score, "scores": scores, "offset_bars": o}


# ---------------------------------------------------------------------------------
# 4. Using the pattern: notes, MIDI, sound
# ---------------------------------------------------------------------------------
def pattern_notes(pattern, total_bars):
    """The loop repeated over total_bars, as (start_beat, length, note, velocity)."""
    L = pattern["bars"]
    swing = pattern.get("swing", 0.0)
    out = []
    for rep in range(0, total_bars, L):
        for step, note, vel in pattern["hits"]:
            bar = rep + int(step // 16)
            if bar >= total_bars:
                continue
            s = rep * 16 + step
            if int(step) % 2 == 1 and step == int(step):
                s += swing  # late off-beats = swing
            out.append((s / 4.0, 0.12 if note == NOTE["hat"] else 0.25, note, vel))
    return out


def kick_steps_by_bar(pattern):
    """{bar_in_loop: [16th steps with a kick]}: the bass line can follow these."""
    out = {b: [] for b in range(pattern["bars"])}
    for step, note, _v in pattern["hits"]:
        if note == NOTE["kick"]:
            out[int(step // 16)].append(int(step % 16))
    return out


def export_midi(pattern, path, repeats=1):
    song = me.Song(pattern["bpm"], pattern["bars"] * repeats, "drums")
    song.tracks.append(me._track("Drums", "Drums", 9, pattern_notes(pattern, pattern["bars"] * repeats), program=0))
    return me.write_midi(song, path)


def render(pattern, total_bars, rate=44100, kit=None):
    """Stereo float array of the pattern played for total_bars."""
    spb = 60.0 / pattern["bpm"]
    length = int((total_bars * 4 * spb + 1.0) * rate)
    out = np.zeros(length)
    sounds = {}
    for beat, _dur, note, vel in pattern_notes(pattern, total_bars):
        if note not in sounds:
            sounds[note] = (kit or {}).get(note)
            if sounds[note] is None:
                sounds[note] = _resample(me._drum(note, 127), me.RATE, rate)
        snd = sounds[note] * (vel / 127.0)
        i0 = int(beat * spb * rate)
        i1 = min(length, i0 + len(snd))
        if i0 < length:
            out[i0:i1] += snd[: i1 - i0]
    return np.stack([out, out], axis=1)


def render_wav(pattern, path, total_bars=None, kit=None):
    total = total_bars or max(pattern["bars"], 8)
    audio = render(pattern, total, me.RATE, kit)
    _write_wav(path, audio, me.RATE)
    return path


def _resample(x, src, dst):
    if src == dst or len(x) == 0:
        return x
    n = int(len(x) * dst / src)
    return np.interp(np.linspace(0, len(x), n, endpoint=False), np.arange(len(x)), x)


def _write_wav(path, stereo, rate):
    peak = float(np.max(np.abs(stereo))) or 1.0
    pcm = (stereo / peak * 0.92 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------------------------
# 5. Your own drum kit (a folder of samples)
# ---------------------------------------------------------------------------------
KIT_WORDS = {
    36: ("kick", "kik", "bd", "bassdrum"),
    38: ("snare", "snr", "sd", "clap", "clp", "rim"),
    42: ("closed", "chh", "hihat", "hi-hat", "hi hat", "hat", "hh"),
    46: ("open", "ohh", "oh "),
}


def load_kit(folder, rate=44100):
    """Pick one sample per drum from a folder by file name (kick, snare/clap,
    hat, open hat). Returns {note: samples} for whatever it found."""
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() == ".wav")
    kit = {}
    for note, words in KIT_WORDS.items():
        for f in files:
            name = f.stem.lower()
            if note == 42 and any(w in name for w in KIT_WORDS[46][:2]):
                continue  # don't use an open hat as the closed hat
            if any(w in name for w in words):
                try:
                    y, sr = _read_wav_mono(f)
                    kit[note] = _resample(y, sr, rate)
                    break
                except Exception:
                    continue
    return kit


def _read_wav_mono(path):
    with wave.open(str(path), "rb") as w:
        ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        x = np.frombuffer(raw, "<i2").astype(float) / 32768
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        i = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        x = np.where(i & 0x800000, i - 0x1000000, i).astype(float) / 8388608
    elif width == 4:
        x = np.frombuffer(raw, "<i4").astype(float) / 2147483648
    else:
        x = (np.frombuffer(raw, np.uint8).astype(float) - 128) / 128
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


# ---------------------------------------------------------------------------------
# 6. Layer the copied drums under another track (e.g. the MusicGen result)
# ---------------------------------------------------------------------------------
def mix_under(music_path, pattern, out_path, kit=None, drum_level=0.8):
    """Line the drum loop up with the music's beat and mix them together."""
    music, rate = _read_stereo(music_path)
    mono = music.mean(axis=1)
    y = _resample(mono, rate, SR)
    onset, _ = _band_curves(an._stft_mag(y.astype("float32"), N_FFT, HOP))
    curve = onset["kick"] + onset["snare"] + onset["hat"]
    _bpm, phase = fit_grid(curve, pattern["bpm"], spread=0.003)
    # among the 4 possible beat positions, start on the one with the most energy
    step = FPS * 60.0 / pattern["bpm"] / 4.0
    n = int((len(curve) - phase) / step) - 1
    grid = np.round(phase + np.arange(max(n, 4)) * step).astype(int).clip(0, len(curve) - 1)
    beat_shift = int(np.argmax([curve[grid[k::4]].sum() for k in range(4)]))
    start_sec = (phase + beat_shift * step) / FPS
    bars = int(len(music) / rate / (4 * 60.0 / pattern["bpm"])) + 1
    drums = render(pattern, bars, rate, kit)
    off = int(start_sec * rate)
    mixed = music.copy()
    end = min(len(mixed), off + len(drums))
    music_peak = float(np.max(np.abs(music))) or 1.0
    drum_peak = float(np.max(np.abs(drums))) or 1.0
    mixed[off:end] += drums[: end - off] / drum_peak * music_peak * drum_level
    _write_wav(out_path, mixed, rate)
    return out_path


def _read_stereo(path):
    """Read a WAV as float stereo (converting with ffmpeg if it's an unusual WAV)."""
    try:
        with wave.open(str(path), "rb") as w:
            ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
        if width != 2:
            raise wave.Error("not 16-bit")
        x = np.frombuffer(raw, "<i2").astype(float) / 32768
        x = x.reshape(-1, ch)
    except (wave.Error, EOFError):
        import shutil
        import subprocess
        import tempfile
        if not shutil.which("ffmpeg"):
            raise DrumError("Can't read this audio file without ffmpeg.") from None
        tmp = Path(tempfile.gettempdir()) / "shmai_mix_in.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "2", "-ar", "44100",
                        "-c:a", "pcm_s16le", str(tmp)], check=True, capture_output=True)
        return _read_stereo(tmp)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], sr
