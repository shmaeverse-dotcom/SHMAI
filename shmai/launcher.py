"""
Starts shmAI from a desktop icon, with no terminal window.

1. Checks the needed Python packages are installed. If any are missing (first
   launch), a small "Setting up shmAI" window installs them automatically.
2. Opens the app.
3. If something goes wrong, shows a message box and writes the details to
   logs/shmai.log, since there's no terminal to print to.

Used by shmAI.pyw (Windows), the macOS app bundle, and the Linux .desktop
file that scripts/install_shortcut.py creates.
"""
import importlib.util
import os
import subprocess
import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
REQUIRED = ["requests"]                        # the app can't start without these
RECOMMENDED = ["numpy", "pygame", "yt_dlp", "PIL", "tkinterdnd2"]  # features need these


def _log_file():
    LOG_DIR.mkdir(exist_ok=True)
    return open(LOG_DIR / "shmai.log", "a", encoding="utf-8", buffering=1)


def _missing(mods):
    return [m for m in mods if importlib.util.find_spec(m) is None]


def _python_exe():
    """The console-free pythonw.exe can't run pip nicely on Windows: use python.exe beside it."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return sys.executable


def _install_requirements(log):
    flags = 0x08000000 if sys.platform.startswith("win") else 0  # CREATE_NO_WINDOW
    cmd = [_python_exe(), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")]
    log.write("Running: " + " ".join(cmd) + "\n")
    proc = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags)
    log.write(proc.stdout[-4000:] + proc.stderr[-4000:] + "\n")
    if proc.returncode != 0 and "externally-managed" in proc.stderr:
        # some Linux systems protect the system Python; install for this user instead
        proc = subprocess.run(cmd + ["--user", "--break-system-packages"], capture_output=True, text=True)
        log.write(proc.stdout[-4000:] + proc.stderr[-4000:] + "\n")
    return proc.returncode == 0


def _setup_window(log):
    """Small branded window shown while packages install on first launch."""
    import tkinter as tk
    from tkinter import ttk

    win = tk.Tk()
    win.title("shmAI setup")
    win.configure(bg="#03050a")
    win.geometry("460x170")
    win.resizable(False, False)
    tk.Label(win, text="shmAI", font=("Helvetica", 26, "bold"), fg="#00e5ff", bg="#03050a").pack(pady=(18, 4))
    msg = tk.Label(win, text="Setting up for the first time... (about a minute)", font=("Helvetica", 12),
                   fg="#eef6ff", bg="#03050a")
    msg.pack()
    bar = ttk.Progressbar(win, mode="indeterminate", length=360)
    bar.pack(pady=16)
    bar.start(12)
    result = {}

    def work():
        result["ok"] = _install_requirements(log)
        win.after(0, win.destroy)

    threading.Thread(target=work, daemon=True).start()
    win.mainloop()
    return result.get("ok", False)


def _error_box(title, text):
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(title, text)
        r.destroy()
    except Exception:
        pass


def main():
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    log = _log_file()
    # With no terminal, send anything printed to the log file instead.
    if sys.stdout is None or sys.executable.lower().endswith("pythonw.exe"):
        sys.stdout = sys.stderr = log
    try:
        import tkinter  # noqa: F401
    except ImportError:
        _error_box("shmAI", "Python's Tkinter is missing. Reinstall Python from python.org.")
        return
    if _missing(REQUIRED + RECOMMENDED):
        ok = _setup_window(log)
        still = _missing(REQUIRED)
        if still:
            _error_box("shmAI setup",
                       "Couldn't install the parts shmAI needs (check your internet connection).\n\n"
                       f"Details are in {LOG_DIR / 'shmai.log'}")
            return
        if not ok:
            log.write("Some optional packages failed to install; continuing.\n")
    try:
        from shmai.app import App
        App().run()
    except Exception:
        log.write(traceback.format_exc())
        _error_box("shmAI crashed", "Sorry, shmAI hit an error and closed.\n\n"
                                    f"Details were saved to {LOG_DIR / 'shmai.log'}")


if __name__ == "__main__":
    main()
