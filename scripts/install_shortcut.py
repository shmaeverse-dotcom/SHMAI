#!/usr/bin/env python3
"""
Creates shmAI icons so the app opens with a click: no terminal.

Run it once by double-clicking "Create Desktop Icon" in the shmAI folder.
A small window lets you choose:
    [x] Icon on my Desktop
    [x] Add to Start menu (Windows) / Applications (Mac) / app menu (Linux)
    [ ] Open shmAI automatically when I log in

What gets created:
    Windows  shortcuts (.lnk) that run shmAI.pyw with pythonw (no console)
    macOS    ~/Applications/shmAI.app (+ a Desktop alias, + a login item)
    Linux    shmai.desktop launchers (+ autostart entry)

"Remove icons" undoes all of it. If you move the shmAI folder, run this again.
"""
import os
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_PNG = ROOT / "assets" / "icon.png"
ICON_ICO = ROOT / "assets" / "icon.ico"
ICON_ICNS = ROOT / "assets" / "icon.icns"
LAUNCHER = ROOT / "shmai" / "launcher.py"
APP_NAME = "shmAI"


# ---------------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------------
def _pythonw():
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def _ps(script):
    flags = 0x08000000  # no console window
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, creationflags=flags)


def _win_folder(name):
    """Real Desktop/Programs/Startup folder (handles OneDrive-redirected Desktops)."""
    res = _ps(f"[Environment]::GetFolderPath('{name}')")
    return Path(res.stdout.strip()) if res.returncode == 0 and res.stdout.strip() else None


def _win_targets(desktop, menu, login):
    out = []
    for wanted, folder in ((desktop, "Desktop"), (menu, "Programs"), (login, "Startup")):
        if wanted:
            path = _win_folder(folder)
            if path:
                out.append(path / f"{APP_NAME}.lnk")
    return out


def install_windows(desktop, menu, login):
    made = []
    for lnk in _win_targets(desktop, menu, login):
        script = (
            "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
            "$s.TargetPath = '{target}'; $s.Arguments = '\"{pyw}\"';"
            "$s.WorkingDirectory = '{root}'; $s.IconLocation = '{icon}';"
            "$s.Description = 'shmAI music studio'; $s.Save()"
        ).format(lnk=str(lnk).replace("'", "''"), target=_pythonw().replace("'", "''"),
                 pyw=str(ROOT / "shmAI.pyw").replace("'", "''"), root=str(ROOT).replace("'", "''"),
                 icon=str(ICON_ICO).replace("'", "''"))
        res = _ps(script)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or "PowerShell couldn't create the shortcut.")
        made.append(str(lnk))
    return made


def remove_windows():
    removed = []
    for lnk in _win_targets(True, True, True):
        if lnk.exists():
            lnk.unlink()
            removed.append(str(lnk))
    return removed


# ---------------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------------
MAC_APP = Path.home() / "Applications" / f"{APP_NAME}.app"
MAC_DESKTOP = Path.home() / "Desktop" / f"{APP_NAME}.app"
MAC_AGENT = Path.home() / "Library" / "LaunchAgents" / "com.shmai.app.plist"


def install_mac(desktop, menu, login):
    made = []
    contents = MAC_APP / "Contents"
    (contents / "MacOS").mkdir(parents=True, exist_ok=True)
    (contents / "Resources").mkdir(parents=True, exist_ok=True)
    runner = contents / "MacOS" / APP_NAME
    runner.write_text(f'#!/bin/bash\ncd "{ROOT}"\nexec "{sys.executable}" "{LAUNCHER}"\n')
    runner.chmod(runner.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    shutil.copyfile(ICON_ICNS, contents / "Resources" / "icon.icns")
    with open(contents / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleName": APP_NAME, "CFBundleDisplayName": APP_NAME, "CFBundleExecutable": APP_NAME,
                       "CFBundleIdentifier": "com.shmai.app", "CFBundleIconFile": "icon", "CFBundlePackageType": "APPL",
                       "CFBundleShortVersionString": "1.0", "NSHighResolutionCapable": True}, f)
    made.append(str(MAC_APP))  # the app bundle itself lives in ~/Applications
    if desktop:
        if MAC_DESKTOP.is_symlink() or MAC_DESKTOP.exists():
            MAC_DESKTOP.unlink()
        os.symlink(MAC_APP, MAC_DESKTOP)
        made.append(str(MAC_DESKTOP))
    if login:
        MAC_AGENT.parent.mkdir(parents=True, exist_ok=True)
        with open(MAC_AGENT, "wb") as f:
            plistlib.dump({"Label": "com.shmai.app", "ProgramArguments": ["/usr/bin/open", "-a", str(MAC_APP)],
                           "RunAtLoad": True}, f)
        made.append(str(MAC_AGENT))
    return made


def remove_mac():
    removed = []
    for p in (MAC_DESKTOP, MAC_AGENT):
        if p.is_symlink() or p.exists():
            p.unlink()
            removed.append(str(p))
    if MAC_APP.exists():
        shutil.rmtree(MAC_APP)
        removed.append(str(MAC_APP))
    return removed


# ---------------------------------------------------------------------------------
# Linux
# ---------------------------------------------------------------------------------
def _linux_paths():
    desktop_dir = Path.home() / "Desktop"
    try:
        out = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True).stdout.strip()
        if out:
            desktop_dir = Path(out)
    except FileNotFoundError:
        pass
    return {
        "menu": Path.home() / ".local/share/applications/shmai.desktop",
        "desktop": desktop_dir / "shmai.desktop",
        "login": Path.home() / ".config/autostart/shmai.desktop",
    }


def install_linux(desktop, menu, login):
    entry = (
        "[Desktop Entry]\nType=Application\nName=shmAI\nComment=shmAI music studio\n"
        f'Exec="{sys.executable}" "{LAUNCHER}"\nPath={ROOT}\nIcon={ICON_PNG}\nTerminal=false\n'
        "Categories=AudioVideo;Audio;\nStartupWMClass=Tk\n"
    )
    made = []
    for key, wanted in (("menu", menu), ("desktop", desktop), ("login", login)):
        if not wanted:
            continue
        path = _linux_paths()[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry)
        path.chmod(0o755)
        if key == "desktop" and shutil.which("gio"):  # let GNOME launch it without asking
            subprocess.run(["gio", "set", str(path), "metadata::trusted", "true"], capture_output=True)
        made.append(str(path))
    return made


def remove_linux():
    removed = []
    for path in _linux_paths().values():
        if path.exists():
            path.unlink()
            removed.append(str(path))
    return removed


# ---------------------------------------------------------------------------------
def install(desktop=True, menu=True, login=False):
    if sys.platform.startswith("win"):
        return install_windows(desktop, menu, login)
    if sys.platform == "darwin":
        return install_mac(desktop, menu, login)
    return install_linux(desktop, menu, login)


def remove():
    if sys.platform.startswith("win"):
        return remove_windows()
    if sys.platform == "darwin":
        return remove_mac()
    return remove_linux()


def gui():
    import tkinter as tk
    from tkinter import messagebox

    bg, fg, acc = "#03050a", "#eef6ff", "#00e5ff"
    win = tk.Tk()
    win.title("shmAI: desktop icon")
    win.configure(bg=bg, padx=24, pady=18)
    win.resizable(False, False)
    try:
        win.iconphoto(True, tk.PhotoImage(file=str(ICON_PNG)))
    except tk.TclError:
        pass
    tk.Label(win, text="shmAI", font=("Helvetica", 26, "bold"), fg=acc, bg=bg).pack(anchor="w")
    tk.Label(win, text="Open shmAI with a click: no terminal needed.", font=("Helvetica", 12), fg=fg,
             bg=bg).pack(anchor="w", pady=(0, 12))
    menu_name = {"win32": "Start menu", "darwin": "Applications"}.get(sys.platform, "app menu")
    v_desk, v_menu, v_login = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=False)
    for var, text in ((v_desk, "Put a shmAI icon on my Desktop"), (v_menu, f"Add shmAI to the {menu_name}"),
                      (v_login, "Open shmAI automatically when I log in")):
        tk.Checkbutton(win, text=text, variable=var, font=("Helvetica", 13), fg=fg, bg=bg, selectcolor="#10202a",
                       activebackground=bg, activeforeground=acc, highlightthickness=0).pack(anchor="w", pady=2)

    def do_install():
        try:
            made = install(v_desk.get(), v_menu.get(), v_login.get())
        except Exception as e:
            messagebox.showerror("shmAI", f"Couldn't create the icon:\n{e}")
            return
        messagebox.showinfo("shmAI", "Done! Double-click the shmAI icon to open the app.\n\n" + "\n".join(made))
        win.destroy()

    def do_remove():
        removed = remove()
        messagebox.showinfo("shmAI", "Removed:\n" + "\n".join(removed) if removed else "Nothing to remove.")

    row = tk.Frame(win, bg=bg)
    row.pack(fill="x", pady=(16, 0))
    tk.Button(row, text="Create icon", command=do_install, font=("Helvetica", 13, "bold"), bg=acc, fg="#02121a",
              activebackground="#7af4ff", relief="flat", padx=16, pady=6).pack(side="right")
    tk.Button(row, text="Remove icons", command=do_remove, font=("Helvetica", 12), bg="#16202a", fg=fg,
              relief="flat", padx=12, pady=6).pack(side="left")
    win.mainloop()


if __name__ == "__main__":
    if "--yes" in sys.argv:          # non-interactive: desktop + menu
        print("\n".join(install(True, True, "--login" in sys.argv)))
    elif "--remove" in sys.argv:
        print("\n".join(remove()))
    else:
        gui()
