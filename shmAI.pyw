"""
Double-click to open shmAI without a terminal window (Windows: .pyw files
run with pythonw). On a Mac or Linux, use the icon made by
"Create Desktop Icon" instead.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shmai.launcher import main  # noqa: E402

main()
