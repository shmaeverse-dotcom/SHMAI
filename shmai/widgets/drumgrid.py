"""
Step-sequencer view of a copied drum loop: 4 bars per row (8 for longer
loops), three lanes per row (KICK, SNARE, HATS). Open hats show as hollow squares and 1/32 rolls as
a small extra mark between steps. Beat columns are slightly brighter so
the grid reads like FL Studio's step sequencer.
"""
import tkinter as tk

from ..theme import PANEL, TEXT_DIM, blend, dim

LANE_ROWS = (("K", (36,)), ("S", (38,)), ("H", (42, 46)))


class DrumGrid(tk.Canvas):
    def __init__(self, parent, app, accent, accent2, bg=PANEL):
        # lane height follows the text size so the K / S / H labels never overlap
        self.cell = max(12, int(app.fonts["small"].metrics("linespace") * 0.85))
        super().__init__(parent, height=self.cell * 4, bg=bg, highlightthickness=0)
        self.app = app
        self.accent, self.accent2, self.bg = accent, accent2, bg
        self.pattern = None
        self.message = ""
        self.bind("<Configure>", lambda e: self.redraw())

    def set_pattern(self, pattern):
        self.pattern, self.message = pattern, ""
        self._resize()
        self.redraw()

    def set_message(self, text):
        self.pattern, self.message = None, text
        self._resize()
        self.redraw()

    def _resize(self):
        rows = 1 if not self.pattern else -(-self.pattern["bars"] // self._per_row())
        lane_h = self.cell + 1
        self.configure(height=rows * (3 * lane_h + 8) + 4 if self.pattern else self.cell * 4)

    def _per_row(self):
        return 8 if self.pattern and self.pattern["bars"] >= 8 else 4

    def redraw(self):
        self.delete("all")
        w = max(self.winfo_width(), 200)
        f = self.app.fonts
        if not self.pattern:
            self.create_text(w / 2, self.cell * 2, text=self.message or "No drums copied yet.", font=f["small"],
                             fill=TEXT_DIM, width=w - 20)
            return
        p = self.pattern
        hits = {}
        for step, note, vel in p["hits"]:
            hits[(int(step), note, step != int(step))] = vel
        label_w = f["small"].measure("K") + 10
        per = self._per_row()
        cw = min(self.cell + 2, (w - label_w - 6) / (16.0 * per))
        lane_h = self.cell + 1
        for bar0 in range(0, p["bars"], per):
            row = bar0 // per
            y0 = 4 + row * (3 * lane_h + 8)
            for li, (name, notes) in enumerate(LANE_ROWS):
                y = y0 + li * lane_h
                self.create_text(2, y + lane_h / 2, text=name, anchor="w", font=f["small"], fill=TEXT_DIM)
                for b in range(per):
                    bar = bar0 + b
                    if bar >= p["bars"]:
                        break
                    for s in range(16):
                        x = label_w + (b * 16 + s) * cw
                        gstep = bar * 16 + s
                        on_beat = s % 4 == 0
                        base = blend(self.bg, self.accent, 0.16 if on_beat else 0.07)
                        vel = None
                        hollow = False
                        for n in notes:
                            if (gstep, n, False) in hits:
                                vel = hits[(gstep, n, False)]
                                hollow = n == 46
                        if vel:
                            col = blend(self.accent, self.accent2, (vel - 40) / 87.0)
                            if hollow:  # open hat
                                self.create_rectangle(x + 1, y + 1, x + cw - 1, y + lane_h - 2, outline=col,
                                                      width=2 if cw > 6 else 1)
                            else:
                                self.create_rectangle(x + 1, y + 1, x + cw - 1, y + lane_h - 2, fill=col, outline="")
                        else:
                            self.create_rectangle(x + 1, y + 1, x + cw - 1, y + lane_h - 2, fill=base, outline="")
                        if name == "H" and (gstep, 42, True) in hits:  # 1/32 roll between steps
                            self.create_rectangle(x + cw - 2, y + lane_h / 2 - 2, x + cw + 1, y + lane_h / 2 + 1,
                                                  fill=self.accent2, outline="")
                    # bar divider
                    xb = label_w + b * 16 * cw
                    self.create_line(xb, y0 - 1, xb, y0 + 3 * lane_h, fill=dim(self.accent, 0.6))
