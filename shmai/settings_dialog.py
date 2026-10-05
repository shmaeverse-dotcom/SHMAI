"""
Settings window: server connection, display size/spacing, sound, folders.
Opened from the gear icon (top-right), Home > Settings, or Ctrl+comma.
"""
import tkinter as tk
from tkinter import filedialog

from .theme import BG, PANEL, PAGES, TEXT_DIM
from .widgets.controls import GlowButton, Panel, Toggle, label, make_entry, make_scale
from .worker_client import WorkerClient


class SettingsDialog(tk.Toplevel):
    def __init__(self, app, focus=None):
        super().__init__(app.root, bg=BG)
        self.app = app
        self.title("shmAI Settings")
        self.transient(app.root)
        self.resizable(True, True)
        self.accent = PAGES["home"]["accent"]
        acc = self.accent
        sp = app.sp
        cfg = app.cfg

        self.v_url = tk.StringVar(value=cfg.get("worker_url", ""))
        self.v_token = tk.StringVar(value=cfg.get("app_token", ""))
        self.v_out = tk.StringVar(value=cfg.get("output_dir", ""))
        self.v_sound_file = tk.StringVar(value=cfg.get("select_sound", ""))
        self.v_scale = tk.DoubleVar(value=cfg.get("ui_scale", 1.0))
        self.v_spacing = tk.DoubleVar(value=cfg.get("ui_spacing", 1.0))

        outer = tk.Frame(self, bg=BG, padx=sp(20), pady=sp(16))
        outer.pack(fill="both", expand=True)
        label(outer, app, "SETTINGS", font="h1", fg=acc, bg=BG).pack(anchor="w", pady=(0, sp(10)))

        # ---- server -------------------------------------------------------------
        box = Panel(outer, acc, padx=sp(16), pady=sp(12))
        box.pack(fill="x", pady=sp(6))
        label(box, app, "SERVER (Cloudflare Worker)", font="h2", fg=acc).grid(row=0, column=0, columnspan=3,
                                                                              sticky="w", pady=(0, sp(8)))
        label(box, app, "Worker URL").grid(row=1, column=0, sticky="w")
        make_entry(box, app, acc, self.v_url, width=46).grid(row=1, column=1, columnspan=2, sticky="we", pady=sp(4))
        label(box, app, "App Token").grid(row=2, column=0, sticky="w")
        self.token_entry = make_entry(box, app, acc, self.v_token, width=36)
        self.token_entry.configure(show="•")
        self.token_entry.grid(row=2, column=1, sticky="we", pady=sp(4))
        Toggle(box, app, "hide", "show", False, accent=acc,
               command=lambda on: self.token_entry.configure(show="" if on else "•")).grid(row=2, column=2, padx=sp(8))
        label(box, app, "Example URL:  https://shmai-worker.your-name.workers.dev", font="small",
              fg=TEXT_DIM).grid(row=3, column=1, columnspan=2, sticky="w")
        row = tk.Frame(box, bg=PANEL)
        row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(sp(8), 0))
        GlowButton(row, app, "Test Connection", self._test, accent=acc, bg=PANEL).pack(side="left")
        self.test_msg = label(row, app, "", font="small", fg=TEXT_DIM, wraplength=520, justify="left")
        self.test_msg.pack(side="left", padx=sp(12))
        box.columnconfigure(1, weight=1)

        # ---- display -----------------------------------------------------------------
        disp = Panel(outer, acc, padx=sp(16), pady=sp(12))
        disp.pack(fill="x", pady=sp(6))
        label(disp, app, "DISPLAY", font="h2", fg=acc).grid(row=0, column=0, columnspan=2, sticky="w")
        label(disp, app, "Text size").grid(row=1, column=0, sticky="w")
        self.scale_slider = make_scale(disp, app, acc, self.v_scale, 0.8, 1.6, resolution=0.05, length=320)
        self.scale_slider.grid(row=1, column=1, sticky="w")
        label(disp, app, "Spacing").grid(row=2, column=0, sticky="w")
        make_scale(disp, app, acc, self.v_spacing, 0.6, 1.8, resolution=0.05, length=320).grid(row=2, column=1,
                                                                                               sticky="w")
        self.anim = Toggle(disp, app, "Animations off", "on", cfg.get("animations", True), accent=acc)
        self.anim.grid(row=3, column=0, columnspan=2, sticky="w", pady=sp(4))

        # ---- sound + files ----------------------------------------------------------------
        misc = Panel(outer, acc, padx=sp(16), pady=sp(12))
        misc.pack(fill="x", pady=sp(6))
        label(misc, app, "SOUND & FILES", font="h2", fg=acc).grid(row=0, column=0, columnspan=3, sticky="w")
        self.snd = Toggle(misc, app, "Selection sound off", "on", cfg.get("sound_enabled", True), accent=acc)
        self.snd.grid(row=1, column=0, columnspan=3, sticky="w", pady=sp(4))
        label(misc, app, "Custom sound (.wav)").grid(row=2, column=0, sticky="w")
        make_entry(misc, app, acc, self.v_sound_file, width=34).grid(row=2, column=1, sticky="we", pady=sp(4))
        GlowButton(misc, app, "Browse", lambda: self._browse_file(self.v_sound_file), accent=acc,
                   bg=PANEL).grid(row=2, column=2, padx=sp(6))
        label(misc, app, "Save files to").grid(row=3, column=0, sticky="w")
        make_entry(misc, app, acc, self.v_out, width=34).grid(row=3, column=1, sticky="we", pady=sp(4))
        GlowButton(misc, app, "Browse", self._browse_dir, accent=acc, bg=PANEL).grid(row=3, column=2, padx=sp(6))
        misc.columnconfigure(1, weight=1)

        # ---- buttons ----------------------------------------------------------------------
        btns = tk.Frame(outer, bg=BG)
        btns.pack(fill="x", pady=(sp(12), 0))
        GlowButton(btns, app, "Save", self._save, accent=acc, primary=True).pack(side="right")
        GlowButton(btns, app, "Cancel", self.destroy, accent=acc).pack(side="right", padx=sp(10))

        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        if focus == "display":
            self.scale_slider.focus_set()

    def _browse_dir(self):
        path = filedialog.askdirectory(parent=self, initialdir=self.v_out.get() or None)
        if path:
            self.v_out.set(path)

    def _browse_file(self, var):
        path = filedialog.askopenfilename(parent=self, filetypes=[("WAV sound", "*.wav"), ("All files", "*.*")])
        if path:
            var.set(path)

    def _test(self):
        # Test with the values typed in the box, even before saving.
        temp = dict(self.app.cfg, worker_url=self.v_url.get().strip(), app_token=self.v_token.get().strip())
        self.test_msg.configure(text="Contacting server...", fg=TEXT_DIM)

        def done(data):
            if self.winfo_exists():
                self.test_msg.configure(text=f"Connected ✓  Model: {data.get('model', '?')}", fg=self.accent)

        def fail(msg):
            if self.winfo_exists():
                self.test_msg.configure(text=msg, fg="#ff7a7a")
        self.app.run_async(WorkerClient(temp).health, done, fail)

    def _save(self):
        old = dict(self.app.cfg)
        cfg = self.app.cfg
        cfg["worker_url"] = self.v_url.get().strip().rstrip("/")
        cfg["app_token"] = self.v_token.get().strip()
        cfg["output_dir"] = self.v_out.get().strip() or old.get("output_dir")
        cfg["select_sound"] = self.v_sound_file.get().strip()
        cfg["ui_scale"] = round(float(self.v_scale.get()), 2)
        cfg["ui_spacing"] = round(float(self.v_spacing.get()), 2)
        cfg["animations"] = self.anim.get()
        cfg["sound_enabled"] = self.snd.get()
        self.destroy()
        self.app.apply_settings(old)
