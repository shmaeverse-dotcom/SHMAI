#!/usr/bin/env python3
"""
Make a dated backup copy of a shmAI folder so you can always roll back.

    python3 scripts/backup.py                       # back up THIS folder
    python3 scripts/backup.py "C:/path/to/old/SHMAI" # back up another folder
    python3 scripts/backup.py --label before-vnext   # add a name to the backup

Backups go to  backups/shmai_<label>_<date-time>/  inside this folder.
To roll back: copy the files from that backup folder over your app folder
(or just run  python3 muse.py  from inside the backup folder).
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SKIP = {"backups", "node_modules", ".git", "__pycache__", ".wrangler", ".venv", "venv"}


def main():
    ap = argparse.ArgumentParser(description="Back up a shmAI folder.")
    ap.add_argument("source", nargs="?", default=str(HERE), help="folder to back up (default: this app)")
    ap.add_argument("--label", default="backup", help="short name for the backup, e.g. v1")
    args = ap.parse_args()

    src = Path(args.source).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")
    label = "".join(ch for ch in args.label if ch.isalnum() or ch in "-_") or "backup"
    dest = HERE / "backups" / f"shmai_{label}_{time.strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(src, dest, ignore=lambda d, names: [n for n in names if n in SKIP])
    count = sum(1 for p in dest.rglob("*") if p.is_file())
    print(f"Backed up {count} files\n  from {src}\n  to   {dest}")


if __name__ == "__main__":
    main()
