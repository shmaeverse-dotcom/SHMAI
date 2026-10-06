"""
Dancing anime characters, drawn live on a page's canvas.

Style (from the owner's reference images): modern TV-anime look with clean
dark line art, long glossy hair with a shine band, big sparkly eyes with a
heavy upper lash line, blush, and warm/tan skin tones. Adult characters in
role outfits, one per page:

    artist      Home            long black hair + pink ribbons, blue eyes, mic
    executive   Beat Finder     glasses, twin tails with red tips, blazer + tie
    engineer    Audio Analyzer  white blunt-bang bob, pale skin, studio headphones
    producer    Melody Gen      long black hair + silver clips, smug grin, drumsticks
    songwriter  Song Writer     side braid, bindi, gold earrings, polka-dot top
    tech        Clarity         high ponytail, glowing visor, cable

No text label underneath. Everything is vector shapes (no image files),
so it stays sharp at any size.

Public API (used by every page): Dancer(canvas, role, accent, accent2),
.place(x, ground_y, height), .tick(dt), .draw(), .tag, .bbox()
"""
import math

from ..theme import blend, dim

LINE = "#17111c"
WHITE = "#ffffff"

ROLES = {
    "artist": {
        "skin": "#c98d62", "hair": "#16161e", "hair_hi": "#4b4c66", "eyes": "#3d6fd6",
        "style": "ribbons", "ribbon": "#f2a7c3", "top": "accent", "bottom": "#1b2030",
        "bottom_style": "skirt", "mouth": "o", "brows": "thin", "bpm": 116, "moves": ("mic_pump", "sway"),
    },
    "executive": {
        "skin": "#9a5d38", "hair": "#18181e", "hair_hi": "#45455a", "tips": "#6b1d2a", "eyes": "#e0577c",
        "style": "twintails", "glasses": True, "top": "blazer", "tie": "#8c1c2b", "bottom": "#202027",
        "bottom_style": "pants", "mouth": "grin", "brows": "thin", "choker": True, "bpm": 100,
        "moves": ("point", "sway"),
    },
    "engineer": {
        "skin": "#f4e7ee", "hair": "#f5f3fa", "hair_hi": "#c9cbe8", "eyes": "#6aa9ea", "style": "bob",
        "top": "#121218", "bottom": "#121218", "bottom_style": "pants", "mouth": "flat", "brows": "none",
        "lashes": True, "blush_lines": True, "headphones": True, "bpm": 106, "moves": ("headbang", "sway"),
    },
    "producer": {
        "skin": "#9b603b", "hair": "#16161d", "hair_hi": "#403b58", "eyes": "#c4472f", "style": "clips",
        "top": "hoodie", "bottom": "#24242c", "bottom_style": "pants", "mouth": "smug", "brows": "thin",
        "bpm": 124, "moves": ("drum", "fist"),
    },
    "songwriter": {
        "skin": "#d39869", "hair": "#121218", "hair_hi": "#3d3d52", "eyes": "#2b3340", "style": "braid",
        "bindi": True, "earrings": True, "top": "polka", "top_color": "#2d4776", "bottom": "#2d4776",
        "bottom_style": "long_skirt", "mouth": "neutral", "brows": "thick", "bpm": 92,
        "moves": ("write", "sway"),
    },
    "tech": {
        "skin": "#b6784d", "hair": "#1a1a22", "hair_hi": "#45465c", "eyes": "#7fe3ff", "style": "ponytail",
        "visor": True, "top": "#1c2433", "bottom": "#1c2433", "bottom_style": "pants", "mouth": "smile",
        "brows": "thin", "choker": True, "bpm": 112, "moves": ("robot", "sway"),
    },
}


class Dancer:
    def __init__(self, canvas, role, accent, accent2):
        self.canvas = canvas
        self.role = role if role in ROLES else "artist"
        self.s = ROLES[self.role]
        self.accent = accent
        self.accent2 = accent2
        self.time = 0.0
        self.anchor = (0, 0)
        self.height = 240
        self.highlight = 0.0  # 0..1 glow, used by the Home line-up on hover
        self.tag = f"dancer{id(self)}"  # unique, so several dancers can share a canvas

    def place(self, x, y, height):
        self.anchor = (x, y)
        self.height = height

    def bbox(self):
        """Rough clickable area (x1, y1, x2, y2)."""
        x, g = self.anchor
        return x - self.height * 0.3, g - self.height * 1.02, x + self.height * 0.3, g

    def tick(self, dt):
        self.time += dt
        self.draw()

    # ---- helpers -------------------------------------------------------------------
    @staticmethod
    def _limb(x, y, length, angle_deg):
        a = math.radians(angle_deg)
        return x + length * math.sin(a), y + length * math.cos(a)

    @staticmethod
    def _knee(hip, foot, seg, out_dir):
        hx, hy = hip
        fx, fy = foot
        d = math.hypot(fx - hx, fy - hy) or 1
        mx, my = (hx + fx) / 2, (hy + fy) / 2
        bend = math.sqrt(max(0.0, seg * seg - (d / 2) ** 2))
        nx, ny = -(fy - hy) / d, (fx - hx) / d
        return mx + nx * bend * out_dir, my + ny * bend * out_dir

    def _poly(self, pts, fill, outline=LINE, width=None, smooth=True):
        self.canvas.create_polygon(pts, fill=fill, outline=outline, width=width or self.lw, smooth=smooth,
                                   tags=self.tag)

    def _line(self, pts, fill, width, smooth=True, cap="round"):
        self.canvas.create_line(pts, fill=fill, width=width, smooth=smooth, capstyle=cap, joinstyle="round",
                                tags=self.tag)

    def _oval(self, cx, cy, rx, ry, fill, outline="", width=1):
        self.canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=fill, outline=outline, width=width,
                                tags=self.tag)

    # ---- pose --------------------------------------------------------------------------
    def _pose(self):
        beat = self.time * self.s["bpm"] / 60.0
        ph = beat * 2 * math.pi
        move = self.s["moves"][int(beat // 8) % 2]
        s = math.sin(ph)
        # Arm angles: degrees from hanging straight down. 90 = out sideways,
        # 180 = straight up, negative = across the body.
        p = {"bob": abs(math.sin(ph / 2)), "sway": math.sin(ph / 2), "tilt": 6 * math.sin(ph / 2 + 0.6),
             "l_up": 18, "l_lo": 10, "r_up": 18, "r_lo": 10, "step": math.sin(ph / 2),
             "blink": (self.time % 3.9) < 0.12, "talk": 0.5 + 0.5 * math.sin(ph), "hair": math.sin(ph / 2 - 0.9)}
        if move == "mic_pump":
            p.update(r_up=100, r_lo=200 + 8 * s, l_up=125 + 30 * s, l_lo=160 + 20 * s)
        elif move == "sway":
            p.update(l_up=18 + 18 * s, l_lo=30 + 22 * s, r_up=18 - 18 * s, r_lo=30 - 22 * s)
        elif move == "point":
            p.update(tilt=8 * abs(s) - 4, r_up=60, r_lo=150 + 10 * s, l_up=12, l_lo=-30)
        elif move == "headbang":
            p.update(tilt=14 * s, l_up=150, l_lo=170 + 12 * s, r_up=150, r_lo=170 - 12 * s)
        elif move == "drum":
            hit = max(0.0, s)
            p.update(l_up=32, l_lo=-35 + 55 * hit, r_up=32, r_lo=-35 + 55 * (1 - hit))
        elif move == "fist":
            p.update(r_up=158 + 14 * s, r_lo=175 + 10 * s, l_up=18, l_lo=-30)
        elif move == "write":
            scrib = math.sin(ph * 4)
            p.update(l_up=38, l_lo=-70, r_up=28 + 4 * scrib, r_lo=-72 + 10 * scrib)
        elif move == "robot":
            up = s > 0
            p.update(l_up=90, l_lo=180 if up else 90, r_up=90, r_lo=90 if up else 180, tilt=7 if up else -7, bob=0.3)
        return p

    # ---- main draw ------------------------------------------------------------------------
    def draw(self):
        c = self.canvas
        c.delete(self.tag)
        sp = self.s
        x0, ground = self.anchor
        H = self.height
        u = H / 9.4                        # about 4.5 heads tall: anime proportions, not chibi
        self.lw = max(1.5, u * 0.07)
        p = self._pose()
        self.u, self.p = u, p
        acc = self.accent
        top = sp["top"]
        if top in ("accent", "hoodie"):
            self.top_col = blend(acc, "#000000", 0.25)   # outfit in the page colour
        elif top == "blazer":
            self.top_col = "#26262e"
        elif top == "polka":
            self.top_col = sp["top_color"]
        else:
            self.top_col = top                           # a plain colour

        hip_x = x0 + p["sway"] * 0.3 * u
        hip_y = ground - 3.75 * u + p["bob"] * 0.25 * u
        sh_x = hip_x + p["sway"] * 0.12 * u
        sh_y = hip_y - 2.3 * u
        neck = (sh_x, sh_y - 0.05 * u)
        r = 1.12 * u                       # head radius
        tilt = math.radians(p["tilt"])

        def hp(dx, dy):
            """Point on the head (offset from head centre), rotated by head tilt around the neck."""
            ox, oy = dx, dy - 0.22 * u - r
            return (neck[0] + ox * math.cos(tilt) - oy * math.sin(tilt),
                    neck[1] + ox * math.sin(tilt) + oy * math.cos(tilt))
        self.hp, self.r = hp, r

        # floor glow (+ extra glow when highlighted on the Home line-up)
        hl = self.highlight
        for i in range(3, 0, -1):
            w = (1.3 + i * 0.3 + hl * 0.5) * u
            self._oval(x0, ground, w, 0.12 * u * i, dim(acc, 0.08 + 0.06 * (3 - i) + 0.15 * hl))

        self._back_hair(hp, u, r, p)
        self._legs(hip_x, hip_y, ground, u, p)
        self._torso(sh_x, sh_y, hip_x, hip_y, u)
        hands = self._arms(sh_x, sh_y, u, p)
        # neck
        self._line([neck[0], neck[1] + 0.25 * u, *hp(0, 0.75 * r)], blend(sp["skin"], "#000000", 0.12), u * 0.42)
        if sp.get("choker"):
            nx, ny = hp(0, 1.0 * r)
            self._line([nx - 0.2 * u, ny, nx + 0.2 * u, ny], LINE, u * 0.1)
        self._collar(sh_x, sh_y, u)
        self._head(hp, u, r, p)
        self._props(hands, u)

    # ---- body parts --------------------------------------------------------------------------
    def _legs(self, hip_x, hip_y, ground, u, p):
        sp = self.s
        seg = 1.85 * u
        style = sp["bottom_style"]
        for side in (-1, 1):
            hip = (hip_x + side * 0.32 * u, hip_y)
            foot = (self.anchor[0] + side * 0.45 * u + side * p["step"] * 0.14 * u, ground - 0.12 * u)
            if style == "long_skirt":
                # only the ankles show below a long skirt
                hem_y = hip_y + 3.0 * u
                t = (hem_y - hip[1]) / max(1e-6, foot[1] - hip[1])
                hip = (hip[0] + (foot[0] - hip[0]) * t, hem_y)
                knee = ((hip[0] + foot[0]) / 2, (hip[1] + foot[1]) / 2)
            else:
                knee = self._knee(hip, foot, seg, -side)
            col = sp["bottom"] if style == "pants" else self.s["skin"]
            self._line([*hip, *knee, *foot], LINE, u * 0.62, smooth=False)
            self._line([*hip, *knee, *foot], col, u * 0.48, smooth=False)
            fx, fy = foot
            shoe = "#f2f2f6" if self.role in ("artist", "producer") else "#121216"
            self._oval(fx + side * 0.12 * u, fy, 0.36 * u, 0.16 * u, shoe, LINE, self.lw)
        if style in ("skirt", "long_skirt"):
            length = 1.3 if style == "skirt" else 3.15
            w_top, w_bot = 0.62 * u, (1.15 if style == "skirt" else 1.0) * u
            sw = p["sway"] * 0.15 * u
            pts = [hip_x - w_top, hip_y - 0.2 * u, hip_x + w_top, hip_y - 0.2 * u,
                   hip_x + w_bot + sw, hip_y + length * u, hip_x - w_bot + sw, hip_y + length * u]
            self._poly(pts, sp["bottom"], smooth=False)
            for k in (-0.4, 0.05, 0.5):  # pleats / folds
                self._line([hip_x + k * w_top, hip_y, hip_x + k * w_bot + sw, hip_y + length * u * 0.95],
                           blend(sp["bottom"], "#000000", 0.35), max(1, u * 0.04), smooth=False)

    def _torso(self, sx, sy, hx, hy, u):
        sp = self.s
        sw, ww, bw = 0.95 * u, 0.6 * u, 0.72 * u  # shoulders, waist, hips
        pts = [sx - sw, sy + 0.1 * u, sx - sw * 0.98, sy + 0.05 * u, sx + sw * 0.98, sy + 0.05 * u, sx + sw, sy + 0.1 * u,
               (sx + hx) / 2 + ww, (sy + hy) / 2 + 0.3 * u, hx + bw, hy + 0.05 * u,
               hx - bw, hy + 0.05 * u, (sx + hx) / 2 - ww, (sy + hy) / 2 + 0.3 * u]
        top = sp["top"]
        fill = self.top_col
        if top == "hoodie":
            pts = [sx - sw * 1.1, sy + 0.1 * u, sx + sw * 1.1, sy + 0.1 * u, hx + bw * 1.25, hy + 0.35 * u,
                   hx - bw * 1.25, hy + 0.35 * u]
        self._poly(pts, fill, smooth=False)
        if top == "blazer":
            # white shirt + tie in the V, lapels
            self._poly([sx - 0.32 * u, sy + 0.05 * u, sx + 0.32 * u, sy + 0.05 * u, sx, sy + 1.25 * u], "#f4f4f8",
                       smooth=False)
            self._poly([sx - 0.09 * u, sy + 0.2 * u, sx + 0.09 * u, sy + 0.2 * u, sx + 0.13 * u, sy + 1.05 * u,
                        sx, sy + 1.25 * u, sx - 0.13 * u, sy + 1.05 * u], sp["tie"], smooth=False)
            for side in (-1, 1):
                self._line([sx + side * 0.32 * u, sy + 0.05 * u, sx + side * 0.12 * u, sy + 1.3 * u], LINE,
                           max(1, u * 0.05), smooth=False)
        elif top == "hoodie":
            self._line([sx - 0.9 * u, hy - 0.2 * u, sx + 0.9 * u, hy - 0.2 * u], blend(fill, "#000000", 0.4),
                       max(1, u * 0.06))
            self._poly([sx - 0.55 * u, (sy + hy) / 2 + 0.2 * u, sx + 0.55 * u, (sy + hy) / 2 + 0.2 * u,
                        sx + 0.65 * u, hy - 0.2 * u, sx - 0.65 * u, hy - 0.2 * u], blend(fill, "#000000", 0.18),
                       smooth=False)  # front pocket
            for dx in (-0.2, 0.2):
                self._line([sx + dx * u, sy + 0.1 * u, sx + dx * u, sy + 0.8 * u], "#f0f0f4", max(1, u * 0.05))
            self._line([sx - 0.5 * u, sy + 0.95 * u, sx + 0.5 * u, sy + 0.95 * u], self.accent2, max(2, u * 0.1))
        elif top == "polka":
            # polka dots + a patterned dupatta draped over one shoulder (reference 1)
            for row in range(5):
                ty = sy + 0.35 * u + row * 0.5 * u
                t = (ty - sy) / (hy - sy)
                half = sw + (bw - sw) * t - 0.25 * u
                n = 4
                for k in range(n):
                    tx = sx - half + (2 * half) * (k + (0.5 if row % 2 else 0.0)) / n
                    if abs(tx - sx) < half:
                        self._oval(tx, ty, 0.09 * u, 0.09 * u, "#a49c86")
            self._poly([sx - sw, sy + 0.1 * u, sx - sw * 0.35, sy + 0.05 * u, hx + bw * 0.1, hy + 0.1 * u,
                        hx - bw * 0.55, hy + 0.15 * u], "#8c8467", smooth=False)
            self._line([sx - sw * 0.35, sy + 0.05 * u, hx + bw * 0.1, hy + 0.1 * u], "#d8c79a", max(1, u * 0.06),
                       smooth=False)
        else:
            # glowing accent stripe on plain tops
            self._line([sx - 0.7 * u, sy + 1.0 * u, sx + 0.7 * u, sy + 1.0 * u], self.accent2, max(2, u * 0.08))

    def _collar(self, sx, sy, u):
        """Neckline drawn over the neck so the top looks worn, not pasted on."""
        top = self.s["top"]
        if top in ("blazer", "hoodie"):
            return
        self.canvas.create_arc(sx - 0.38 * u, sy - 0.25 * u, sx + 0.38 * u, sy + 0.35 * u, start=200, extent=140,
                               style="arc", outline=LINE, width=self.lw, tags=self.tag)

    def _arms(self, sx, sy, u, p):
        sp = self.s
        hands = {}
        sleeve = self.top_col if sp["top"] != "blazer" else "#26262e"
        long_sleeve = sp["top"] in ("blazer", "hoodie", "polka") or self.role in ("tech", "engineer")
        for side, up, lo in ((-1, p["l_up"], p["l_lo"]), (1, p["r_up"], p["r_lo"])):
            s0 = (sx + side * 0.88 * u, sy + 0.25 * u)
            e = self._limb(*s0, 1.3 * u, side * up)
            h = self._limb(*e, 1.2 * u, side * lo)
            self._line([*s0, *e, *h], LINE, u * 0.46, smooth=False)
            self._line([*s0, *e], sleeve, u * 0.34)
            self._line([*e, *h], sleeve if long_sleeve else sp["skin"], u * 0.29)
            self._oval(*h, 0.2 * u, 0.2 * u, sp["skin"], LINE, self.lw)
            hands[side] = (h, e)
        return hands

    # ---- hair (behind the head) ----------------------------------------------------------------------
    def _back_hair(self, hp, u, r, p):
        sp, style = self.s, self.s["style"]
        hair = sp["hair"]
        sway = p["hair"] * 0.25 * u
        if style in ("ribbons", "clips"):
            L = 4.6 * u
            pts = [*hp(-1.08 * r, -0.4 * r), *hp(-1.25 * r, 0.9 * r), *hp(-1.15 * r + sway, L * 0.7),
                   *hp(-0.7 * r + sway, L), *hp(0.7 * r + sway, L), *hp(1.15 * r + sway, L * 0.7),
                   *hp(1.25 * r, 0.9 * r), *hp(1.08 * r, -0.4 * r)]
            self._poly(pts, blend(hair, "#000000", 0.2))
        elif style == "twintails":
            for side in (-1, 1):
                base = hp(side * 1.05 * r, 0.25 * r)
                pts = [*base, *hp(side * 1.5 * r + sway, 1.4 * r), *hp(side * 1.5 * r + sway, 2.7 * r),
                       *hp(side * 1.22 * r + sway, 3.3 * r), *hp(side * 0.98 * r + sway, 2.6 * r),
                       *hp(side * 0.85 * r, 1.0 * r)]
                self._poly(pts, hair)
                # dark wine-red ombre tips (reference 5): two steps so it fades
                for frac, col in ((0.0, blend(hair, sp["tips"], 0.55)), (0.45, sp["tips"])):
                    y1 = 2.25 + frac * 0.8
                    tip = [*hp(side * 1.5 * r + sway, y1 * r), *hp(side * 1.5 * r + sway, 2.7 * r),
                           *hp(side * 1.22 * r + sway, 3.3 * r), *hp(side * 0.98 * r + sway, 2.6 * r),
                           *hp(side * 1.0 * r + sway, y1 * r)]
                    self._poly(tip, col, outline="")
        elif style == "bob":
            pts = [*hp(-1.12 * r, -0.5 * r), *hp(-1.22 * r, 0.6 * r), *hp(-1.12 * r + sway * 0.3, 1.25 * r),
                   *hp(1.12 * r + sway * 0.3, 1.25 * r), *hp(1.22 * r, 0.6 * r), *hp(1.12 * r, -0.5 * r)]
            self._poly(pts, blend(hair, "#9fa3c8", 0.25), smooth=False)
        elif style == "braid":
            pts = [*hp(-1.05 * r, -0.4 * r), *hp(-1.15 * r, 0.9 * r), *hp(-0.8 * r, 1.4 * r),
                   *hp(0.8 * r, 1.4 * r), *hp(1.15 * r, 0.9 * r), *hp(1.05 * r, -0.4 * r)]
            self._poly(pts, blend(hair, "#000000", 0.2))
        elif style == "ponytail":
            top = hp(0.2 * r, -1.0 * r)
            pts = [*top, *hp(1.0 * r + sway, -1.2 * r), *hp(1.4 * r + sway, 0.2 * r),
                   *hp(1.2 * r + sway * 1.5, 1.8 * r), *hp(0.75 * r + sway, 0.4 * r), *hp(0.4 * r, -0.6 * r)]
            self._poly(pts, hair)

    # ---- head, face, front hair -------------------------------------------------------------------------
    def _head(self, hp, u, r, p):
        sp = self.s
        skin = sp["skin"]
        # anime face: round cranium, cheeks tapering to a soft pointed chin
        face = [*hp(-0.95 * r, -0.25 * r), *hp(-0.88 * r, -0.8 * r), *hp(-0.4 * r, -1.05 * r),
                *hp(0.4 * r, -1.05 * r), *hp(0.88 * r, -0.8 * r), *hp(0.95 * r, -0.25 * r),
                *hp(0.86 * r, 0.35 * r), *hp(0.5 * r, 0.78 * r), *hp(0.0, 0.98 * r),
                *hp(-0.5 * r, 0.78 * r), *hp(-0.86 * r, 0.35 * r)]
        self._poly(face, skin)
        # ears
        for side in (-1, 1):
            ex, ey = hp(side * 0.95 * r, 0.05 * r)
            self._oval(ex, ey, 0.14 * r, 0.22 * r, skin, LINE, self.lw)
            if sp.get("earrings"):  # big gold chandbali earrings (reference 1)
                gx, gy = hp(side * 0.98 * r, 0.42 * r)
                self._oval(gx, gy + 0.18 * r, 0.2 * r, 0.22 * r, "", "#d9b04a", max(2, u * 0.08))
                self._oval(gx, gy + 0.2 * r, 0.1 * r, 0.1 * r, "#d9b04a")
            if self.role == "executive" and side == 1:  # ear piercings (reference 5)
                for k in range(2):
                    px, py = hp(1.02 * r, (-0.08 + k * 0.17) * r)
                    self._oval(px, py, 0.035 * r, 0.035 * r, "#e8e8ee")
        self._face(hp, u, r, p)
        self._front_hair(hp, u, r, p)
        self._head_extras(hp, u, r)

    def _face(self, hp, u, r, p):
        sp = self.s
        c = self.canvas
        lw = self.lw
        eye_y = 0.12 * r
        for side in (-1, 1):
            ex, ey = hp(side * 0.42 * r, eye_y)
            w, h = 0.24 * r, 0.3 * r
            if p["blink"]:
                self._line([ex - w * 1.1, ey + 0.05 * r, ex, ey + 0.12 * r, ex + w * 1.1, ey + 0.05 * r], LINE,
                           max(2, u * 0.09))
                continue
            # white of the eye
            self._oval(ex, ey, w, h, WHITE)
            # iris: dark rim, colour, lighter lower half (gloss)
            ix = ex - side * 0.03 * r
            self._oval(ix, ey + 0.03 * r, w * 0.82, h * 0.92, blend(sp["eyes"], "#000000", 0.45))
            self._oval(ix, ey + 0.06 * r, w * 0.68, h * 0.78, sp["eyes"])
            self._oval(ix, ey + 0.16 * r, w * 0.5, h * 0.42, blend(sp["eyes"], "#ffffff", 0.35))
            self._oval(ix, ey + 0.02 * r, w * 0.3, h * 0.36, blend(sp["eyes"], "#000000", 0.7))
            # sparkle highlights
            self._oval(ix - side * 0.08 * r, ey - 0.08 * r, w * 0.24, h * 0.2, WHITE)
            self._oval(ix + side * 0.09 * r, ey + 0.13 * r, w * 0.11, h * 0.09, WHITE)
            # heavy upper lash line with a flick at the outer corner
            lash = [ex - side * w * 1.05, ey - h * 0.35, ex - side * w * 0.3, ey - h * 1.02,
                    ex + side * w * 0.5, ey - h * 1.0, ex + side * w * 1.2, ey - h * 0.55,
                    ex + side * w * 1.35, ey - h * 0.85]
            self._line(lash, LINE, max(2.5, u * 0.11))
            if sp.get("lashes"):  # spiky lashes (reference 4)
                for k in range(3):
                    bx = ex + side * w * (0.4 + k * 0.3)
                    self._line([bx, ey - h * 0.95, bx + side * w * 0.35, ey - h * 1.35], LINE, max(1.5, u * 0.05))
                    lx = ex + side * w * (-0.2 + k * 0.4)
                    self._line([lx, ey + h * 0.95, lx + side * w * 0.15, ey + h * 1.25], LINE, max(1, u * 0.03))
            # lower lid
            c.create_arc(ex - w * 0.9, ey - h * 0.3, ex + w * 0.9, ey + h * 1.0, start=225 if side < 0 else 260,
                         extent=55, style="arc", outline=LINE, width=max(1, lw * 0.6), tags=self.tag)
            # eyebrows
            if sp["brows"] != "none":
                bw = max(2, u * (0.12 if sp["brows"] == "thick" else 0.06))
                bx, by = hp(side * 0.42 * r, -0.33 * r)
                self._line([bx - side * 0.22 * r, by + 0.05 * r, bx, by - 0.04 * r, bx + side * 0.25 * r, by + 0.02 * r],
                           blend(sp["hair"], "#000000", 0.3) if sp["style"] != "bob" else "#b8b9d6", bw)
            # blush (+ the little hatch lines from references 4 and 5)
            blx, bly = hp(side * 0.55 * r, 0.42 * r)
            self._oval(blx, bly, 0.2 * r, 0.08 * r, blend(sp["skin"], "#ff5c7a", 0.35))
            if sp.get("blush_lines") or self.role == "executive":
                for k in range(3):
                    hx = blx - 0.1 * r + k * 0.09 * r
                    self._line([hx, bly - 0.05 * r, hx - 0.04 * r, bly + 0.05 * r], blend(sp["skin"], "#e0405c", 0.6), 1)
        # nose: tiny shadow stroke
        nx, ny = hp(0.03 * r, 0.42 * r)
        self._line([nx, ny - 0.06 * r, nx - 0.04 * r, ny + 0.03 * r], blend(sp["skin"], "#000000", 0.35), max(1, lw * 0.7))
        self._mouth(hp, u, r, p)
        if sp.get("bindi"):
            bx, by = hp(0, -0.38 * r)
            self._oval(bx, by, 0.06 * r, 0.06 * r, "#1a0f14")

    def _mouth(self, hp, u, r, p):
        sp = self.s
        mx, my = hp(0, 0.66 * r)
        kind = sp["mouth"]
        talk = p["talk"]
        lip = blend(sp["skin"], "#a23a3a", 0.5)
        if kind == "o":
            self._oval(mx, my, 0.06 * r, (0.05 + 0.04 * talk) * r, "#8a2f3d", LINE, max(1, self.lw * 0.6))
        elif kind == "grin":  # big open smile with tongue (reference 5)
            open_h = (0.14 + 0.08 * talk) * r
            self._poly([mx - 0.2 * r, my - 0.05 * r, mx + 0.2 * r, my - 0.05 * r, mx + 0.1 * r, my + open_h,
                        mx - 0.1 * r, my + open_h], "#7b2234", smooth=True)
            self._oval(mx, my + open_h * 0.7, 0.09 * r, 0.05 * r, "#e88a9a")
        elif kind == "smug":  # cat-like smirk (reference 3)
            self._line([mx - 0.18 * r, my - 0.02 * r, mx - 0.07 * r, my + 0.05 * r, mx, my, mx + 0.07 * r,
                        my + 0.05 * r, mx + 0.18 * r, my - 0.04 * r], LINE, max(1.5, u * 0.05))
        elif kind == "smile":
            self._line([mx - 0.15 * r, my - 0.02 * r, mx, my + 0.07 * r, mx + 0.15 * r, my - 0.02 * r], LINE,
                       max(1.5, u * 0.05))
        elif kind == "flat":  # deadpan (reference 4)
            self._line([mx - 0.06 * r, my + 0.02 * r, mx + 0.06 * r, my], LINE, max(1.5, u * 0.045), smooth=False)
        else:  # neutral full lips (reference 1)
            self._poly([mx - 0.16 * r, my, mx, my - 0.05 * r, mx + 0.16 * r, my, mx, my + 0.09 * r], lip)
            self._line([mx - 0.15 * r, my + 0.01 * r, mx + 0.15 * r, my + 0.01 * r], blend(lip, "#000000", 0.4),
                       max(1, u * 0.03), smooth=False)

    def _front_hair(self, hp, u, r, p):
        sp, style = self.s, self.s["style"]
        hair, hi = sp["hair"], sp["hair_hi"]
        sway = p["hair"] * 0.12 * u
        if style == "bob":
            # blunt straight bangs + straight sides (reference 4)
            top = [*hp(-1.12 * r, 0.75 * r), *hp(-1.12 * r, -0.55 * r), *hp(-0.9 * r, -1.08 * r),
                   *hp(0, -1.25 * r), *hp(0.9 * r, -1.08 * r), *hp(1.12 * r, -0.55 * r), *hp(1.12 * r, 0.75 * r),
                   *hp(0.85 * r, 0.75 * r), *hp(0.8 * r, -0.22 * r), *hp(-0.8 * r, -0.22 * r), *hp(-0.85 * r, 0.75 * r)]
            self._poly(top, hair, smooth=False)
            for k in range(-3, 4):
                x = k * 0.22 * r
                self._line([*hp(x, -0.85 * r), *hp(x + 0.02 * r, -0.24 * r)], blend(hair, "#8c90c0", 0.45), 1, smooth=False)
        else:
            # pointed anime bangs; middle part for the braid style (reference 1)
            if style == "braid":
                bangs = [*hp(-1.1 * r, 0.5 * r), *hp(-1.08 * r, -0.5 * r), *hp(-0.7 * r, -1.1 * r), *hp(0, -1.2 * r),
                         *hp(0.7 * r, -1.1 * r), *hp(1.08 * r, -0.5 * r), *hp(1.1 * r, 0.5 * r),
                         *hp(0.86 * r, 0.1 * r), *hp(0.55 * r, -0.65 * r), *hp(0.05 * r, -0.95 * r),
                         *hp(-0.05 * r, -0.95 * r), *hp(-0.55 * r, -0.65 * r), *hp(-0.86 * r, 0.1 * r)]
            else:
                bangs = [*hp(-1.12 * r, 0.6 * r), *hp(-1.1 * r, -0.55 * r), *hp(-0.75 * r, -1.12 * r),
                         *hp(0, -1.25 * r), *hp(0.75 * r, -1.12 * r), *hp(1.1 * r, -0.55 * r), *hp(1.12 * r, 0.6 * r),
                         *hp(0.9 * r, -0.05 * r), *hp(0.78 * r, -0.2 * r), *hp(0.55 * r, 0.05 * r),
                         *hp(0.4 * r, -0.4 * r), *hp(0.18 * r, -0.1 * r), *hp(0.02 * r, -0.5 * r),
                         *hp(-0.2 * r, -0.12 * r), *hp(-0.38 * r, -0.42 * r), *hp(-0.6 * r, 0.02 * r),
                         *hp(-0.78 * r, -0.25 * r), *hp(-0.92 * r, -0.05 * r)]
            self._poly(bangs, hair, smooth=False)
            # long side locks framing the face
            for side in (-1, 1):
                if style == "braid" and side == 1:
                    continue
                lock = [*hp(side * 0.9 * r, -0.2 * r), *hp(side * 1.1 * r, 0.5 * r),
                        *hp(side * 1.0 * r + sway, 1.8 * r), *hp(side * 0.86 * r + sway, 2.3 * r),
                        *hp(side * 0.82 * r, 1.0 * r), *hp(side * 0.78 * r, 0.2 * r)]
                self._poly(lock, hair)
        # glossy shine band across the crown (in every reference)
        self._line([*hp(-0.62 * r, -0.92 * r), *hp(-0.25 * r, -1.06 * r), *hp(0.15 * r, -1.07 * r)], hi,
                   max(2, u * 0.12))
        self._line([*hp(0.35 * r, -1.02 * r), *hp(0.55 * r, -0.96 * r)], hi, max(2, u * 0.1))
        if style == "braid":  # thick braid over the right shoulder
            x0, y0 = hp(0.95 * r, 0.6 * r)
            for k in range(7):
                bx = x0 + 0.05 * u * k + sway * k * 0.1
                by = y0 + k * 0.42 * u
                self._oval(bx, by, 0.26 * u, 0.24 * u, hair, LINE, self.lw)
                self._line([bx - 0.18 * u, by - 0.05 * u, bx + 0.12 * u, by + 0.12 * u], hi, max(1, u * 0.04))

    def _head_extras(self, hp, u, r):
        sp = self.s
        style = sp["style"]
        if style == "ribbons":  # pink ribbons on both sides (reference 2)
            for side in (-1, 1):
                bx, by = hp(side * 0.95 * r, -0.85 * r)
                for flip in (-1, 1):
                    self._poly([bx, by, bx + flip * 0.38 * r, by - 0.22 * r, bx + flip * 0.38 * r, by + 0.18 * r],
                               sp["ribbon"], smooth=False)
                self._oval(bx, by, 0.08 * r, 0.08 * r, blend(sp["ribbon"], "#000000", 0.2), LINE, self.lw)
                self._poly([bx, by, bx - 0.1 * r, by + 0.55 * r, bx + 0.06 * r, by + 0.5 * r], sp["ribbon"],
                           smooth=False)
        elif style == "clips":  # two silver hair clips (reference 3)
            for k in range(2):
                cx, cy = hp(-0.62 * r + k * 0.1 * r, -0.72 * r + k * 0.16 * r)
                self._line([cx - 0.16 * r, cy - 0.06 * r, cx + 0.16 * r, cy + 0.06 * r], "#dadce6", max(2, u * 0.1),
                           smooth=False)
        if sp.get("glasses"):  # thick black frames (reference 5)
            for side in (-1, 1):
                gx, gy = hp(side * 0.42 * r, 0.12 * r)
                self.canvas.create_rectangle(gx - 0.33 * r, gy - 0.3 * r, gx + 0.33 * r, gy + 0.3 * r, outline=LINE,
                                             width=max(2, u * 0.09), tags=self.tag)
            self._line([*hp(-0.09 * r, 0.05 * r), *hp(0.09 * r, 0.05 * r)], LINE, max(2, u * 0.07), smooth=False)
        if sp.get("headphones"):
            band = [*hp(-1.15 * r, 0.0), *hp(-1.05 * r, -1.0 * r), *hp(0, -1.4 * r), *hp(1.05 * r, -1.0 * r),
                    *hp(1.15 * r, 0.0)]
            self._line(band, LINE, u * 0.26)
            self._line(band, "#2b2b36", u * 0.15)
            for side in (-1, 1):
                ex, ey = hp(side * 1.12 * r, 0.1 * r)
                self._oval(ex, ey, 0.26 * r, 0.42 * r, self.accent, LINE, self.lw)
                self._oval(ex, ey, 0.13 * r, 0.22 * r, self.accent2)
        if sp.get("visor"):
            pts = [*hp(-1.08 * r, -0.08 * r), *hp(1.08 * r, -0.08 * r), *hp(1.02 * r, 0.32 * r), *hp(-1.02 * r, 0.32 * r)]
            self._poly(pts, dim(self.accent2, 0.55), outline=self.accent2, smooth=False)
            self._line([*hp(-0.8 * r, 0.02 * r), *hp(-0.2 * r, 0.02 * r)], WHITE, max(1, u * 0.04), smooth=False)

    # ---- props in hand ---------------------------------------------------------------------------------
    def _props(self, hands, u):
        (rh, re), (lh, le) = hands[1], hands[-1]
        role = self.role
        if role == "artist":  # microphone
            ang = math.atan2(rh[1] - re[1], rh[0] - re[0])
            tip = (rh[0] + math.cos(ang) * 0.6 * u, rh[1] + math.sin(ang) * 0.6 * u)
            self._line([*rh, *tip], "#1b1b22", u * 0.2)
            self._oval(*tip, 0.24 * u, 0.24 * u, "#c9d2e0", LINE, self.lw)
        elif role == "executive":  # pointing finger (reference 5) + phone in the other hand
            ang = math.atan2(rh[1] - re[1], rh[0] - re[0])
            self._line([*rh, rh[0] + math.cos(ang) * 0.32 * u, rh[1] + math.sin(ang) * 0.32 * u], self.s["skin"],
                       u * 0.09)
            self.canvas.create_rectangle(lh[0] - 0.15 * u, lh[1] - 0.35 * u, lh[0] + 0.15 * u, lh[1] + 0.08 * u,
                                         fill="#0d0d12", outline=self.accent, width=max(1, self.lw - 0.5), tags=self.tag)
        elif role == "producer":  # drumsticks
            for h, e in ((rh, re), (lh, le)):
                ang = math.atan2(h[1] - e[1], h[0] - e[0])
                self._line([*h, h[0] + math.cos(ang) * 1.0 * u, h[1] + math.sin(ang) * 1.0 * u], "#e8c890",
                           max(2, u * 0.09))
        elif role == "songwriter":  # notebook + pencil
            x, y = lh
            self._poly([x - 0.45 * u, y - 0.65 * u, x + 0.3 * u, y - 0.72 * u, x + 0.38 * u, y + 0.3 * u,
                        x - 0.37 * u, y + 0.38 * u], "#f8f4e8", smooth=False)
            for k in range(4):
                yy = y - 0.45 * u + k * 0.19 * u
                self._line([x - 0.3 * u, yy, x + 0.24 * u, yy - 0.04 * u], self.accent, 1, smooth=False)
            x2, y2 = rh
            self._line([x2, y2, x2 - 0.42 * u, y2 - 0.42 * u], "#ffcc33", max(2, u * 0.1))
        elif role == "tech":  # glowing cable
            self._line([*lh, lh[0] - 0.5 * u, lh[1] + 0.7 * u, lh[0] - 0.15 * u, lh[1] + 1.4 * u], self.accent2,
                       max(2, u * 0.08))
