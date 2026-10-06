# shmAI

A music-creation desktop app with a Tron / PS3 XMB / original-Xbox look:

| Page | What it does | Runs where |
|---|---|---|
| **Home** | The shmAI cast dancing in a line-up: click a character to open their page (neon cyan) | your computer |
| **Beat Finder** | Search + download from YouTube, SoundCloud, Bandcamp, Mixcloud, with thumbnails (Xbox green) | your computer |
| **Audio Analyzer + Key Finder** | Drag in a song: BPM, key, Camelot code, loudness, waveform (purple) | your computer |
| **Melody Generator** | Cloud MusicGen audio **or** local multi-instrument MIDI; drop in a song to make something similar (red-orange) | cloud *or* your computer |
| **Song Writer** | Guided questions or freeform chat with a pro-songwriter AI (light blue) | cloud |
| **Clarity** | Placeholder for the future in-DAW plugin | — |

The cloud features go through **your own Cloudflare Worker** (the `worker/`
folder). The secret API keys live only there; the desktop app just knows the
Worker's address and a shared App Token.

---

## 1. Back up your current version first

If you already have a shmAI folder on your computer, back it up before
copying this version in:

```
python3 scripts/backup.py "PATH/TO/YOUR/CURRENT/SHMAI" --label pre-vnext
```

This makes `backups/shmai_pre-vnext_<date-time>/`. To roll back, copy those
files back.

## 2. Install (one time)

You need **Python 3.9+** from https://python.org (on Windows, tick *"Add
Python to PATH"* in the installer). Then, in a terminal inside this folder:

```
python3 -m pip install -r requirements.txt
```

(On Windows, type `py` instead of `python3` if `python3` isn't found.)

**Recommended: ffmpeg.** It converts downloads to MP3 and lets the analyzer
open MP3/M4A/FLAC. Windows: `winget install ffmpeg` · Mac: `brew install ffmpeg`
· Linux: `sudo apt install ffmpeg`.

**Beat Finder sources: SoundScrape** (SoundCloud/Bandcamp/Mixcloud). It's an
older library that needs this exact install on modern Python:

```
python3 -m pip install --no-deps soundscrape soundcloud
python3 -m pip install demjson3 mutagen clint simplejson args
```

If you skip it, those sources still work through yt-dlp.

**Linux only:** `sudo apt install python3-tk` if you get "Tkinter is missing".

## 3. Run: just click the icon

**One time:** in the shmAI folder, double-click **Create Desktop Icon**:
- Windows: `Create Desktop Icon.pyw`
- Mac: `Create Desktop Icon.command` (a Terminal window opens just for this one-time step)
- Linux: run `python3 scripts/install_shortcut.py`

Tick what you want (Desktop icon, Start menu / Applications, open at login) and
click **Create icon**. From then on, **double-click the shmAI icon**: no terminal.
The very first launch installs any missing parts automatically (about a minute;
a small "Setting up" window shows). On Windows you can also double-click
`shmAI.pyw` directly. If shmAI ever closes unexpectedly, the details are in
`logs/shmai.log`.

(Terminal still works too: `python3 muse.py`.)

## 4. Connect the cloud features

1. Deploy the Worker: follow **`worker/README.md`** (about 10 minutes).
2. In shmAI click the **gear** (top-right) → paste your **Worker URL** and
   **App Token** → **Test Connection** → **Save**.

These are saved in `config.json` next to `muse.py` (git-ignored, see
`config.example.json`). Want to try the app without deploying anything?
Run `python3 scripts/mock_worker.py` and use Worker URL `http://127.0.0.1:8799`,
App Token `test-token`. That gives you fake lyrics and a test tone.

---

## Using it

- **Navigation:** click the tabs, or press **Ctrl+1 … Ctrl+6**. On Home, click
  a character (or use ◀ ▶ + Enter): the executive producer opens Beat Finder,
  the audio engineer the Analyzer, the producer the Melody Generator, the
  songwriter the Song Writer, the tech Clarity. **Ctrl+,** opens Settings.
- **Drag and drop:** drag audio files from Explorer / Finder straight onto the
  Audio Analyzer or the Melody Generator.
- **Text size & spacing:** Settings → *Display*. Changes apply right away.
- **Animations** (starfield, dancers, transitions) can be turned off in Settings.
- **Selection sound:** to keep your own sound, put your `.wav` at
  `assets/sounds/select.wav` or choose it in Settings → *Custom sound*.
- **Files** are saved to `Music/shmAI/<page name>/` in your home folder
  (change it in Settings).

### Song Writer
Pick an orb at the top:
- **GUIDED:** set length in bars, mood, genre, topic, clean/explicit,
  structure and an artist style to emulate, then **WRITE MY SONG**.
- **FREEFORM:** just describe the song. Keep chatting to revise ("make the
  hook shorter", "second verse angrier"). The full conversation is sent each
  time, so it remembers.
- **NEW SONG / COPY LYRICS / SAVE LYRICS** do what they say.

### Melody Generator
Click a category on the left (each shows its current value) and edit it in
the box under the orb.

**SIMILAR TO…**: drop a song onto the page (or click the drop box). shmAI
measures its tempo and key, copies them into BPM / KEY (switch off with the
toggle), and:
- **Cloud:** uploads a 30-second clip privately to your Worker and MusicGen
  writes a *new* instrumental that follows its melody and feel. The clip is
  deleted when the job finishes.
- **Local MIDI:** composes in the same tempo and key.

**COPY DRUMS**: switch it on and the dropped song's drum pattern is copied:
kicks, snares, hi-hats, open hats, 1/32 hi-hat rolls and swing, written onto a
step grid you can see. It looks for the song's **4-, 8- or 16-bar loop**
(Auto checks all three and notices regular fills / switch-ups), or you can
force a length.
- **Quick**: runs on your computer, free and instant-ish (a few seconds).
- **Accurate**: your Worker splits the drums out of the song first (Demucs on
  Replicate, a few cents, ~1 minute) for a cleaner copy.
- **KIT**: play the pattern with the built-in drums or pick a folder of your
  own samples (files named with kick / snare or clap / hat / open).
- **PREVIEW** plays the loop; **SAVE MIDI** exports it for your DAW.
- When you GENERATE: the MIDI engine uses the copied loop (and the bass follows
  its kicks); the Cloud engine asks MusicGen for no drums, then layers the
  copied loop on top in time (`…_with_drums.wav`) and saves the drum MIDI next to it.

Heads-up: re-playing a drum *pattern* is everyday producer practice; the sounds
are your kit, not the original recording. Open vs. closed hi-hats are the
least reliable part of the copy, so check those by ear.

**ENGINE** picks between:
- **Cloud (MusicGen):** real instrumental audio, up to 30 s. The orb shows
  progress; the file downloads and plays automatically.
- **Local MIDI:** instant and free. Makes a `.mid` (lead + chords + bass +
  drums, each with its own instrument under **LAYERS**) plus a preview `.wav`.

---

## Project layout

```
muse.py                  start here
config.example.json      settings template (real one: config.json)
shmai/app.py             window, nav bar, page switching, background tasks
shmai/theme.py           colors, fonts
shmai/config.py          settings file
shmai/worker_client.py   talks to the Worker (friendly error messages)
shmai/sound.py           selection blip + audio playback
shmai/pages/             one file per page
shmai/widgets/           starfield, dancing characters, glow buttons
shmai/engines/           downloader, analyzer, MIDI engine
shmai/clarity_bridge.py  stub for the future Clarity plugin link
worker/                  Cloudflare Worker (see worker/README.md)
scripts/backup.py        make a dated backup
scripts/mock_worker.py   fake Worker for offline testing
assets/fonts/            Orbitron, Rajdhani, Share Tech Mono (SIL Open Font License)
```

### Hooks for later stages
- Every Worker request carries `user_id` (made once per install, in
  `config.json`) and an empty `settings` object, ready for memory and
  personalization.
- `shmai/clarity_bridge.py` + the Clarity tab are the plug points for the
  in-DAW plugin.
- The Melody Generator's ENGINE list is where a future ACE-Step engine would go.
