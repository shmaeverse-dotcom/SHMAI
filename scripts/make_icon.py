#!/usr/bin/env python3
"""Draws the shmAI app icon (neon S + waveform) and saves PNG / ICO / ICNS
into assets/. Already done; re-run only if you change the design.
Needs Pillow."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
S = 1024
CYAN = (0, 229, 255)


def make():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # dark rounded tile with a subtle vertical gradient
    tile = Image.new("RGBA", (S, S))
    td = ImageDraw.Draw(tile)
    for y in range(S):
        t = y / S
        td.line([(0, y), (S, y)], fill=(int(6 + 10 * t), int(10 + 14 * (1 - t)), int(22 + 20 * (1 - t)), 255))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    img.paste(tile, (0, 0), mask)

    # neon layer: ring + big S + waveform, blurred copy underneath = glow
    neon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    nd = ImageDraw.Draw(neon)
    nd.rounded_rectangle((70, 70, S - 70, S - 70), radius=185, outline=CYAN + (255,), width=18)
    font = ImageFont.truetype(str(ROOT / "assets/fonts/Orbitron.ttf"), 560)
    try:
        font.set_variation_by_name("Black")
    except Exception:
        pass
    nd.text((S / 2, S * 0.43), "S", font=font, fill=(200, 250, 255, 255), anchor="mm")
    bars = [0.35, 0.7, 1.0, 0.55, 0.85, 0.45, 0.75, 0.3]
    bw, gap = 46, 26
    x0 = S / 2 - (len(bars) * (bw + gap) - gap) / 2
    for i, b in enumerate(bars):
        h = 150 * b
        x = x0 + i * (bw + gap)
        nd.rounded_rectangle((x, S * 0.82 - h, x + bw, S * 0.82), radius=18, fill=CYAN + (255,))
    glow = neon.filter(ImageFilter.GaussianBlur(28))
    img.alpha_composite(glow)
    img.alpha_composite(glow)
    img.alpha_composite(neon)
    return img


if __name__ == "__main__":
    icon = make()
    icon.resize((512, 512), Image.LANCZOS).save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save(OUT / "icon.icns")
    print("Saved assets/icon.png, icon.ico, icon.icns")
