"""
Beat Finder search + download engine.

Sources:
    YouTube     search + download with yt-dlp (unchanged behavior)
    SoundCloud  search with yt-dlp ("scsearch"); download with SoundScrape,
                falling back to yt-dlp if SoundScrape fails
    Bandcamp    paste a link (Bandcamp has no search API); SoundScrape
                first, yt-dlp as backup
    Mixcloud    paste a link; SoundScrape first, yt-dlp as backup

About SoundScrape: it's an older library. On current Python it needs a
small fix (it imports "demjson", which no longer installs; we hand it
"demjson3" instead). See README "Beat Finder sources" for the install line.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..errors import FriendlyError

SOURCES = ["YouTube", "SoundCloud", "Bandcamp", "Mixcloud"]
SEARCHABLE = {"YouTube": "ytsearch", "SoundCloud": "scsearch"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".webm", ".aac"}

# Runs SoundScrape in a separate process with the demjson -> demjson3 fix.
SOUNDSCRAPE_SHIM = (
    "import sys\n"
    "try:\n"
    "    import demjson3; sys.modules['demjson'] = demjson3\n"
    "except ImportError:\n"
    "    pass\n"
    "sys.argv = ['soundscrape'] + sys.argv[1:]\n"
    "from soundscrape.soundscrape import main\n"
    "main()\n"
)


class FinderError(FriendlyError):
    """Friendly error for the Beat Finder page."""


def is_url(text):
    return bool(re.match(r"^https?://", text.strip(), re.I))


def source_from_url(url):
    u = url.lower()
    if "soundcloud.com" in u:
        return "SoundCloud"
    if "bandcamp.com" in u:
        return "Bandcamp"
    if "mixcloud.com" in u:
        return "Mixcloud"
    return "YouTube"


def have_ytdlp():
    return importlib.util.find_spec("yt_dlp") is not None


def have_soundscrape():
    return importlib.util.find_spec("soundscrape") is not None


def have_ffmpeg():
    return shutil.which("ffmpeg") is not None


class _QuietLogger:
    """Keeps yt-dlp from printing raw errors to the console; we show our own."""
    def debug(self, msg):
        pass

    info = warning = debug

    def error(self, msg):
        pass


def _ydl(opts):
    if not have_ytdlp():
        raise FinderError("yt-dlp isn't installed. Run:  python3 -m pip install yt-dlp")
    import yt_dlp
    base = {"quiet": True, "no_warnings": True, "noplaylist": True, "logger": _QuietLogger()}
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def _fmt_duration(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    return f"{sec // 60}:{sec % 60:02d}"


def search(source, query, limit=15):
    """Return a list of results: dict(title, artist, duration, url, source)."""
    query = query.strip()
    if not query:
        raise FinderError("Type something to search for, or paste a link.")
    if is_url(query):
        return _resolve_url(query)
    if source not in SEARCHABLE:
        raise FinderError(f"{source} doesn't offer search. Paste a {source} link into the search bar instead "
                          f"(e.g. https://artist.{source.lower()}.com/track/...).")
    try:
        with _ydl({"extract_flat": "in_playlist", "skip_download": True}) as ydl:
            info = ydl.extract_info(f"{SEARCHABLE[source]}{limit}:{query}", download=False)
    except FinderError:
        raise
    except Exception as e:
        raise FinderError(f"Search failed. Check your internet connection.\n({_short(e)})") from None
    results = []
    for entry in info.get("entries") or []:
        if not entry:
            continue
        url = entry.get("url") or entry.get("webpage_url") or ""
        if source == "YouTube" and url and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
        results.append({
            "title": entry.get("title") or "(untitled)",
            "artist": entry.get("uploader") or entry.get("channel") or "",
            "duration": _fmt_duration(entry.get("duration")),
            "url": url,
            "source": source,
        })
    if not results:
        raise FinderError("No results. Try different words.")
    return results


def _resolve_url(url):
    """A pasted link: list its track(s) without downloading."""
    src = source_from_url(url)
    try:
        with _ydl({"extract_flat": "in_playlist", "skip_download": True, "noplaylist": False}) as ydl:
            info = ydl.extract_info(url, download=False)
    except FinderError:
        raise
    except Exception:
        # yt-dlp couldn't read it; still offer it so SoundScrape can try.
        return [{"title": url, "artist": "", "duration": "", "url": url, "source": src}]
    entries = info.get("entries")
    if entries:
        return [{"title": e.get("title") or "(untitled)", "artist": e.get("uploader") or info.get("uploader") or "",
                 "duration": _fmt_duration(e.get("duration")), "url": e.get("url") or e.get("webpage_url") or url,
                 "source": src} for e in entries if e]
    return [{"title": info.get("title") or url, "artist": info.get("uploader") or info.get("artist") or "",
             "duration": _fmt_duration(info.get("duration")), "url": info.get("webpage_url") or url, "source": src}]


def _short(e):
    msg = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
    return re.sub(r"\x1b\[[0-9;]*m", "", msg)[:200]


def download(item, dest_dir, progress=None, log=None):
    """Download one result. Returns the saved file path.
    progress(fraction or None), log(text) are optional callbacks."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    source = item.get("source") or source_from_url(item["url"])
    errors = []
    if source in ("SoundCloud", "Bandcamp", "Mixcloud") and have_soundscrape():
        if log:
            log(f"Trying SoundScrape for {source}...")
        try:
            return _download_soundscrape(item["url"], source, dest_dir)
        except FinderError as e:
            errors.append(f"SoundScrape: {e}")
            if log:
                log("SoundScrape didn't work; trying yt-dlp...")
    try:
        return _download_ytdlp(item["url"], dest_dir, progress)
    except FinderError as e:
        errors.append(str(e))
    raise FinderError("\n".join(errors))


def _download_ytdlp(url, dest_dir, progress=None):
    def hook(d):
        if progress and d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                progress(min(0.99, d.get("downloaded_bytes", 0) / total))
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(title).120B [%(id)s].%(ext)s"),
        "progress_hooks": [hook],
        "restrictfilenames": False,
        "windowsfilenames": True,
    }
    if have_ffmpeg():
        # Convert to MP3 so every DAW and player can open it.
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}]
    try:
        with _ydl(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = Path(ydl.prepare_filename(info))
    except FinderError:
        raise
    except Exception as e:
        raise FinderError(f"Download failed: {_short(e)}") from None
    if have_ffmpeg():
        path = path.with_suffix(".mp3")
    if not path.exists():
        # fall back to the newest audio file in the folder
        path = _newest_audio(dest_dir, since=time.time() - 3600) or path
    if progress:
        progress(1.0)
    return path


def _download_soundscrape(url, source, dest_dir):
    before = {p for p in dest_dir.iterdir()} if dest_dir.exists() else set()
    started = time.time()
    args = [sys.executable, "-c", SOUNDSCRAPE_SHIM, url, "-p", str(dest_dir), "-n", "1"]
    if source == "Bandcamp":
        args.append("-b")
    elif source == "Mixcloud":
        args.append("-m")
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600, cwd=str(dest_dir),
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    except subprocess.TimeoutExpired:
        raise FinderError("timed out") from None
    new = [p for p in dest_dir.iterdir() if p not in before and p.suffix.lower() in AUDIO_EXT]
    if not new:
        new_path = _newest_audio(dest_dir, since=started)
        if new_path:
            return new_path
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise FinderError(detail[-1][:200] if detail else "no file was downloaded")
    return max(new, key=lambda p: p.stat().st_mtime)


def _newest_audio(folder, since):
    files = [p for p in Path(folder).iterdir() if p.suffix.lower() in AUDIO_EXT and p.stat().st_mtime >= since]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None
