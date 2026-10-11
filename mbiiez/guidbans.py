"""GUID bans, shared by every server.

The engine (OpenJK codemp/server/sv_guidban.cpp) keeps them in
guidbans.txt beside the game data, refuses a banned ja_guid at connect,
drops one already playing within a few seconds of the file changing, and
counts each drop in the file. This reads and edits that same file, under
the same flock ("<file>.lock").

guidbans.txt, tab separated (times in unix seconds, 0 for never):
    GUID  drops  last drop  last name  last ip  added  from ip ban  note
guidseen.txt, written by the engine on every connect (kept 30 days):
    ip  GUID  last seen  name

A client's GUID is salted with the server's address, so one player has a
different GUID on every server. Bans follow him by IP instead: banning a
GUID here bans the others seen on its IPs in the last LINK_DAYS too, and
the engine does the same for any GUID that turns up on a banned one's IP.
An IP ban (mbiiez.bansync) bans every GUID seen on that IP, with "from ip
ban" set to it, and unbanning the IP lifts those again.
"""
import copy
import fcntl
import os
import re
import time

from mbiiez import settings

BAN_FILE = "guidbans.txt"
SEEN_FILE = "guidseen.txt"
LINK_DAYS = 7
FIELDS = ["guid", "drops", "last_drop", "name", "ip", "added", "ban_ip", "note"]
_GUID_RE = re.compile(r"^[0-9A-Fa-f]{16,64}$")


def valid_guid(guid):
    return bool(_GUID_RE.match(str(guid or "").strip()))


def _path(name):
    return os.path.join(settings.locations.mbii_path, name)


def _clean(text, limit=200):
    return re.sub(r"[\t\r\n]", " ", str(text or ""))[:limit]


class _Locked:
    """The ban list, loaded under the engine's lock, saved on exit if changed."""

    def __enter__(self):
        self.fd = os.open(_path(BAN_FILE) + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        self.bans = []
        self.changed = False
        self.revision = 0
        try:
            with open(_path(BAN_FILE), "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.rstrip("\r\n")
                    if line.startswith("# MBIIEZ_SHARED_REVISION="):
                        self.revision=int(line.split("=",1)[1])
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t", len(FIELDS) - 1)
                    parts += [""] * (len(FIELDS) - len(parts))
                    ban = dict(zip(FIELDS, parts))
                    ban["guid"] = ban["guid"].strip()
                    if not ban["guid"]:
                        continue
                    for key in ("drops", "last_drop", "added"):
                        try:
                            ban[key] = int(ban[key] or 0)
                        except ValueError:
                            ban[key] = 0
                    self.bans.append(ban)
        except FileNotFoundError:
            pass
        self.before=copy.deepcopy(self.bans)
        return self

    def find(self, guid):
        guid = str(guid or "").strip().upper()
        for ban in self.bans:
            if ban["guid"].upper() == guid:
                return ban
        return None

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None and self.changed:
                from mbiiez.api import shared_node
                if shared_node.enabled():
                    before={row['guid'].lower():row for row in self.before};after={row['guid'].lower():row for row in self.bans}
                    for key in before.keys()-after.keys():shared_node.append(dict(kind='ban_delete',dataset='guid_bans',key=key,base_revision=self.revision))
                    for key,row in after.items():
                        if before.get(key)!=row:shared_node.append(dict(kind='ban_update' if key in before else 'ban_set',dataset='guid_bans',row=[row[name] for name in FIELDS],base_revision=self.revision))
                    return False
                # Written in place, as the engine does: its lock is on the
                # .lock file, so this never races it.
                with open(_path(BAN_FILE), "w", encoding="utf-8") as f:
                    f.write("# GUID bans for every server. Tab separated, times in unix seconds:\n")
                    f.write("# GUID\tdrops\tlast drop\tlast name\tlast ip\tadded\tfrom ip ban\tnote\n")
                    for ban in self.bans:
                        f.write("\t".join(str(ban[k]) for k in FIELDS) + "\n")
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        return False


def _seen():
    """guidseen.txt as a list of {ip, guid, seen, name}."""
    rows = []
    try:
        with open(_path(SEEN_FILE), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t", 3)
                if len(parts) < 3:
                    continue
                try:
                    seen = int(parts[2])
                except ValueError:
                    continue
                rows.append({"ip": parts[0], "guid": parts[1], "seen": seen,
                             "name": parts[3] if len(parts) > 3 else ""})
    except FileNotFoundError:
        pass
    return rows


def list_bans():
    with _Locked() as locked:
        bans = [dict(b) for b in locked.bans]
    seen = _seen()
    for ban in bans:
        guid = ban["guid"].upper()
        ban["ips"] = sorted({r["ip"] for r in seen if r["guid"].upper() == guid})
    return sorted(bans, key=lambda b: b["added"], reverse=True)


def add_ban(guid, note="", name="", ip="", ban_ip=""):
    guid = str(guid or "").strip().upper()
    if not valid_guid(guid):
        return False, "Not a valid GUID (16-64 hex characters)."
    with _Locked() as locked:
        ban = locked.find(guid)
        if ban:
            if note:
                ban["note"] = _clean(note)
                locked.changed = True
            return True, "{} is already banned.".format(guid)
        if not name or not ip:
            # The last name and IP it was seen with, if it's been seen.
            mine = [r for r in _seen() if r["guid"].upper() == guid]
            if mine:
                latest = max(mine, key=lambda r: r["seen"])
                name = name or latest["name"]
                ip = ip or latest["ip"]
        locked.bans.append({"guid": guid, "drops": 0, "last_drop": 0, "name": _clean(name, 64),
                            "ip": _clean(ip, 48), "added": int(time.time()),
                            "ban_ip": _clean(ban_ip, 48), "note": _clean(note)})
        linked = _link(locked, guid, ban_ip)
        locked.changed = True
    if linked:
        return True, "{} banned on every server, with {} more GUID{} seen on the same IPs.".format(
            guid, len(linked), "" if len(linked) == 1 else "s")
    return True, "{} banned on every server.".format(guid)


def _link(locked, guid, ban_ip=""):
    """Ban the other GUIDs seen lately on the IPs this one was seen on."""
    since = time.time() - LINK_DAYS * 86400
    seen = [r for r in _seen() if r["seen"] >= since]
    ips = {r["ip"] for r in seen if r["guid"].upper() == guid}
    linked = []
    for row in sorted(seen, key=lambda r: r["seen"], reverse=True):
        other = row["guid"].upper()
        if row["ip"] not in ips or not valid_guid(other) or locked.find(other):
            continue
        locked.bans.append({"guid": other, "drops": 0, "last_drop": 0, "name": _clean(row["name"], 64),
                            "ip": row["ip"], "added": int(time.time()), "ban_ip": _clean(ban_ip, 48),
                            "note": "same IP ({}) as banned {}".format(row["ip"], guid)})
        linked.append(other)
    return linked


def remove_ban(guid):
    with _Locked() as locked:
        ban = locked.find(guid)
        if not ban:
            return False, "{} isn't banned.".format(guid)
        locked.bans.remove(ban)
        locked.changed = True
    return True, "{} unbanned on every server.".format(ban["guid"])


def set_note(guid, note):
    with _Locked() as locked:
        ban = locked.find(guid)
        if not ban:
            return False, "{} isn't banned.".format(guid)
        ban["note"] = _clean(note)
        locked.changed = True
    return True, "Note saved."


def ban_from_ip(ip, note=""):
    """An IP was banned: ban every GUID seen on it. Returns the GUIDs banned."""
    banned = []
    rows = [r for r in _seen() if r["ip"] == ip]
    with _Locked() as locked:
        for row in sorted(rows, key=lambda r: r["seen"], reverse=True):
            guid = row["guid"].upper()
            if not valid_guid(guid) or locked.find(guid):
                continue
            locked.bans.append({"guid": guid, "drops": 0, "last_drop": 0, "name": _clean(row["name"], 64),
                                "ip": ip, "added": int(time.time()), "ban_ip": ip,
                                "note": _clean(note or "IP ban {}".format(ip))})
            locked.changed = True
            banned.append(guid)
    return banned


def unban_from_ip(ip):
    """An IP was unbanned: lift the GUID bans it brought in. Returns them."""
    with _Locked() as locked:
        lifted = [b for b in locked.bans if b["ban_ip"] == ip]
        for ban in lifted:
            locked.bans.remove(ban)
        locked.changed = bool(lifted)
    return [b["guid"] for b in lifted]
