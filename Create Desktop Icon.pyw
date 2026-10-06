"""Double-click once to create the shmAI desktop icon (Windows)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "scripts" / "install_shortcut.py"), run_name="__main__")
