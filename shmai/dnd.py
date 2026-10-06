"""
Drag-and-drop of files from Explorer / Finder / your file manager.

Plain Tkinter can't receive dropped files, so we use the small free
"tkinterdnd2" package (pip install tkinterdnd2), which includes what's needed
for Windows, macOS and Linux. Without it, the app still works: the drop
areas just act as click-to-browse buttons.
"""
import tkinter as tk
from pathlib import Path
from urllib.parse import unquote, urlparse

AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aif", ".aiff", ".opus", ".aac", ".wma", ".webm"}

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:  # not installed, or its native part failed to load
    TkinterDnD = None
    DND_FILES = None

_enabled = False


def make_root():
    """Create the main window, with drag-and-drop support when available."""
    global _enabled
    if TkinterDnD is not None:
        try:
            root = TkinterDnD.Tk()
            _enabled = True
            return root
        except Exception as e:  # e.g. the native library couldn't load on this system
            print(f"[shmAI] Drag-and-drop unavailable: {e}")
    return tk.Tk()


def available():
    return _enabled


def _paths_from_event(widget, data):
    paths = []
    for item in widget.tk.splitlist(data):
        if item.startswith("file://"):  # some Linux file managers send URLs
            item = unquote(urlparse(item).path)
        paths.append(Path(item))
    return paths


def audio_files(paths):
    return [p for p in paths if p.suffix.lower() in AUDIO_EXTS and p.is_file()]


def enable_drop(widget, on_drop, on_enter=None, on_leave=None):
    """Let `widget` accept dropped files. on_drop(list_of_Paths) gets every
    dropped file (callers usually filter with audio_files()). Returns True if
    drag-and-drop is active."""
    if not _enabled:
        return False

    def drop(event):
        if on_leave:
            on_leave()
        on_drop(_paths_from_event(widget, event.data))
        return event.action

    def enter(event):
        if on_enter:
            on_enter()
        return event.action

    def leave(event):
        if on_leave:
            on_leave()
        return event.action

    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", drop)
        widget.dnd_bind("<<DropEnter>>", enter)
        widget.dnd_bind("<<DropLeave>>", leave)
        return True
    except (tk.TclError, AttributeError):
        return False
