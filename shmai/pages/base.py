"""
Base class for every page.

Each page is a full-size Canvas. The animated starfield and the dancing
character are drawn ON the canvas, and the page's buttons and panels are
placed on top of it with canvas.create_window(). That's why stars show
"behind" the controls: they're in the gaps between them.

To make a new page:
    class MyPage(BasePage):
        key = "home"          # which color theme (see theme.PAGES)
        role = "artist"       # which dancing character
        def build(self): ...  # create widgets once
        def layout(self, w, h): ...  # position things when the window resizes
        def animate(self, dt): ...   # optional per-frame animation
"""
import tkinter as tk

from ..theme import BG, PAGES
from ..widgets.dancer import Dancer
from ..widgets.starfield import Starfield


class BasePage(tk.Frame):
    key = "home"
    role = "artist"
    # Flag for pages whose layout is based on reference images the owner has.
    reference_layout = ""

    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        pal = PAGES[self.key]
        self.accent = pal["accent"]
        self.accent2 = pal["accent2"]
        self.title = pal["name"]
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.starfield = Starfield(self.canvas, self.accent)
        self.dancer = Dancer(self.canvas, self.role, self.accent, self.accent2)
        self._size = (0, 0)
        self.build()
        self.canvas.bind("<Configure>", self._on_resize)

    # ---- hooks for subclasses ---------------------------------------------
    def build(self):
        pass

    def layout(self, w, h):
        pass

    def animate(self, dt):
        pass

    def on_show(self, **kwargs):
        """Called each time the page is opened. kwargs come from the caller
        (e.g. the Home menu can open Song Writer straight into 'guided')."""

    def on_hide(self):
        pass

    def dancer_spot(self, w, h):
        """Where the dancer stands: (feet x, ground y, height). Bottom-right
        by default. Pages keep this corner free of panels."""
        height = max(150, min(250, h * 0.3))
        return w - height * 0.5 - 20, h - 18, height

    # ---- internals --------------------------------------------------------------
    def _on_resize(self, event):
        w, h = event.width, event.height
        if (w, h) == self._size:
            return
        self._size = (w, h)
        self.dancer.place(*self.dancer_spot(w, h))
        self.layout(w, h)
        self.dancer.draw()

    def tick(self, dt):
        self.starfield.tick(dt)
        self.animate(dt)
        self.dancer.tick(dt)
        # keep the dancer above decorations but below embedded widgets
        self.canvas.tag_raise(self.dancer.tag)

    def win(self, widget, x, y, anchor="nw", **kw):
        """Place a widget on the canvas; returns the item id for moving later."""
        return self.canvas.create_window(x, y, window=widget, anchor=anchor, **kw)

    def sp(self, n):
        return self.app.sp(n)
