"""
Drawing helpers for the sci-fi look: rounded shapes, honeycomb pills,
fake glows (Tk can't do transparency, so a glow is several outlines whose
colors fade into the background), and wireframe spheres.
"""
import math

from ..theme import dim


def rounded_rect_points(x1, y1, x2, y2, r):
    """Points for a rounded rectangle; draw with create_polygon(..., smooth=True)."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
        x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]


def hex_pill_points(x1, y1, x2, y2, cut=None):
    """A long hexagon (pointed ends), like a honeycomb cell stretched sideways."""
    h = y2 - y1
    c = h / 2 if cut is None else cut
    return [x1 + c, y1, x2 - c, y1, x2, y1 + h / 2, x2 - c, y2, x1 + c, y2, x1, y1 + h / 2]


def hexagon_points(cx, cy, r, rotation=0.0):
    pts = []
    for i in range(6):
        a = math.radians(60 * i + rotation)
        pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
    return pts


def glow_polygon(canvas, points, color, tags=(), layers=4, width=2, fill="", smooth=False, strength=1.0):
    """Draw a polygon with a soft neon glow around it. Returns item ids."""
    ids = []
    # Outer, wide, dark strokes first, then narrower, brighter ones on top.
    for i in range(layers, 0, -1):
        t = (1 - i / (layers + 1)) * 0.55 * strength
        ids.append(canvas.create_polygon(points, outline=dim(color, t), fill="",
                                         width=width + i * 3, smooth=smooth, tags=tags))
    ids.append(canvas.create_polygon(points, outline=color, fill=fill, width=width,
                                     smooth=smooth, tags=tags))
    return ids


def glow_oval(canvas, x1, y1, x2, y2, color, tags=(), layers=4, width=2, fill="", strength=1.0):
    ids = []
    for i in range(layers, 0, -1):
        t = (1 - i / (layers + 1)) * 0.55 * strength
        ids.append(canvas.create_oval(x1, y1, x2, y2, outline=dim(color, t), width=width + i * 3, tags=tags))
    ids.append(canvas.create_oval(x1, y1, x2, y2, outline=color, fill=fill, width=width, tags=tags))
    return ids


def glow_text(canvas, x, y, text, font, color, tags=(), anchor="center", strength=1.0):
    """Text with a soft halo (offset copies in darker shades)."""
    ids = []
    halo = dim(color, 0.35 * strength)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        ids.append(canvas.create_text(x + dx, y + dy, text=text, font=font, fill=halo, anchor=anchor, tags=tags))
    ids.append(canvas.create_text(x, y, text=text, font=font, fill=color, anchor=anchor, tags=tags))
    return ids


def wire_sphere(canvas, cx, cy, r, spin, color, tags=(), lat=5, lon=8, tilt=0.35, width=1, bright=1.0):
    """A holographic wireframe globe. `spin` (radians) rotates it."""
    ids = []
    ct, st = math.cos(tilt), math.sin(tilt)

    def project(x, y, z):
        # tilt around the X axis, then flat projection
        y2 = y * ct - z * st
        z2 = y * st + z * ct
        return cx + x * r, cy + y2 * r, z2

    # longitude lines (meridians)
    for i in range(lon):
        a = spin + math.pi * i / lon
        pts, depth = [], 0
        for j in range(25):
            phi = math.pi * j / 24 - math.pi / 2
            x = math.cos(phi) * math.cos(a)
            z = math.cos(phi) * math.sin(a)
            y = math.sin(phi)
            px, py, pz = project(x, y, z)
            pts += [px, py]
            depth += pz
        front = depth / 25 > 0
        col = dim(color, (0.95 if front else 0.35) * bright)
        ids.append(canvas.create_line(pts, fill=col, width=width + (1 if front else 0), smooth=True, tags=tags))
    # latitude rings
    for k in range(1, lat + 1):
        phi = math.pi * k / (lat + 1) - math.pi / 2
        pts = []
        for j in range(37):
            a = 2 * math.pi * j / 36
            x = math.cos(phi) * math.cos(a)
            z = math.cos(phi) * math.sin(a)
            y = math.sin(phi)
            px, py, _ = project(x, y, z)
            pts += [px, py]
        ids.append(canvas.create_line(pts, fill=dim(color, 0.6 * bright), width=width, smooth=True, tags=tags))
    return ids
