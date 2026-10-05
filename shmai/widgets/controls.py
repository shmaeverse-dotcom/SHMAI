"""
Reusable controls with the glow-and-scale look.

GlowButton  - neon button: glows and grows on hover, plays the select blip
Toggle      - on/off switch (used for Clean/Explicit, layers, etc.)
make_entry / make_text / make_listbox / make_combo / make_scale
            - standard Tk inputs dressed in the page's colors, with a glow
              border on hover and focus
Panel       - dark box with a neon border
"""
import tkinter as tk
from tkinter import ttk

from ..theme import BG, PANEL, PANEL_2, TEXT, TEXT_DIM, blend, dim
from .fx import rounded_rect_points


class GlowButton(tk.Canvas):
    """A neon button. On hover it glows (extra outlines fading into the
    background) and its text grows ~12%. Clicking plays the select sound."""

    def __init__(self, parent, app, text, command=None, accent="#00e5ff", accent2=None,
                 width=None, height=None, primary=False, bg=BG):
        self.app = app
        self.text = text
        self.command = command
        self.accent = accent
        self.accent2 = accent2 or blend(accent, "#ffffff", 0.5)
        self.primary = primary
        self.enabled = True
        self.hover = False
        self.pressed = False
        fh = app.fonts["button_hover"]
        pad = app.sp(22)
        self._bw = width or (fh.measure(text) + pad * 2 + 16)
        self._bh = height or (fh.metrics("linespace") + app.sp(14) + 14)
        super().__init__(parent, width=self._bw, height=self._bh, bg=bg, highlightthickness=0,
                         cursor="hand2", takefocus=1)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<FocusIn>", self._on_enter)
        self.bind("<FocusOut>", self._on_leave)
        self._draw()

    def configure_text(self, text):
        self.text = text
        self._draw()

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def invoke(self):
        if self.enabled and self.command:
            self.app.sound.play_select()
            self.command()

    def _on_enter(self, _e=None):
        self.hover = True
        self._draw()

    def _on_leave(self, _e=None):
        self.hover = self.pressed = False
        self._draw()

    def _on_press(self, _e):
        if self.enabled:
            self.pressed = True
            self._draw()

    def _on_release(self, e):
        was = self.pressed
        self.pressed = False
        self._draw()
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        if was and inside:
            self.invoke()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width() if self.winfo_width() > 1 else self._bw
        h = self.winfo_height() if self.winfo_height() > 1 else self._bh
        acc = self.accent if self.enabled else "#3a4250"
        glow = self.hover and self.enabled
        # "Scale": not hovered = drawn smaller inside the canvas; hovered =
        # fills it. Together with the bigger font this reads as a zoom.
        inset = 3 if glow else 8
        x1, y1, x2, y2 = inset, inset, w - inset, h - inset
        r = (y2 - y1) / 2.6
        if glow:
            for i in range(3, 0, -1):
                pts = rounded_rect_points(x1 - i + 1, y1 - i + 1, x2 + i - 1, y2 + i - 1, r)
                self.create_polygon(pts, outline=dim(acc, 0.25 * (4 - i)), fill="", width=2 + i * 1.5,
                                    smooth=True)
        if self.pressed:
            fill = acc
        elif self.primary:
            fill = blend(PANEL, acc, 0.35 if glow else 0.22)
        else:
            fill = blend(PANEL, acc, 0.18 if glow else 0.06)
        pts = rounded_rect_points(x1, y1, x2, y2, r)
        self.create_polygon(pts, outline=acc if (glow or self.primary) else dim(acc, 0.7), fill=fill,
                            width=2, smooth=True)
        # little highlight line along the top, glossy Xbox-style
        self.create_line(x1 + r, y1 + 4, x2 - r, y1 + 4, fill=blend(fill, "#ffffff", 0.18))
        color = "#05080c" if self.pressed else (self.accent2 if glow else (TEXT if self.enabled else "#5c6675"))
        font = self.app.fonts["button_hover" if glow else "button"]
        self.create_text(w / 2, h / 2, text=self.text, fill=color, font=font)


class Toggle(tk.Canvas):
    """On/off switch with a label on each side, e.g. CLEAN [==o] EXPLICIT."""

    def __init__(self, parent, app, left, right, value=False, command=None, accent="#00e5ff", bg=PANEL):
        self.app = app
        self.left, self.right = left, right
        self.value = value
        self.command = command
        self.accent = accent
        f = app.fonts["small"]
        self.track_w = app.sp(54) + 10
        self._bh = f.metrics("linespace") + 14
        self._bw = f.measure(left) + f.measure(right) + self.track_w + 40
        super().__init__(parent, width=self._bw, height=self._bh, bg=bg, highlightthickness=0, cursor="hand2")
        self.bind("<Button-1>", lambda e: self.set(not self.value, notify=True))
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self._draw(False)

    def set(self, value, notify=False):
        self.value = bool(value)
        if notify:
            self.app.sound.play_select()
            if self.command:
                self.command(self.value)
        self._draw(False)

    def get(self):
        return self.value

    def _draw(self, hover):
        self.delete("all")
        f = self.app.fonts["small"]
        h = self._bh
        lx = 4
        self.create_text(lx, h / 2, text=self.left, anchor="w", font=f,
                         fill=TEXT if not self.value else TEXT_DIM)
        tx = lx + f.measure(self.left) + 14
        th = h * 0.58
        ty1, ty2 = (h - th) / 2, (h + th) / 2
        acc = self.accent
        if hover:
            self.create_polygon(rounded_rect_points(tx - 3, ty1 - 3, tx + self.track_w + 3, ty2 + 3, th / 2 + 3),
                                outline=dim(acc, 0.45), fill="", width=3, smooth=True)
        self.create_polygon(rounded_rect_points(tx, ty1, tx + self.track_w, ty2, th / 2),
                            outline=acc, fill=blend(PANEL, acc, 0.4 if self.value else 0.08), width=2, smooth=True)
        kx = tx + (self.track_w - th / 2 - 2 if self.value else th / 2 + 2)
        self.create_oval(kx - th / 2 + 3, ty1 + 3, kx + th / 2 - 3, ty2 - 3, fill=acc if self.value else TEXT_DIM,
                         outline="")
        self.create_text(tx + self.track_w + 14, h / 2, text=self.right, anchor="w", font=f,
                         fill=acc if self.value else TEXT_DIM)


class Panel(tk.Frame):
    """A dark rectangle with a neon border."""

    def __init__(self, parent, accent, bg=PANEL, border=2, **kw):
        super().__init__(parent, bg=bg, highlightthickness=border, highlightbackground=dim(accent, 0.75),
                         highlightcolor=accent, **kw)


def _glow_on_hover(widget, accent):
    """Brighten an input's border when the mouse is over it (the glow)."""
    normal = dim(accent, 0.55)
    widget.configure(highlightthickness=2, highlightbackground=normal, highlightcolor=accent)
    widget.bind("<Enter>", lambda e: widget.configure(highlightbackground=accent), add="+")
    widget.bind("<Leave>", lambda e: widget.configure(highlightbackground=normal), add="+")


def make_entry(parent, app, accent, textvariable=None, width=30, font="body"):
    e = tk.Entry(parent, textvariable=textvariable, width=width, font=app.fonts[font], bg=PANEL_2, fg=TEXT,
                 insertbackground=accent, relief="flat", selectbackground=dim(accent, 0.6),
                 selectforeground=TEXT, disabledbackground=PANEL, disabledforeground=TEXT_DIM)
    _glow_on_hover(e, accent)
    return e


def make_text(parent, app, accent, height=8, width=40, font="body", wrap="word"):
    t = tk.Text(parent, height=height, width=width, font=app.fonts[font], bg=PANEL_2, fg=TEXT,
                insertbackground=accent, relief="flat", wrap=wrap, padx=app.sp(10), pady=app.sp(8),
                selectbackground=dim(accent, 0.6), selectforeground=TEXT)
    _glow_on_hover(t, accent)
    return t


def make_listbox(parent, app, accent, height=10, font="body"):
    lb = tk.Listbox(parent, height=height, font=app.fonts[font], bg=PANEL_2, fg=TEXT, relief="flat",
                    selectbackground=blend(PANEL_2, accent, 0.45), selectforeground="#ffffff",
                    activestyle="none", exportselection=False)
    _glow_on_hover(lb, accent)
    return lb


def make_scrollbar(parent, accent, command, orient="vertical"):
    return tk.Scrollbar(parent, orient=orient, command=command, bg=PANEL, troughcolor=BG,
                        activebackground=accent, highlightthickness=0, bd=0, relief="flat")


def style_ttk(app, name, accent):
    """Create a ttk style named e.g. 'melody.TCombobox' in the page's colors."""
    st = app.ttk_style
    st.configure(f"{name}.TCombobox", fieldbackground=PANEL_2, background=blend(PANEL, accent, 0.3),
                 foreground=TEXT, arrowcolor=accent, bordercolor=dim(accent, 0.6), lightcolor=dim(accent, 0.6),
                 darkcolor=PANEL, selectbackground=PANEL_2, selectforeground=TEXT, padding=app.sp(6))
    st.map(f"{name}.TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)],
           bordercolor=[("focus", accent), ("hover", accent)], lightcolor=[("focus", accent), ("hover", accent)],
           background=[("active", blend(PANEL, accent, 0.5))])
    st.configure(f"{name}.Horizontal.TProgressbar", troughcolor=PANEL_2, background=accent,
                 bordercolor=dim(accent, 0.5), lightcolor=accent, darkcolor=accent)
    return f"{name}.TCombobox"


def make_combo(parent, app, accent, page, values, textvariable=None, width=22, editable=False):
    style = style_ttk(app, page, accent)
    cb = ttk.Combobox(parent, values=values, textvariable=textvariable, width=width, style=style,
                      font=app.fonts["body"], state="normal" if editable else "readonly")
    # Dropdown list colors (the popup is a plain Tk listbox)
    parent.option_add("*TCombobox*Listbox.background", PANEL_2)
    parent.option_add("*TCombobox*Listbox.foreground", TEXT)
    parent.option_add("*TCombobox*Listbox.selectBackground", dim(accent, 0.7))
    parent.option_add("*TCombobox*Listbox.font", app.fonts["body"])
    return cb


class GlowSlider(tk.Canvas):
    """A neon slider. Drag, click, scroll the mouse wheel, or use the arrow
    keys. Shows its value on the right. Linked to a Tk variable."""

    def __init__(self, parent, app, accent, variable, from_, to, resolution=1, length=260, command=None,
                 fmt=None, bg=PANEL):
        self.app = app
        self.accent = accent
        self.var = variable
        self.lo, self.hi, self.res = from_, to, resolution
        self.command = command
        self.fmt = fmt or (lambda v: f"{v:g}")
        self.hover = False
        self.drag = False
        f = app.fonts["mono"]
        self.value_w = f.measure(self.fmt(to) + "00") + 10
        self.track_len = length
        self._bh = max(app.sp(30), f.metrics("linespace") + 10)
        super().__init__(parent, width=length + self.value_w + 20, height=self._bh, bg=bg, highlightthickness=0,
                         cursor="hand2", takefocus=1)
        for ev, fn in (("<Enter>", self._enter), ("<Leave>", self._leave), ("<ButtonPress-1>", self._press),
                       ("<B1-Motion>", self._move), ("<ButtonRelease-1>", self._release),
                       ("<MouseWheel>", lambda e: self._step(1 if e.delta > 0 else -1)),
                       ("<Button-4>", lambda e: self._step(1)), ("<Button-5>", lambda e: self._step(-1)),
                       ("<Left>", lambda e: self._step(-1)), ("<Right>", lambda e: self._step(1)),
                       ("<FocusIn>", self._enter), ("<FocusOut>", self._leave)):
            self.bind(ev, fn)
        self._trace = variable.trace_add("write", lambda *a: self._draw())
        self.bind("<Destroy>", lambda e: self._untrace(), add="+")
        self._draw()

    def _untrace(self):
        try:
            self.var.trace_remove("write", self._trace)
        except (tk.TclError, ValueError):
            pass

    def _enter(self, _e=None):
        self.hover = True
        self._draw()

    def _leave(self, _e=None):
        self.hover = False
        self._draw()

    def _x0(self):
        return 12

    def _set_from_x(self, x):
        t = (x - self._x0()) / self.track_len
        v = self.lo + max(0.0, min(1.0, t)) * (self.hi - self.lo)
        self._set(v)

    def _set(self, v):
        v = round(v / self.res) * self.res
        v = max(self.lo, min(self.hi, v))
        if isinstance(self.var, tk.IntVar):
            v = int(round(v))
        else:
            v = round(v, 4)
        if v != self.var.get():
            self.var.set(v)
            if self.command:
                self.command(v)

    def _step(self, d):
        self._set(self.var.get() + d * self.res)

    def _press(self, e):
        self.focus_set()
        self.drag = True
        self._set_from_x(e.x)

    def _move(self, e):
        if self.drag:
            self._set_from_x(e.x)

    def _release(self, _e):
        if self.drag:
            self.app.sound.play_select()
        self.drag = False

    def _draw(self):
        if not self.winfo_exists():
            return
        self.delete("all")
        h = self._bh
        x0, x1 = self._x0(), self._x0() + self.track_len
        cy = h / 2
        try:
            v = float(self.var.get())
        except (tk.TclError, ValueError):
            v = self.lo
        t = (v - self.lo) / (self.hi - self.lo) if self.hi != self.lo else 0
        kx = x0 + t * self.track_len
        acc = self.accent
        self.create_line(x0, cy, x1, cy, fill=PANEL_2, width=8, capstyle="round")
        self.create_line(x0, cy, x1, cy, fill=dim(acc, 0.35), width=2)
        self.create_line(x0, cy, kx, cy, fill=acc, width=6, capstyle="round")
        r = h * (0.32 if (self.hover or self.drag) else 0.26)
        if self.hover or self.drag:
            for i in range(3, 0, -1):
                self.create_oval(kx - r - i * 3, cy - r - i * 3, kx + r + i * 3, cy + r + i * 3,
                                 outline=dim(acc, 0.18 * (4 - i)), width=2)
        self.create_oval(kx - r, cy - r, kx + r, cy + r, fill=blend(acc, "#ffffff", 0.3), outline=acc, width=2)
        self.create_text(x1 + 16, cy, text=self.fmt(v), anchor="w", font=self.app.fonts["mono"],
                         fill=acc if (self.hover or self.drag) else TEXT)


def make_scale(parent, app, accent, variable, from_, to, resolution=1, length=260, command=None, fmt=None,
               bg=PANEL):
    return GlowSlider(parent, app, accent, variable, from_, to, resolution, length, command, fmt, bg)


def label(parent, app, text, font="body", fg=TEXT, bg=PANEL, **kw):
    return tk.Label(parent, text=text, font=app.fonts[font], fg=fg, bg=bg, **kw)
