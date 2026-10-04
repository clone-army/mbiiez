"""One ban list for every instance.

MBII keeps its IP bans per server: in memory, written out to the instance's
own fs_homepath/MBII/banIP.dat ("banip_v2 1.2.3.4 5.6.7.8 ") on every addip
and removeip, and read back when it starts. So a ban made on one server
(web panel, SMOD, rcon addip) only ever reached that server.

This keeps a master list (banlist.json beside the accounts file, shared by
every instance) and brings every instance into line with it:

  - an IP that appeared in an instance's banIP.dat since the last sync was
    banned there - it's added to the master list;
  - one that disappeared was unbanned there - it's taken off the master;
  - then every running instance gets addip / removeip over rcon for what it's
    missing or has extra, and a stopped one has its banIP.dat written (read
    when it next starts).

The web panel's Bans page edits the master list directly and syncs straight
away; otherwise sync() runs every minute from mbii-web.

An IP ban also bans every GUID seen on that IP (mbiiez.guidbans), and
unbanning the IP lifts them again.
"""
import copy
import fcntl
import json
import os
import re
import subprocess
import threading
import time

from mbiiez import settings

MASTER_FILE = "banlist.json"
SYNC_SECONDS = 60
_IP_RE = re.compile(r"^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$")

_thread_lock = threading.Lock()
_started = False


def valid_ip(ip):
    return bool(_IP_RE.match(str(ip or "").strip()))


def _master_path():
    return os.path.join(settings.locations.mbii_path, MASTER_FILE)


def _instances():
    names = []
    for filename in sorted(os.listdir(settings.locations.config_path)):
        if filename.endswith(".json"):
            names.append(filename[:-5])
    return names


def _ban_file(name):
    return os.path.join(settings.locations.homepath_base, name, "MBII", "banIP.dat")


def _base_ban_file():
    return os.path.join(settings.locations.mbii_path, "banIP.dat")


def _read_ban_file(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            words = f.read().split()
    except FileNotFoundError:
        return None
    return [w for w in words if valid_ip(w)]


def _instance_bans(name):
    """What an instance has banned: its own banIP.dat, or - before it's ever
    written one - the shared default it would read instead."""
    ips = _read_ban_file(_ban_file(name))
    if ips is None:
        ips = _read_ban_file(_base_ban_file()) or []
    return ips


def _write_ban_file(path, ips):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("banip_v2 " + "".join(ip + " " for ip in ips))
    os.replace(tmp, path)


def _running(name):
    homepath = os.path.join(settings.locations.homepath_base, name)
    try:
        out = subprocess.run(["pgrep", "-f", "fs_homepath {} ".format(homepath)],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return False
    return bool(out.strip())


class _Locked:
    """The master list, loaded and held under an exclusive lock (so the web
    page and the timer never write over each other), saved on exit."""

    def __enter__(self):
        path = _master_path()
        self.fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (FileNotFoundError, ValueError):
            self.data = {}
        self.data.setdefault("bans", {})     # ip -> {note, added, by}
        self.data.setdefault("seen", {})     # instance -> [ips] after the last sync
        self.before=copy.deepcopy(self.data["bans"])
        return self.data

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                from mbiiez.api import shared_node
                if shared_node.enabled():
                    revision=self.data.get('shared_revision',0);after=self.data['bans']
                    for key in self.before.keys()-after.keys():shared_node.append(dict(kind='ban_delete',dataset='ip_bans',key=key,base_revision=revision))
                    for key,row in after.items():
                        if self.before.get(key)!=row:shared_node.append(dict(kind='ban_update' if key in self.before else 'ban_set',dataset='ip_bans',row=dict(ip=key,**row),base_revision=revision))
                path = _master_path()
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, sort_keys=True)
                os.replace(tmp, path)
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
        return False


def _follow_guids(ip, banned, log):
    """Ban (or unban) the GUIDs seen on an IP along with it. Returns them."""
    from mbiiez import guidbans
    guids = []
    try:
        if banned:
            guids = guidbans.ban_from_ip(ip)
            if guids:
                log.append("{}: GUIDs banned with it: {}".format(ip, ", ".join(guids)))
        else:
            guids = guidbans.unban_from_ip(ip)
            if guids:
                log.append("{}: GUIDs unbanned with it: {}".format(ip, ", ".join(guids)))
    except Exception as e:
        log.append("{}: GUID bans not updated ({})".format(ip, e))
    return guids


def _guid_text(guids, done):
    if not guids:
        return ""
    return " {} GUID{} seen on it {} too.".format(len(guids), "" if len(guids) == 1 else "s", done)


def _rcon(name, command):
    from mbiiez.instance import instance as MBInstance
    MBInstance(name).console.rcon(command, True)


def _sync_locked(data, log):
    bans = data["bans"]
    seen = data["seen"]
    names = _instances()
    current = {name: _instance_bans(name) for name in names}

    # 1. Changes made on a server since last time go into the master list.
    for name in names:
        before = seen.get(name)
        now = set(current[name])
        if before is None:
            # Never synced: all it has counts as bans (first run merges
            # every server's list into one).
            added, removed = now, set()
        else:
            added, removed = now - set(before), set(before) - now
        for ip in sorted(added):
            if ip not in bans:
                bans[ip] = {"note": "", "added": int(time.time()), "by": "in game on {}".format(name)}
                log.append("{} banned on {} - banning everywhere".format(ip, name))
                _follow_guids(ip, True, log)
        for ip in sorted(removed):
            if ip in bans:
                del bans[ip]
                log.append("{} unbanned on {} - unbanning everywhere".format(ip, name))
                _follow_guids(ip, False, log)

    # 2. Every instance brought into line with it.
    wanted = sorted(bans)
    for name in names:
        have = set(current[name])
        missing = [ip for ip in wanted if ip not in have]
        extra = sorted(have - set(wanted))
        if missing or extra:
            if _running(name):
                try:
                    for ip in missing:
                        _rcon(name, "addip " + ip)
                        time.sleep(0.15)
                    for ip in extra:
                        _rcon(name, "removeip " + ip)
                        time.sleep(0.15)
                except Exception as e:
                    log.append("{}: rcon failed ({}) - will retry".format(name, e))
                    # Leave its "seen" as it was, so nothing it has is
                    # mistaken for a change next time.
                    seen[name] = sorted(have)
                    continue
                # MBII rewrites banIP.dat on each addip/removeip: what's
                # there now is what it really has. Anything that didn't
                # take is retried next time, never taken for an unban.
                time.sleep(0.5)
                seen[name] = sorted(_instance_bans(name))
                if set(seen[name]) != set(wanted):
                    log.append("{}: not all changes took yet - will retry".format(name))
                continue
            else:
                _write_ban_file(_ban_file(name), wanted)
        seen[name] = list(wanted)


def sync():
    """Run one sync. Returns a list of what changed (for logs)."""
    log = []
    with _thread_lock, _Locked() as data:
        _sync_locked(data, log)
    return log


def list_bans():
    with _Locked() as data:
        bans = dict(data["bans"])
    return [dict(ip=ip, **info) for ip, info in sorted(bans.items(), key=lambda kv: kv[1].get("added", 0), reverse=True)]


def add_ban(ip, note="", by=""):
    ip = str(ip or "").strip()
    if not valid_ip(ip):
        return False, "Not a valid IPv4 address."
    log = []
    guids = []
    with _thread_lock, _Locked() as data:
        if ip in data["bans"]:
            data["bans"][ip]["note"] = note or data["bans"][ip].get("note", "")
        else:
            data["bans"][ip] = {"note": note or "", "added": int(time.time()), "by": by or "web panel"}
            guids = _follow_guids(ip, True, log)
        _sync_locked(data, log)
    return True, "{} banned on every server.{}".format(ip, _guid_text(guids, "banned"))


def remove_ban(ip):
    ip = str(ip or "").strip()
    log = []
    with _thread_lock, _Locked() as data:
        if ip not in data["bans"]:
            return False, "{} isn't banned.".format(ip)
        del data["bans"][ip]
        guids = _follow_guids(ip, False, log)
        _sync_locked(data, log)
    return True, "{} unbanned on every server.{}".format(ip, _guid_text(guids, "unbanned"))


def set_note(ip, note):
    ip = str(ip or "").strip()
    with _thread_lock, _Locked() as data:
        if ip not in data["bans"]:
            return False, "{} isn't banned.".format(ip)
        data["bans"][ip]["note"] = str(note or "")[:200]
    return True, "Note saved."


def start_background(logger=print):
    """Sync every SYNC_SECONDS in a daemon thread (once per process)."""
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            try:
                for line in sync():
                    logger("[bansync] " + line)
            except Exception as e:
                logger("[bansync] sync failed: {}".format(e))
            time.sleep(SYNC_SECONDS)

    threading.Thread(target=loop, name="bansync", daemon=True).start()
