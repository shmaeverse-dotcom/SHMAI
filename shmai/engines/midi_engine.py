"""
Local MIDI engine (runs on your computer, no internet, no cost).

compose(settings) -> Song with up to four layers:
    lead    the melody (your chosen instrument)
    chords  harmony (pad / piano / strings...)
    bass    bass line following the chord roots
    drums   genre-based groove (General MIDI drums, channel 10)

write_midi(song, path)  saves a standard .mid file for any DAW.
render_wav(song, path)  makes a quick preview .wav with a tiny built-in
                        synth (needs numpy), so you can listen right away.
"""
import math
import random
import struct
import wave

try:
    import numpy as np
except ImportError:  # preview rendering is optional
    np = None

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}

# Instrument name -> (General MIDI program number, synth voice for preview)
INSTRUMENTS = {
    "Grand Piano": (0, "piano"), "Electric Piano (Rhodes)": (4, "epiano"), "Organ": (16, "organ"),
    "Acoustic Guitar": (24, "pluck"), "Electric Guitar": (27, "pluck"), "Distorted Guitar": (30, "lead"),
    "Bass Guitar": (33, "bass"), "Synth Bass / 808": (38, "bass808"), "Violin": (40, "strings"),
    "Cello": (42, "strings"), "String Ensemble": (48, "strings"), "Harp": (46, "pluck"),
    "Trumpet": (56, "brass"), "Saxophone": (65, "brass"), "Flute": (73, "flute"),
    "Synth Lead": (81, "lead"), "Synth Pad": (89, "pad"), "Bells": (14, "bell"), "Marimba": (12, "bell"),
    "Kalimba": (108, "bell"), "Choir Pad (aahs)": (52, "pad"),
}
LEAD_INSTRUMENTS = [n for n in INSTRUMENTS if n not in ("Bass Guitar", "Synth Bass / 808")]
BASS_INSTRUMENTS = ["Synth Bass / 808", "Bass Guitar", "Cello"]
CHORD_INSTRUMENTS = ["Synth Pad", "Grand Piano", "Electric Piano (Rhodes)", "String Ensemble", "Organ",
                     "Choir Pad (aahs)", "Acoustic Guitar"]

GENRES = ["Hip Hop", "Trap", "Drill", "Lo-fi", "R&B", "Pop", "Afrobeats", "Reggaeton", "House", "Techno",
          "Drum & Bass", "EDM", "Rock", "Jazz", "Soul", "Gospel", "Country", "Cinematic", "Ambient", "Phonk"]
MOODS = ["Happy", "Sad", "Dark", "Dreamy", "Energetic", "Chill", "Romantic", "Aggressive", "Mysterious",
         "Epic", "Nostalgic", "Uplifting"]
KEYS = ["Auto"] + [f"{n} {m}" for m in ("minor", "major") for n in
                   ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]]

MINOR_MOODS = {"Sad", "Dark", "Mysterious", "Aggressive", "Nostalgic", "Dreamy", "Epic"}

# Chord progressions as scale degrees (0 = the key's home chord)
PROGRESSIONS = {
    "minor": [[0, 5, 2, 6], [0, 3, 4, 0], [0, 6, 5, 4], [0, 5, 3, 4], [0, 3, 6, 2]],
    "major": [[0, 4, 5, 3], [0, 5, 3, 4], [0, 3, 0, 4], [5, 3, 0, 4], [0, 2, 3, 4]],
}

# Drum patterns on a 16-step grid per bar. Notes: 36 kick, 38 snare, 39 clap, 42 closed hat, 46 open hat
DRUMS = {
    "boom_bap": {36: [0, 7, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14]},
    "trap": {36: [0, 7, 11], 39: [8], 42: list(range(16)), 46: [14]},
    "drill": {36: [0, 6, 10], 38: [6, 14], 42: [0, 3, 6, 8, 11, 14]},
    "four_floor": {36: [0, 4, 8, 12], 39: [4, 12], 42: [2, 6, 10, 14], 46: [14]},
    "rock": {36: [0, 6, 8], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14]},
    "afro": {36: [0, 6, 10], 38: [4, 13], 42: [0, 3, 6, 8, 11, 14]},
    "dembow": {36: [0, 4, 8, 12], 38: [3, 6, 11, 14], 42: [0, 2, 4, 6, 8, 10, 12, 14]},
    "dnb": {36: [0, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14]},
    "lofi": {36: [0, 9], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14]},
    "none": {},
}
GENRE_GROOVE = {
    "Hip Hop": "boom_bap", "Trap": "trap", "Drill": "drill", "Lo-fi": "lofi", "R&B": "boom_bap",
    "Pop": "four_floor", "Afrobeats": "afro", "Reggaeton": "dembow", "House": "four_floor",
    "Techno": "four_floor", "Drum & Bass": "dnb", "EDM": "four_floor", "Rock": "rock", "Jazz": "lofi",
    "Soul": "boom_bap", "Gospel": "boom_bap", "Country": "rock", "Cinematic": "none", "Ambient": "none",
    "Phonk": "trap",
}


class Song:
    def __init__(self, bpm, bars, key_name):
        self.bpm = bpm
        self.bars = bars
        self.key_name = key_name
        self.tracks = []  # dicts: name, instrument, program, channel, notes[(start, dur, pitch, vel)]

    @property
    def beats(self):
        return self.bars * 4

    @property
    def seconds(self):
        return self.beats * 60.0 / self.bpm


def parse_key(key, mood, rnd):
    """'F# minor' -> (root pitch class, 'minor'). 'Auto' picks from the mood."""
    if not key or key == "Auto":
        mode = "minor" if mood in MINOR_MOODS else "major"
        return rnd.randrange(12), mode
    parts = key.replace("♯", "#").replace("♭", "b").split()
    name = FLAT_TO_SHARP.get(parts[0], parts[0])
    mode = "minor" if len(parts) > 1 and parts[1].lower().startswith("min") else "major"
    root = NOTE_NAMES.index(name) if name in NOTE_NAMES else 0
    return root, mode


def compose(settings, seed=None):
    """settings keys: bpm, duration (seconds), key, mood, genre, instrument,
    layers {chords, bass, drums}, chord_instrument, bass_instrument."""
    rnd = random.Random(seed)
    bpm = int(settings.get("bpm") or 100)
    duration = float(settings.get("duration") or 15)
    bars = max(2, int(round(duration * bpm / 240.0 / 2)) * 2)
    mood = settings.get("mood") or "Chill"
    genre = settings.get("genre") or "Hip Hop"
    root, mode = parse_key(settings.get("key"), mood, rnd)
    key_name = f"{NOTE_NAMES[root]} {mode}"
    song = Song(bpm, bars, key_name)
    scale = SCALES[mode]
    prog = rnd.choice(PROGRESSIONS[mode])
    layers = settings.get("layers") or {"chords": True, "bass": True, "drums": True}

    def degree_pitch(deg, octave):
        o, d = divmod(deg, 7)
        return 12 * (octave + o) + root + scale[d]

    def chord_at(bar):
        return prog[bar % len(prog)]

    # ---- chords ----------------------------------------------------------------
    if layers.get("chords", True):
        name = settings.get("chord_instrument") or "Synth Pad"
        notes = []
        for bar in range(bars):
            deg = chord_at(bar)
            pitches = [degree_pitch(deg + i, 4) for i in (0, 2, 4)]
            if mood in ("Dreamy", "Chill", "Romantic", "Nostalgic") or genre in ("Lo-fi", "Jazz", "R&B", "Soul"):
                pitches.append(degree_pitch(deg + 6, 4))  # add the 7th for color
            if genre in ("House", "EDM", "Pop", "Reggaeton", "Afrobeats"):
                for step in (0, 1.5, 2.5):  # rhythmic stabs
                    for p in pitches:
                        notes.append((bar * 4 + step, 0.9, p, 70))
            else:
                for p in pitches:
                    notes.append((bar * 4, 3.95, p, 62))
        song.tracks.append(_track("Chords", name, 1, notes))

    # ---- bass --------------------------------------------------------------------
    if layers.get("bass", True):
        name = settings.get("bass_instrument") or ("Synth Bass / 808" if genre in ("Trap", "Drill", "Phonk", "Hip Hop")
                                                    else "Bass Guitar")
        notes = []
        groove = DRUMS[GENRE_GROOVE.get(genre, "boom_bap")]
        kicks = groove.get(36, [0, 8])
        for bar in range(bars):
            p = degree_pitch(chord_at(bar), 2)
            hits = kicks or [0, 8]
            for i, step in enumerate(hits):
                nxt = hits[i + 1] if i + 1 < len(hits) else 16
                length = max(1, nxt - step) / 4.0
                pitch = p + (12 if (genre in ("House", "Techno", "EDM") and step % 8 == 4) else 0)
                notes.append((bar * 4 + step / 4.0, length * 0.95, pitch, 96))
        song.tracks.append(_track("Bass", name, 2, notes))

    # ---- drums ---------------------------------------------------------------------
    if layers.get("drums", True) and GENRE_GROOVE.get(genre, "boom_bap") != "none":
        pattern = DRUMS[GENRE_GROOVE.get(genre, "boom_bap")]
        notes = []
        for bar in range(bars):
            for drum, steps in pattern.items():
                for st in steps:
                    vel = 110 if drum in (36, 38, 39) else (70 + 25 * (st % 4 == 0))
                    swing = 0.06 if (genre == "Lo-fi" and st % 2 == 1) else 0
                    notes.append((bar * 4 + st / 4.0 + swing, 0.2, drum, vel))
            if genre in ("Trap", "Phonk") and bar % 2 == 1:  # hi-hat roll at the end of every 2nd bar
                for k in range(6):
                    notes.append((bar * 4 + 3.5 + k / 12.0, 0.08, 42, 65 + k * 5))
        song.tracks.append(_track("Drums", "Drums", 9, notes, program=0))

    # ---- lead melody (call & response motifs) ---------------------------------------
    lead = settings.get("instrument") or "Grand Piano"
    density = {"Energetic": 0.75, "Aggressive": 0.7, "Happy": 0.65, "Uplifting": 0.6}.get(mood, 0.5)
    if genre in ("Ambient", "Cinematic"):
        density = 0.3
    rhythm_cells = [[1, 1, 1, 1], [1.5, 0.5, 1, 1], [0.5, 0.5, 1, 2], [1, 0.5, 0.5, 2], [2, 1, 1],
                    [0.75, 0.75, 0.5, 2], [0.5, 0.5, 0.5, 0.5, 2]]
    if density < 0.4:
        rhythm_cells = [[2, 2], [3, 1], [4], [1, 3]]
    elif density > 0.65:
        rhythm_cells += [[0.5] * 8, [0.25, 0.25, 0.5, 0.5, 0.5, 2]]

    def make_motif():
        cell = rnd.choice(rhythm_cells)
        cell2 = rnd.choice(rhythm_cells)
        return cell + cell2  # 2 bars of rhythm

    motif_a, motif_b = make_motif(), make_motif()
    notes = []
    current = 7 + rnd.choice([0, 2, 4])  # start on a chord tone around the middle
    for phrase in range(0, bars, 2):
        rhythm = motif_a if (phrase // 2) % 2 == 0 else motif_b
        t = 0.0
        for dur in rhythm:
            if t >= 8:
                break
            bar = phrase + int(t // 4)
            if bar >= bars:
                break
            chord = chord_at(bar)
            strong = (t % 2) == 0
            if strong:
                # land on a chord tone close to the current note
                targets = [chord + i + 7 * o for o in (0, 1, 2) for i in (0, 2, 4)]
                current = min(targets, key=lambda d: abs(d - current) + rnd.random() * 2)
            else:
                current += rnd.choice([-2, -1, -1, 1, 1, 2])
            current = max(4, min(16, current))
            rest = rnd.random() > (0.55 + density * 0.4)
            if not rest:
                vel = 96 if strong else 80
                notes.append((phrase * 4 + t, dur * 0.92, degree_pitch(current, 4), vel))
            t += dur
    song.tracks.insert(0, _track("Lead", lead, 0, notes))
    return song


def _track(name, instrument, channel, notes, program=None):
    prog = INSTRUMENTS.get(instrument, (0, "piano"))[0] if program is None else program
    return {"name": name, "instrument": instrument, "program": prog, "channel": channel, "notes": notes}


# ---------------------------------------------------------------------------------------
# MIDI file writer (Standard MIDI File, type 1)
# ---------------------------------------------------------------------------------------
TPB = 480  # ticks per beat


def _varlen(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(out)


def _chunk(kind, data):
    return kind + struct.pack(">I", len(data)) + data


def write_midi(song, path):
    tracks = []
    # tempo track
    tempo = int(60_000_000 / song.bpm)
    meta = _varlen(0) + b"\xff\x51\x03" + tempo.to_bytes(3, "big")
    meta += _varlen(0) + b"\xff\x58\x04\x04\x02\x18\x08"  # 4/4
    meta += _varlen(0) + b"\xff\x2f\x00"
    tracks.append(_chunk(b"MTrk", meta))

    for tr in song.tracks:
        ch = tr["channel"] & 0x0F
        events = []
        for start, dur, pitch, vel in tr["notes"]:
            on = int(round(start * TPB))
            off = int(round((start + dur) * TPB))
            pitch = max(0, min(127, pitch))
            events.append((on, 1, bytes([0x90 | ch, pitch, max(1, min(127, vel))])))
            events.append((max(off, on + 1), 0, bytes([0x80 | ch, pitch, 0])))
        events.sort(key=lambda e: (e[0], e[1]))
        data = bytearray()
        name = tr["name"].encode("ascii", "replace")
        data += _varlen(0) + b"\xff\x03" + _varlen(len(name)) + name
        if ch != 9:
            data += _varlen(0) + bytes([0xC0 | ch, tr["program"] & 0x7F])
        last = 0
        for tick, _order, msg in events:
            data += _varlen(tick - last) + msg
            last = tick
        data += _varlen(0) + b"\xff\x2f\x00"
        tracks.append(_chunk(b"MTrk", bytes(data)))

    header = _chunk(b"MThd", struct.pack(">HHH", 1, len(tracks), TPB))
    with open(path, "wb") as f:
        f.write(header + b"".join(tracks))
    return path


# ---------------------------------------------------------------------------------------
# Preview synth (numpy). Not studio quality: it's for quick listening.
# ---------------------------------------------------------------------------------------
RATE = 44100


def _midi_hz(p):
    return 440.0 * 2 ** ((p - 69) / 12.0)


def _voice(kind, freq, n, vel):
    t = np.arange(n) / RATE
    amp = vel / 127.0
    nyq_h = max(1, int((RATE / 2) / max(freq, 1)))

    def saw(h=10):
        out = np.zeros(n)
        for k in range(1, min(h, nyq_h) + 1):
            out += np.sin(2 * np.pi * freq * k * t) / k
        return out * 0.55

    def env(a, d, s, r):
        e = np.ones(n) * s
        ai, di, ri = int(a * RATE), int(d * RATE), int(r * RATE)
        ai = min(ai, n)
        e[:ai] = np.linspace(0, 1, ai, endpoint=False) if ai else e[:ai]
        de = min(n, ai + di)
        if de > ai:
            e[ai:de] = np.linspace(1, s, de - ai)
        if ri and n > ri:
            e[-ri:] *= np.linspace(1, 0, ri)
        return e

    if kind in ("piano", "epiano"):
        w = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(4 * np.pi * freq * t) + 0.15 * np.sin(6 * np.pi * freq * t)
        if kind == "epiano":
            w += 0.25 * np.sin(2 * np.pi * freq * 7.0 * t) * np.exp(-t * 12)
        w *= np.exp(-t * (2.2 if kind == "piano" else 1.6))
        e = env(0.003, 0.0, 1.0, 0.05)
    elif kind == "organ":
        w = sum(np.sin(2 * np.pi * freq * m * t) / (i + 1) for i, m in enumerate((1, 2, 3, 4, 6)))
        e = env(0.01, 0.05, 0.9, 0.05)
    elif kind == "pluck":
        w = saw(8) * np.exp(-t * 4.5)
        e = env(0.002, 0.0, 1.0, 0.04)
    elif kind in ("bass", "bass808"):
        if kind == "bass808":
            glide = freq * (1 + 0.6 * np.exp(-t * 40))
            w = np.sin(2 * np.pi * np.cumsum(glide) / RATE) * 1.3
            w = np.tanh(w * 1.6)
            e = env(0.002, 0.3, 0.75, 0.06)
        else:
            w = np.sin(2 * np.pi * freq * t) + 0.3 * saw(4)
            e = env(0.004, 0.2, 0.7, 0.05)
    elif kind == "strings":
        w = saw(9) * (1 + 0.004 * np.sin(2 * np.pi * 5 * t))
        e = env(0.18, 0.1, 0.85, 0.15)
    elif kind == "brass":
        w = saw(12)
        e = env(0.05, 0.1, 0.8, 0.08)
    elif kind == "flute":
        w = np.sin(2 * np.pi * freq * t * (1 + 0.003 * np.sin(2 * np.pi * 5 * t))) + 0.02 * np.random.randn(n)
        e = env(0.06, 0.05, 0.85, 0.08)
    elif kind == "bell":
        w = (np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2.76 * t)
             + 0.25 * np.sin(2 * np.pi * freq * 5.4 * t)) * np.exp(-t * 3.5)
        e = env(0.001, 0.0, 1.0, 0.05)
    elif kind == "pad":
        w = sum(np.sin(2 * np.pi * freq * det * t) for det in (0.995, 1.0, 1.005)) / 2 + 0.25 * saw(5)
        e = env(0.35, 0.2, 0.8, 0.3)
    else:  # lead
        vib = 1 + 0.005 * np.sin(2 * np.pi * 5.5 * t)
        w = np.zeros(n)
        for k in range(1, min(12, nyq_h) + 1):
            w += np.sin(2 * np.pi * freq * k * t * vib) / k
        w *= 0.5
        e = env(0.01, 0.1, 0.75, 0.06)
    return w * e * amp * 0.35


def _drum(pitch, vel):
    amp = vel / 127.0
    if pitch == 36:  # kick
        n = int(0.35 * RATE)
        t = np.arange(n) / RATE
        f = 50 + 110 * np.exp(-t * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 9) * amp * 0.9
    if pitch in (38, 39):  # snare / clap
        n = int(0.22 * RATE)
        t = np.arange(n) / RATE
        noise = np.random.randn(n) * np.exp(-t * (18 if pitch == 38 else 24))
        body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * (0.6 if pitch == 38 else 0)
        return (noise * 0.35 + body) * amp
    n = int((0.25 if pitch == 46 else 0.06) * RATE)  # hats
    t = np.arange(n) / RATE
    noise = np.random.randn(n)
    noise = np.diff(noise, prepend=0)  # crude high-pass: keeps it bright
    return noise * np.exp(-t * (12 if pitch == 46 else 60)) * amp * 0.12


def render_wav(song, path):
    """Render a quick stereo preview .wav. Returns path, or None without numpy."""
    if np is None:
        return None
    total = int((song.seconds + 1.5) * RATE)
    left = np.zeros(total)
    right = np.zeros(total)
    spb = 60.0 / song.bpm
    pans = {"Lead": 0.1, "Chords": -0.25, "Bass": 0.0, "Drums": 0.0}
    for tr in song.tracks:
        kind = INSTRUMENTS.get(tr["instrument"], (0, "piano"))[1]
        pan = pans.get(tr["name"], 0.0)
        lg, rg = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        gain = {"Chords": 0.55, "Bass": 0.8, "Drums": 1.0}.get(tr["name"], 0.9)
        for start, dur, pitch, vel in tr["notes"]:
            i0 = int(start * spb * RATE)
            if tr["channel"] == 9:
                sig = _drum(pitch, vel)
            else:
                n = int((dur * spb + 0.15) * RATE)
                sig = _voice(kind, _midi_hz(pitch), n, vel)
            i1 = min(total, i0 + len(sig))
            if i0 >= total:
                continue
            seg = sig[: i1 - i0] * gain
            left[i0:i1] += seg * lg
            right[i0:i1] += seg * rg
    peak = max(np.abs(left).max(), np.abs(right).max(), 1e-6)
    stereo = np.stack([left, right], axis=1) / peak * 0.89
    pcm = (stereo * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return path
