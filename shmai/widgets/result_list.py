"""
Scrollable list of search results with thumbnails (Beat Finder).

Each row: a 16:9 thumbnail, the title, then artist · duration, plus a ✓
badge once downloaded. Rows glow on hover; click selects, double-click
(or Enter) triggers on_activate. Thumbnails arrive later (loaded in the
background) via set_thumbnail().
"""
import tkinter as tk

from ..theme import PANEL_2, TEXT, TEXT_DIM, blend, dim
from .fx import rounded_rect_points


class ResultList(tk.Frame):
    def __init__(self, parent, app, accent, on_select=None, on_activate=None, bg=PANEL_2):
        super().__init__(parent, bg=bg)
        self.app = app
        self.accent = accent
        self.bg = bg
        self.on_select = on_select
        self.on_activate = on_activate
        self.items = []
        self.images = {}       # index -> PhotoImage (kept so Tk doesn't garbage-collect it)
        self.done = set()      # indexes already downloaded
        self.sel = None
        self.hover = None
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=2, highlightbackground=dim(accent, 0.55),
                                highlightcolor=accent, takefocus=1)
        self.sb = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview, bg=PANEL_2, troughcolor=bg,
                               activebackground=accent, highlightthickness=0, bd=0)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        c = self.canvas
        c.bind("<Configure>", lambda e: self.redraw())
        c.bind("<Motion>", self._motion)
        c.bind("<Leave>", lambda e: self._set_hover(None))
        c.bind("<Button-1>", self._click)
        c.bind("<Double-Button-1>", self._double)
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))
        c.bind("<Up>", lambda e: self.select((self.sel or 0) - 1, notify=True))
        c.bind("<Down>", lambda e: self.select(0 if self.sel is None else self.sel + 1, notify=True))
        c.bind("<Return>", lambda e: self._activate())
        c.bind("<Enter>", lambda e: c.configure(highlightbackground=accent), add="+")
        c.bind("<Leave>", lambda e: c.configure(highlightbackground=dim(accent, 0.55)), add="+")

    # ---- sizes (follow the text-size setting) -------------------------------------------
    def thumb_size(self):
        s = self.app.fonts.scale
        return int(128 * s), int(72 * s)

    def row_h(self):
        return self.thumb_size()[1] + self.app.sp(16)

    # ---- data ---------------------------------------------------------------------------------
    def set_items(self, items):
        self.items = list(items)
        self.images.clear()
        self.done.clear()
        self.sel = 0 if items else None
        self.hover = None
        self.canvas.yview_moveto(0)
        self.redraw()

    def set_thumbnail(self, index, photo):
        if 0 <= index < len(self.items):
            self.images[index] = photo
            self.redraw()

    def mark_downloaded(self, index):
        self.done.add(index)
        self.redraw()

    def selected_index(self):
        return self.sel

    def select(self, index, notify=False):
        if not self.items:
            return
        index = max(0, min(len(self.items) - 1, index))
        self.sel = index
        self.redraw()
        # keep the selected row on screen
        rh = self.row_h()
        top, bottom = index * rh, (index + 1) * rh
        total = max(1, len(self.items) * rh)
        view_top = self.canvas.canvasy(0)
        view_h = self.canvas.winfo_height()
        if top < view_top:
            self.canvas.yview_moveto(top / total)
        elif bottom > view_top + view_h:
            self.canvas.yview_moveto(max(0, bottom - view_h) / total)
        if notify and self.on_select:
            self.on_select(index)

    # ---- mouse ------------------------------------------------------------------------------------
    def _index_at(self, y):
        i = int(self.canvas.canvasy(y) // self.row_h())
        return i if 0 <= i < len(self.items) else None

    def _set_hover(self, i):
        if i != self.hover:
            self.hover = i
            self.canvas.configure(cursor="hand2" if i is not None else "")
            self.redraw()

    def _motion(self, e):
        self._set_hover(self._index_at(e.y))

    def _click(self, e):
        self.canvas.focus_set()
        i = self._index_at(e.y)
        if i is not None:
            self.app.sound.play_select()
            self.select(i, notify=True)

    def _double(self, e):
        if self._index_at(e.y) is not None:
            self._activate()

    def _activate(self):
        if self.sel is not None and self.on_activate:
            self.on_activate(self.sel)

    # ---- drawing -----------------------------------------------------------------------------------
    def redraw(self):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 200)
        rh = self.row_h()
        tw, th = self.thumb_size()
        f = self.app.fonts
        pad = self.app.sp(10)
        acc = self.accent
        c.configure(scrollregion=(0, 0, w, max(len(self.items) * rh, c.winfo_height())))
        if not self.items:
            c.create_text(w / 2, 60, text="Search results will appear here.", font=f["body"], fill=TEXT_DIM)
            return
        for i, item in enumerate(self.items):
            y1 = i * rh
            sel, hov = i == self.sel, i == self.hover
            if sel or hov:
                x1, x2 = 4, w - 6
                if hov and not sel:
                    c.create_polygon(rounded_rect_points(x1, y1 + 3, x2, y1 + rh - 3, 10), smooth=True,
                                     outline=dim(acc, 0.5), fill=blend(self.bg, acc, 0.08), width=2)
                else:
                    for g in range(3, 0, -1):  # glow
                        c.create_polygon(rounded_rect_points(x1 - g + 1, y1 + 3 - g + 1, x2 + g - 1, y1 + rh - 3 + g - 1,
                                                             10), smooth=True, outline=dim(acc, 0.15 * (4 - g)),
                                         fill="", width=2)
                    c.create_polygon(rounded_rect_points(x1, y1 + 3, x2, y1 + rh - 3, 10), smooth=True, outline=acc,
                                     fill=blend(self.bg, acc, 0.2), width=2)
            # thumbnail (or a placeholder tile until it loads)
            tx, ty = pad + 4, y1 + (rh - th) / 2
            photo = self.images.get(i)
            if photo is not None:
                c.create_image(tx, ty, image=photo, anchor="nw")
            else:
                c.create_rectangle(tx, ty, tx + tw, ty + th, fill=blend(self.bg, acc, 0.12), outline=dim(acc, 0.5))
                c.create_text(tx + tw / 2, ty + th / 2, text="♪", font=f["h1"], fill=dim(acc, 0.7))
            c.create_rectangle(tx, ty, tx + tw, ty + th, outline=acc if sel else dim(acc, 0.45), width=2)
            if i in self.done:
                c.create_oval(tx + tw - 26, ty + 4, tx + tw - 4, ty + 26, fill=acc, outline="")
                c.create_text(tx + tw - 15, ty + 15, text="✓", font=f["small"], fill="#0a0f0a")
            # text
            x = tx + tw + pad * 1.5
            maxw = w - x - pad * 2
            title = _fit(item.get("title") or "(untitled)", f["body"], maxw)
            c.create_text(x, ty + th * 0.3, text=title, anchor="w", font=f["body"], fill=TEXT if (sel or hov) else
                          blend(TEXT, self.bg, 0.15))
            meta = " · ".join(v for v in (item.get("artist"), item.get("duration"), item.get("source")) if v)
            c.create_text(x, ty + th * 0.72, text=_fit(meta, f["small"], maxw), anchor="w", font=f["small"],
                          fill=acc if sel else TEXT_DIM)


def _fit(text, font, width):
    """Shorten text with … so it fits in `width` pixels."""
    if width <= 20 or font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text + "…"
