"""
MELODY GENERATOR: Xbox "Network Settings" layout, fiery red-orange.

    Left:  honeycomb-edged menu list. Every category is a real input and
           shows its current value right in the list.
    Right: a big glowing orb that shows the engine status, with a
           detail/info box under it where you edit the selected category.

Two engines:
    Cloud (MusicGen)  -> your Cloudflare Worker -> Replicate MusicGen.
                         Instrumental audio. The app polls the job, downloads
                         the file, and plays it.
    Local MIDI        -> the built-in multi-instrument MIDI engine (lead +
                         chords + bass + drums). Saves a .mid for your DAW and
                         a quick preview .wav.

REFERENCE-LAYOUT FLAG: built from the written description (Xbox Network
Settings screen). Compare against your reference images.
"""
import math
import shutil
import time
import tkinter as tk
from tkinter import filedialog

from ..config import output_dir
from .. import dnd
from ..engines import midi_engine as me
from ..engines import reference as ref_engine
from ..sound import open_folder
from ..theme import BG, PANEL, TEXT, TEXT_DIM, blend, dim
from ..widgets.controls import GlowButton, Panel, Toggle, label, make_combo, make_entry, make_scale
from ..widgets.dropzone import DropZone
from ..widgets.fx import glow_polygon, glow_text, hex_pill_points, hexagon_points
from .base import BasePage

ENGINES = ["Cloud (MusicGen)", "Local MIDI"]
POLL_SECONDS = 3
POLL_TIMEOUT = 6 * 60

# (id, menu label, editor type, help text)
MENU = [
    ("engine", "ENGINE", "choice", "Cloud makes real instrumental audio with MusicGen (needs your Worker). "
                                   "Local MIDI composes notes on your computer: free, instant, DAW-ready."),
    ("similar", "SIMILAR TO…", "drop", "Drop a song here and the generator makes a NEW instrumental like it. "
                                      "Cloud follows its melody and feel; tempo & key are matched for both engines."),
    ("instrument", "INSTRUMENT", "choice", "The lead instrument that carries the melody."),
    ("layers", "LAYERS", "layers", "Add backing parts. Each layer can use its own instrument "
                                   "(multi-instrument)."),
    ("genre", "GENRE", "choice", "Sets the groove, drum pattern and chord style."),
    ("style", "STYLE NOTES", "text", "Free text: e.g. 'dusty vinyl, sidechained pads, staccato strings'."),
    ("key", "KEY", "choice", "Musical key. Auto picks one that fits the mood."),
    ("mood", "MOOD", "choice", "The emotion of the piece: picks major/minor and energy."),
    ("bpm", "BPM", "number", "Tempo in beats per minute."),
    ("duration", "DURATION", "seconds", "Length of the clip. Cloud clips max out at 30 seconds."),
    ("reference", "REFERENCE VIBE", "text", "Describe a vibe or reference: 'late-night drive', '90s video game "
                                            "menu', 'sunrise on a beach'."),
    ("prompt", "EXTRA PROMPT", "text", "Anything else for the AI (cloud engine)."),
]


class MelodyGeneratorPage(BasePage):
    key = "melody"
    role = "producer"
    reference_layout = "Xbox Network Settings"

    def build(self):
        app, acc, sp = self.app, self.accent, self.sp
        self.t = 0.0
        self.sel = 0
        self.hover = None
        self.menu_hit = []
        self.state = "idle"          # idle | working | done | error
        self.state_text = "READY"
        self.progress = 0.0
        self.job = None              # active cloud job info
        self.last_audio = None       # path of the latest audio file
        self.last_midi = None
        self.flash = 0.0
        self.ref = None              # prepared reference song (see engines/reference.py)
        self.ref_busy = False
        self.match_ref = True        # copy the reference's tempo & key into BPM / KEY

        self.v = {
            "engine": tk.StringVar(value=ENGINES[0]),
            "instrument": tk.StringVar(value="Grand Piano"),
            "genre": tk.StringVar(value="Hip Hop"),
            "style": tk.StringVar(),
            "key": tk.StringVar(value="Auto"),
            "mood": tk.StringVar(value="Chill"),
            "bpm": tk.IntVar(value=90),
            "duration": tk.IntVar(value=15),
            "reference": tk.StringVar(),
            "prompt": tk.StringVar(),
            "chord_instrument": tk.StringVar(value="Synth Pad"),
            "bass_instrument": tk.StringVar(value="Synth Bass / 808"),
        }
        self.layer_on = {"chords": True, "bass": True, "drums": True}

        # ---- detail / info box (under the orb) ----
        self.info = Panel(self.canvas, acc, padx=sp(16), pady=sp(12))
        self.info_title = label(self.info, app, "", font="h2", fg=acc)
        self.info_title.pack(anchor="w")
        self.info_help = label(self.info, app, "", font="small", fg=TEXT_DIM, justify="left", wraplength=560)
        self.info_help.pack(anchor="w", pady=(sp(2), sp(8)))
        self.editor_host = tk.Frame(self.info, bg=PANEL)
        self.editor_host.pack(fill="x")
        self.editors = {mid: self._make_editor(mid, kind) for mid, _l, kind, _h in MENU}
        tk.Frame(self.info, bg=dim(acc, 0.5), height=2).pack(fill="x", pady=sp(10))
        label(self.info, app, "WHAT WILL BE GENERATED", font="small", fg=acc).pack(anchor="w")
        self.summary = label(self.info, app, "", font="small", fg=TEXT, justify="left", wraplength=560)
        self.summary.pack(anchor="w", pady=(sp(2), 0))

        # ---- action buttons ----
        self.actions = tk.Frame(self.canvas, bg=BG)
        self.gen_btn = GlowButton(self.actions, app, "GENERATE", self.generate, accent=acc, primary=True)
        self.gen_btn.pack(side="left")
        self.play_btn = GlowButton(self.actions, app, "PLAY", self.play, accent=acc)
        self.play_btn.pack(side="left", padx=sp(8))
        GlowButton(self.actions, app, "STOP", self.app.sound.stop, accent=acc).pack(side="left")
        self.save_btn = GlowButton(self.actions, app, "SAVE AS", self.save_as, accent=acc)
        self.save_btn.pack(side="left", padx=sp(8))
        GlowButton(self.actions, app, "FOLDER", lambda: open_folder(output_dir(self.app.cfg, "Melody Generator")),
                   accent=acc).pack(side="left")

        self.info_id = self.win(self.info, 0, 0)
        self.actions_id = self.win(self.actions, 0, 0)

        for var in self.v.values():
            var.trace_add("write", lambda *a: self._refresh_summary())
        c = self.canvas
        c.bind("<Motion>", self._motion)
        c.bind("<Button-1>", self._click)
        c.bind("<Up>", lambda e: self._select(self.sel - 1))
        c.bind("<Down>", lambda e: self._select(self.sel + 1))
        # Dropping a song anywhere on this page also works.
        dnd.enable_drop(c, self._page_drop)
        self._select(0, sound=False)
        self._refresh_summary()
        self._update_buttons()

    # ---- editors (one per menu item) -----------------------------------------------
    def _make_editor(self, mid, kind):
        app, acc = self.app, self.accent
        f = tk.Frame(self.editor_host, bg=PANEL)
        if mid == "engine":
            for name in ENGINES:
                tk.Radiobutton(f, text=name, value=name, variable=self.v["engine"], font=app.fonts["body"],
                               bg=PANEL, fg=TEXT, selectcolor=blend(PANEL, acc, 0.4), activebackground=PANEL,
                               activeforeground=acc, highlightthickness=0,
                               command=self.app.sound.play_select).pack(anchor="w")
        elif mid == "instrument":
            make_combo(f, app, acc, "melody", me.LEAD_INSTRUMENTS, self.v["instrument"], width=28).pack(anchor="w")
        elif mid == "genre":
            make_combo(f, app, acc, "melody", me.GENRES, self.v["genre"], width=28, editable=True).pack(anchor="w")
        elif mid == "key":
            make_combo(f, app, acc, "melody", me.KEYS, self.v["key"], width=28).pack(anchor="w")
        elif mid == "mood":
            make_combo(f, app, acc, "melody", me.MOODS, self.v["mood"], width=28, editable=True).pack(anchor="w")
        elif mid == "bpm":
            row = tk.Frame(f, bg=PANEL)
            row.pack(anchor="w")
            make_scale(row, app, acc, self.v["bpm"], 60, 200, resolution=1, length=360).pack(side="left")
            e = make_entry(row, app, acc, self.v["bpm"], width=5, font="mono")
            e.pack(side="left", padx=self.sp(8))
        elif mid == "duration":
            make_scale(f, app, acc, self.v["duration"], 5, 30, resolution=1, length=360,
                       fmt=lambda v: f"{int(v)} sec").pack(anchor="w")
        elif mid == "similar":
            self.dropzone = DropZone(f, app, acc, self.accent2, self.load_reference, title="DROP A SONG HERE",
                                     height=int(110 * app.fonts.scale))
            self.dropzone.pack(fill="x")
            row = tk.Frame(f, bg=PANEL)
            row.pack(fill="x", pady=(self.sp(8), 0))
            Toggle(row, app, "Keep my BPM / key", "Match its tempo & key", True, accent=acc,
                   command=self._set_match).pack(side="left")
            GlowButton(row, app, "CLEAR", self.clear_reference, accent=acc, bg=PANEL).pack(side="right")
        elif mid == "layers":
            for layer, var, choices in (("chords", self.v["chord_instrument"], me.CHORD_INSTRUMENTS),
                                        ("bass", self.v["bass_instrument"], me.BASS_INSTRUMENTS),
                                        ("drums", None, None)):
                row = tk.Frame(f, bg=PANEL)
                row.pack(anchor="w", pady=self.sp(3), fill="x")
                Toggle(row, app, f"{layer.upper():<7}", "ON", self.layer_on[layer], accent=acc,
                       command=lambda v, n=layer: self._set_layer(n, v)).pack(side="left")
                if var is not None:
                    make_combo(row, app, acc, "melody", choices, var, width=20).pack(side="left", padx=self.sp(10))
        else:  # free text
            e = make_entry(f, app, acc, self.v[mid], width=44)
            e.pack(anchor="w", fill="x")
        return f

    def _set_layer(self, name, value):
        self.layer_on[name] = value
        self._refresh_summary()

    # ---- selection ------------------------------------------------------------------
    def _select(self, idx, sound=True):
        idx = max(0, min(len(MENU) - 1, idx))
        if sound and idx != self.sel:
            self.app.sound.play_select()
        self.sel = idx
        mid, text, kind, help_text = MENU[idx]
        for ed in self.editors.values():
            ed.pack_forget()
        self.editors[mid].pack(anchor="w", fill="x")
        self.info_title.configure(text=text)
        self.info_help.configure(text=help_text)
        self.flash = 1.0

    def on_show(self, engine=None, **kwargs):
        if engine in ENGINES:
            self.v["engine"].set(engine)
        self.canvas.focus_set()

    # ---- values -----------------------------------------------------------------------
    def _value_text(self, mid):
        if mid == "similar":
            return "analyzing…" if self.ref_busy else (self.ref["name"] if self.ref else "—")
        if mid == "layers":
            on = [n.title() for n, v in self.layer_on.items() if v]
            return " + ".join(on) if on else "Lead only"
        if mid == "duration":
            return f"{self._get_int('duration', 15)} sec"
        if mid == "bpm":
            return str(self._get_int("bpm", 90))
        val = str(self.v[mid].get()).strip()
        return val if val else "—"

    def _get_int(self, name, default):
        try:
            return int(self.v[name].get())
        except (tk.TclError, ValueError):
            return default

    def collect(self):
        """All current selections as one dict (what gets generated)."""
        layers = dict(self.layer_on)
        instruments = [self.v["instrument"].get()]
        if layers["chords"]:
            instruments.append(self.v["chord_instrument"].get())
        if layers["bass"]:
            instruments.append(self.v["bass_instrument"].get())
        if layers["drums"]:
            instruments.append("drums")
        bpm = max(40, min(240, self._get_int("bpm", 90)))
        return {
            "engine": self.v["engine"].get(),
            "instrument": self.v["instrument"].get(),
            "instruments": instruments,
            "layers": layers,
            "chord_instrument": self.v["chord_instrument"].get(),
            "bass_instrument": self.v["bass_instrument"].get(),
            "genre": self.v["genre"].get().strip(),
            "style": self.v["style"].get().strip(),
            "key": self.v["key"].get(),
            "mood": self.v["mood"].get().strip(),
            "bpm": bpm,
            "duration": max(5, min(30, self._get_int("duration", 15))),
            "reference": self.v["reference"].get().strip(),
            "prompt": self.v["prompt"].get().strip(),
            "similar": self.ref,
        }

    def _refresh_summary(self):
        s = self.collect()
        parts = [f"{s['engine']}", f"{s['genre']} · {s['mood']}", ", ".join(s["instruments"]),
                 f"{s['bpm']} BPM · key {s['key']} · {s['duration']} sec"]
        extra = [x for x in (s["style"], s["reference"], s["prompt"]) if x]
        if extra:
            parts.append(" / ".join(extra))
        if s["similar"]:
            how = "follows its melody" if s["engine"] != "Local MIDI" else "matches its tempo & key"
            parts.append(f"Similar to: {s['similar']['name']} ({how})")
        self.summary.configure(text="\n".join(parts))

    # ---- "similar to" reference song -----------------------------------------------------
    def _page_drop(self, paths):
        files = dnd.audio_files(paths)
        if files:
            self._select(self._menu_index("similar"))
            self.app.sound.play_select()
            self.load_reference(files[0])

    def _menu_index(self, mid):
        return next(i for i, m in enumerate(MENU) if m[0] == mid)

    def load_reference(self, path):
        """Analyze the dropped song (tempo, key) and cut a 30 s clip to upload."""
        if self.ref_busy:
            return
        self.ref_busy = True
        self.dropzone.set_busy(f"Listening to {path.name} …")

        def done(ref):
            self.ref_busy = False
            self.ref = ref
            info = " · ".join(x for x in (f"≈ {ref['bpm']} BPM" if ref.get("bpm") else "", ref.get("key") or "",
                                          ref.get("camelot") or "") if x)
            self.dropzone.set_loaded(ref["name"], info)
            if self.match_ref:
                self._apply_reference()
            self._refresh_summary()

        def fail(msg):
            self.ref_busy = False
            self.dropzone.set_message(msg.splitlines()[0])

        self.app.run_async(lambda: ref_engine.prepare(path), done, fail)

    def _apply_reference(self):
        """Copy the reference's tempo & key into the BPM and KEY settings."""
        if not self.ref:
            return
        if self.ref.get("bpm"):
            self.v["bpm"].set(max(60, min(200, self.ref["bpm"])))
        if self.ref.get("key") in me.KEYS:
            self.v["key"].set(self.ref["key"])

    def _set_match(self, value):
        self.match_ref = value
        if value:
            self._apply_reference()

    def clear_reference(self):
        self.ref = None
        self.dropzone.clear()
        self._refresh_summary()

    # ---- layout + drawing ----------------------------------------------------------------
    def _menu_geometry(self, w, h):
        s = self.app.fonts.scale
        x1 = 30
        x2 = x1 + max(380, 400 * s)
        item_h = max(44, min(62, (h - 60) / (len(MENU) + 0.6)))
        top = 36
        return x1, x2, top, item_h

    def _orb_geometry(self, w, h):
        _x1, mx2, _t, _ih = self._menu_geometry(w, h)
        right_w = w - mx2
        cx = mx2 + right_w * 0.45
        r = min(h * 0.14, right_w * 0.18)
        cy = 30 + r * 1.35
        return cx, cy, r

    def layout(self, w, h):
        if w < 10:
            return
        _x1, mx2, _t, _ih = self._menu_geometry(w, h)
        cx, cy, r = self._orb_geometry(w, h)
        dancer_w = max(160, min(250, h * 0.3)) + 30
        left = mx2 + 40
        width = max(380, w - left - dancer_w)
        # buttons sit right under the orb; the detail box hangs below them
        # and can grow downward without covering anything.
        actions_y = cy + r * 1.5
        self.canvas.coords(self.actions_id, left, actions_y)
        self.canvas.itemconfigure(self.actions_id, anchor="nw")
        top = actions_y + self.gen_btn.winfo_reqheight() + self.sp(14)
        self.canvas.coords(self.info_id, left, top)
        self.canvas.itemconfigure(self.info_id, width=width)
        wrap = max(300, width - 50)
        self.info_help.configure(wraplength=wrap)
        self.summary.configure(wraplength=wrap)

    def animate(self, dt):
        c = self.canvas
        self.t += dt
        self.flash = max(0.0, self.flash - dt * 3)
        w, h = self._size
        if w < 10:
            return
        c.delete("mg")
        self._draw_menu(c, w, h)
        self._draw_orb(c, w, h)
        c.tag_raise("mg", "starfield")

    def _draw_menu(self, c, w, h):
        x1, x2, top, ih = self._menu_geometry(w, h)
        self.menu_hit = []
        for i, (mid, text, _k, _h) in enumerate(MENU):
            y1 = top + i * ih
            y2 = y1 + ih - 8
            selected = i == self.sel
            hovering = self.hover == i
            grow = (6 if hovering else 0) + (4 if selected else 0)
            pts = hex_pill_points(x1 - grow, y1 - grow / 3, x2 + grow, y2 + grow / 3, cut=(y2 - y1) * 0.45)
            if selected or hovering:
                glow_polygon(c, pts, self.accent, tags="mg", layers=3, width=2,
                             fill=blend(BG, self.accent, 0.22 if selected else 0.1), strength=0.9)
            else:
                c.create_polygon(pts, outline=dim(self.accent, 0.45), fill=blend(BG, self.accent, 0.05), width=2,
                                 tags="mg")
            # honeycomb cell marker at the left edge
            hx = x1 + (y2 - y1) * 0.6
            hy = (y1 + y2) / 2
            size = (y2 - y1) * 0.22
            c.create_polygon(hexagon_points(hx, hy, size), outline=self.accent2 if selected else dim(self.accent, 0.6),
                             fill=self.accent if selected else "", width=2, tags="mg")
            f = self.app.fonts["button_hover" if (selected or hovering) else "button"]
            c.create_text(hx + size + 16, hy, text=text, anchor="w", font=f,
                          fill="#ffffff" if (selected or hovering) else dim(TEXT, 0.75), tags="mg")
            val = self._value_text(mid)
            if len(val) > 22:
                val = val[:21] + "…"
            c.create_text(x2 - (y2 - y1) * 0.5, hy, text=val, anchor="e", font=self.app.fonts["small"],
                          fill=self.accent2 if selected else dim(self.accent2, 0.7), tags="mg")
            self.menu_hit.append((i, x1, y1, x2, y2))

    def _draw_orb(self, c, w, h):
        cx, cy, r = self._orb_geometry(w, h)
        acc, acc2 = self.accent, self.accent2
        working = self.state == "working"
        pulse = 0.5 + 0.5 * math.sin(self.t * (5 if working else 1.6))
        # outer glow halo
        for i in range(7, 0, -1):
            rr = r * (1 + i * 0.07)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=dim(acc, 0.03 + 0.025 * (7 - i) * (0.7 + 0.3 * pulse)),
                          outline="", tags="mg")
        # body: layered circles from dark edge to hot core (fake gradient)
        for i in range(10):
            rr = r * (1 - i * 0.085)
            col = blend(blend(BG, acc, 0.45), blend(acc2, "#ffffff", 0.35), (i / 9) ** 1.6)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=col, outline="", tags="mg")
        # rotating rings
        spin = self.t * (3.0 if working else 0.6)
        for k in range(3):
            rr = r * (1.12 + k * 0.1)
            start = math.degrees(spin * (1 if k % 2 == 0 else -1.3)) + k * 60
            c.create_arc(cx - rr, cy - rr * 0.98, cx + rr, cy + rr * 0.98, start=start, extent=100 + 40 * k,
                         style="arc", outline=dim(acc2, 0.9 - 0.2 * k), width=3 - (k == 2), tags="mg")
        # progress arc while working
        if working:
            rr = r * 1.48
            c.create_arc(cx - rr, cy - rr, cx + rr, cy + rr, start=90, extent=-359.9 * self.progress,
                         style="arc", outline=acc2, width=5, tags="mg")
        if self.state == "done" or self.flash > 0:
            fl = self.flash if self.state != "done" else max(self.flash, 0.4 * pulse)
            rr = r * (1.0 + 0.25 * fl)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=blend(acc2, "#ffffff", 0.5), width=2,
                          tags="mg")
        color = "#fff2e0" if self.state != "error" else "#ffe0e0"
        glow_text(c, cx, cy, self.state_text, self.app.fonts["h2"], color, tags="mg")
        if working and self.job:
            elapsed = int(time.time() - self.job.get("started", time.time()))
            c.create_text(cx, cy + r * 0.38, text=f"{elapsed}s", font=self.app.fonts["mono"], fill="#2a0c00",
                          tags="mg")

    # ---- mouse --------------------------------------------------------------------------
    def _menu_at(self, x, y):
        for i, x1, y1, x2, y2 in self.menu_hit:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def _motion(self, e):
        self.hover = self._menu_at(e.x, e.y)
        self.canvas.configure(cursor="hand2" if self.hover is not None else "")

    def _click(self, e):
        i = self._menu_at(e.x, e.y)
        self.canvas.focus_set()
        if i is not None:
            self._select(i)

    # ---- status helpers ------------------------------------------------------------------
    def _set_state(self, state, text, progress=None):
        self.state = state
        self.state_text = text
        if progress is not None:
            self.progress = progress
        self._update_buttons()

    def _update_buttons(self):
        busy = self.state == "working"
        self.gen_btn.set_enabled(not busy)
        self.play_btn.set_enabled(bool(self.last_audio) and not busy)
        self.save_btn.set_enabled(bool(self.last_audio or self.last_midi) and not busy)

    def _error(self, msg):
        self.job = None
        self._set_state("error", "ERROR")
        self.info_title.configure(text="SOMETHING WENT WRONG")
        self.info_help.configure(text=msg)

    # ---- generate --------------------------------------------------------------------------
    def generate(self):
        if self.state == "working":
            return
        s = self.collect()
        stamp = time.strftime("%Y%m%d_%H%M%S")
        folder = output_dir(self.app.cfg, "Melody Generator")
        self._select(self.sel, sound=False)  # restore normal help text after an error
        if s["engine"] == "Local MIDI":
            self._generate_midi(s, folder, stamp)
        else:
            self._generate_cloud(s, folder, stamp)

    def _generate_midi(self, s, folder, stamp):
        self._set_state("working", "COMPOSING", 0.3)
        self.job = {"started": time.time()}

        def work():
            song = me.compose(s)
            base = folder / f"melody_{stamp}_{s['genre'].replace(' ', '')}_{song.key_name.replace(' ', '')}"
            mid = me.write_midi(song, base.with_suffix(".mid"))
            wav = me.render_wav(song, base.with_suffix(".wav"))
            return song, mid, wav

        def done(result):
            song, mid, wav = result
            self.job = None
            self.last_midi = mid
            self.last_audio = wav
            self._set_state("done", "DONE", 1.0)
            self.flash = 1.0
            note = f"MIDI saved: {mid.name}  ({song.bars} bars, {song.key_name}, {song.bpm} BPM)"
            if wav is None:
                note += "\nInstall numpy for an instant audio preview (pip install numpy)."
            self.info_help.configure(text=note)
            if wav:
                self.play()

        self.app.run_async(work, done, self._error)

    def _generate_cloud(self, s, folder, stamp):
        params = {
            "prompt": s["prompt"], "instrument": s["instruments"], "genre": s["genre"], "style": s["style"],
            "mood": s["mood"], "bpm": s["bpm"], "duration": s["duration"], "reference": s["reference"],
            "format": "wav",
        }
        if s["key"] != "Auto":
            params["key"] = s["key"]
        self.job = {"started": time.time(), "folder": folder, "stamp": stamp}
        if s["similar"]:
            # 1) upload the 30 s clip, 2) generate following it
            self._set_state("working", "UPLOADING", 0.03)
            clip = s["similar"]["clip"]

            def uploaded(ref_id):
                params["reference_id"] = ref_id
                self._start_cloud(params)

            self.app.run_async(lambda: self.app.client.upload_reference(clip), uploaded, self._error)
            return
        self._start_cloud(params)

    def _start_cloud(self, params):
        self._set_state("working", "SENDING", 0.05)

        def started(data):
            self.job.update(id=data["id"])
            self._set_state("working", "GENERATING", 0.12)
            self.info_help.configure(text=f"MusicGen prompt: {data.get('prompt', '')}")
            self.app.root.after(POLL_SECONDS * 1000, self._poll)

        self.app.run_async(lambda: self.app.client.melody_generate(params), started, self._error)

    def _poll(self):
        job = self.job
        if not job or "id" not in job:
            return
        if time.time() - job["started"] > POLL_TIMEOUT:
            self._error("Generation is taking unusually long. Try again in a few minutes.")
            return

        def got(data):
            if self.job is not job:
                return
            status = data.get("status")
            if status == "succeeded" and data.get("audioKey"):
                self._download(data["audioKey"])
            elif status in ("failed", "canceled"):
                self._error(data.get("error") or "MusicGen couldn't finish this one. Try again.")
            else:
                # fake-but-honest progress: creeps toward 90% while we wait
                elapsed = time.time() - job["started"]
                self._set_state("working", "GENERATING" if status == "processing" else "STARTING",
                                min(0.9, 0.12 + elapsed / 120))
                self.app.root.after(POLL_SECONDS * 1000, self._poll)

        self.app.run_async(lambda: self.app.client.melody_status(job["id"]), got, self._error)

    def _download(self, key):
        job = self.job
        ext = key.rsplit(".", 1)[-1]
        dest = job["folder"] / f"melody_{job['stamp']}_{self.v['genre'].get().replace(' ', '')}.{ext}"
        self._set_state("working", "DOWNLOADING", 0.92)

        def work():
            path = self.app.client.download_audio(
                key, dest, progress=lambda p: self.app.call_soon(self._set_progress, 0.92 + 0.08 * p))
            try:
                self.app.client.delete_audio(key)  # tidy up R2: the file is on your computer now
            except Exception:
                pass
            return path

        def done(path):
            self.job = None
            self.last_audio = path
            self.last_midi = None
            self._set_state("done", "DONE", 1.0)
            self.flash = 1.0
            self.info_help.configure(text=f"Saved: {path}")
            self.play()

        self.app.run_async(work, done, self._error)

    def _set_progress(self, p):
        self.progress = p

    # ---- play / save -----------------------------------------------------------------------
    def play(self):
        if not self.last_audio:
            return
        how = self.app.sound.play_file(self.last_audio)
        if how == "external":
            self.info_help.configure(text=f"Opened in your music player: {self.last_audio}")
        elif how == "failed":
            self.info_help.configure(text=f"Couldn't play audio here (install pygame). File saved at: "
                                          f"{self.last_audio}")

    def save_as(self):
        src = self.last_midi or self.last_audio
        if not src:
            return
        types = [("MIDI", "*.mid")] if src.suffix == ".mid" else [("Audio", f"*{src.suffix}")]
        if self.last_midi and self.last_audio:
            types.append(("Preview audio", "*.wav"))
        dest = filedialog.asksaveasfilename(parent=self, initialfile=src.name, defaultextension=src.suffix,
                                            filetypes=types)
        if not dest:
            return
        source = self.last_audio if (dest.lower().endswith(".wav") and self.last_audio) else src
        shutil.copyfile(source, dest)
        self.info_help.configure(text=f"Saved a copy to {dest}")
