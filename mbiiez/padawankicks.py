"""Players the shield's PadawanTK switch has kicked on this node's servers
(wireless connections located in Texas), from the shield_kicks table the
shield plugin fills (kept db.RETENTION_DAYS["shield_kicks"] days)."""
import datetime
import re
import sqlite3
import time

from mbiiez import settings

MAX_ROWS = 2000
_COLOUR = re.compile(r"\^[0-9a-zA-Z]|\x1b\[[0-9;]*m")


def _stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")


def search(filters=None):
    """The newest MAX_ROWS PadawanTK kicks matching `filters`
    ({q, instance, days}), newest first. The query matches the player, IP,
    city or region."""
    from mbiiez.db import db
    filters = filters if isinstance(filters, dict) else {}
    query = str(filters.get("q") or "").strip()[:64]
    instance = str(filters.get("instance") or "").strip()[:64]
    kept = db.RETENTION_DAYS.get("shield_kicks", 180)
    try:
        days = max(1, min(kept, int(filters.get("days") or 30)))
    except (TypeError, ValueError):
        days = 30

    where, args = ["added >= ?", "rule = 'padawan_tk'"], [_stamp(int(time.time()) - days * 86400)]
    if instance:
        where.append("instance = ? COLLATE NOCASE")
        args.append(instance)
    if query:
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(" + " OR ".join("{} LIKE ? ESCAPE '\\'".format(c) for c in ("player", "ip", "city", "region")) + ")")
        args += [like] * 4

    rows, instances = [], []
    try:
        conn = sqlite3.connect("file:{}?mode=ro".format(settings.database.database), uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT added, instance, player, ip, city, region FROM shield_kicks WHERE {} "
                "ORDER BY added DESC LIMIT {}".format(" AND ".join(where), MAX_ROWS + 1), args).fetchall()
            instances = sorted({r[0] for r in conn.execute(
                "SELECT DISTINCT instance FROM shield_kicks WHERE rule = 'padawan_tk'") if r[0]}, key=str.lower)
        finally:
            conn.close()
    except sqlite3.Error:
        pass  # No table yet: nothing's been kicked on this node.

    entries = []
    for added, inst, player, ip, city, region in rows[:MAX_ROWS]:
        try:
            t = int(datetime.datetime.strptime(str(added)[:19], "%Y-%m-%d %H:%M:%S").timestamp())
        except ValueError:
            continue
        entries.append({"t": t, "instance": inst or "", "player": _COLOUR.sub("", str(player or "")).strip(),
                        "ip": ip or "", "city": city or "", "region": region or ""})
    return {"query": query, "instance": instance, "days": days, "entries": entries,
            "truncated": len(rows) > MAX_ROWS, "instances": instances, "kept_days": kept}
