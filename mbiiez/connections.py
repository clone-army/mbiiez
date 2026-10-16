"""Who's been connecting, for tracing trolls: every connection to every
instance on this node, the names used and the IPs and GUIDs behind them.

Three sources, merged:

  - the connections table (mbiiez.db): a CONNECT row for each ClientConnect
    in an instance's games log - name, IP, instance (kept 14 days). MBII logs
    everyone again on each map change, so the same player shows up many times;
  - connections.log beside guidbans.txt, written by the engine on every
    connect and every name change in game - with the GUID too (trimmed here
    to LOG_DAYS);
  - guidseen.txt, the engine's IP / GUID / last name list (30 days) - used to
    link IPs to GUIDs.

Connects of the same name on the same IP and instance, less than SESSION_GAP
apart, are one session (someone playing on through map changes). IPs and
GUIDs seen together are one "person": a GUID seen on two IPs joins them, an
IP used under two GUIDs joins those - so a name change, a new IP or a new
GUID still leads back to the rest. Shared IPs (a household, a VPN) can join
people who aren't the same - the page says so.
"""
import datetime
import os
import re
import sqlite3
import time

from mbiiez import settings

LOG_FILE = "connections.log"
LOG_DAYS = 30
SESSION_GAP = 3 * 3600
MAX_PEOPLE = 25
MAX_SESSIONS = 300
MAX_CHAT = 1000
CHAT_PAGE = 250

_COLOUR = re.compile(r"\^[0-9a-zA-Z]|\x1b\[[0-9;]*m")
_IP = re.compile(r"^(?:\d{1,3}\.){1,3}\d{0,3}$")
_GUID = re.compile(r"^[0-9A-Fa-f]{32}$")


def clean_name(name):
    return _COLOUR.sub("", str(name or "")).strip()


def _key(name):
    return clean_name(name).lower()


_TELL = re.compile(r"^\s*\d+:\d+ tell: (.*)$")


def split_tell(line, is_known=lambda name: False):
    """A games log tell line ("  12:34 tell: A to B: hi") as (sender, target,
    message), names cleaned, or None. Names can hold " to " themselves, so of
    every way to split it, the one whose names `is_known` says are players
    wins; failing that, the first."""
    m = _TELL.match(line.rstrip("\r\n"))
    if not m:
        return None
    rest = m.group(1)
    splits = []
    i = rest.find(" to ")
    while i > 0:
        target, sep, message = rest[i + 4:].partition(": ")
        if sep and target:
            splits.append((clean_name(rest[:i]), clean_name(target), message.strip()))
        i = rest.find(" to ", i + 1)
    if not splits:
        return None
    return max(splits, key=lambda s: (is_known(s[0].lower()) + is_known(s[1].lower()), -splits.index(s)))


def known_names(instance):
    """Every name that's connected to `instance`, cleaned and lowercased -
    for split_tell's is_known."""
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            rows = conn.execute("SELECT DISTINCT player FROM connections WHERE instance = ?", (instance,)).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return set()
    return {_key(r[0]) for r in rows if r[0]}


def _log_path():
    return os.path.join(settings.locations.mbii_path, LOG_FILE)


def _prune_log():
    """At most once a day: drop connections.log lines older than LOG_DAYS.
    The engine only ever appends, a line at a time, so a line written while
    this rewrites the file can be lost - not one that matters."""
    path = _log_path()
    marker = path + ".pruned"
    try:
        if time.time() - os.path.getmtime(marker) < 86400:
            return
    except OSError:
        pass
    try:
        cutoff = time.time() - LOG_DAYS * 86400
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        keep = [l for l in lines if l.split("\t", 1)[0].isdigit() and int(l.split("\t", 1)[0]) >= cutoff]
        if len(keep) != len(lines):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.writelines(keep)
            os.chmod(tmp, 0o644)
            os.replace(tmp, path)
        with open(marker, "w") as f:
            f.write(str(int(time.time())))
    except OSError:
        pass


def _events(since):
    """Every connect and rename since `since` (unix time), oldest first:
    {t, instance, ip, name, guid, kind, old}."""
    out = []
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT added, player, instance, ip FROM connections WHERE type = 'CONNECT' AND added >= ?",
                (datetime.datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M:%S"),)).fetchall()
        finally:
            conn.close()
        for added, player, instance, ip in rows:
            try:
                t = datetime.datetime.strptime(str(added)[:19], "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                continue
            if ip and ip != "Unknown":
                out.append({"t": int(t), "instance": instance or "", "ip": ip, "name": clean_name(player),
                            "guid": "", "kind": "connect", "old": ""})
    except sqlite3.Error:
        pass
    _prune_log()
    try:
        with open(_log_path(), "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                p = line.rstrip("\r\n").split("\t")
                if len(p) < 7 or not p[0].isdigit() or int(p[0]) < since:
                    continue
                out.append({"t": int(p[0]), "instance": p[1], "ip": p[4], "name": clean_name(p[6]),
                            "guid": p[5].upper(), "kind": p[2], "old": clean_name(p[7]) if len(p) > 7 else ""})
    except OSError:
        pass
    out.sort(key=lambda e: e["t"])
    return out


def _chat(since, names):
    """Chat lines (say, team, tell) since `since` by any of `names`, oldest
    first: {t, instance, type, name, target, message}."""
    names = sorted({clean_name(n) for n in names if n})
    if not names:
        return []
    out = _chat_rows("added >= ? AND player COLLATE NOCASE IN ({})".format(",".join("?" * len(names))),
                     [_stamp(since)] + names)
    out.sort(key=lambda c: c["t"])
    return out


def _stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def _chat_rows(where, args, tail=""):
    """Chatter rows matching `where`, as {t, instance, type, name, target, message}."""
    out = []
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            cols = [c[1] for c in conn.execute("PRAGMA table_info(chatter)")]
            rows = conn.execute(
                "SELECT added, instance, type, player, {}, message FROM chatter WHERE {} {}".format(
                    "target" if "target" in cols else "''", where, tail), args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    for added, instance, type_, player, target, message in rows:
        try:
            t = datetime.datetime.strptime(str(added)[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            continue
        out.append({"t": int(t), "instance": instance or "", "type": (type_ or "").upper(), "name": clean_name(player),
                    "target": clean_name(target), "message": message or ""})
    return out


def _chat_session(by_name, line):
    """The session a chat line was said in: the latest one of that name on
    that server started by then, if it's not long over."""
    best = None
    for s in by_name.get((line["instance"], _key(line["name"])), ()):
        if s["start"] - 120 <= line["t"]:
            best = s
        else:
            break
    if best and line["t"] <= best["end"] + SESSION_GAP:
        return best
    return None


def _sessions_by_name(since):
    by_name = {}
    for s in sorted(_sessions(_events(since)), key=lambda s: s["start"]):
        by_name.setdefault((s["instance"], _key(s["name"])), []).append(s)
    return by_name


def chat_search(filters=None):
    """What the Chat Log page shows: chat on every instance, newest first, a
    page at a time - each line with the IP (and GUID) of the session it was
    said in. The query matches the message, the name or who a tell went to;
    an IP (or the start of one) matches the lines said from it instead."""
    filters = filters if isinstance(filters, dict) else {}
    query = str(filters.get("q") or "").strip()[:64]
    instance = str(filters.get("instance") or "").strip()[:64]
    type_ = str(filters.get("type") or "").upper()
    type_ = type_ if type_ in ("PUBLIC", "TEAM", "TELL") else ""
    try:
        days = max(1, min(LOG_DAYS, int(filters.get("days") or 1)))
        page = max(0, int(filters.get("page") or 0))
    except (TypeError, ValueError):
        days, page = 1, 0
    include_server = bool(filters.get("server"))
    now = int(time.time())
    by_ip = bool(query and _IP.match(query))

    where, args = ["added >= ?"], [_stamp(now - days * 86400)]
    if instance:
        where.append("instance = ? COLLATE NOCASE")
        args.append(instance)
    if type_:
        where.append("type = ?")
        args.append(type_)
    if not include_server:
        where.append("player != 'Server'")
    if query and not by_ip:
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(message LIKE ? ESCAPE '\\' OR player LIKE ? ESCAPE '\\' OR target LIKE ? ESCAPE '\\')")
        args += [like] * 3
    # By IP every line in range has to be placed before filtering; otherwise
    # just the page asked for (and one more, to know if there's another).
    tail = "ORDER BY added DESC" if by_ip else "ORDER BY added DESC LIMIT {} OFFSET {}".format(CHAT_PAGE + 1, page * CHAT_PAGE)
    lines = _chat_rows(" AND ".join(where), args, tail)

    if lines:
        by_name = _sessions_by_name(min(c["t"] for c in lines) - 2 * SESSION_GAP)
        banned_ips, _ = _bans()
        for line in lines:
            s = _chat_session(by_name, line)
            line["ip"] = s["ip"] if s else ""
            line["guid"] = s["guid"] if s else ""
            line["banned"] = bool(s) and s["ip"] in banned_ips
    if by_ip:
        lines = [c for c in lines if c["ip"].startswith(query)][page * CHAT_PAGE:(page + 1) * CHAT_PAGE + 1]

    instances = []
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            instances = sorted({r[0] for r in conn.execute("SELECT DISTINCT instance FROM chatter") if r[0]}, key=str.lower)
        finally:
            conn.close()
    except sqlite3.Error:
        pass

    from mbiiez.db import db
    return {"query": query, "instance": instance, "type": type_, "days": days, "page": page, "server": include_server,
            "lines": lines[:CHAT_PAGE], "more": len(lines) > CHAT_PAGE, "instances": instances, "now": now,
            "kept_days": db.RETENTION_DAYS.get("chatter", 7)}


def _guidseen():
    from mbiiez import guidbans
    try:
        return guidbans._seen()
    except Exception:
        return []


def _sessions(events):
    """Connects of one name on one IP and instance, close together, as one."""
    open_ = {}
    out = []
    for e in events:
        k = (e["instance"], e["ip"], _key(e["name"]))
        s = open_.get(k)
        if s and e["t"] - s["end"] <= SESSION_GAP:
            s["end"] = e["t"]
            s["connects"] += e["kind"] == "connect"
            s["guid"] = s["guid"] or e["guid"]
        else:
            s = {"start": e["t"], "end": e["t"], "instance": e["instance"], "ip": e["ip"], "name": e["name"],
                 "guid": e["guid"], "connects": 1 if e["kind"] == "connect" else 0, "renamed_from": ""}
            open_[k] = s
            out.append(s)
        if e["kind"] == "rename" and e["old"] and not s["renamed_from"]:
            s["renamed_from"] = e["old"]
    return out


class _People:
    """Union-find over IPs and GUIDs seen together."""

    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _bans():
    ips, guids = set(), set()
    try:
        from mbiiez import bansync
        ips = {b["ip"] for b in bansync.list_bans()}
    except Exception:
        pass
    try:
        from mbiiez import guidbans
        guids = {b["guid"].upper() for b in guidbans.list_bans()}
    except Exception:
        pass
    return ips, guids


def search(query="", days=14):
    """What the Connections page shows. With a query (an IP or the start of
    one, a GUID, or part of a name): everyone it matches, each with every
    name, IP and GUID linked to them and their sessions. Without one: the
    latest sessions, and the IPs that have been used under more than one name."""
    query = str(query or "").strip()[:64]
    days = max(1, min(LOG_DAYS, int(days or 14)))
    now = int(time.time())
    events = _events(now - days * 86400)
    sessions = _sessions(events)
    seen = [r for r in _guidseen() if r["seen"] >= now - days * 86400]
    banned_ips, banned_guids = _bans()

    people = _People()
    for s in sessions:
        people.find("ip:" + s["ip"])
        if s["guid"]:
            people.join("ip:" + s["ip"], "guid:" + s["guid"])
    for r in seen:
        if r["guid"] and r["ip"]:
            people.join("ip:" + r["ip"], "guid:" + r["guid"].upper())

    result = {"query": query, "days": days, "now": now, "people": [], "sessions": [], "shared_ips": [],
              "events": len(events), "has_engine_log": os.path.exists(_log_path())}

    if not query:
        recent = sorted(sessions, key=lambda s: s["end"], reverse=True)[:MAX_SESSIONS]
        result["sessions"] = [dict(s, banned=s["ip"] in banned_ips) for s in recent]
        by_ip = {}
        for s in sessions:
            d = by_ip.setdefault(s["ip"], {"ip": s["ip"], "names": {}, "last": 0, "instances": set()})
            n = d["names"].setdefault(_key(s["name"]), {"name": s["name"], "last": 0, "sessions": 0})
            n["last"] = max(n["last"], s["end"])
            n["sessions"] += 1
            n["name"] = s["name"] if s["end"] >= n["last"] else n["name"]
            d["last"] = max(d["last"], s["end"])
            d["instances"].add(s["instance"])
        shared = [d for d in by_ip.values() if len([k for k in d["names"] if k]) > 1]
        shared.sort(key=lambda d: (-len(d["names"]), -d["last"]))
        result["shared_ips"] = [{"ip": d["ip"], "last": d["last"], "banned": d["ip"] in banned_ips,
                                 "instances": sorted(d["instances"]),
                                 "names": sorted([n for n in d["names"].values() if n["name"]], key=lambda n: -n["last"])} for d in shared[:100]]
        return result

    # Which people the query matches.
    q = query.lower()
    roots = []

    def add(node):
        r = people.find(node)
        if r not in roots:
            roots.append(r)

    if _GUID.match(query):
        add("guid:" + query.upper())
    elif _IP.match(query):
        for s in sessions:
            if s["ip"].startswith(query):
                add("ip:" + s["ip"])
        for r in seen:
            if r["ip"].startswith(query):
                add("ip:" + r["ip"])
    else:
        for s in sorted(sessions, key=lambda s: s["end"], reverse=True):
            if q in _key(s["name"]):
                add("ip:" + s["ip"])
        for r in seen:
            if q in _key(r["name"]):
                add("ip:" + r["ip"])
    result["more"] = max(0, len(roots) - MAX_PEOPLE)
    roots = roots[:MAX_PEOPLE]

    # Chat carries only a name, so each line goes to the session that name
    # was playing on that server at the time - and so to its person.
    by_name = {}
    for s in sorted(sessions, key=lambda s: s["start"]):
        by_name.setdefault((s["instance"], _key(s["name"])), []).append(s)
    root_names = set()
    for root in roots:
        for s in sessions:
            if people.find("ip:" + s["ip"]) == root:
                root_names.add(s["name"])
    chat = _chat(now - days * 86400, root_names)
    chat_by_session = {}
    for line in chat:
        s = _chat_session(by_name, line)
        if s:
            chat_by_session.setdefault(id(s), []).append(line)

    for root in roots:
        members = [n for n in list(people.parent) if people.find(n) == root]
        ips = {n[3:] for n in members if n.startswith("ip:")}
        guids = {n[5:] for n in members if n.startswith("guid:")}
        mine = [s for s in sessions if s["ip"] in ips or (s["guid"] and s["guid"] in guids)]
        names = {}
        for s in mine:
            n = names.setdefault(_key(s["name"]), {"name": s["name"], "first": s["start"], "last": s["end"],
                                                    "sessions": 0, "ips": set(), "instances": set()})
            n["first"] = min(n["first"], s["start"])
            if s["end"] >= n["last"]:
                n["last"], n["name"] = s["end"], s["name"]
            n["sessions"] += 1
            n["ips"].add(s["ip"])
            n["instances"].add(s["instance"])
        for r in seen:
            if r["ip"] in ips and r["name"]:
                nm = clean_name(r["name"])
                n = names.setdefault(_key(nm), {"name": nm, "first": r["seen"], "last": r["seen"], "sessions": 0,
                                                "ips": set(), "instances": set()})
                n["ips"].add(r["ip"])
        ip_rows = []
        for ip in sorted(ips):
            on = [s for s in mine if s["ip"] == ip]
            ip_rows.append({"ip": ip, "banned": ip in banned_ips,
                            "first": min((s["start"] for s in on), default=0), "last": max((s["end"] for s in on), default=0),
                            "matched": ip.startswith(query) if _IP.match(query) else False})
        result["people"].append({
            "names": [dict(n, ips=sorted(n["ips"]), instances=sorted(n["instances"]))
                      for n in sorted(names.values(), key=lambda n: -n["last"]) if n["name"]],
            "ips": sorted(ip_rows, key=lambda r: -r["last"]),
            "guids": [{"guid": g, "banned": g in banned_guids} for g in sorted(guids)],
            "first": min((s["start"] for s in mine), default=0),
            "last": max((s["end"] for s in mine), default=0),
            "sessions": [dict(s, banned=s["ip"] in banned_ips) for s in sorted(mine, key=lambda s: -s["end"])[:MAX_SESSIONS]],
            "chat": sorted([dict(line, ip=s["ip"]) for s in mine for line in chat_by_session.get(id(s), ())],
                           key=lambda c: -c["t"])[:MAX_CHAT],
        })
    result["people"].sort(key=lambda p: -p["last"])
    return result
