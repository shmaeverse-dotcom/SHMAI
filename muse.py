#!/usr/bin/env python3
"""
shmAI: start here.

    python3 muse.py

Pages: Home (XMB menu), Beat Finder, Audio Analyzer (+ Key Finder),
Melody Generator, Song Writer, and Clarity (coming soon).

Song Writer and the cloud Melody Generator talk to YOUR Cloudflare Worker.
Set its URL and App Token in Settings (gear icon, top-right) or in
config.json. See README.md for step-by-step setup.
"""
import sys

if sys.version_info < (3, 9):
    sys.exit("shmAI needs Python 3.9 or newer. You have " + sys.version.split()[0])

try:
    import tkinter  # noqa: F401
except ImportError:
    sys.exit("Tkinter is missing. On Linux: sudo apt install python3-tk. "
             "On Mac/Windows: reinstall Python from python.org (Tkinter is included).")

try:
    import requests  # noqa: F401
except ImportError:
    sys.exit("Some packages are missing. Run:  python3 -m pip install -r requirements.txt")

from shmai.app import App


def main():
    App().run()


if __name__ == "__main__":
    main()
