"""
The main shmAI window: top navigation bar, page switching with a fade
transition, the shared animation clock, and background-task helper.
"""
import math
import queue
import threading
import time
import tkinter as tk
import traceback
from tkinter import ttk

from . import theme
from .config import ASSETS_DIR, load_config, save_config
from .sound import SoundSystem
from .theme import BG, PAGES, TEXT_DIM, blend, dim
from .widgets.fx import glow_text
from .errors import FriendlyError
from .worker_client import WorkerClient

FPS = 30

# (page key, tab label, module, class) in tab order. Pages are created the
# first time you open them, so startup stays fast.
PAGE_LIST = [
    ("home", "HOME", "home", "HomePage"),
    ("beat", "BEAT FINDER", "beat_finder", "BeatFinderPage"),
    ("analyzer", "AUDIO ANALYZER", "audio_analyzer", "AudioAnalyzerPage"),
    ("melody", "MELODY GEN", "melody_generator", "MelodyGeneratorPage"),
    ("song", "SONG WRITER", "song_writer", "SongWriterPage"),
    ("clarity", "CLARITY", "clarity", "ClarityPage"),
]


class App:
    def __init__(self):
        self.cfg = load_config()
        theme.install_bundled_fonts()  # must run before Tk() exists

        self.root = tk.Tk()
        self.root.title("shmAI")
        self.root.configure(bg=BG)
        self.root.geometry("1440x900")
        self.root.minsize(1180, 760)
        try:  # taskbar / title-bar icon
            self._icon = tk.PhotoImage(file=str(ASSETS_DIR / "icon.png"))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        self.ttk_style = ttk.Style(self.root)
        try:
            self.ttk_style.theme_use("clam")  # the only built-in theme that takes custom colors well
        except tk.TclError:
            pass

        self.fonts = theme.Fonts(self.root, self.cfg.get("ui_scale", 1.0))
        self.sound = SoundSystem(self.cfg)
        self.client = WorkerClient(self.cfg)

        self._ui_queue = queue.Queue()
        self.pages = {}
        self.current = None
        self._transitioning = False
        self._tab_hover = None

        self._build_nav()
        self.container = tk.Frame(self.root, bg=BG)
        self.container.pack(fill="both", expand=True)

        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show_page("home", animate=False)
        self.root.after(50, self._pump_ui_queue)
        self._last_tick = time.perf_counter()
        self.root.after(1000 // FPS, self._tick)

    # ---- spacing helper (the adjustable spacing option) ----------------------
    def sp(self, n):
        return max(1, int(round(n * float(self.cfg.get("ui_spacing", 1.0)))))

    # ---- navigation bar ---------------------------------------------------------
    def _build_nav(self):
        self.nav = tk.Canvas(self.root, height=self._nav_height(), bg=BG, highlightthickness=0)
        self.nav.pack(fill="x", side="top")
        self.nav.bind("<Configure>", lambda e: self._draw_nav())
        self.nav.bind("<Motion>", self._nav_motion)
        self.nav.bind("<Leave>", lambda e: self._set_tab_hover(None))
        self.nav.bind("<Button-1>", self._nav_click)
        self._tab_boxes = []

    def _nav_height(self):
        return self.fonts.size("button") * 2 + self.sp(26) + 10

    def _draw_nav(self):
        c = self.nav
        c.delete("all")
        w = c.winfo_width()
        h = int(c.cget("height"))
        acc = PAGES.get(self.current or "home")["accent"]
        # bottom neon rail
        c.create_line(0, h - 2, w, h - 2, fill=dim(acc, 0.9), width=2)
        c.create_line(0, h - 5, w, h - 5, fill=dim(acc, 0.25), width=3)
        # logo
        glow_text(c, 22, h / 2, "shmAI", self.fonts["h1"], acc, anchor="w")
        logo_w = self.fonts["h1"].measure("shmAI") + 50

        # tabs
        self._tab_boxes = []
        x = logo_w
        gap = self.sp(8)
        for key, label, _m, _c in PAGE_LIST:
            hover = key == self._tab_hover
            active = key == self.current
            f = self.fonts["button_hover" if hover else "button"]
            tw = self.fonts["button_hover"].measure(label) + self.sp(28)
            pacc = PAGES[key]["accent"]
            if active or hover:
                for i in range(3, 0, -1):  # glow
                    c.create_rectangle(x - i, 8 - i, x + tw + i, h - 12 + i, outline=dim(pacc, 0.18 * (4 - i)),
                                       width=2)
                c.create_rectangle(x, 8, x + tw, h - 12, outline=pacc if hover else dim(pacc, 0.8),
                                   fill=blend(BG, pacc, 0.16 if active else 0.08), width=2)
            if active:
                c.create_line(x + 6, h - 12, x + tw - 6, h - 12, fill=pacc, width=4)
            color = pacc if (active or hover) else TEXT_DIM
            c.create_text(x + tw / 2, (h - 4) / 2, text=label, font=f, fill=color)
            self._tab_boxes.append((x, x + tw, key))
            x += tw + gap

        # settings gear (right side)
        gx = w - 40
        hover = self._tab_hover == "__settings__"
        col = acc if hover else TEXT_DIM
        r = 13 if not hover else 15
        pts = []
        for i in range(16):
            a = math.pi * 2 * i / 16
            rr = r if i % 2 == 0 else r * 0.72
            pts += [gx + rr * math.cos(a), h / 2 - 2 + rr * math.sin(a)]
        if hover:
            c.create_oval(gx - r - 6, h / 2 - r - 8, gx + r + 6, h / 2 + r + 4, outline=dim(acc, 0.4), width=3)
        c.create_polygon(pts, outline=col, fill=blend(BG, col, 0.15), width=2)
        c.create_oval(gx - 5, h / 2 - 7, gx + 5, h / 2 + 3, outline=col, width=2)
        self._tab_boxes.append((gx - 22, gx + 22, "__settings__"))
        # clock, like the XMB / Xbox dashboard corner
        self._clock_id = c.create_text(gx - 36, h / 2 - 2, text=time.strftime("%I:%M %p").lstrip("0"),
                                       font=self.fonts["mono"], fill=TEXT_DIM, anchor="e")

    def _tab_at(self, x):
        for x1, x2, key in self._tab_boxes:
            if x1 <= x <= x2:
                return key
        return None

    def _set_tab_hover(self, key):
        if key != self._tab_hover:
            self._tab_hover = key
            self.nav.configure(cursor="hand2" if key else "")
            self._draw_nav()

    def _nav_motion(self, e):
        self._set_tab_hover(self._tab_at(e.x))

    def _nav_click(self, e):
        key = self._tab_at(e.x)
        if key == "__settings__":
            self.sound.play_select()
            self.open_settings()
        elif key:
            self.sound.play_select()
            self.show_page(key)

    def _bind_keys(self):
        for i, (key, *_rest) in enumerate(PAGE_LIST, start=1):
            self.root.bind_all(f"<Control-Key-{i}>", lambda e, k=key: self.show_page(k))
        self.root.bind_all("<Control-comma>", lambda e: self.open_settings())

    # ---- pages ---------------------------------------------------------------------
    def _get_page(self, key):
        if key not in self.pages:
            import importlib
            for k, _label, module, cls in PAGE_LIST:
                if k == key:
                    mod = importlib.import_module(f".pages.{module}", __package__)
                    self.pages[key] = getattr(mod, cls)(self.container, self)
                    break
        return self.pages[key]

    def show_page(self, key, animate=True, **kwargs):
        """Switch pages with a quick fade (dip) transition."""
        if self._transitioning:
            return
        if key == self.current:
            self.pages[key].on_show(**kwargs)
            return
        if animate and self.cfg.get("animations", True) and self._alpha_supported():
            self._transitioning = True
            self._fade(1.0, 0.2, 5, lambda: self._swap(key, kwargs, fade_in=True))
        else:
            self._swap(key, kwargs, fade_in=False)

    def _alpha_supported(self):
        try:
            self.root.attributes("-alpha")
            return True
        except tk.TclError:
            return False

    def _fade(self, start, end, steps, then):
        def step(i):
            a = start + (end - start) * i / steps
            try:
                self.root.attributes("-alpha", a)
            except tk.TclError:
                pass
            if i < steps:
                self.root.after(16, lambda: step(i + 1))
            else:
                then()
        step(0)

    def _swap(self, key, kwargs, fade_in):
        try:
            old = self.pages.get(self.current)
            if old is not None:
                old.on_hide()
                old.pack_forget()
            page = self._get_page(key)
            page.pack(fill="both", expand=True)
            self.current = key
            self._draw_nav()
            page.on_show(**kwargs)
            self.root.update_idletasks()
        except Exception:
            self._transitioning = False
            self.root.attributes("-alpha", 1.0)
            raise
        if fade_in:
            self._fade(0.2, 1.0, 6, self._end_transition)
        else:
            self._transitioning = False

    def _end_transition(self):
        self._transitioning = False

    def rebuild_pages(self):
        """Recreate pages (after a spacing change). Text size changes are live."""
        current = self.current or "home"
        for page in self.pages.values():
            page.destroy()
        self.pages.clear()
        self.current = None
        self.nav.configure(height=self._nav_height())
        self.show_page(current, animate=False)

    # ---- animation clock ---------------------------------------------------------------
    def _tick(self):
        now = time.perf_counter()
        dt = min(0.1, now - self._last_tick)
        self._last_tick = now
        page = self.pages.get(self.current)
        animated = self.cfg.get("animations", True)
        if page is not None:
            # With animations off we still redraw (so hover effects and
            # canvas-drawn pages never go blank), but time stands still.
            try:
                page.tick(dt if animated else 0.0)
            except tk.TclError:
                pass  # page was being destroyed
            except Exception:
                traceback.print_exc()
        if int(now) != int(now - dt):  # once a second: update the clock
            try:
                self.nav.itemconfigure(self._clock_id, text=time.strftime("%I:%M %p").lstrip("0"))
            except (tk.TclError, AttributeError):
                pass
        spent = time.perf_counter() - now
        fps = FPS if animated else 10  # save CPU when nothing moves
        self.root.after(max(5, int(1000 / fps - spent * 1000)), self._tick)

    # ---- background work -------------------------------------------------------------
    def run_async(self, work, on_done=None, on_error=None):
        """Run `work()` on a background thread so the window never freezes.
        on_done(result) / on_error(message) are called back on the UI thread."""
        def runner():
            try:
                result = work()
            except FriendlyError as e:
                self._ui_queue.put((on_error, str(e)))
            except Exception as e:  # unexpected: log details, show something friendly
                traceback.print_exc()
                self._ui_queue.put((on_error, f"Something went wrong: {e}"))
            else:
                self._ui_queue.put((on_done, result))
        threading.Thread(target=runner, daemon=True).start()

    def call_soon(self, fn, *args):
        """Thread-safe: ask the UI thread to run fn(*args) (for progress updates)."""
        self._ui_queue.put((lambda _r: fn(*args), None))

    def _pump_ui_queue(self):
        try:
            while True:
                callback, value = self._ui_queue.get_nowait()
                if callback:
                    try:
                        callback(value)
                    except Exception:
                        traceback.print_exc()
        except queue.Empty:
            pass
        self.root.after(40, self._pump_ui_queue)

    # ---- settings ------------------------------------------------------------------
    def open_settings(self, focus=None):
        from .settings_dialog import SettingsDialog
        SettingsDialog(self, focus=focus)

    def apply_settings(self, old_cfg):
        save_config(self.cfg)
        self.fonts.set_scale(self.cfg.get("ui_scale", 1.0))
        self.sound.reload_select_sound()
        if self.cfg.get("ui_spacing") != old_cfg.get("ui_spacing") or \
                self.cfg.get("ui_scale") != old_cfg.get("ui_scale"):
            self.rebuild_pages()
        else:
            self._draw_nav()

    def quit(self):
        self.sound.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
