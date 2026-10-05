"""
SONG WRITER: Xbox dashboard "hanging orb" screen, light neon blue.

Top: wireframe orbs hang on vertical vine lines with glowing labels:
    GUIDED / FREEFORM / NEW SONG / COPY LYRICS / SAVE LYRICS
Below: two ways to write (pick with the orbs):
    A) Guided questions: length in bars, mood, genre, topic, clean/explicit,
       song structure and artist style. Compiled into one brief.
    B) Freeform chat: describe the song in plain words, then ask for
       revisions as many times as you like (multi-turn).
Both use the same Worker endpoint (/songwriter/chat), and the whole
conversation is sent each time so the songwriter remembers context.

REFERENCE-LAYOUT FLAG: built from the written description (Xbox hanging-orb
dashboard). Compare against your reference images.
"""
import math
import time
import tkinter as tk
from tkinter import filedialog

from ..config import output_dir
from ..theme import PANEL, TEXT, TEXT_DIM, dim
from ..widgets.controls import (GlowButton, Panel, Toggle, label, make_combo, make_entry, make_scale,
                                make_scrollbar, make_text)
from ..widgets.fx import glow_oval, glow_text, wire_sphere
from .base import BasePage

MOODS = ["Happy", "Sad", "Heartbroken", "Hopeful", "Angry", "Confident", "Romantic", "Nostalgic",
         "Dark", "Dreamy", "Hype", "Chill", "Empowering", "Bittersweet", "Mysterious"]
GENRES = ["Pop", "Hip Hop", "Trap", "Drill", "R&B", "Soul", "Afrobeats", "Reggaeton", "Rock", "Pop Punk",
          "Indie", "Country", "Gospel", "EDM", "House", "Lo-fi", "Jazz", "K-Pop", "Musical Theatre"]
STRUCTURES = [
    "Verse - Chorus - Verse - Chorus - Bridge - Chorus",
    "Intro - Verse - Pre-Chorus - Chorus - Verse - Pre-Chorus - Chorus - Bridge - Chorus - Outro",
    "Hook - Verse - Hook - Verse - Hook (rap)",
    "Intro - Verse - Hook - Verse - Hook - Bridge - Hook - Outro",
    "Verse - Verse - Bridge - Verse (AABA)",
    "Verse - Chorus - Verse - Chorus - Chorus (no bridge)",
]

ORBS = [("guided", "GUIDED"), ("freeform", "FREEFORM"), ("new", "NEW SONG"),
        ("copy", "COPY LYRICS"), ("save", "SAVE LYRICS")]
TAG = "orbs"


class SongWriterPage(BasePage):
    key = "song"
    role = "songwriter"
    reference_layout = "Xbox hanging-orb dashboard"

    # ---- build ------------------------------------------------------------------
    def build(self):
        app, acc, sp = self.app, self.accent, self.sp
        self.mode = "guided"
        self.messages = []        # full chat history sent to the Worker
        self.busy = False
        self.hover = None
        self.orb_hit = []
        self.t = 0.0
        self.flash = {}

        # --- guided form (left) ---
        self.form = Panel(self.canvas, acc, padx=sp(16), pady=sp(12))
        f = self.form
        label(f, app, "GUIDED QUESTIONS", font="h2", fg=acc).grid(row=0, column=0, columnspan=2, sticky="w",
                                                                    pady=(0, sp(8)))
        self.v_bars = tk.IntVar(value=64)
        self.v_mood = tk.StringVar(value="Confident")
        self.v_genre = tk.StringVar(value="Hip Hop")
        self.v_topic = tk.StringVar()
        self.v_structure = tk.StringVar(value=STRUCTURES[0])
        self.v_artist = tk.StringVar()
        self.v_notes = tk.StringVar()

        def row(r, text, widget):
            label(f, app, text, font="small", fg=TEXT_DIM).grid(row=r, column=0, sticky="w", pady=sp(3))
            widget.grid(row=r, column=1, sticky="we", pady=sp(3), padx=(sp(10), 0))

        row(1, "Length (bars)", make_scale(f, app, acc, self.v_bars, 8, 128, resolution=4, length=240))
        row(2, "Mood", make_combo(f, app, acc, "song", MOODS, self.v_mood, width=20, editable=True))
        row(3, "Genre", make_combo(f, app, acc, "song", GENRES, self.v_genre, width=20, editable=True))
        row(4, "Topic", make_entry(f, app, acc, self.v_topic, width=22))
        self.explicit = Toggle(f, app, "CLEAN", "EXPLICIT", False, accent=acc)
        row(5, "Content", self.explicit)
        row(6, "Structure", make_combo(f, app, acc, "song", STRUCTURES, self.v_structure, width=20, editable=True))
        row(7, "Artist style", make_entry(f, app, acc, self.v_artist, width=22))
        row(8, "Extra notes", make_entry(f, app, acc, self.v_notes, width=22))
        self.write_btn = GlowButton(f, app, "WRITE MY SONG", self.send_guided, accent=acc, primary=True, bg=PANEL)
        self.write_btn.grid(row=9, column=0, columnspan=2, sticky="we", pady=(sp(10), 0))
        f.columnconfigure(1, weight=1)

        # --- conversation (right) ---
        self.chat = Panel(self.canvas, acc, padx=sp(12), pady=sp(10))
        c = self.chat
        head = tk.Frame(c, bg=PANEL)
        head.pack(fill="x")
        self.chat_title = label(head, app, "SESSION", font="h2", fg=acc)
        self.chat_title.pack(side="left")
        self.status = label(head, app, "", font="mono", fg=TEXT_DIM)
        self.status.pack(side="right")
        # Second Clean/Explicit switch for freeform mode (the form is hidden
        # there). Both switches stay in sync.
        self.explicit_chat = Toggle(head, app, "CLEAN", "EXPLICIT", False, accent=acc,
                                    command=lambda v: self.explicit.set(v))
        self.explicit.command = lambda v: self.explicit_chat.set(v)

        body = tk.Frame(c, bg=PANEL)
        body.pack(fill="both", expand=True, pady=sp(6))
        self.text = make_text(body, app, acc, height=10, width=60)
        sb = make_scrollbar(body, acc, self.text.yview)
        self.text.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.tag_configure("user_h", foreground=acc, font=app.fonts["small"], spacing1=sp(10))
        self.text.tag_configure("user", foreground=self.accent2)
        self.text.tag_configure("ai_h", foreground="#ffffff", font=app.fonts["small"], spacing1=sp(10))
        self.text.tag_configure("ai", foreground=TEXT, lmargin1=sp(6), lmargin2=sp(6))
        self.text.tag_configure("info", foreground=TEXT_DIM, font=app.fonts["small"])
        self.text.tag_configure("error", foreground="#ff8080", font=app.fonts["small"])

        inp = tk.Frame(c, bg=PANEL)
        inp.pack(fill="x")
        # pack SEND first so it always keeps its full size; the text box takes the rest
        self.send_btn = GlowButton(inp, app, "SEND", self.send_freeform, accent=acc, primary=True, bg=PANEL)
        self.send_btn.pack(side="right", padx=(sp(8), 0))
        self.input = make_text(inp, app, acc, height=3, width=20)
        self.input.pack(side="left", fill="x", expand=True)
        self.input.bind("<Return>", self._enter_pressed)
        self.hint = label(c, app, "Enter = send · Shift+Enter = new line", font="small", fg=TEXT_DIM)
        self.hint.pack(anchor="w", pady=(sp(4), 0))

        self.form_id = self.win(self.form, 0, 0)
        self.chat_id = self.win(self.chat, 0, 0)
        self._intro()

        c2 = self.canvas
        c2.bind("<Motion>", self._motion)
        c2.bind("<Button-1>", self._click)

    def _intro(self):
        self._append("info", "Pick GUIDED to answer a few questions, or FREEFORM to just describe your song. "
                             "Then keep chatting to revise lines, swap hooks or change the vibe. "
                             "Artist styles are emulated, never copied: lyrics are always original.\n")

    # ---- page events ------------------------------------------------------------
    def on_show(self, mode=None, **kwargs):
        if mode in ("guided", "freeform"):
            self.set_mode(mode)

    def set_mode(self, mode):
        self.mode = mode
        self.flash[mode] = 1.0
        self.layout(*self._size)
        if mode == "freeform":
            self.input.focus_set()

    # ---- layout --------------------------------------------------------------------
    def layout(self, w, h):
        if w < 10:
            return
        sp = self.sp
        top = self._orb_band(h)
        margin = sp(24)
        dancer_w = max(160, min(250, h * 0.3)) + 40  # keep the dancer's corner clear
        bottom = h - margin
        if self.mode == "guided":
            self.canvas.itemconfigure(self.form_id, state="normal")
            fw = max(420, int(w * 0.33))
            self.canvas.coords(self.form_id, margin, top)
            self.canvas.itemconfigure(self.form_id, width=fw, height=bottom - top)
            cx = margin + fw + sp(18)
        else:
            self.canvas.itemconfigure(self.form_id, state="hidden")
            cx = margin
        if self.mode == "freeform":
            self.explicit_chat.pack(side="right", padx=self.sp(16))
        else:
            self.explicit_chat.pack_forget()
        self.canvas.coords(self.chat_id, cx, top)
        self.canvas.itemconfigure(self.chat_id, width=max(300, w - cx - dancer_w), height=bottom - top)
        self.chat_title.configure(text="GUIDED SESSION" if self.mode == "guided" else "FREEFORM CHAT")

    # ---- hanging orbs -------------------------------------------------------------------
    def _orb_band(self, h):
        """Height of the hanging-orb area at the top."""
        return max(190 * self.app.fonts.scale, h * 0.27)

    def animate(self, dt):
        c = self.canvas
        self.t += dt
        w, h = self._size
        if w < 10:
            return
        c.delete(TAG)
        self.orb_hit = []
        top = self._orb_band(h)
        n = len(ORBS)
        usable = w - 120
        s = self.app.fonts.scale
        for i, (oid, text) in enumerate(ORBS):
            selected = oid == self.mode
            hovering = self.hover == oid
            fl = self.flash.get(oid, 0.0)
            if fl > 0:
                self.flash[oid] = max(0.0, fl - dt * 2)
            base_x = 60 + usable * (i + 0.5) / n
            # alternate vine lengths, like the dashboard's staggered orbs
            hang = top * (0.42 + 0.14 * ((i % 2) * 1.0) + 0.04 * math.sin(i * 2.1))
            sway = math.sin(self.t * 0.9 + i * 1.3) * 6
            ox, oy = base_x + sway, hang + math.sin(self.t * 1.4 + i) * 3
            r = (34 + (8 if selected else 0) + (6 if hovering else 0) + 10 * fl) * s
            vine_col = dim(self.accent, 0.55 if (selected or hovering) else 0.3)
            # vine: a gentle curve from the top edge down to the orb, with nodes
            c.create_line(base_x, 0, base_x + sway * 0.3, oy * 0.5, ox, oy - r, fill=vine_col, width=2,
                          smooth=True, tags=TAG)
            for k in range(1, 4):
                vy = (oy - r) * k / 4
                vx = base_x + sway * (vy / max(1, oy)) * 0.8
                c.create_oval(vx - 2.5, vy - 2.5, vx + 2.5, vy + 2.5, fill=vine_col, outline="", tags=TAG)
            col = self.accent2 if (selected or hovering) else self.accent
            if selected or hovering:
                glow_oval(c, ox - r * 1.25, oy - r * 1.25, ox + r * 1.25, oy + r * 1.25, self.accent, tags=TAG,
                          layers=4, width=1, strength=0.9)
            wire_sphere(c, ox, oy, r, self.t * (0.8 if selected else 0.35) + i, col, tags=TAG, lat=4, lon=7,
                        bright=1.0 if (selected or hovering) else 0.65)
            ty = oy + r + 22 * s
            if selected or hovering:
                glow_text(c, ox, ty, text, self.app.fonts["h2"], self.accent2, tags=TAG)
            else:
                c.create_text(ox, ty, text=text, font=self.app.fonts["small"], fill=dim(TEXT, 0.65), tags=TAG)
            self.orb_hit.append((oid, ox - r * 1.3, oy - r * 1.3, ox + r * 1.3, ty + 16 * s))
        c.tag_raise(TAG, "starfield")
        if self.busy:
            dots = "." * (1 + int(self.t * 3) % 3)
            self.status.configure(text=f"✎ writing{dots:<3}")

    def _orb_at(self, x, y):
        for oid, x1, y1, x2, y2 in self.orb_hit:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return oid
        return None

    def _motion(self, e):
        self.hover = self._orb_at(e.x, e.y)
        self.canvas.configure(cursor="hand2" if self.hover else "")

    def _click(self, e):
        oid = self._orb_at(e.x, e.y)
        if not oid:
            return
        self.app.sound.play_select()
        self.flash[oid] = 1.0
        if oid in ("guided", "freeform"):
            self.set_mode(oid)
        elif oid == "new":
            self.new_song()
        elif oid == "copy":
            self.copy_lyrics()
        elif oid == "save":
            self.save_lyrics()

    # ---- transcript ---------------------------------------------------------------------
    def _append(self, kind, text):
        t = self.text
        t.configure(state="normal")
        if kind == "user":
            t.insert("end", "\nYOU\n", "user_h")
            t.insert("end", text.strip() + "\n", "user")
        elif kind == "ai":
            t.insert("end", "\nSONGWRITER\n", "ai_h")
            t.insert("end", text.strip() + "\n", "ai")
        else:
            t.insert("end", text, kind)
        t.configure(state="disabled")
        t.see("end")

    # ---- sending ------------------------------------------------------------------------
    def compile_brief(self):
        """Turn the guided answers into one clear brief for the songwriter."""
        explicit = self.explicit.get()
        lines = ["SONG BRIEF (from the guided questions)",
                 f"- Length: {self.v_bars.get()} bars total",
                 f"- Genre: {self.v_genre.get().strip() or 'your choice'}",
                 f"- Mood: {self.v_mood.get().strip() or 'your choice'}",
                 f"- Topic: {self.v_topic.get().strip() or 'your choice: surprise me'}",
                 f"- Structure: {self.v_structure.get().strip() or 'your choice'}",
                 f"- Content rating: {'Explicit' if explicit else 'Clean'}"]
        if self.v_artist.get().strip():
            lines.append(f"- Emulate the STYLE of: {self.v_artist.get().strip()} "
                         "(capture flow, themes and delivery; lyrics must be 100% original)")
        if self.v_notes.get().strip():
            lines.append(f"- Extra notes: {self.v_notes.get().strip()}")
        lines.append("Write the complete song now.")
        options = {
            "explicit": explicit, "bars": self.v_bars.get(), "genre": self.v_genre.get().strip(),
            "mood": self.v_mood.get().strip(), "topic": self.v_topic.get().strip(),
            "structure": self.v_structure.get().strip(), "artist_style": self.v_artist.get().strip(),
        }
        return "\n".join(lines), options

    def send_guided(self):
        if self.busy:
            return
        brief, options = self.compile_brief()
        if self.messages:
            self._append("info", "\n— New guided brief (starting a fresh song) —\n")
            self.messages = []
        self._send(brief, "guided", options)

    def send_freeform(self):
        if self.busy:
            return
        text = self.input.get("1.0", "end").strip()
        if not text:
            self.input.focus_set()
            return
        self.input.delete("1.0", "end")
        mode = "guided" if (self.mode == "guided" and self.messages) else "freeform"
        self._send(text, mode, {"explicit": self.explicit.get()})

    def _enter_pressed(self, e):
        if e.state & 0x0001:  # Shift held: normal new line
            return None
        self.send_freeform()
        return "break"

    def _send(self, text, mode, options):
        self.messages.append({"role": "user", "content": text})
        self._append("user", text)
        self._set_busy(True)
        history = list(self.messages)

        def done(reply):
            self._set_busy(False)
            self.messages.append({"role": "assistant", "content": reply})
            self._append("ai", reply)

        def fail(msg):
            self._set_busy(False)
            # Take the unanswered message back out so the conversation stays valid.
            if self.messages and self.messages[-1]["role"] == "user":
                last = self.messages.pop()["content"]
                if mode == "freeform" and not self.input.get("1.0", "end").strip():
                    self.input.insert("1.0", last)  # give their text back to retry
            self._append("error", f"\n⚠ {msg}\n")

        self.app.run_async(lambda: self.app.client.songwriter_chat(history, mode, options), done, fail)

    def _set_busy(self, busy):
        self.busy = busy
        self.write_btn.set_enabled(not busy)
        self.send_btn.set_enabled(not busy)
        if not busy:
            self.status.configure(text="")

    # ---- orb actions -------------------------------------------------------------------
    def new_song(self):
        if self.busy:
            return
        self.messages = []
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._intro()

    def _last_reply(self):
        for m in reversed(self.messages):
            if m["role"] == "assistant":
                return m["content"]
        return ""

    def copy_lyrics(self):
        reply = self._last_reply()
        if not reply:
            self._append("info", "\nNothing to copy yet: write a song first.\n")
            return
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(reply)
        self._append("info", "\n✓ Latest lyrics copied to the clipboard.\n")

    def save_lyrics(self):
        reply = self._last_reply()
        if not reply:
            self._append("info", "\nNothing to save yet: write a song first.\n")
            return
        folder = output_dir(self.app.cfg, "Song Writer")
        default = f"song_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        path = filedialog.asksaveasfilename(parent=self, initialdir=str(folder), initialfile=default,
                                            defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(reply + "\n")
        self._append("info", f"\n✓ Saved to {path}\n")
