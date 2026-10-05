# Backups

`python3 scripts/backup.py` copies an app folder here as `shmai_<label>_<date-time>/`.

Before installing this version over your existing shmAI, back up the old one:

```
python3 scripts/backup.py "PATH/TO/YOUR/CURRENT/SHMAI" --label pre-vnext
```

To roll back, copy that backup folder's files back (or run `python3 muse.py` from inside it).
The backup folders themselves are ignored by git (they stay on your computer).
