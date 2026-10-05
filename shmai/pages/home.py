"""
HOME: PS3 XMB-style main menu, neon cyan.

    A horizontal row of category icons. The selected category is larger,
    glows, and drops a vertical column of sub-items beneath it. Use the
    arrow keys (left/right = category, up/down = item, Enter = open) or the
    mouse. The flowing XMB "wave" ribbon drifts behind the menu.

REFERENCE-LAYOUT FLAG: built from the written description (PS3 XMB). Compare
against your reference images and note anything to adjust.
"""
import math

from ..config import output_dir
from ..sound import open_folder
from ..theme import BG, TEXT, TEXT_DIM, blend, dim
from ..widgets.fx import glow_oval, glow_text, hexagon_points
from .base import BasePage

# (category id, label, icon, [(sub-item label, action), ...])
# action = ("page", page_key, {options}) or ("call", method_name)
CATEGORIES = [
    ("beat", "Beat Finder", "disc", [
        ("Search YouTube", ("page", "beat", {"source": "YouTube"})),
        ("Search SoundCloud", ("page", "beat", {"source": "SoundCloud"})),
        ("Bandcamp Link", ("page", "beat", {"source": "Bandcamp"})),
        ("Mixcloud Link", ("page", "beat", {"source": "Mixcloud"})),
        ("Open Downloads Folder", ("call", "open_downloads")),
    ]),
    ("analyzer", "Audio Analyzer", "wave", [
        ("Analyze a Track", ("page", "analyzer", {"view": "analyze"})),
        ("Key Finder", ("page", "analyzer", {"view": "key"})),
    ]),
    ("melody", "Melody Generator", "keys", [
        ("Cloud Melody (MusicGen)", ("page", "melody", {"engine": "Cloud (MusicGen)"})),
        ("MIDI Composer", ("page", "melody", {"engine": "Local MIDI"})),
    ]),
    ("song", "Song Writer", "pen", [
        ("Guided Questions", ("page", "song", {"mode": "guided"})),
        ("Freeform Chat", ("page", "song", {"mode": "freeform"})),
    ]),
    ("clarity", "Clarity", "link", [
        ("About Clarity (coming soon)", ("page", "clarity", {})),
    ]),
    ("settings", "Settings", "gear", [
        ("Server Connection", ("call", "open_settings")),
        ("Display Size & Spacing", ("call", "open_display_settings")),
        ("Selection Sound On / Off", ("call", "toggle_sound")),
        ("Test Server Connection", ("call", "test_connection")),
    ]),
]

TAG = "xmb"


def draw_icon(c, kind, cx, cy, s, color, tags):
    """Simple vector icons in the XMB style. s = half-size in pixels."""
    w = max(2, s * 0.09)
    if kind == "disc":  # vinyl record
        c.create_oval(cx - s, cy - s, cx + s, cy + s, outline=color, width=w, tags=tags)
        c.create_oval(cx - s * 0.68, cy - s * 0.68, cx + s * 0.68, cy + s * 0.68, outline=dim(color, 0.5),
                      width=1, tags=tags)
        c.create_oval(cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3, fill=color, outline="", tags=tags)
        c.create_oval(cx - s * 0.07, cy - s * 0.07, cx + s * 0.07, cy + s * 0.07, fill=BG, outline="", tags=tags)
    elif kind == "wave":  # waveform
        pts = []
        for i in range(41):
            x = cx - s + 2 * s * i / 40
            amp = math.sin(i / 40 * math.pi) * s * 0.85
            pts += [x, cy + amp * math.sin(i * 1.3)]
        c.create_line(pts, fill=color, width=w, smooth=True, tags=tags)
        c.create_line(cx - s, cy, cx + s, cy, fill=dim(color, 0.4), tags=tags)
    elif kind == "keys":  # piano keys
        for i in range(5):
            x = cx - s + i * s * 0.4
            c.create_rectangle(x, cy - s * 0.7, x + s * 0.38, cy + s * 0.75, outline=color, width=w * 0.7, tags=tags)
        for i in (0, 1, 3):
            x = cx - s + (i + 1) * s * 0.4 - s * 0.1
            c.create_rectangle(x, cy - s * 0.7, x + s * 0.2, cy + s * 0.1, fill=color, outline="", tags=tags)
    elif kind == "pen":  # pen over paper lines
        for k in range(3):
            y = cy + s * (0.15 + 0.28 * k)
            c.create_line(cx - s, y, cx + s * 0.4, y, fill=dim(color, 0.6), width=max(1, w * 0.6), tags=tags)
        c.create_polygon(cx + s * 0.9, cy - s * 0.9, cx + s * 0.6, cy - s * 1.0, cx - s * 0.5, cy + s * 0.25,
                         cx - s * 0.6, cy + s * 0.6, cx - s * 0.25, cy + s * 0.5, outline=color, fill=dim(color, 0.3),
                         width=w * 0.7, tags=tags)
    elif kind == "link":  # crystal / plugin link
        c.create_polygon(hexagon_points(cx, cy, s, 30), outline=color, fill="", width=w, tags=tags)
        c.create_polygon(cx, cy - s * 0.6, cx + s * 0.5, cy, cx, cy + s * 0.6, cx - s * 0.5, cy, outline=color,
                         fill=dim(color, 0.35), width=w * 0.7, tags=tags)
    elif kind == "gear":
        pts = []
        for i in range(20):
            a = math.pi * 2 * i / 20
            r = s if i % 2 == 0 else s * 0.75
            pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
        c.create_polygon(pts, outline=color, fill="", width=w, tags=tags)
        c.create_oval(cx - s * 0.32, cy - s * 0.32, cx + s * 0.32, cy + s * 0.32, outline=color, width=w, tags=tags)


class HomePage(BasePage):
    key = "home"
    role = "artist"
    reference_layout = "PS3 XMB home"

    def build(self):
        self.cat = 0        # selected category
        self.items = [0] * len(CATEGORIES)  # selected item per category
        self.cat_pos = 0.0  # animated (smooth) versions
        self.hover = None   # ("cat", i) / ("item", j)
        self.wave_t = 0.0
        self.pulse = 0.0
        self.hitboxes = []
        c = self.canvas
        c.bind("<Motion>", self._motion)
        c.bind("<Button-1>", self._click)
        c.bind("<MouseWheel>", self._wheel)
        c.bind("<Button-4>", lambda e: self._move_item(-1))
        c.bind("<Button-5>", lambda e: self._move_item(1))
        for key, fn in (("<Left>", lambda e: self._move_cat(-1)), ("<Right>", lambda e: self._move_cat(1)),
                        ("<Up>", lambda e: self._move_item(-1)), ("<Down>", lambda e: self._move_item(1)),
                        ("<Return>", lambda e: self._activate())):
            c.bind(key, fn)

    def on_show(self, **kwargs):
        self.canvas.focus_set()

    # ---- input --------------------------------------------------------------
    def _move_cat(self, d):
        new = max(0, min(len(CATEGORIES) - 1, self.cat + d))
        if new != self.cat:
            self.cat = new
            self.app.sound.play_select()
            self.pulse = 1.0

    def _move_item(self, d):
        n = len(CATEGORIES[self.cat][3])
        new = max(0, min(n - 1, self.items[self.cat] + d))
        if new != self.items[self.cat]:
            self.items[self.cat] = new
            self.app.sound.play_select()

    def _wheel(self, e):
        self._move_item(-1 if e.delta > 0 else 1)

    def _activate(self):
        label, action = CATEGORIES[self.cat][3][self.items[self.cat]]
        self.app.sound.play_select()
        if action[0] == "page":
            self.app.show_page(action[1], **action[2])
        else:
            getattr(self, action[1])()

    def _hit(self, x, y):
        for kind, idx, (x1, y1, x2, y2) in self.hitboxes:
            if x1 <= x <= x2 and y1 <= y <= y2:
                return kind, idx
        return None

    def _motion(self, e):
        self.hover = self._hit(e.x, e.y)
        self.canvas.configure(cursor="hand2" if self.hover else "")

    def _click(self, e):
        self.canvas.focus_set()
        hit = self._hit(e.x, e.y)
        if not hit:
            return
        kind, idx = hit
        if kind == "cat":
            if idx == self.cat:
                self._activate()
            else:
                self.cat = idx
                self.pulse = 1.0
                self.app.sound.play_select()
        else:
            self.items[self.cat] = idx
            self._activate()

    # ---- sub-item actions ---------------------------------------------------------
    def open_downloads(self):
        open_folder(output_dir(self.app.cfg, "Beat Finder"))

    def open_settings(self):
        self.app.open_settings()

    def open_display_settings(self):
        self.app.open_settings(focus="display")

    def toggle_sound(self):
        self.app.cfg["sound_enabled"] = not self.app.cfg.get("sound_enabled", True)
        self.app.apply_settings(dict(self.app.cfg))
        self.status = ("Selection sound ON" if self.app.cfg["sound_enabled"] else "Selection sound OFF", 3.0)

    def test_connection(self):
        self.status = ("Contacting server...", 30.0)

        def done(data):
            self.status = (f"Connected ✓  ({data.get('model', 'ok')})", 5.0)

        def fail(msg):
            self.status = (msg.splitlines()[0], 6.0)
        self.app.run_async(self.app.client.health, done, fail)

    # ---- drawing ------------------------------------------------------------------------
    def layout(self, w, h):
        pass  # everything is redrawn each frame in animate()

    def animate(self, dt):
        c = self.canvas
        w, h = max(c.winfo_width(), 100), max(c.winfo_height(), 100)
        self.wave_t += dt
        self.pulse = max(0.0, self.pulse - dt * 2.5)
        # smooth movement toward the selected positions (XMB slide)
        self.cat_pos += (self.cat - self.cat_pos) * min(1, dt * 10)

        c.delete(TAG)
        self.hitboxes = []
        acc, acc2 = self.accent, self.accent2
        s = self.app.fonts.scale
        sp = float(self.app.cfg.get("ui_spacing", 1.0))

        # --- XMB wave ribbon ---------------------------------------------------------
        base_y = h * 0.6
        for k in range(7):
            pts = []
            for i in range(61):
                x = w * i / 60
                y = base_y + math.sin(i / 60 * math.pi * 2 + self.wave_t * (0.35 + k * 0.05) + k * 0.4) * h * 0.07
                y += math.sin(i / 60 * math.pi * 3.3 - self.wave_t * 0.25 + k) * h * 0.025
                pts += [x, y + k * 5]
            c.create_line(pts, fill=dim(acc, 0.14 + 0.05 * (k % 3)), width=2 if k % 3 else 3, smooth=True, tags=TAG)

        # --- category icons -------------------------------------------------------------
        row_y = h * 0.27
        col_x = w * 0.3          # where the selected category sits (XMB style, left of center)
        spacing = 175 * s * sp
        for i, (cid, label, icon, items) in enumerate(CATEGORIES):
            x = col_x + (i - self.cat_pos) * spacing
            if x < -spacing or x > w + spacing:
                continue
            selected = i == self.cat
            hovering = self.hover == ("cat", i)
            closeness = max(0.0, 1 - abs(i - self.cat_pos))
            size = (30 + 16 * closeness + (6 if hovering else 0) + 6 * self.pulse * selected) * s
            color = blend(dim(acc, 0.55), acc2 if (selected or hovering) else acc, closeness if not hovering else 1)
            if selected or hovering:
                glow_oval(c, x - size * 1.55, row_y - size * 1.55, x + size * 1.55, row_y + size * 1.55,
                          dim(acc, 0.7), tags=TAG, layers=4, width=1, strength=0.8)
            draw_icon(c, icon, x, row_y, size, color, TAG)
            if selected:
                glow_text(c, x, row_y + size + 30 * s, label.upper(), self.app.fonts["h2"], acc2, tags=TAG)
            else:
                c.create_text(x, row_y + size + 26 * s, text=label, font=self.app.fonts["small"],
                              fill=dim(TEXT, 0.45 + 0.5 * hovering), tags=TAG)
            self.hitboxes.append(("cat", i, (x - spacing / 2, row_y - size * 1.6, x + spacing / 2,
                                             row_y + size + 40 * s)))

        # --- sub-item column under the selected icon ----------------------------------
        cid, label, icon, items = CATEGORIES[self.cat]
        top = row_y + 120 * s * sp
        step = 58 * s * sp
        for j, (text, _a) in enumerate(items):
            y = top + j * step
            if y > h - 30:
                break
            selected = j == self.items[self.cat]
            hovering = self.hover == ("item", j)
            f = self.app.fonts["h2" if selected else "body"]
            x = col_x - 20 * s
            if selected or hovering:
                # selection bar with glow, like the XMB highlight
                bw = max(f.measure(text) + 90 * s, 360 * s)
                for g in range(3, 0, -1):
                    c.create_rectangle(x - 18 - g * 2, y - 24 * s - g * 2, x + bw + g * 2, y + 24 * s + g * 2,
                                       outline=dim(acc, 0.15 * (4 - g)), width=2, tags=TAG)
                c.create_rectangle(x - 18, y - 24 * s, x + bw, y + 24 * s, outline=acc if selected else dim(acc, 0.6),
                                   fill=blend(BG, acc, 0.13), width=2, tags=TAG)
            # small item marker
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill=acc if selected else dim(acc, 0.45), outline="", tags=TAG)
            c.create_text(x + 22, y, text=text, anchor="w", font=f,
                          fill=TEXT if (selected or hovering) else dim(TEXT, 0.55), tags=TAG)
            self.hitboxes.append(("item", j, (x - 20, y - 26 * s, x + max(f.measure(text) + 90 * s, 360 * s),
                                              y + 26 * s)))

        # --- hint + status line ------------------------------------------------------
        hint = "◀ ▶  choose      ▲ ▼  select      ENTER / click  open"
        c.create_text(24, h - 24, text=hint, anchor="sw", font=self.app.fonts["small"], fill=TEXT_DIM, tags=TAG)
        msg, ttl = getattr(self, "status", ("", 0))
        if ttl > 0:
            self.status = (msg, ttl - dt)
            c.create_text(24, h - 24 - self.app.fonts.size("small") * 2.2, text=msg, anchor="sw",
                          font=self.app.fonts["body"], fill=acc2, tags=TAG)
        c.tag_lower(TAG)
        c.tag_lower("starfield")
