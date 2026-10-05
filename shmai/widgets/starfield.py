"""
Animated moving starfield / cosmos background.

Stars fly slowly toward you (a gentle "warp" drift). Close stars are
brighter and leave short streaks. A few soft nebula clouds drift behind
them. Everything is tinted with the page's accent color.

The page calls `tick(dt)` about 30 times a second while it's visible.
"""
import math
import random

from ..theme import BG, blend, dim

TAG = "starfield"
NEB_LAYERS = 9


def _neb_strength(k):
    return 0.012 + 0.0075 * k


class Starfield:
    def __init__(self, canvas, tint, count=150, speed=0.11):
        self.canvas = canvas
        self.tint = tint
        self.speed = speed
        self.stars = []
        self.nebulae = []
        self.time = 0.0
        rnd = random.Random(hash(tint) & 0xFFFF)

        # Nebula clouds: stacks of ovals, dark outside -> slightly brighter
        # inside, each layer nudged off-center so the cloud looks organic
        # instead of like a target. Reads as a soft glow on black.
        for _ in range(3):
            neb = {
                "x": rnd.uniform(0.1, 0.9), "y": rnd.uniform(0.15, 0.85),
                "r": rnd.uniform(0.16, 0.28), "phase": rnd.uniform(0, 6.28),
                "drift": rnd.uniform(0.004, 0.012), "items": [],
                "offsets": [(rnd.uniform(-0.25, 0.25), rnd.uniform(-0.2, 0.2)) for _ in range(NEB_LAYERS)],
            }
            for k in range(NEB_LAYERS):
                neb["items"].append(canvas.create_oval(0, 0, 0, 0, fill=dim(tint, _neb_strength(k)),
                                                       outline="", tags=(TAG,)))
            self.nebulae.append(neb)

        for _ in range(count):
            star = {
                "x": rnd.uniform(-1, 1), "y": rnd.uniform(-1, 1), "z": rnd.uniform(0.08, 1.0),
                "white": rnd.random() < 0.55,
                "streak": canvas.create_line(0, 0, 0, 0, fill=BG, width=1, tags=(TAG,)),
                "dot": canvas.create_oval(0, 0, 0, 0, fill=BG, outline="", tags=(TAG,)),
            }
            self.stars.append(star)
        self.rnd = rnd
        canvas.tag_lower(TAG)

    def set_tint(self, tint):
        self.tint = tint
        for neb in self.nebulae:
            for k, item in enumerate(neb["items"]):
                self.canvas.itemconfigure(item, fill=dim(tint, _neb_strength(k)))

    def tick(self, dt):
        c = self.canvas
        w = max(c.winfo_width(), 50)
        h = max(c.winfo_height(), 50)
        cx, cy = w / 2, h / 2
        spread = max(w, h) * 0.55
        self.time += dt

        for neb in self.nebulae:
            nx = (neb["x"] + math.sin(self.time * neb["drift"] * 6 + neb["phase"]) * 0.04) * w
            ny = (neb["y"] + math.cos(self.time * neb["drift"] * 5 + neb["phase"]) * 0.03) * h
            base = neb["r"] * max(w, h)
            for k, item in enumerate(neb["items"]):
                r = base * (1 - k * 0.095)
                ox, oy = neb["offsets"][k]
                x, y = nx + ox * base * k / NEB_LAYERS, ny + oy * base * k / NEB_LAYERS
                c.coords(item, x - r * 1.5, y - r * 0.85, x + r * 1.5, y + r * 0.85)

        for s in self.stars:
            old_z = s["z"]
            s["z"] -= self.speed * dt
            if s["z"] <= 0.04:
                s["x"], s["y"] = self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1)
                s["z"] = 1.0
                old_z = 1.0
            z = s["z"]
            sx, sy = cx + s["x"] / z * spread * 0.35, cy + s["y"] / z * spread * 0.35
            if not (-20 < sx < w + 20 and -20 < sy < h + 20):
                s["z"] = 0.0  # off-screen: respawn next frame
                continue
            px, py = cx + s["x"] / old_z * spread * 0.35, cy + s["y"] / old_z * spread * 0.35
            near = 1 - z  # 0 far .. 1 close
            size = 1.2 + near * 2.8
            base = "#ffffff" if s["white"] else self.tint
            color = dim(blend(self.tint, base, 0.6), 0.45 + near * 0.55)
            c.coords(s["dot"], sx - size / 2, sy - size / 2, sx + size / 2, sy + size / 2)
            c.itemconfigure(s["dot"], fill=color)
            # Streak trail grows as stars get close.
            tx = sx + (px - sx) * (1 + near * 5)
            ty = sy + (py - sy) * (1 + near * 5)
            c.coords(s["streak"], tx, ty, sx, sy)
            c.itemconfigure(s["streak"], fill=dim(color, 0.6), width=max(1, size * 0.6))
        c.tag_lower(TAG)
