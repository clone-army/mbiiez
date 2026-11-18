"""Nicknames the shield's PadawanTK switch must never kick.

Shared by every instance on this node and stored beside banlist.json
(padawanwhitelist.json), rewritten atomically under a flock. Names are
compared the way a player reads them: colour codes removed, lower-cased,
spaces collapsed (see nicknamebans.normalize); the whole name must match.
It only exempts a player from the PadawanTK rule - VPN blocking still applies.
"""
import fcntl
import json
import os
import threading
import time

from mbiiez import settings
from mbiiez.nicknamebans import normalize, MAX_PATTERN

FILE = "padawanwhitelist.json"
_thread_lock = threading.Lock()
_cache = {"mtime": None, "names": {}}


def _path():
    return os.path.join(settings.locations.mbii_path, FILE)


def _read():
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            return [e for e in json.load(f).get("names", []) if e.get("name")]
    except (FileNotFoundError, ValueError):
        return []


class _Locked:
    def __enter__(self):
        self.fd = os.open(_path() + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.entries = _read()
        self.changed = False
        return self

    def find(self, name):
        key = normalize(name)
        return next((e for e in self.entries if normalize(e["name"]) == key), None)

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self.changed:
                tmp = _path() + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"names": self.entries}, f, indent=1)
                os.replace(tmp, _path())
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        return False


def is_whitelisted(name):
    """True if this nickname is exempt from PadawanTK kicks (re-reads the file only when it changes)."""
    try:
        mtime = os.stat(_path()).st_mtime_ns
    except FileNotFoundError:
        return False
    if _cache["mtime"] != mtime:
        _cache["names"] = {normalize(e["name"]) for e in _read()}
        _cache["mtime"] = mtime
    return normalize(name) in _cache["names"]


def list_names():
    with _Locked() as locked:
        entries = [dict(e) for e in locked.entries]
    return sorted(entries, key=lambda e: e.get("added", 0), reverse=True)


def add_name(name, note="", by=""):
    name = " ".join(str(name or "").split())[:MAX_PATTERN]
    if not normalize(name):
        return False, "Enter a nickname."
    with _thread_lock, _Locked() as locked:
        entry = locked.find(name)
        if entry:
            entry["note"] = str(note or entry.get("note", ""))[:200]
        else:
            locked.entries.append({"name": name, "note": str(note or "")[:200],
                                   "added": int(time.time()), "by": by or "web panel"})
        locked.changed = True
    return True, "{} will no longer be kicked by PadawanTK.".format(name)


def remove_name(name):
    with _thread_lock, _Locked() as locked:
        entry = locked.find(name)
        if not entry:
            return False, "That nickname isn't whitelisted."
        locked.entries.remove(entry)
        locked.changed = True
    return True, "{} removed from the whitelist.".format(name)
