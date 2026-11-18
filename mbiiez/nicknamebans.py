"""Nickname bans, shared by every instance on this node.

The engine has no concept of banning a name, so this is enforced here: when
a player connects, or changes name, their name is checked against the list
and they're kicked (clientkick) if it matches. Adding a ban also sweeps the
players already on every running instance.

Names are compared the way a player reads them: colour codes (^1, ^7 ...)
removed, lower-cased, runs of spaces collapsed. A rule matches either the
whole name ("exact") or any part of it ("contains"). A rule can also IP-ban
whoever it catches (mbiiez.bansync) - off by default, since a name is easy
to share by accident.

Stored in nicknamebans.json beside banlist.json (every instance reads the
same file), rewritten atomically under a flock.
"""
import fcntl
import json
import os
import re
import threading
import time

from mbiiez import settings

BAN_FILE = "nicknamebans.json"
MODES = ("exact", "contains")
MAX_PATTERN = 64
MIN_CONTAINS = 3          # a one- or two-letter "contains" rule would catch half the server
_COLOUR = re.compile(r"\^[0-9]")
_SPACES = re.compile(r"\s+")

_thread_lock = threading.Lock()
_cache = {"mtime": None, "rules": []}


def normalize(name):
    return _SPACES.sub(" ", _COLOUR.sub("", str(name or ""))).strip().lower()


def _path():
    return os.path.join(settings.locations.mbii_path, BAN_FILE)


class _Locked:
    """The rule list, loaded under a lock, saved (atomically) on exit if changed."""

    def __enter__(self):
        self.fd = os.open(_path() + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.rules = []
        self.changed = False
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.rules = [r for r in data.get("bans", []) if r.get("pattern")]
        except (FileNotFoundError, ValueError):
            pass
        return self

    def find(self, pattern, mode):
        key = normalize(pattern)
        for rule in self.rules:
            if normalize(rule["pattern"]) == key and rule["mode"] == mode:
                return rule
        return None

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self.changed:
                tmp = _path() + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"bans": self.rules}, f, indent=1)
                os.replace(tmp, _path())
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        return False


def _rules():
    """The rules, re-read only when the file changes (this runs on every connect)."""
    try:
        mtime = os.stat(_path()).st_mtime_ns
    except FileNotFoundError:
        return []
    if _cache["mtime"] != mtime:
        try:
            with open(_path(), "r", encoding="utf-8") as f:
                _cache["rules"] = [r for r in json.load(f).get("bans", []) if r.get("pattern")]
            _cache["mtime"] = mtime
        except (OSError, ValueError):
            pass
    return _cache["rules"]


def _matches(rule, name):
    pattern, name = normalize(rule["pattern"]), normalize(name)
    if not pattern or not name:
        return False
    return name == pattern if rule.get("mode") == "exact" else pattern in name


def check(name):
    """The first rule banning this name, or None."""
    for rule in _rules():
        if _matches(rule, name):
            return rule
    return None


def list_bans():
    with _Locked() as locked:
        bans = [dict(r) for r in locked.rules]
    return sorted(bans, key=lambda r: r.get("added", 0), reverse=True)


def add_ban(pattern, mode="exact", note="", ban_ip=False, by=""):
    pattern = re.sub(r"[\r\n\t]", " ", str(pattern or "")).strip()[:MAX_PATTERN]
    mode = mode if mode in MODES else "exact"
    clean = normalize(pattern)
    if not clean:
        return False, "Enter a nickname."
    if mode == "contains" and len(clean) < MIN_CONTAINS:
        return False, "A 'contains' ban needs at least {} characters, or it would catch too many players.".format(MIN_CONTAINS)
    with _thread_lock, _Locked() as locked:
        rule = locked.find(pattern, mode)
        if rule:
            rule["note"] = str(note or rule.get("note", ""))[:200]
            rule["ban_ip"] = bool(ban_ip)
        else:
            locked.rules.append({"pattern": pattern, "mode": mode, "note": str(note or "")[:200],
                                 "ban_ip": bool(ban_ip), "added": int(time.time()), "by": by or "web panel",
                                 "drops": 0, "last_drop": 0, "last_name": "", "last_ip": ""})
        locked.changed = True
    threading.Thread(target=sweep, daemon=True).start()
    return True, "Nickname '{}' banned on every server ({}).".format(pattern, "exact name" if mode == "exact" else "contains")


def remove_ban(pattern, mode="exact"):
    with _thread_lock, _Locked() as locked:
        rule = locked.find(pattern, mode)
        if not rule:
            return False, "That nickname isn't banned."
        locked.rules.remove(rule)
        locked.changed = True
    return True, "Nickname '{}' unbanned.".format(pattern)


def set_note(pattern, mode, note):
    with _thread_lock, _Locked() as locked:
        rule = locked.find(pattern, mode)
        if not rule:
            return False, "That nickname isn't banned."
        rule["note"] = str(note or "")[:200]
        locked.changed = True
    return True, "Note saved."


def record_drop(rule, name, ip=""):
    """Count a kick against its rule (and IP-ban the player if the rule says so)."""
    with _thread_lock, _Locked() as locked:
        stored = locked.find(rule["pattern"], rule["mode"])
        if stored:
            stored["drops"] = int(stored.get("drops", 0)) + 1
            stored["last_drop"] = int(time.time())
            stored["last_name"] = normalize(name)[:MAX_PATTERN]
            if ip:
                stored["last_ip"] = ip
            locked.changed = True
    if rule.get("ban_ip") and ip:
        try:
            from mbiiez import bansync
            bansync.add_ban(ip, "nickname ban: {}".format(rule["pattern"]), "nickname ban")
        except Exception:
            pass


def enforce(instance, player_id, name, ip=""):
    """Kick this player if their name is banned. True if they were kicked."""
    rule = check(name)
    if not rule:
        return False
    try:
        instance.console.rcon("clientkick {}".format(player_id))
        instance.log_handler.log("Nickname ban '{}' ({}): kicked {} (slot {}, {})".format(
            rule["pattern"], rule["mode"], normalize(name), player_id, ip or "no ip"))
    except Exception as e:
        try:
            instance.log_handler.log("Nickname ban: failed to kick slot {}: {}".format(player_id, e))
        except Exception:
            pass
        return False
    record_drop(rule, name, ip)
    return True


def sweep():
    """Kick anyone already playing under a banned name, on every running instance."""
    if not _rules():
        return
    try:
        from mbiiez import bansync
        from mbiiez.instance import instance
        names = bansync._instances()
    except Exception:
        return
    for name in names:
        try:
            inst = instance(name)
            if not inst.server_running():
                continue
            for player in inst.players():
                enforce(inst, player["id"], player.get("name_raw", ""), player.get("ip", ""))
        except Exception:
            continue
