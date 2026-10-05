"""
AUDIO ANALYZER (with KEY FINDER), neon purple-lavender.

Two views, switched with the pills at the top:
    ANALYZE     waveform + stat cards (BPM, key, length, loudness)
    KEY FINDER  Xbox "memory unit" screen: a big circular holographic
                wireframe with the detected key inside, a circle-of-fifths
                ring around it, and four controller-port blocks along the
                bottom (your loaded track sits in PORT 1, SLOT A).

Runs 100% locally (numpy; ffmpeg for MP3/M4A). Functionality is the same
as before: load a track, get its BPM and key.

Blank-screen fix: everything on this page is drawn on the canvas every
frame, with a clear "no track loaded" state, so the Key Finder can never
show an empty screen, even before analysis or with animations turned off.

REFERENCE-LAYOUT FLAG: Key Finder is built from the written description
(Xbox memory-unit screen). Compare against your reference images.
"""
import math
import tkinter as tk
from tkinter import filedialog

from ..engines import analyzer as an
from ..theme import BG, TEXT, TEXT_DIM, blend, dim
from ..widgets.controls import GlowButton, label
from ..widgets.fx import glow_text, rounded_rect_points, wire_sphere
from .base import BasePage

FIFTHS = [0, 7, 2, 9, 4, 11, 6, 1, 8, 3, 10, 5]  # circle of fifths (pitch classes)
TAG = "an"


class AudioAnalyzerPage(BasePage):
    key = "analyzer"
    role = "engineer"
    reference_layout = "Xbox memory-unit screen (Key Finder)"

    def build(self):
        app, acc, sp = self.app, self.accent, self.sp
        self.view = "analyze"
        self.result = None
        self.path = None
        self.busy = False
        self.error = ""
        self.t = 0.0
        self.reveal = 0.0  # 0 -> 1 animation after a new result

        self.top = tk.Frame(self.canvas, bg=BG)
        self.btn_analyze_view = GlowButton(self.top, app, "ANALYZE", lambda: self.set_view("analyze"), accent=acc)
        self.btn_analyze_view.pack(side="left")
        self.btn_key_view = GlowButton(self.top, app, "KEY FINDER", lambda: self.set_view("key"), accent=acc)
        self.btn_key_view.pack(side="left", padx=(sp(8), sp(30)))
        GlowButton(self.top, app, "LOAD TRACK", self.load, accent=acc, primary=True).pack(side="left")
        self.run_btn = GlowButton(self.top, app, "RE-ANALYZE", self.run_analysis, accent=acc)
        self.run_btn.pack(side="left", padx=sp(8))
        self.file_lbl = label(self.top, app, "No track loaded", font="small", fg=TEXT_DIM, bg=BG)
        self.file_lbl.pack(side="left", padx=sp(14))
        self.top_id = self.win(self.top, sp(28), sp(22))
        self._update_view_buttons()
        self.run_btn.set_enabled(False)

    # ---- page events -----------------------------------------------------------------
    def on_show(self, view=None, **kwargs):
        if view == "key":
            self.set_view("key")
        elif view == "analyze":
            self.set_view("analyze")
        self.draw()  # always paint something immediately (blank-screen guard)

    def set_view(self, view):
        self.view = view
        self._update_view_buttons()
        self.draw()

    def _update_view_buttons(self):
        self.btn_analyze_view.primary = self.view == "analyze"
        self.btn_key_view.primary = self.view == "key"
        self.btn_analyze_view._draw()
        self.btn_key_view._draw()

    def layout(self, w, h):
        self.draw()

    # ---- loading / analysis ----------------------------------------------------------------
    def load(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a track to analyze", filetypes=[
            ("Audio", "*.wav *.mp3 *.m4a *.flac *.ogg *.aiff *.aif"), ("All files", "*.*")])
        if path:
            self.path = path
            self.run_analysis()

    def run_analysis(self):
        if self.busy or not self.path:
            return
        self.busy = True
        self.error = ""
        self.run_btn.set_enabled(False)
        self.file_lbl.configure(text=f"Analyzing {self.path.split('/')[-1].split(chr(92))[-1]} ...", fg=TEXT)
        path = self.path

        def done(result):
            self.busy = False
            self.result = result
            self.reveal = 0.0
            self.run_btn.set_enabled(True)
            self.file_lbl.configure(text=result["name"], fg=self.accent2)
            self.draw()

        def fail(msg):
            self.busy = False
            self.error = msg
            self.run_btn.set_enabled(True)
            self.file_lbl.configure(text="Couldn't analyze that file", fg="#ff8080")
            self.draw()

        self.app.run_async(lambda: an.analyze(path), done, fail)

    # ---- drawing ------------------------------------------------------------------------------
    def animate(self, dt):
        self.t += dt
        self.reveal = min(1.0, self.reveal + dt * 1.6)
        self.draw()

    def draw(self):
        c = self.canvas
        w, h = self._size
        if w < 10 or h < 10:
            return
        c.delete(TAG)
        if self.view == "key":
            self._draw_key_finder(c, w, h)
        else:
            self._draw_analyze(c, w, h)
        c.tag_raise(TAG, "starfield")

    def _content_top(self):
        return self.sp(22) + self.top.winfo_reqheight() + self.sp(24)

    # ---- ANALYZE view -------------------------------------------------------------------------
    def _draw_analyze(self, c, w, h):
        acc, acc2 = self.accent, self.accent2
        f = self.app.fonts
        m = self.sp(28)
        dancer_w = max(160, min(250, h * 0.3)) + 30
        top = self._content_top()
        x1, x2 = m, w - m
        wy1, wy2 = top, top + (h - top) * 0.42
        # waveform panel
        c.create_polygon(rounded_rect_points(x1, wy1, x2, wy2, 18), outline=acc, fill=blend(BG, acc, 0.06), width=2,
                         smooth=True, tags=TAG)
        mid = (wy1 + wy2) / 2
        c.create_line(x1 + 20, mid, x2 - 20, mid, fill=dim(acc, 0.35), tags=TAG)
        r = self.result
        if self.busy:
            self._scanner(c, x1, wy1, x2, wy2)
        elif r:
            top_pts, bot_pts = [], []
            wf = r["waveform"]
            n = len(wf)
            amp = (wy2 - wy1) / 2 - 18
            shown = int(n * self.reveal)
            for i in range(shown):
                x = x1 + 20 + (x2 - x1 - 40) * i / max(1, n - 1)
                top_pts.append((x, mid - wf[i] * amp))
                bot_pts.append((x, mid + wf[i] * amp))
            if shown > 2:
                outline = top_pts + bot_pts[::-1]  # go right along the top, back left along the bottom
                c.create_polygon([v for pt in outline for v in pt], fill=dim(acc, 0.55), outline=acc2, width=1,
                                 tags=TAG)
            # playhead sweep
            px = x1 + 20 + (x2 - x1 - 40) * ((self.t * 0.08) % 1.0)
            c.create_line(px, wy1 + 8, px, wy2 - 8, fill=dim(acc2, 0.8), width=2, tags=TAG)
        else:
            msg = self.error or "Load a track (WAV, MP3, M4A, FLAC...) to see its waveform, BPM and key."
            c.create_text((x1 + x2) / 2, mid, text=msg, font=f["body"], fill="#ff8080" if self.error else TEXT_DIM,
                          width=(x2 - x1) * 0.8, justify="center", tags=TAG)

        # stat cards
        cards = [
            ("BPM", f"{r['bpm']:g}" if r and r.get("bpm") else "—",
             " / ".join(f"{b:g}" for b in r.get("bpm_alternatives", [])) if r else "", "half / double"),
            ("KEY", r["key"] if r else "—", r["camelot"] if r else "", "camelot"),
            ("LENGTH", _fmt_time(r["duration"]) if r else "—", "", ""),
            ("PEAK", f"{r['peak_db']} dB" if r else "—", f"RMS {r['rms_db']} dB" if r else "", ""),
        ]
        cy1 = wy2 + self.sp(26)
        cy2 = min(h - m, cy1 + 170 * f.scale)
        avail = w - m * 2 - dancer_w
        gap = self.sp(18)
        cw = (avail - gap * (len(cards) - 1)) / len(cards)
        for i, (title, value, sub, sub_label) in enumerate(cards):
            cx1 = m + i * (cw + gap)
            cx2 = cx1 + cw
            pts = [cx1 + 18, cy1, cx2, cy1, cx2, cy2 - 18, cx2 - 18, cy2, cx1, cy2, cx1, cy1 + 18]  # clipped corners
            c.create_polygon(pts, outline=acc, fill=blend(BG, acc, 0.08), width=2, tags=TAG)
            c.create_text(cx1 + 18, cy1 + 22, text=title, anchor="w", font=f["small"], fill=acc, tags=TAG)
            big = f["mono_big"] if len(value) <= 7 else f["h1"]
            glow_text(c, (cx1 + cx2) / 2, (cy1 + cy2) / 2 + 4, value, big, "#ffffff", tags=TAG, strength=0.8)
            if sub:
                c.create_text((cx1 + cx2) / 2, cy2 - 22, text=sub, font=f["mono"], fill=acc2, tags=TAG)
        if r:
            c.create_text(m, min(h - 16, cy2 + self.sp(22)), anchor="w", font=f["small"], fill=TEXT_DIM, tags=TAG,
                          text=f"Also possible: {', '.join(r['alternatives'])}   ·   Relative key: {r['relative']}")

    def _scanner(self, c, x1, y1, x2, y2):
        """Animated scan while analysis runs."""
        x = x1 + (x2 - x1) * ((self.t * 0.6) % 1.0)
        for k in range(6):
            c.create_line(x - k * 6, y1 + 6, x - k * 6, y2 - 6, fill=dim(self.accent2, 0.9 - k * 0.15), width=2,
                          tags=TAG)
        c.create_text((x1 + x2) / 2, (y1 + y2) / 2, text="ANALYZING...", font=self.app.fonts["h2"],
                      fill=self.accent2, tags=TAG)

    # ---- KEY FINDER view (memory unit screen) ---------------------------------------------------------
    def _draw_key_finder(self, c, w, h):
        acc, acc2 = self.accent, self.accent2
        f = self.app.fonts
        m = self.sp(28)
        dancer_w = max(160, min(250, h * 0.3)) + 30
        top = self._content_top()
        port_h = max(90, min(130, h * 0.15))
        area_bottom = h - port_h - m - self.sp(20)
        cy = (top + area_bottom) / 2
        r = min((area_bottom - top) / 2 - 30, w * 0.2)
        cx = m + r + 70
        res = self.result

        # holographic wireframe globe
        for k in range(4, 0, -1):
            rr = r * (1.05 + k * 0.05)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=dim(acc, 0.07 * (5 - k)), width=3, tags=TAG)
        wire_sphere(c, cx, cy, r * 0.82, self.t * 0.4, acc, tags=TAG, lat=6, lon=10, tilt=0.4,
                    bright=0.55 if res else 0.35)
        # circle-of-fifths ring with the 24 keys
        ring = r * 1.08
        for i, pc in enumerate(FIFTHS):
            ang = math.radians(-90 + i * 30)
            hit = bool(res) and ((res["mode"] == "major" and res["root"] == pc) or
                                 (res["mode"] == "minor" and (res["root"] + 3) % 12 == pc))
            px, py = cx + ring * math.cos(ang), cy + ring * math.sin(ang)
            maj = an.DISPLAY_NAMES[pc]
            mnr = an.DISPLAY_NAMES[(pc + 9) % 12] + "m"
            col = acc2 if hit else dim(acc, 0.7)
            if hit:
                pulse = 0.5 + 0.5 * math.sin(self.t * 4)
                c.create_oval(px - 26, py - 26, px + 26, py + 26, outline=blend(acc, "#ffffff", pulse * 0.5), width=3,
                              tags=TAG)
            c.create_text(px, py - 8, text=maj, font=f["small"], fill=col, tags=TAG)
            c.create_text(px, py + 10, text=mnr, font=f["small"], fill=dim(col, 0.8), tags=TAG)
            tx1, ty1 = cx + r * 0.92 * math.cos(ang), cy + r * 0.92 * math.sin(ang)
            tx2, ty2 = cx + r * 0.98 * math.cos(ang), cy + r * 0.98 * math.sin(ang)
            c.create_line(tx1, ty1, tx2, ty2, fill=col, width=2, tags=TAG)
        # centre readout
        c.create_oval(cx - r * 0.42, cy - r * 0.42, cx + r * 0.42, cy + r * 0.42, fill=blend(BG, acc, 0.1),
                      outline=acc, width=2, tags=TAG)
        if self.busy:
            sweep = (self.t * 240) % 360
            c.create_arc(cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5, start=sweep, extent=80, style="arc",
                         outline=acc2, width=4, tags=TAG)
            glow_text(c, cx, cy, "SCANNING", f["h2"], acc2, tags=TAG)
        elif res:
            glow_text(c, cx, cy - 10, res["key"].upper(), f["h1"], "#ffffff", tags=TAG)
            c.create_text(cx, cy + r * 0.2, text=res["camelot"], font=f["mono"], fill=acc2, tags=TAG)
        else:
            glow_text(c, cx, cy - 10, "NO TRACK", f["h2"], acc2, tags=TAG)
            c.create_text(cx, cy + r * 0.18, text="press LOAD TRACK", font=f["small"], fill=TEXT_DIM, tags=TAG)

        # right info column
        ix = cx + ring + 90
        iw = w - ix - dancer_w
        y = top + 10
        if iw > 200:
            c.create_text(ix, y, anchor="nw", text="KEY FINDER", font=f["h1"], fill=acc, tags=TAG)
            y += f.size("h1") * 2.2
            rows = [("DETECTED KEY", res["key"] if res else "—"),
                    ("CAMELOT", res["camelot"] if res else "—"),
                    ("RELATIVE KEY", res["relative"] if res else "—"),
                    ("ALSO POSSIBLE", ", ".join(res["alternatives"][:2]) if res else "—"),
                    ("TEMPO", f"{res['bpm']:g} BPM" if res and res.get("bpm") else "—")]
            for name, val in rows:
                c.create_text(ix, y, anchor="nw", text=name, font=f["small"], fill=TEXT_DIM, tags=TAG)
                c.create_text(ix, y + f.size("small") * 1.6, anchor="nw", text=val, font=f["h2"], fill=TEXT, tags=TAG)
                y += f.size("small") * 1.6 + f.size("h2") * 2.0
            # confidence bar
            conf = res["confidence"] * self.reveal if res else 0
            c.create_text(ix, y, anchor="nw", text="CONFIDENCE", font=f["small"], fill=TEXT_DIM, tags=TAG)
            by = y + f.size("small") * 1.8
            bw = min(iw - 20, 360)
            c.create_rectangle(ix, by, ix + bw, by + 14, outline=dim(acc, 0.6), width=2, tags=TAG)
            if conf > 0:
                c.create_rectangle(ix + 2, by + 2, ix + 2 + (bw - 4) * conf, by + 12, fill=acc, outline="", tags=TAG)
            if self.error:
                c.create_text(ix, by + 40, anchor="nw", text=self.error, font=f["small"], fill="#ff8080",
                              width=iw - 20, tags=TAG)

        # controller ports (memory unit slots), like the Xbox memory screen
        n = 4
        px1, px2 = m, w - m - dancer_w
        py1 = h - m - port_h
        gap = self.sp(16)
        pw = (px2 - px1 - gap * (n - 1)) / n
        for i in range(n):
            x1 = px1 + i * (pw + gap)
            x2 = x1 + pw
            active = i == 0 and (res or self.busy)
            col = acc if active else dim(acc, 0.5)
            c.create_polygon(rounded_rect_points(x1, py1, x2, py1 + port_h, 16), outline=col,
                             fill=blend(BG, acc, 0.12 if active else 0.04), width=2, smooth=True, tags=TAG)
            # the controller-port socket shape
            sx, sy = x1 + 22, py1 + port_h / 2
            c.create_polygon(sx, sy - 16, sx + 30, sy - 16, sx + 36, sy, sx + 30, sy + 16, sx, sy + 16,
                             outline=col, fill="", width=2, tags=TAG)
            for k in range(3):
                c.create_line(sx + 8 + k * 8, sy - 7, sx + 8 + k * 8, sy + 7, fill=col, width=2, tags=TAG)
            c.create_text(sx + 50, py1 + 22, anchor="w", text=f"PORT {i + 1}", font=f["small"], fill=col, tags=TAG)
            for j, slot in enumerate(("A", "B")):
                ty = py1 + 22 + (j + 1) * f.size("small") * 1.7
                filled = active and slot == "A"
                txt = (res["name"] if res else "loading...") if filled else "Empty"
                limit = max(6, int((pw - 90) / (f.size("small") * 0.55)))
                if len(txt) > limit:
                    txt = txt[: limit - 1] + "…"
                c.create_text(sx + 50, ty, anchor="w", text=f"{slot}  {txt}", font=f["small"],
                              fill=acc2 if filled else TEXT_DIM, tags=TAG)


def _fmt_time(sec):
    sec = int(round(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"
