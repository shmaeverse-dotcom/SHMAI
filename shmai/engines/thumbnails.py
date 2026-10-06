"""
Downloads small preview images (thumbnails) for Beat Finder results.

Needs Pillow (pip install pillow) to read JPG/WEBP; without it the list
just shows a music-note tile instead.
"""
import io
from concurrent.futures import ThreadPoolExecutor

import requests

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

_pool = ThreadPoolExecutor(max_workers=4)
_cache = {}  # url -> PIL image (already cropped/resized)


def available():
    return Image is not None


def _fetch(url, size):
    key = (url, size)
    if key in _cache:
        return _cache[key]
    res = requests.get(url, timeout=8, headers={"User-Agent": "shmAI-desktop/1.0"})
    res.raise_for_status()
    img = Image.open(io.BytesIO(res.content)).convert("RGB")
    # crop to fill a 16:9 box, then shrink
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    img = img.resize((max(tw, int(img.width * scale)), max(th, int(img.height * scale))), Image.LANCZOS)
    left, top = (img.width - tw) // 2, (img.height - th) // 2
    img = img.crop((left, top, left + tw, top + th))
    if len(_cache) > 300:
        _cache.clear()
    _cache[key] = img
    return img


def load_async(url, size, deliver):
    """Fetch in the background; deliver(pil_image) is called from the worker
    thread. The caller must turn it into a PhotoImage on the UI thread."""
    if not url or Image is None:
        return

    def job():
        try:
            deliver(_fetch(url, size))
        except Exception:
            pass  # a missing thumbnail is never worth an error message
    _pool.submit(job)


def to_photo(pil_image):
    return ImageTk.PhotoImage(pil_image)
