"""
HOME: the character line-up, neon cyan.

Same moving starfield and flowing XMB "wave" ribbon as before, but no
buttons: just the shmAI cast dancing in a row. Click a character (or use
the arrow keys + Enter) to open their page:

    executive producer -> Beat Finder     audio engineer -> Audio Analyzer
    producer           -> Melody Gen      artist (host)  -> stays on Home, does a hop
    songwriter         -> Song Writer     tech           -> Clarity

Hovering a character makes them glow, grow a little, and shows their page
name above their head. The tabs at the top work as before.
"""
import math

from ..theme import PAGES, dim
from ..widgets.dancer import Dancer
from ..widgets.fx import glow_text
from .base import BasePage

# (page to open, character role); None = the host, who stays on Home
CAST = [
    ("beat", "executive"),
    ("analyzer", "engineer"),
    ("melody", "producer"),
    (None, "artist"),
    ("song", "songwriter"),
    ("clarity", "tech"),
]
TAG = "xmb"


class HomePage(BasePage):
    key = "home"
    role = "artist"
    reference_layout = "Home line-up (starfield + XMB wave)"

    def build(self):
        self.wave_t = 0.0
        self.hover = None      # index of the character under the mouse
        self.focus = None      # index chosen with the arrow keys
        self.jump = {}         # index -> seconds left in a hop
        self.cast = []
        for page, role in CAST:
            pal = PAGES[page or "home"]
            d = Dancer(self.canvas, role, pal["accent"], pal["accent2"])
            d.time = len(self.cast) * 0.37  # stagger so they don't move in lockstep
            self.cast.append({"page": page, "dancer": d, "name": pal["name"] if page else "shmAI"})
        c = self.canvas
        c.bind("<Motion>", self._motion)
        c.bind("<Leave>", lambda e: self._set_hover(None))
        c.bind("<Button-1>", self._click)
        c.bind("<Left>", lambda e: self._move_focus(-1))
        c.bind("<Right>", lambda e: self._move_focus(1))
        c.bind("<Return>", lambda e: self._open(self.focus) if self.focus is not None else None)

    def on_show(self, **kwargs):
        self.canvas.focus_set()

    # ---- placement ----------------------------------------------------------------------------
    def _slots(self, w, h):
        n = len(self.cast)
        margin = w * 0.04
        step = (w - 2 * margin) / n
        height = min(h * 0.62, step * 1.75)
        ground = h * 0.86
        return [(margin + step * (i + 0.5), ground, height) for i in range(n)]

    def dancer_spot(self, w, h):
        # The usual corner dancer isn't used on Home (the line-up replaces it): park it off-screen.
        return -5000, -5000, 10

    def layout(self, w, h):
        for (x, g, ht), member in zip(self._slots(w, h), self.cast):
            member["dancer"].place(x, g, ht)

    # ---- input ---------------------------------------------------------------------------------
    def _index_at(self, x, y):
        for i, m in enumerate(self.cast):
            x1, y1, x2, y2 = m["dancer"].bbox()
            if x1 <= x <= x2 and y1 <= y <= y2:
                return i
        return None

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.canvas.configure(cursor="hand2" if i is not None else "")

    def _motion(self, e):
        self._set_hover(self._index_at(e.x, e.y))

    def _click(self, e):
        self.canvas.focus_set()
        i = self._index_at(e.x, e.y)
        if i is not None:
            self._open(i)

    def _move_focus(self, d):
        n = len(self.cast)
        self.focus = (n // 2 if self.focus is None else (self.focus + d) % n)
        self.app.sound.play_select()

    def _open(self, i):
        self.app.sound.play_select()
        self.jump[i] = 0.45
        page = self.cast[i]["page"]
        if page:
            self.app.root.after(220, lambda: self.app.show_page(page))  # let the hop start first

    # ---- animation ------------------------------------------------------------------------------
    def tick(self, dt):
        # Overrides BasePage.tick: the line-up replaces the single corner dancer.
        self.starfield.tick(dt)
        self.animate(dt)

    def animate(self, dt):
        c = self.canvas
        w, h = self._size
        if w < 10:
            return
        self.wave_t += dt
        c.delete(TAG)
        acc = self.accent

        # flowing XMB wave ribbon behind the cast
        base_y = h * 0.52
        for k in range(7):
            pts = []
            for i in range(61):
                x = w * i / 60
                y = base_y + math.sin(i / 60 * math.pi * 2 + self.wave_t * (0.35 + k * 0.05) + k * 0.4) * h * 0.07
                y += math.sin(i / 60 * math.pi * 3.3 - self.wave_t * 0.25 + k) * h * 0.025
                pts += [x, y + k * 5]
            c.create_line(pts, fill=dim(acc, 0.14 + 0.05 * (k % 3)), width=2 if k % 3 else 3, smooth=True, tags=TAG)
        # a faint stage line under their feet
        g = h * 0.86
        c.create_line(w * 0.03, g + 2, w * 0.97, g + 2, fill=dim(acc, 0.35), width=2, tags=TAG)
        c.tag_lower(TAG)
        c.tag_lower("starfield")

        slots = self._slots(w, h)
        for i, (m, (x, ground, height)) in enumerate(zip(self.cast, slots)):
            d = m["dancer"]
            active = i in (self.hover, self.focus)
            target = 1.0 if active else 0.0
            d.highlight += (target - d.highlight) * min(1.0, dt * 10)
            hop = 0.0
            if i in self.jump:
                self.jump[i] -= dt
                t = 1 - max(0.0, self.jump[i]) / 0.45
                hop = math.sin(math.pi * t) * height * 0.12
                if self.jump[i] <= 0:
                    del self.jump[i]
            # grow ~8% when highlighted (glow-and-scale)
            d.place(x, ground - hop, height * (1 + 0.08 * d.highlight))
            d.tick(dt)
            if d.highlight > 0.05:
                x1, y1, x2, y2 = d.bbox()
                glow_text(c, x, y1 - 14, m["name"], self.app.fonts["h2"], d.accent2, tags=TAG,
                          strength=d.highlight)
