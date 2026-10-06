"""
BEAT FINDER: original-Xbox music player layout, Xbox green.

    Header bar with the search bar + SEARCH (kept from before).
    Left: a column of chunky pill buttons (sources + actions), like the
          original Xbox "Music" screen's button stack.
    Center: the track list inside a thick, glowing rounded frame, with
          organic green "tubes" curling around the edges.
    Bottom: progress/status strip with the DOWNLOAD button (kept).

Sources: YouTube (yt-dlp), SoundCloud, Bandcamp, Mixcloud (SoundScrape with
yt-dlp as backup). Bandcamp and Mixcloud work by pasting a link.

REFERENCE-LAYOUT FLAG: built from the written description (original Xbox
music player). Compare against your reference images.
"""
import math
import tkinter as tk
from tkinter import ttk

from ..config import output_dir
from ..engines import downloader as dl
from ..sound import open_folder
from ..theme import BG, PANEL, TEXT, TEXT_DIM, blend, dim
from ..engines import thumbnails
from ..widgets.result_list import ResultList
from ..widgets.controls import (GlowButton, Panel, label, make_combo, make_entry,
                                style_ttk)
from ..widgets.fx import rounded_rect_points
from .base import BasePage

PLACEHOLDER = {
    "YouTube": "Search YouTube, or paste a link",
    "SoundCloud": "Search SoundCloud, or paste a link",
    "Bandcamp": "Paste a Bandcamp track or album link",
    "Mixcloud": "Paste a Mixcloud mix link",
}


class BeatFinderPage(BasePage):
    key = "beat"
    role = "executive"
    reference_layout = "original Xbox music player"

    def build(self):
        app, acc, sp = self.app, self.accent, self.sp
        self.t = 0.0
        self.results = []
        self.downloaded = {}   # url -> local file path
        self.busy = False
        self.v_source = tk.StringVar(value="YouTube")
        self.v_query = tk.StringVar()

        # ---- search bar (header) ----
        self.search = tk.Frame(self.canvas, bg=BG)
        make_combo(self.search, app, acc, "beat", dl.SOURCES, self.v_source, width=11).pack(side="left")
        self.entry = make_entry(self.search, app, acc, self.v_query, width=40)
        self.entry.pack(side="left", padx=sp(10), ipady=sp(5), fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self.do_search())
        self.search_btn = GlowButton(self.search, app, "SEARCH", self.do_search, accent=acc, primary=True)
        self.search_btn.pack(side="left")
        self.v_source.trace_add("write", lambda *a: self._source_changed())

        # ---- left pill column ----
        self.left = tk.Frame(self.canvas, bg=BG)
        self.src_btns = {}
        pill_w = int(190 * app.fonts.scale)
        pill_h = app.fonts["button_hover"].metrics("linespace") + 16  # compact pills so the column fits
        label(self.left, app, "SOURCES", font="small", fg=dim(acc, 0.9), bg=BG).pack(anchor="w", pady=(0, sp(4)))
        for name in dl.SOURCES:
            b = GlowButton(self.left, app, name, lambda n=name: self.v_source.set(n), accent=acc,
                           width=pill_w, height=pill_h)
            b.pack(anchor="w", pady=sp(2))
            self.src_btns[name] = b
        label(self.left, app, "ACTIONS", font="small", fg=dim(acc, 0.9), bg=BG).pack(anchor="w", pady=(sp(14), sp(4)))
        self.play_btn = GlowButton(self.left, app, "PLAY", self.play_selected, accent=acc,
                                   width=pill_w, height=pill_h)
        self.play_btn.pack(anchor="w", pady=sp(2))
        GlowButton(self.left, app, "STOP", self.app.sound.stop, accent=acc,
                   width=pill_w, height=pill_h).pack(anchor="w", pady=sp(2))
        GlowButton(self.left, app, "OPEN FOLDER", lambda: open_folder(output_dir(app.cfg, "Beat Finder")),
                   accent=acc, width=pill_w, height=pill_h).pack(anchor="w", pady=sp(2))

        # ---- track list ----
        self.list_frame = tk.Frame(self.canvas, bg=PANEL)
        head = tk.Frame(self.list_frame, bg=PANEL)
        head.pack(fill="x", pady=(0, sp(4)))
        self.count_lbl = label(head, app, "TRACKS", font="h2", fg=acc)
        self.count_lbl.pack(side="left")
        self.src_lbl = label(head, app, "", font="small", fg=TEXT_DIM)
        self.src_lbl.pack(side="right")
        # results with thumbnails: click = select, double-click / Enter = download
        self.results_view = ResultList(self.list_frame, app, acc, on_select=lambda i: self._selection_changed(),
                                       on_activate=lambda i: self.download_selected())
        self.results_view.pack(fill="both", expand=True)

        # ---- bottom status strip with DOWNLOAD ----
        self.bottom = Panel(self.canvas, acc, padx=sp(14), pady=sp(10))
        self.dl_btn = GlowButton(self.bottom, app, "DOWNLOAD", self.download_selected, accent=acc, primary=True,
                                 bg=PANEL)
        self.dl_btn.pack(side="left")
        info = tk.Frame(self.bottom, bg=PANEL)
        info.pack(side="left", fill="x", expand=True, padx=sp(14))
        self.status = label(info, app, "Search for beats, samples or references.", font="body", fg=TEXT,
                            anchor="w", justify="left")
        self.status.pack(fill="x")
        style_ttk(app, "beat", acc)
        self.progress = ttk.Progressbar(info, style="beat.Horizontal.TProgressbar", maximum=1.0, mode="determinate")
        self.progress.pack(fill="x", pady=(sp(6), 0))

        self.search_id = self.win(self.search, 0, 0)
        self.left_id = self.win(self.left, 0, 0)
        self.list_id = self.win(self.list_frame, 0, 0)
        self.bottom_id = self.win(self.bottom, 0, 0)
        self._source_changed()
        self._update_buttons()

    # ---- page events -------------------------------------------------------------
    def on_show(self, source=None, **kwargs):
        if source in dl.SOURCES:
            self.v_source.set(source)
        self.entry.focus_set()

    def _source_changed(self):
        src = self.v_source.get()
        for name, b in self.src_btns.items():
            b.primary = name == src
            b._draw()
        self.src_lbl.configure(text=PLACEHOLDER.get(src, ""))
        if src in ("Bandcamp", "Mixcloud") and not dl.have_soundscrape():
            self.src_lbl.configure(text=PLACEHOLDER[src] + "  (SoundScrape not installed: using yt-dlp)")

    # ---- layout + decoration ----------------------------------------------------------
    def _geometry(self, w, h):
        sp = self.sp
        m = sp(28)
        head_h = self.search.winfo_reqheight()
        left_w = self.left.winfo_reqwidth()
        bottom_h = self.bottom.winfo_reqheight()
        dancer_w = max(160, min(250, h * 0.3)) + 30
        lx = m + left_w + sp(36)
        ly = m + head_h + sp(30)
        lw = w - lx - m - dancer_w  # stop before the dancer's column
        lh = h - ly - bottom_h - m - sp(36)
        return m, head_h, left_w, lx, ly, lw, lh, bottom_h, dancer_w

    def layout(self, w, h):
        if w < 10:
            return
        m, head_h, left_w, lx, ly, lw, lh, bottom_h, dancer_w = self._geometry(w, h)
        c = self.canvas
        title_w = self.app.fonts["title"].measure("MUSIC") + self.sp(40)
        c.coords(self.search_id, m + title_w, m)
        c.itemconfigure(self.search_id, width=max(400, w - m * 2 - title_w))
        c.coords(self.left_id, m, ly)
        pad = self.sp(18)
        c.coords(self.list_id, lx + pad, ly + pad)
        c.itemconfigure(self.list_id, width=max(200, lw - pad * 2), height=max(120, lh - pad * 2))
        c.coords(self.bottom_id, m, h - m)
        c.itemconfigure(self.bottom_id, anchor="sw", width=max(400, w - m * 2 - dancer_w))
        self._draw_static(w, h)

    def _draw_static(self, w, h):
        """The thick rounded frame and title. Tubes are animated in animate()."""
        c = self.canvas
        c.delete("bf_static")
        m, head_h, left_w, lx, ly, lw, lh, bottom_h, dancer_w = self._geometry(w, h)
        acc = self.accent
        # title, original-Xbox style
        c.create_text(m, m + head_h / 2, text="MUSIC", anchor="w", font=self.app.fonts["title"],
                      fill=dim(acc, 0.35), tags="bf_static")
        c.create_text(m - 2, m + head_h / 2 - 2, text="MUSIC", anchor="w", font=self.app.fonts["title"],
                      fill=acc, tags="bf_static")
        # thick jelly frame around the track list
        r = 30
        for i in range(5, 0, -1):
            c.create_polygon(rounded_rect_points(lx - i * 2, ly - i * 2, lx + lw + i * 2, ly + lh + i * 2, r + i * 2),
                             outline=dim(acc, 0.1 * (6 - i)), fill="", width=3, smooth=True, tags="bf_static")
        c.create_polygon(rounded_rect_points(lx, ly, lx + lw, ly + lh, r), outline=acc, fill=PANEL, width=5,
                         smooth=True, tags="bf_static")
        c.create_polygon(rounded_rect_points(lx + 6, ly + 6, lx + lw - 6, ly + lh - 6, r - 6),
                         outline=blend(acc, "#ffffff", 0.4), fill="", width=1, smooth=True, tags="bf_static")
        c.tag_raise("bf_static", "starfield")

    def animate(self, dt):
        """Organic green tubes curling along the edges (original Xbox dashboard)."""
        self.t += dt
        w, h = self._size
        if w < 10:
            return
        c = self.canvas
        c.delete("bf_tubes")
        acc = self.accent
        m, head_h, left_w, lx, ly, lw, lh, bottom_h, dancer_w = self._geometry(w, h)
        for k in range(3):
            pts = []
            for i in range(30):
                t = i / 29
                x = lx + lw * (0.05 + 0.9 * t)
                y = ly - 18 - k * 9 + math.sin(t * math.pi * 3 + self.t * (0.8 + k * 0.3) + k) * 7
                pts += [x, y]
            c.create_line(pts, fill=dim(acc, 0.65 - k * 0.18), width=6 - k * 2, smooth=True, capstyle="round",
                          tags="bf_tubes")
        for k in range(2):
            pts = []
            for i in range(24):
                t = i / 23
                y = ly + lh * (0.08 + 0.84 * t)
                x = lx + lw + 16 + k * 10 + math.sin(t * math.pi * 2.5 + self.t * (0.7 + k * 0.4)) * 6
                pts += [x, y]
            c.create_line(pts, fill=dim(acc, 0.5 - k * 0.2), width=5 - k * 2, smooth=True, capstyle="round",
                          tags="bf_tubes")
        c.tag_raise("bf_tubes", "starfield")

    # ---- searching -------------------------------------------------------------------
    def do_search(self):
        if self.busy:
            return
        query = self.v_query.get().strip()
        source = self.v_source.get()
        if dl.is_url(query):
            self.v_source.set(dl.source_from_url(query))
            source = self.v_source.get()
        self._set_busy(True, f"Searching {source}...")
        self.progress.configure(mode="indeterminate")
        self.progress.start(15)

        def done(results):
            self._stop_progress()
            self._set_busy(False, f"{len(results)} result(s). Select one and press DOWNLOAD (or double-click).")
            self.results = results
            self.results_view.set_items(results)
            for i, r in enumerate(results):
                if r["url"] in self.downloaded:
                    self.results_view.mark_downloaded(i)
            self.count_lbl.configure(text=f"TRACKS  ({len(results)})")
            self._load_thumbnails(results)
            self._update_buttons()

        def fail(msg):
            self._stop_progress()
            self._set_busy(False, msg, error=True)

        self.app.run_async(lambda: dl.search(source, query), done, fail)

    def _load_thumbnails(self, results):
        """Fetch each result's preview image in the background."""
        self._thumb_batch = getattr(self, "_thumb_batch", 0) + 1
        batch = self._thumb_batch
        size = self.results_view.thumb_size()

        def show(index, pil_image):
            if batch == self._thumb_batch:  # ignore images from an older search
                self.results_view.set_thumbnail(index, thumbnails.to_photo(pil_image))

        for i, r in enumerate(results):
            thumbnails.load_async(r.get("thumbnail"), size,
                                  lambda img, i=i: self.app.call_soon(show, i, img))

    def _stop_progress(self):
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)

    # ---- downloading ---------------------------------------------------------------------
    def _selected(self):
        i = self.results_view.selected_index()
        return self.results[i] if i is not None and i < len(self.results) else None

    def download_selected(self):
        item = self._selected()
        if self.busy or not item:
            if not item:
                self.status.configure(text="Select a track first.", fg=TEXT_DIM)
            return
        idx = self.results_view.selected_index()
        self._set_busy(True, f"Downloading: {item['title']}")
        self.progress.configure(value=0)
        folder = output_dir(self.app.cfg, "Beat Finder")

        def work():
            return dl.download(item, folder,
                               progress=lambda f: self.app.call_soon(self.progress.configure, {"value": f}),
                               log=lambda text: self.app.call_soon(self.status.configure, {"text": text}))

        def done(path):
            self.downloaded[item["url"]] = path
            self.progress.configure(value=1.0)
            self._set_busy(False, f"✓ Saved: {path}")
            if self.results and idx < len(self.results) and self.results[idx]["url"] == item["url"]:
                self.results_view.mark_downloaded(idx)
            self._update_buttons()

        def fail(msg):
            self.progress.configure(value=0)
            self._set_busy(False, msg, error=True)

        self.app.run_async(work, done, fail)

    def play_selected(self):
        item = self._selected()
        path = self.downloaded.get(item["url"]) if item else None
        if not path:
            self.status.configure(text="Download the track first, then press PLAY.", fg=TEXT_DIM)
            return
        if self.app.sound.play_file(path) == "failed":
            self.status.configure(text=f"Couldn't play here: open it from the folder: {path}", fg=TEXT_DIM)

    # ---- state ----------------------------------------------------------------------------
    def _selection_changed(self):
        self._update_buttons()

    def _set_busy(self, busy, text, error=False):
        self.busy = busy
        self.status.configure(text=text, fg="#ff8080" if error else TEXT)
        self._update_buttons()

    def _update_buttons(self):
        item = self._selected()
        self.dl_btn.set_enabled(bool(item) and not self.busy)
        self.search_btn.set_enabled(not self.busy)
        self.play_btn.set_enabled(bool(item and item["url"] in self.downloaded))
