"""
A glowing dashed "drop a file here" box. Also clickable (opens a file
browser), so it works even without drag-and-drop support.
"""
import tkinter as tk
from tkinter import filedialog

from .. import dnd
from ..theme import PANEL, TEXT, TEXT_DIM, blend, dim
from .fx import rounded_rect_points


class DropZone(tk.Canvas):
    def __init__(self, parent, app, accent, accent2, on_file, title="DROP A SONG HERE", height=120, bg=PANEL):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, cursor="hand2")
        self.app = app
        self.accent, self.accent2 = accent, accent2
        self.on_file = on_file
        self.title = title
        self.bg = bg
        self.hover = False
        self.drag = False
        self.busy = False
        self.loaded_name = ""
        self.loaded_info = ""
        self.message = ""
        self.dnd_on = dnd.enable_drop(self, self._dropped, on_enter=lambda: self._set_drag(True),
                                      on_leave=lambda: self._set_drag(False))
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.browse())

    # ---- state -----------------------------------------------------------------------
    def set_loaded(self, name, info=""):
        self.loaded_name, self.loaded_info, self.message, self.busy = name, info, "", False
        self.redraw()

    def set_busy(self, text):
        self.busy, self.message = True, text
        self.redraw()

    def set_message(self, text):
        self.busy, self.message = False, text
        self.redraw()

    def clear(self):
        self.loaded_name = self.loaded_info = self.message = ""
        self.busy = False
        self.redraw()

    def _set_hover(self, v):
        self.hover = v
        self.redraw()

    def _set_drag(self, v):
        self.drag = v
        self.redraw()

    # ---- input -------------------------------------------------------------------------
    def _dropped(self, paths):
        files = dnd.audio_files(paths)
        if files:
            self.app.sound.play_select()
            self.on_file(files[0])
        else:
            self.set_message("That isn't an audio file. Try WAV, MP3, M4A, FLAC, OGG or AIFF.")

    def browse(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self, title="Choose a song", filetypes=[
            ("Audio", "*.wav *.mp3 *.m4a *.flac *.ogg *.aiff *.aif"), ("All files", "*.*")])
        if path:
            self.app.sound.play_select()
            from pathlib import Path
            self.on_file(Path(path))

    # ---- drawing -------------------------------------------------------------------------
    def redraw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 100), max(self.winfo_height(), 60)
        acc, acc2 = self.accent, self.accent2
        f = self.app.fonts
        hot = self.drag or self.hover
        if self.drag:
            for g in range(3, 0, -1):
                self.create_polygon(rounded_rect_points(6 - g * 2, 6 - g * 2, w - 6 + g * 2, h - 6 + g * 2, 14),
                                    outline=dim(acc2, 0.25 * (4 - g)), fill="", width=3, smooth=True)
        self.create_polygon(rounded_rect_points(6, 6, w - 6, h - 6, 14), smooth=True, width=2,
                            outline=acc2 if hot else dim(acc, 0.8), dash=() if self.loaded_name else (10, 6),
                            fill=blend(self.bg, acc, 0.22 if self.drag else (0.1 if hot else 0.04)))
        cx, cy = w / 2, h / 2
        if self.drag:
            self.create_text(cx, cy, text="RELEASE TO USE THIS SONG", font=f["h2"], fill=acc2)
        elif self.busy:
            self.create_text(cx, cy, text=self.message, font=f["body"], fill=acc2)
        elif self.loaded_name:
            self.create_text(cx, cy - f.size("body") * 0.8, text="♫  " + self.loaded_name, font=f["body"], fill=TEXT,
                             width=w - 40)
            self.create_text(cx, cy + f.size("body") * 0.9, text=self.loaded_info, font=f["mono"], fill=acc2)
        else:
            head = self.title if self.dnd_on else "CLICK TO CHOOSE A SONG"
            self.create_text(cx, cy - f.size("small") * 0.9, text=head, font=f["h2"], fill=acc2 if hot else acc)
            self.create_text(cx, cy + f.size("small") * 1.1, font=f["small"], fill=TEXT_DIM, width=w - 40,
                             text=self.message or ("or click to browse" if self.dnd_on else "WAV · MP3 · M4A · FLAC"))
