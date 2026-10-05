"""
CLARITY: placeholder tab for the future in-DAW plugin (stub only).

Clarity will live inside your DAW (FL Studio, Ableton, Logic...) and link
back to this standalone app. This page shows the planned connection status
and what it will do. The real link comes in a later stage (see
shmai/clarity_bridge.py).
"""
import math

from ..clarity_bridge import ClarityBridge
from ..theme import BG, TEXT, TEXT_DIM, blend, dim
from ..widgets.fx import glow_text, hexagon_points, rounded_rect_points
from .base import BasePage

TAG = "cl"
PLANNED = [
    "Send a loop or vocal from your DAW straight to the Audio Analyzer",
    "Drag Melody Generator MIDI directly onto a DAW track",
    "Write lyrics with the Song Writer while your beat plays",
    "Keep shmAI settings in sync between the plugin and this app",
]


class ClarityPage(BasePage):
    key = "clarity"
    role = "tech"
    reference_layout = ""

    def build(self):
        self.bridge = ClarityBridge(self.app.cfg)
        self.t = 0.0

    def animate(self, dt):
        self.t += dt
        c = self.canvas
        w, h = self._size
        if w < 10:
            return
        c.delete(TAG)
        f = self.app.fonts
        acc, gold = self.accent, self.accent2
        m = self.sp(40)
        glow_text(c, m, m + 10, "CLARITY", f["title"], acc, tags=TAG, anchor="w")
        c.create_text(m, m + f.size("title") * 2.2, anchor="w", text="In-DAW plugin link · coming soon",
                      font=f["h2"], fill=gold, tags=TAG)

        # app <-> plugin diagram: two crystals joined by a pulsing link
        cy = h * 0.42
        ax, bx = w * 0.2, w * 0.58
        r = min(h * 0.11, 90)
        for x, label in ((ax, "shmAI APP"), (bx, "DAW PLUGIN")):
            spin = self.t * 20 * (1 if x == ax else -1)
            for k in range(3, 0, -1):
                c.create_polygon(hexagon_points(x, cy, r + k * 6, spin), outline=dim(acc, 0.12 * (4 - k)), fill="",
                                 width=2, tags=TAG)
            c.create_polygon(hexagon_points(x, cy, r, spin), outline=acc, fill=blend(BG, acc, 0.08), width=2, tags=TAG)
            c.create_polygon(x, cy - r * 0.55, x + r * 0.4, cy, x, cy + r * 0.55, x - r * 0.4, cy, outline=gold,
                             fill=blend(BG, gold, 0.25 if x == ax else 0.06), width=2, tags=TAG)
            c.create_text(x, cy + r + 30, text=label, font=f["h2"], fill=TEXT, tags=TAG)
        # dashed "not connected" link with a travelling pulse
        x1, x2 = ax + r + 14, bx - r - 14
        c.create_line(x1, cy, x2, cy, fill=dim(acc, 0.5), width=3, dash=(10, 8), tags=TAG)
        p = (self.t * 0.35) % 1.0
        px = x1 + (x2 - x1) * p
        c.create_oval(px - 7, cy - 7, px + 7, cy + 7, fill=gold, outline="", tags=TAG)
        c.create_text((x1 + x2) / 2, cy - 26, text="NOT CONNECTED", font=f["small"], fill=TEXT_DIM, tags=TAG)

        # planned features panel
        dancer_w = max(160, min(250, h * 0.3)) + 30
        py1 = h * 0.62
        px1, px2 = m, w - m - dancer_w
        py2 = min(h - m, py1 + (len(PLANNED) + 1.6) * f.size("body") * 2.2)
        c.create_polygon(rounded_rect_points(px1, py1, px2, py2, 18), outline=dim(acc, 0.7), fill=blend(BG, acc, 0.04),
                         width=2, smooth=True, tags=TAG)
        c.create_text(px1 + 24, py1 + 26, anchor="w", text="WHAT CLARITY WILL DO", font=f["small"], fill=gold, tags=TAG)
        for i, item in enumerate(PLANNED):
            y = py1 + 26 + (i + 1) * f.size("body") * 2.1
            pulse = 0.6 + 0.4 * math.sin(self.t * 2 + i)
            c.create_polygon(hexagon_points(px1 + 34, y, 7), fill=dim(acc, pulse), outline="", tags=TAG)
            c.create_text(px1 + 54, y, anchor="w", text=item, font=f["body"], fill=TEXT, tags=TAG)
        c.create_text(px1, min(h - 14, py2 + 26), anchor="w", text=f"Status: {self.bridge.status()}",
                      font=f["mono"], fill=TEXT_DIM, tags=TAG)
        c.tag_raise(TAG, "starfield")
