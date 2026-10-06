#!/bin/bash
# Double-click once (Mac) to create the shmAI icon. A Terminal window opens
# only for this one-time setup; after that, open shmAI from its icon.
cd "$(dirname "$0")"
PY=$(command -v python3)
"$PY" scripts/install_shortcut.py
