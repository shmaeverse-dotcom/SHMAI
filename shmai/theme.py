"""
Look and feel: page colors, fonts, and color helpers.

Every page has its own accent color, a mix of the PS3 XMB look and the
original Xbox dashboard. Fonts are bundled in assets/fonts (all free OFL
fonts):
    Orbitron        - headings and titles (Xbox-era sci-fi)
    Rajdhani        - body text and buttons (clean, techy, very readable)
    Share Tech Mono - numbers and readouts (BPM, key, status lines)
If a font can't be loaded, we fall back to a similar system font.
"""
import os
import shutil
import subprocess
import sys
import tkinter.font as tkfont

from .config import ASSETS_DIR

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
BG = "#03050a"          # near-black space background
PANEL = "#0a0f1a"       # dark panel fill
PANEL_2 = "#101828"     # slightly lighter panel (inputs)
TEXT = "#eef6ff"        # main text
TEXT_DIM = "#8fa3bf"    # secondary text

# One accent color per page.
PAGES = {
    "home":     {"accent": "#00e5ff", "accent2": "#7af4ff", "name": "HOME"},          # neon cyan
    "beat":     {"accent": "#7cff3a", "accent2": "#c4ff9a", "name": "BEAT FINDER"},   # Xbox green
    "analyzer": {"accent": "#b98cff", "accent2": "#e0c8ff", "name": "AUDIO ANALYZER"},  # purple-lavender
    "melody":   {"accent": "#ff5a1f", "accent2": "#ffb347", "name": "MELODY GENERATOR"},  # fiery red-orange
    "song":     {"accent": "#6fd0ff", "accent2": "#c6ecff", "name": "SONG WRITER"},   # light neon blue
    "clarity":  {"accent": "#f2f7ff", "accent2": "#ffd86b", "name": "CLARITY"},       # crystal white + gold
}


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def blend(c1, c2, t):
    """Mix two colors. t=0 -> c1, t=1 -> c2. Tk has no transparency, so we
    fake glows and fades by mixing the accent color into the background."""
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def dim(color, t):
    """Fade a color toward the background (t=0 black-ish, t=1 full color)."""
    return blend(BG, color, t)


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_DIR = ASSETS_DIR / "fonts"
FONT_FILES = ["Orbitron.ttf", "Rajdhani-Medium.ttf", "Rajdhani-Bold.ttf", "ShareTechMono-Regular.ttf"]

HEADING_CHOICES = ["Orbitron", "Eurostile", "Bank Gothic", "Segoe UI Semibold", "Helvetica"]
BODY_CHOICES = ["Rajdhani", "Rajdhani Medium", "Segoe UI", "Helvetica Neue", "Helvetica"]
MONO_CHOICES = ["Share Tech Mono", "Consolas", "Menlo", "DejaVu Sans Mono", "Courier"]

# Base point sizes BEFORE the user's size multiplier. These are larger than
# the old UI's sizes on purpose.
BASE_SIZES = {
    "title": 30, "h1": 22, "h2": 17, "body": 15, "button": 15, "small": 13, "mono": 14, "mono_big": 34,
}


def install_bundled_fonts():
    """Make the bundled .ttf fonts visible to Tk. Call BEFORE creating Tk().

    Windows: registered privately for this app only (nothing installed).
    macOS / Linux: copied into your personal fonts folder (one time).
    """
    files = [FONT_DIR / f for f in FONT_FILES if (FONT_DIR / f).exists()]
    if not files:
        return
    try:
        if sys.platform.startswith("win"):
            import ctypes
            FR_PRIVATE = 0x10
            for f in files:
                ctypes.windll.gdi32.AddFontResourceExW(str(f), FR_PRIVATE, 0)
        else:
            if sys.platform == "darwin":
                target = os.path.expanduser("~/Library/Fonts")
            else:
                target = os.path.expanduser("~/.local/share/fonts/shmai")
            os.makedirs(target, exist_ok=True)
            copied = False
            for f in files:
                dest = os.path.join(target, f.name)
                if not os.path.exists(dest):
                    shutil.copyfile(f, dest)
                    copied = True
            if copied and sys.platform != "darwin" and shutil.which("fc-cache"):
                subprocess.run(["fc-cache", "-f", target], capture_output=True, timeout=30)
    except Exception as e:  # fonts are cosmetic; never crash over them
        print(f"[shmAI] Could not load bundled fonts: {e}")


def _pick(families, choices):
    lower = {f.lower(): f for f in families}
    for c in choices:
        if c.lower() in lower:
            return lower[c.lower()]
    return choices[-1]


class Fonts:
    """Named Tk fonts. Changing the size multiplier resizes text everywhere
    at once, because every widget points at these same font objects."""

    def __init__(self, root, scale=1.0):
        families = set(tkfont.families(root))
        self.heading = _pick(families, HEADING_CHOICES)
        self.body = _pick(families, BODY_CHOICES)
        self.mono = _pick(families, MONO_CHOICES)
        self.fonts = {
            "title": tkfont.Font(root, family=self.heading, weight="bold"),
            "h1": tkfont.Font(root, family=self.heading, weight="bold"),
            "h2": tkfont.Font(root, family=self.heading),
            "body": tkfont.Font(root, family=self.body, weight="bold"),
            "button": tkfont.Font(root, family=self.body, weight="bold"),
            "button_hover": tkfont.Font(root, family=self.body, weight="bold"),
            "small": tkfont.Font(root, family=self.body, weight="bold"),
            "mono": tkfont.Font(root, family=self.mono),
            "mono_big": tkfont.Font(root, family=self.mono),
        }
        self.set_scale(scale)

    def set_scale(self, scale):
        self.scale = max(0.6, min(2.0, float(scale)))
        for name, f in self.fonts.items():
            if name == "button_hover":
                # Hovered buttons grow ~12%: part of the glow-and-scale effect.
                f.configure(size=round(BASE_SIZES["button"] * self.scale * 1.12))
            else:
                f.configure(size=round(BASE_SIZES[name] * self.scale))

    def __getitem__(self, name):
        return self.fonts[name]

    def size(self, name):
        return self.fonts[name].cget("size")
