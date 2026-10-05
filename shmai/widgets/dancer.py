"""
Dancing anime-style (chibi) character, drawn live on a page's canvas.

Like the dancing-character plugins in FL Studio: a little figure grooves in
the corner of every page. Each page gets a character that fits its role:

    artist      Home            microphone, long pink hair, cropped jacket
    executive   Beat Finder     sunglasses, suit, tie and gold chain
    engineer    Audio Analyzer  big studio headphones, hoodie
    producer    Melody Gen      backwards cap, drumstick, headphones on neck
    songwriter  Song Writer     beret, notebook and pencil
    tech        Clarity         holo-visor and cable

There's no text label underneath, as requested. Everything is vector shapes,
so no image files are needed and it stays sharp at any size.
"""
import math

from ..theme import blend, dim

OUTLINE = "#140c1c"
SKIN = "#ffdcc4"
SKIN_SHADE = "#f2bba0"

ROLES = {
    #             hair color  outfit (None = page accent)  dance tempo (BPM)
    "artist":     {"hair": "#ff6fb5", "outfit": None, "bpm": 116, "moves": ("mic_pump", "sway")},
    "executive":  {"hair": "#2a1d2e", "outfit": "#151520", "bpm": 98, "moves": ("nod_point", "sway")},
    "engineer":   {"hair": "#5b3cc4", "outfit": None, "bpm": 108, "moves": ("headbang", "sway")},
    "producer":   {"hair": "#3a2418", "outfit": None, "bpm": 124, "moves": ("drum", "fist")},
    "songwriter": {"hair": "#f4c36a", "outfit": None, "bpm": 92, "moves": ("write", "sway")},
    "tech":       {"hair": "#c8d6ff", "outfit": "#1c2433", "bpm": 112, "moves": ("robot", "sway")},
}


class Dancer:
    def __init__(self, canvas, role, accent, accent2):
        self.canvas = canvas
        self.role = role if role in ROLES else "artist"
        self.spec = ROLES[self.role]
        self.accent = accent
        self.accent2 = accent2
        self.outfit = self.spec["outfit"] or blend(accent, "#000000", 0.35)
        self.time = 0.0
        self.anchor = (0, 0)  # (x of feet center, y of ground)
        self.height = 220
        self.tag = f"dancer{id(self)}"  # unique, so several dancers can share a canvas

    def place(self, x, y, height):
        self.anchor = (x, y)
        self.height = height

    # ---- small math helpers ------------------------------------------------
    @staticmethod
    def _limb(x, y, length, angle_deg):
        a = math.radians(angle_deg)
        return x + length * math.sin(a), y + length * math.cos(a)

    @staticmethod
    def _knee(hip, foot, seg, out_dir):
        """Simple 2-bone leg: find the knee so both bones keep their length."""
        hx, hy = hip
        fx, fy = foot
        d = math.hypot(fx - hx, fy - hy)
        mx, my = (hx + fx) / 2, (hy + fy) / 2
        bend = math.sqrt(max(0.0, seg * seg - (d / 2) ** 2))
        if d == 0:
            return mx, my
        nx, ny = -(fy - hy) / d, (fx - hx) / d  # perpendicular
        return mx + nx * bend * out_dir, my + ny * bend * out_dir

    # ---- animation -----------------------------------------------------------
    def tick(self, dt):
        self.time += dt
        self.draw()

    def _pose(self):
        """Work out joint angles for this moment of the dance."""
        bps = self.spec["bpm"] / 60.0
        beat = self.time * bps
        ph = beat * 2 * math.pi
        # Switch between the role's two dance moves every 8 beats.
        move = self.spec["moves"][int(beat // 8) % 2]
        p = {
            "bob": abs(math.sin(ph / 2)),  # dips on every beat
            "sway": math.sin(ph / 2),      # side to side every 2 beats
            "tilt": 7 * math.sin(ph / 2 + 0.6),
            "l_up": 25, "l_lo": 15, "r_up": 25, "r_lo": 15,
            "step": math.sin(ph / 2),
            "blink": (self.time % 3.7) < 0.13,
            "mouth": 0.5 + 0.5 * math.sin(ph),
        }
        # Arm angles are degrees measured from "hanging straight down":
        # 90 = sticking straight out sideways, 180 = straight up,
        # negative = swinging inward across the body.
        s = math.sin(ph)
        if move == "mic_pump":       # mic hand at the mouth, other arm waves
            p.update(r_up=105, r_lo=205 + 8 * s, l_up=130 + 30 * s, l_lo=160 + 20 * s)
        elif move == "sway":         # relaxed arm swing
            p.update(l_up=20 + 20 * s, l_lo=35 + 25 * s, r_up=20 - 20 * s, r_lo=35 - 25 * s)
        elif move == "nod_point":    # cool head nod with a point
            p.update(tilt=10 * abs(s) - 5, r_up=95, r_lo=100 + 15 * s, l_up=15, l_lo=-25)
        elif move == "headbang":     # both hands up
            p.update(tilt=16 * s, l_up=150, l_lo=170 + 12 * s, r_up=150, r_lo=170 - 12 * s)
        elif move == "drum":         # hits an invisible drum pad
            hit = max(0.0, s)
            p.update(l_up=35, l_lo=-35 + 55 * hit, r_up=35, r_lo=-35 + 55 * (1 - hit))
        elif move == "fist":         # fist pump
            p.update(r_up=160 + 15 * s, r_lo=175 + 10 * s, l_up=20, l_lo=-30)
        elif move == "write":        # notebook up, pencil scribbles
            scrib = math.sin(ph * 4)
            p.update(l_up=40, l_lo=-65, r_up=30 + 4 * scrib, r_lo=-70 + 10 * scrib)
        elif move == "robot":        # stiff robot arms
            up = s > 0
            p.update(l_up=90, l_lo=180 if up else 90, r_up=90, r_lo=90 if up else 180,
                     tilt=8 if up else -8, bob=0.3)
        return p

    def draw(self):
        c = self.canvas
        c.delete(self.tag)
        x0, ground = self.anchor
        u = self.height / 8.0
        p = self._pose()

        hip_x = x0 + p["sway"] * 0.35 * u
        hip_y = ground - 2.05 * u + p["bob"] * 0.32 * u
        sh_y = hip_y - 2.1 * u
        sh_x = hip_x + p["sway"] * 0.15 * u
        neck = (sh_x, sh_y - 0.1 * u)
        head_r = 1.55 * u
        tilt = math.radians(p["tilt"])

        def hp(dx, dy):
            """A point on the head, rotated by the head tilt around the neck."""
            hx = dx * math.cos(tilt) - dy * math.sin(tilt)
            hy = dx * math.sin(tilt) + dy * math.cos(tilt)
            return neck[0] + hx, neck[1] + hy

        head_c = hp(0, -1.35 * u)
        lw = max(2, u * 0.1)

        # --- floor glow ------------------------------------------------------
        for i in range(3, 0, -1):
            w = (1.6 + i * 0.35) * u
            c.create_oval(x0 - w, ground - 0.12 * u * i, x0 + w, ground + 0.12 * u * i,
                          fill=dim(self.accent, 0.08 + 0.06 * (3 - i)), outline="", tags=self.tag)

        # --- back hair (long styles) ----------------------------------------
        if self.role in ("artist", "songwriter", "engineer"):
            length = 2.4 if self.role == "artist" else 1.6
            pts = [*hp(-1.45 * u, -1.6 * u), *hp(-1.7 * u, -0.2 * u + length * 0.3 * u),
                   *hp(-1.2 * u, length * 0.55 * u), *hp(1.2 * u, length * 0.55 * u),
                   *hp(1.7 * u, -0.2 * u + length * 0.3 * u), *hp(1.45 * u, -1.6 * u)]
            c.create_polygon(pts, fill=blend(self.spec["hair"], "#000000", 0.25), outline=OUTLINE,
                             width=lw, smooth=True, tags=self.tag)

        # --- legs --------------------------------------------------------------
        seg = 1.12 * u
        for side in (-1, 1):
            hip = (hip_x + side * 0.42 * u, hip_y)
            foot = (x0 + side * 0.62 * u + side * p["step"] * 0.18 * u, ground - 0.15 * u)
            knee = self._knee(hip, foot, seg, -side)
            pant = "#20202c" if self.role in ("executive", "tech") else blend(self.outfit, "#101018", 0.55)
            c.create_line(*hip, *knee, *foot, fill=OUTLINE, width=u * 0.62, capstyle="round",
                          joinstyle="round", tags=self.tag)
            c.create_line(*hip, *knee, *foot, fill=pant, width=u * 0.48, capstyle="round",
                          joinstyle="round", tags=self.tag)
            # sneakers
            fx, fy = foot
            c.create_oval(fx - 0.48 * u + side * 0.12 * u, fy - 0.25 * u, fx + 0.48 * u + side * 0.12 * u,
                          fy + 0.2 * u, fill=self.accent2 if self.role != "executive" else "#0b0b0b",
                          outline=OUTLINE, width=lw, tags=self.tag)

        # --- torso -------------------------------------------------------------
        tw_top, tw_bot = 1.15 * u, 0.85 * u
        torso = [sh_x - tw_top, sh_y, sh_x + tw_top, sh_y, hip_x + tw_bot, hip_y + 0.15 * u,
                 hip_x - tw_bot, hip_y + 0.15 * u]
        c.create_polygon(torso, fill=self.outfit, outline=OUTLINE, width=lw, smooth=False, tags=self.tag)
        # outfit details
        if self.role == "executive":
            c.create_polygon(sh_x - 0.35 * u, sh_y, sh_x + 0.35 * u, sh_y, sh_x, sh_y + 1.1 * u,
                             fill="#f4f4f4", outline="", tags=self.tag)
            c.create_polygon(sh_x - 0.12 * u, sh_y + 0.1 * u, sh_x + 0.12 * u, sh_y + 0.1 * u,
                             sh_x + 0.16 * u, sh_y + 1.3 * u, sh_x, sh_y + 1.5 * u, sh_x - 0.16 * u,
                             sh_y + 1.3 * u, fill=self.accent, outline="", tags=self.tag)
            c.create_arc(sh_x - 0.7 * u, sh_y - 0.6 * u, sh_x + 0.7 * u, sh_y + 0.9 * u, start=200, extent=140,
                         style="arc", outline="#ffd44a", width=max(2, u * 0.12), tags=self.tag)
        else:
            # glowing stripe across the chest in the page color
            c.create_line(sh_x - tw_top * 0.9, sh_y + 0.75 * u, sh_x + tw_top * 0.9, sh_y + 0.75 * u,
                          fill=self.accent2, width=max(2, u * 0.16), tags=self.tag)
            if self.role == "engineer":  # hoodie strings
                for dx in (-0.25, 0.25):
                    c.create_line(sh_x + dx * u, sh_y + 0.05 * u, sh_x + dx * u, sh_y + 0.6 * u,
                                  fill="#ffffff", width=max(1, u * 0.06), tags=self.tag)

        # --- arms ----------------------------------------------------------------
        hands = {}
        for side, up, lo in ((-1, p["l_up"], p["l_lo"]), (1, p["r_up"], p["r_lo"])):
            s = (sh_x + side * (tw_top - 0.15 * u), sh_y + 0.18 * u)
            # side * angle: outward is to the left for the left arm, right for the right arm
            e = self._limb(*s, 1.05 * u, side * up)
            h = self._limb(*e, 1.0 * u, side * lo)
            c.create_line(*s, *e, *h, fill=OUTLINE, width=u * 0.5, capstyle="round", joinstyle="round", tags=self.tag)
            c.create_line(*s, *e, fill=self.outfit, width=u * 0.38, capstyle="round", tags=self.tag)
            c.create_line(*e, *h, fill=SKIN if self.role != "engineer" else self.outfit, width=u * 0.32,
                          capstyle="round", tags=self.tag)
            c.create_oval(h[0] - 0.22 * u, h[1] - 0.22 * u, h[0] + 0.22 * u, h[1] + 0.22 * u, fill=SKIN,
                          outline=OUTLINE, width=lw, tags=self.tag)
            hands[side] = (h, e)

        self._draw_hand_props(hands, u, lw)

        # --- neck + head ---------------------------------------------------------
        c.create_line(neck[0], neck[1] + 0.2 * u, *hp(0, -0.35 * u), fill=SKIN_SHADE, width=u * 0.45, tags=self.tag)
        hx, hy = head_c
        c.create_oval(hx - head_r, hy - head_r * 0.98, hx + head_r, hy + head_r * 0.95, fill=SKIN,
                      outline=OUTLINE, width=lw, tags=self.tag)
        self._draw_face(hp, u, lw, p)
        self._draw_hair_and_hat(hp, u, lw)

    # ---- face ------------------------------------------------------------------
    def _draw_face(self, hp, u, lw, p):
        c = self.canvas
        eye_y = -1.05 * u
        for side in (-1, 1):
            ex, ey = hp(side * 0.62 * u, eye_y)
            if self.role == "executive":
                continue  # sunglasses cover the eyes (drawn below)
            if p["blink"]:
                c.create_line(ex - 0.28 * u, ey, ex + 0.28 * u, ey, fill=OUTLINE, width=max(2, u * 0.1), tags=self.tag)
                continue
            w, h = 0.3 * u, 0.42 * u
            c.create_oval(ex - w, ey - h, ex + w, ey + h, fill="#ffffff", outline=OUTLINE, width=lw, tags=self.tag)
            c.create_oval(ex - w * 0.8, ey - h * 0.7, ex + w * 0.8, ey + h * 0.95, fill=self.accent,
                          outline="", tags=self.tag)
            c.create_oval(ex - w * 0.42, ey - h * 0.2, ex + w * 0.42, ey + h * 0.6, fill=OUTLINE,
                          outline="", tags=self.tag)
            # the big anime sparkle highlights
            c.create_oval(ex - w * 0.55, ey - h * 0.6, ex - w * 0.05, ey - h * 0.1, fill="#ffffff",
                          outline="", tags=self.tag)
            c.create_oval(ex + w * 0.15, ey + h * 0.35, ex + w * 0.45, ey + h * 0.6, fill="#ffffff",
                          outline="", tags=self.tag)
            # blush
            bx, by = hp(side * 0.95 * u, -0.45 * u)
            c.create_oval(bx - 0.25 * u, by - 0.09 * u, bx + 0.25 * u, by + 0.09 * u, fill="#ffaab8",
                          outline="", tags=self.tag)
        if self.role == "executive":
            pts = [*hp(-1.15 * u, -1.3 * u), *hp(1.15 * u, -1.3 * u), *hp(1.0 * u, -0.8 * u),
                   *hp(0.15 * u, -0.85 * u), *hp(0, -1.0 * u), *hp(-0.15 * u, -0.85 * u), *hp(-1.0 * u, -0.8 * u)]
            c.create_polygon(pts, fill="#08080c", outline=OUTLINE, width=lw, tags=self.tag)
            c.create_line(*hp(-0.85 * u, -1.2 * u), *hp(-0.45 * u, -1.2 * u), fill=self.accent2,
                          width=max(1, u * 0.07), tags=self.tag)
        if self.role == "tech":
            pts = [*hp(-1.4 * u, -1.35 * u), *hp(1.4 * u, -1.35 * u), *hp(1.35 * u, -0.8 * u),
                   *hp(-1.35 * u, -0.8 * u)]
            c.create_polygon(pts, fill=dim(self.accent2, 0.55), outline=self.accent2, width=lw, tags=self.tag)
        # mouth: opens a little on the beat (singing / vibing)
        mx, my = hp(0, -0.3 * u)
        mo = 0.06 * u + 0.16 * u * p["mouth"]
        c.create_oval(mx - 0.17 * u, my - mo / 2, mx + 0.17 * u, my + mo / 2, fill="#a8324a",
                      outline=OUTLINE, width=max(1, lw - 1), tags=self.tag)

    # ---- hair / hats / headphones -------------------------------------------
    def _draw_hair_and_hat(self, hp, u, lw):
        c = self.canvas
        hair = self.spec["hair"]
        # spiky anime bangs
        bangs = [*hp(-1.6 * u, -1.2 * u), *hp(-1.5 * u, -2.4 * u), *hp(-0.6 * u, -3.05 * u),
                 *hp(0.5 * u, -3.1 * u), *hp(1.45 * u, -2.5 * u), *hp(1.65 * u, -1.25 * u),
                 *hp(1.2 * u, -1.75 * u), *hp(0.9 * u, -1.4 * u), *hp(0.45 * u, -1.95 * u),
                 *hp(0.1 * u, -1.5 * u), *hp(-0.4 * u, -2.0 * u), *hp(-0.75 * u, -1.45 * u),
                 *hp(-1.15 * u, -1.85 * u)]
        c.create_polygon(bangs, fill=hair, outline=OUTLINE, width=lw, tags=self.tag)
        # hair shine
        c.create_line(*hp(-0.9 * u, -2.6 * u), *hp(-0.3 * u, -2.85 * u), fill=blend(hair, "#ffffff", 0.55),
                      width=max(2, u * 0.12), capstyle="round", tags=self.tag)

        if self.role == "producer":  # backwards cap
            cap = [*hp(-1.55 * u, -2.0 * u), *hp(-1.3 * u, -2.95 * u), *hp(0, -3.3 * u),
                   *hp(1.3 * u, -2.95 * u), *hp(1.55 * u, -2.0 * u)]
            c.create_polygon(cap, fill=self.accent, outline=OUTLINE, width=lw, smooth=True, tags=self.tag)
            c.create_line(*hp(-1.55 * u, -2.0 * u), *hp(-2.3 * u, -1.75 * u), fill=OUTLINE,
                          width=u * 0.28, capstyle="round", tags=self.tag)
            c.create_line(*hp(-1.55 * u, -2.0 * u), *hp(-2.25 * u, -1.78 * u), fill=self.accent2,
                          width=u * 0.18, capstyle="round", tags=self.tag)
        if self.role == "songwriter":  # beret
            beret = [*hp(-1.7 * u, -2.3 * u), *hp(-0.8 * u, -3.35 * u), *hp(0.9 * u, -3.4 * u),
                     *hp(1.75 * u, -2.6 * u), *hp(0.5 * u, -2.35 * u)]
            c.create_polygon(beret, fill=self.accent, outline=OUTLINE, width=lw, smooth=True, tags=self.tag)
            c.create_line(*hp(0.1 * u, -3.35 * u), *hp(0.15 * u, -3.6 * u), fill=OUTLINE, width=max(2, u * 0.12),
                          tags=self.tag)
        if self.role in ("engineer", "artist"):
            # headphones (engineer) / small earpiece mic (artist uses handheld)
            if self.role == "engineer":
                band = [*hp(-1.75 * u, -1.0 * u), *hp(-1.6 * u, -2.8 * u), *hp(0, -3.45 * u),
                        *hp(1.6 * u, -2.8 * u), *hp(1.75 * u, -1.0 * u)]
                c.create_line(band, fill=OUTLINE, width=u * 0.34, smooth=True, tags=self.tag)
                c.create_line(band, fill="#2c2c3a", width=u * 0.2, smooth=True, tags=self.tag)
                for side in (-1, 1):
                    ex, ey = hp(side * 1.68 * u, -0.95 * u)
                    c.create_oval(ex - 0.42 * u, ey - 0.62 * u, ex + 0.42 * u, ey + 0.62 * u,
                                  fill=self.accent, outline=OUTLINE, width=lw, tags=self.tag)
                    c.create_oval(ex - 0.2 * u, ey - 0.3 * u, ex + 0.2 * u, ey + 0.3 * u,
                                  fill=self.accent2, outline="", tags=self.tag)
        if self.role == "tech":  # antenna earpiece
            ax, ay = hp(1.6 * u, -1.6 * u)
            tx, ty = hp(2.0 * u, -3.0 * u)
            c.create_line(ax, ay, tx, ty, fill="#c0c8d8", width=max(2, u * 0.1), tags=self.tag)
            c.create_oval(tx - 0.16 * u, ty - 0.16 * u, tx + 0.16 * u, ty + 0.16 * u, fill=self.accent2,
                          outline=OUTLINE, tags=self.tag)

    # ---- things held in hands ---------------------------------------------------
    def _draw_hand_props(self, hands, u, lw):
        c = self.canvas
        (rh, re), (lh, le) = hands[1], hands[-1]
        if self.role == "artist":  # handheld microphone
            ang = math.atan2(rh[1] - re[1], rh[0] - re[0])
            tip = (rh[0] + math.cos(ang) * 0.7 * u, rh[1] + math.sin(ang) * 0.7 * u)
            c.create_line(*rh, *tip, fill="#1b1b22", width=u * 0.26, capstyle="round", tags=self.tag)
            c.create_oval(tip[0] - 0.3 * u, tip[1] - 0.3 * u, tip[0] + 0.3 * u, tip[1] + 0.3 * u,
                          fill="#c9d2e0", outline=OUTLINE, width=lw, tags=self.tag)
            c.create_line(tip[0] - 0.2 * u, tip[1], tip[0] + 0.2 * u, tip[1], fill="#7a8494", tags=self.tag)
        elif self.role == "executive":  # phone
            c.create_rectangle(rh[0] - 0.18 * u, rh[1] - 0.45 * u, rh[0] + 0.18 * u, rh[1] + 0.1 * u,
                               fill="#0d0d12", outline=self.accent, width=max(1, lw - 1), tags=self.tag)
        elif self.role == "producer":  # drumsticks
            for h, e in ((rh, re), (lh, le)):
                ang = math.atan2(h[1] - e[1], h[0] - e[0])
                tip = (h[0] + math.cos(ang) * 1.1 * u, h[1] + math.sin(ang) * 1.1 * u)
                c.create_line(*h, *tip, fill="#e8c890", width=max(2, u * 0.12), capstyle="round", tags=self.tag)
        elif self.role == "songwriter":  # notebook + pencil
            x, y = lh
            c.create_polygon(x - 0.55 * u, y - 0.75 * u, x + 0.35 * u, y - 0.85 * u, x + 0.45 * u, y + 0.35 * u,
                             x - 0.45 * u, y + 0.45 * u, fill="#f8f4e8", outline=OUTLINE, width=lw, tags=self.tag)
            for k in range(4):
                yy = y - 0.5 * u + k * 0.22 * u
                c.create_line(x - 0.38 * u, yy, x + 0.3 * u, yy - 0.05 * u, fill=self.accent, tags=self.tag)
            x2, y2 = rh
            c.create_line(x2, y2, x2 - 0.5 * u, y2 - 0.5 * u, fill="#ffcc33", width=max(2, u * 0.14), tags=self.tag)
        elif self.role == "tech":  # glowing cable
            c.create_line(*lh, lh[0] - 0.6 * u, lh[1] + 0.8 * u, lh[0] - 0.2 * u, lh[1] + 1.6 * u,
                          fill=self.accent2, width=max(2, u * 0.1), smooth=True, tags=self.tag)
