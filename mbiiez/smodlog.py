"""What SMOD admins have done on this node's servers: every login (and
failed one), command and admin say, from the smod_log table the log watcher
fills (kept db.RETENTION_DAYS["smod_log"] days).

SMOD names an admin by their in-game name and admin slot (adminID - which
smod.admin_N password they logged in with), so the slot is what ties one
admin's rows together across name changes; it's per instance, though, as
each instance has its own passwords.
"""
import datetime
import re
import sqlite3
import time

from mbiiez import settings

MAX_ROWS = 2000
ACTIONS = ("login", "login_failed", "command", "say")

_COLOUR = re.compile(r"\^[0-9a-zA-Z]|\x1b\[[0-9;]*m")


def clean_name(name):
    return _COLOUR.sub("", str(name or "")).strip()


def _stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def _ip(ip):
    """SMOD logs the port too."""
    return str(ip or "").rsplit(":", 1)[0] if str(ip or "").count(":") == 1 else str(ip or "")


def search(filters=None):
    """What the SMOD Log page shows for this node: the newest MAX_ROWS rows
    matching `filters` ({q, instance, action, admin_id, days}), newest
    first, with a per-admin summary over them. The query matches the admin,
    the target, the command, its arguments, a message or an IP."""
    from mbiiez.db import db
    filters = filters if isinstance(filters, dict) else {}
    query = str(filters.get("q") or "").strip()[:64]
    instance = str(filters.get("instance") or "").strip()[:64]
    action = str(filters.get("action") or "").lower()
    action = action if action in ACTIONS else ""
    kept = db.RETENTION_DAYS.get("smod_log", 180)
    try:
        days = max(1, min(kept, int(filters.get("days") or 7)))
    except (TypeError, ValueError):
        days = 7
    now = int(time.time())

    where, args = ["added >= ?"], [_stamp(now - days * 86400)]
    if instance:
        where.append("instance = ? COLLATE NOCASE")
        args.append(instance)
    if action:
        where.append("action = ?")
        args.append(action)
    if query:
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(" + " OR ".join("{} LIKE ? ESCAPE '\\'".format(c) for c in
                                       ("admin", "target", "command", "args", "message", "ip", "target_ip")) + ")")
        args += [like] * 7

    rows, instances = [], []
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT added, instance, action, admin, admin_id, ip, command, args, target, target_ip, message "
                "FROM smod_log WHERE {} ORDER BY added DESC LIMIT {}".format(" AND ".join(where), MAX_ROWS + 1),
                args).fetchall()
            instances = sorted({r[0] for r in conn.execute("SELECT DISTINCT instance FROM smod_log") if r[0]},
                               key=str.lower)
        finally:
            conn.close()
    except sqlite3.Error:
        pass  # No table yet: nothing's been logged on this node.

    entries = []
    for added, inst, act, admin, admin_id, ip, command, cargs, target, target_ip, message in rows[:MAX_ROWS]:
        try:
            t = int(datetime.datetime.strptime(str(added)[:19], "%Y-%m-%d %H:%M:%S").timestamp())
        except ValueError:
            continue
        entries.append({"t": t, "instance": inst or "", "action": act or "", "admin": clean_name(admin),
                        "admin_id": admin_id or 0, "ip": _ip(ip), "command": command or "", "args": cargs or "",
                        "target": clean_name(target), "target_ip": _ip(target_ip), "message": message or ""})

    admins = {}
    for e in entries:
        a = admins.setdefault((e["instance"], e["admin_id"]), {
            "instance": e["instance"], "admin_id": e["admin_id"], "names": [], "ips": [],
            "logins": 0, "failed": 0, "commands": 0, "says": 0, "last": 0, "top": {}})
        if e["admin"] and e["admin"] not in a["names"]:
            a["names"].append(e["admin"])
        if e["ip"] and e["ip"] not in a["ips"]:
            a["ips"].append(e["ip"])
        a["last"] = max(a["last"], e["t"])
        a[{"login": "logins", "login_failed": "failed", "command": "commands", "say": "says"}.get(e["action"], "commands")] += 1
        if e["action"] == "command":
            a["top"][e["command"]] = a["top"].get(e["command"], 0) + 1
    for a in admins.values():
        a["top"] = sorted(a["top"].items(), key=lambda kv: -kv[1])[:5]

    return {"query": query, "instance": instance, "action": action, "days": days, "now": now,
            "entries": entries, "truncated": len(rows) > MAX_ROWS, "instances": instances, "kept_days": kept,
            "admins": sorted(admins.values(), key=lambda a: -a["last"])}
