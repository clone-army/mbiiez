"""Authoritative shared state. Wallet reservations and event receipts are atomic."""

import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from .storage import state_dir
from .sync import validate, FORMATS, number

MAX = 2147483647
SCHEMA = """
CREATE TABLE IF NOT EXISTS records(kind TEXT,key TEXT,data TEXT,PRIMARY KEY(kind,key));
CREATE TABLE IF NOT EXISTS peers(id TEXT PRIMARY KEY,digest TEXT,enabled INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS receipts(peer TEXT,id TEXT,digest TEXT,result TEXT,PRIMARY KEY(peer,id));
CREATE TABLE IF NOT EXISTS reservations(peer TEXT,id TEXT,digest TEXT,changes TEXT,status TEXT,PRIMARY KEY(peer,id));
CREATE TABLE IF NOT EXISTS ban_versions(kind TEXT,key TEXT,version INTEGER,PRIMARY KEY(kind,key));
CREATE TABLE IF NOT EXISTS links(ip TEXT,guid TEXT,seen INTEGER,name TEXT,PRIMARY KEY(ip,guid));
CREATE TABLE IF NOT EXISTS watermarks(peer TEXT,epoch TEXT,sequence INTEGER,PRIMARY KEY(peer,epoch));
CREATE TABLE IF NOT EXISTS sessions(digest TEXT PRIMARY KEY,handle TEXT,peer TEXT);
CREATE TABLE IF NOT EXISTS daily(handle TEXT PRIMARY KEY,claimed INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS admins(handle TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
"""


@contextlib.contextmanager
def transaction():
    path = state_dir() / "shared-ledger.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    db = sqlite3.connect(path, timeout=5)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def key(kind, row):
    return next(iter(validate(kind, [row])))


def get(db, kind, identifier):
    result = db.execute(
        "SELECT data FROM records WHERE kind=? AND key=?", (kind, identifier)
    ).fetchone()
    return json.loads(result[0]) if result else None


def put(db, kind, row):
    identifier = key(kind, row)
    if (
        get(db, kind, identifier) is None
        and db.execute("SELECT COUNT(*) FROM records WHERE kind=?", (kind,)).fetchone()[
            0
        ]
        >= FORMATS[kind][2]
    ):
        raise ValueError("Shared dataset exceeds engine record limit")
    db.execute(
        "INSERT INTO records VALUES(?,?,?) ON CONFLICT(kind,key) DO UPDATE SET data=excluded.data",
        (kind, identifier, json.dumps(row)),
    )


def seed(snapshot):
    # Called once from Local. Subsequent enrollments can never reset the shared wallet.
    with transaction() as db:
        if db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone():
            return False
        for kind, rows in snapshot["datasets"].items():
            for row in validate(kind, rows).values():
                put(db, kind, row)
        for row in snapshot.get("guid_links", []):
            operation(
                db, "local", dict(id=secrets.token_hex(16), kind="guid_seen", row=row)
            )
        for handle in snapshot.get("admin_handles", []):
            db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (account_key(handle),))
        for handle, claimed in snapshot.get("daily_claims", []):
            db.execute(
                "INSERT OR REPLACE INTO daily VALUES(?,?)",
                (account_key(handle), number(claimed)),
            )
        db.execute("INSERT INTO metadata VALUES('seeded',?)", (str(time.time()),))
        return True


def enroll(identifier):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", identifier):
        raise ValueError("Invalid peer ID")
    token = secrets.token_urlsafe(32)
    with transaction() as db:
        db.execute(
            "INSERT INTO peers VALUES(?,?,1) ON CONFLICT(id) DO UPDATE SET digest=excluded.digest,enabled=1",
            (identifier, hashlib.sha256(token.encode()).hexdigest()),
        )
    return token


def verify(identifier, token):
    with transaction() as db:
        row = db.execute(
            "SELECT digest,enabled FROM peers WHERE id=?", (identifier,)
        ).fetchone()
        return bool(
            row
            and row[1]
            and hmac.compare_digest(row[0], hashlib.sha256(token.encode()).hexdigest())
        )


def disable(identifier):
    with transaction() as db:
        db.execute("UPDATE peers SET enabled=0 WHERE id=?", (identifier,))


def snapshot(db):
    version = db.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()
    result = {
        "protocol": 2,
        "daily_claims": [
            list(row)
            for row in db.execute("SELECT handle,claimed FROM daily ORDER BY handle")
        ],
        "admin_handles": [
            row[0] for row in db.execute("SELECT handle FROM admins ORDER BY handle")
        ],
        "revision": int(version[0]) if version else 0,
        "datasets": {name: [] for name in FORMATS},
        "guid_links": [
            list(row)
            for row in db.execute(
                "SELECT ip,guid,seen,name FROM links WHERE seen>? ORDER BY seen DESC LIMIT 16384",
                (int(time.time()) - 7 * 86400,),
            )
        ],
    }
    for kind, raw in db.execute("SELECT kind,data FROM records ORDER BY kind,key"):
        if kind in result["datasets"]:
            result["datasets"][kind].append(json.loads(raw))
    return result


def identity(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,100}", value):
        raise ValueError("Invalid operation ID")
    return value


def account_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_]{1,23}", value):
        raise ValueError("Invalid account handle")
    return value.lower()


def edit_balance(db, handle, delta):
    row = get(db, "accounts", account_key(handle))
    if not row:
        raise ValueError("Account not found")
    new = row[3] + delta
    if not 0 <= new <= MAX:
        raise ValueError("Insufficient credits or balance exceeds engine limit")
    row[3] = new
    put(db, "accounts", row)
    return new


def operation(db, peer, item):
    kind = item.get("kind")
    identifier = identity(item.get("id"))
    if kind == "reserve":
        changes = item.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 2:
            raise ValueError("Invalid wallet reservation")
        normalized = []
        for change in changes:
            handle = account_key(change["handle"])
            amount = number(change["amount"])
            if not amount:
                raise ValueError("Amount must be positive")
            session = change.get("session")
            if (
                session
                and not db.execute(
                    "SELECT 1 FROM sessions WHERE digest=? AND handle=? AND peer=?",
                    (hashlib.sha256(session.encode()).hexdigest(), handle, peer),
                ).fetchone()
            ):
                raise ValueError("Shared session expired; log in again")
            recipient = (
                account_key(change["recipient"]) if change.get("recipient") else None
            )
            if recipient and not get(db, "accounts", recipient):
                raise ValueError("Recipient account not found")
            normalized.append(dict(handle=handle, amount=amount, recipient=recipient))
        if len({row["handle"] for row in normalized}) != len(normalized):
            raise ValueError("Duplicate wallet debit")
        digest = hashlib.sha256(
            json.dumps(normalized, sort_keys=True).encode()
        ).hexdigest()
        previous = db.execute(
            "SELECT digest,status FROM reservations WHERE peer=? AND id=?",
            (peer, identifier),
        ).fetchone()
        if previous:
            if previous[1] == "cancelled":
                raise ValueError("Reservation cancelled")
            if previous[0] != digest:
                raise ValueError("Operation ID reused with different contents")
        else:
            for row in normalized:
                edit_balance(db, row["handle"], -row["amount"])
            db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?)",
                (peer, identifier, digest, json.dumps(normalized), "reserved"),
            )
        return {
            "balances": {
                row["handle"]: get(db, "accounts", row["handle"])[3]
                for row in normalized
            }
        }
    if kind in ("commit", "cancel"):
        reserve = identity(item.get("reservation"))
        previous = db.execute(
            "SELECT changes,status FROM reservations WHERE peer=? AND id=?",
            (peer, reserve),
        ).fetchone()
        if not previous:
            if kind == "commit":
                raise ValueError("Reservation not found")
            # A cancellation may arrive before a delayed prepare. It permanently fences it.
            db.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?)",
                (peer, reserve, "", "[]", "cancelled"),
            )
            return {"cancelled": True}
        changes, status = json.loads(previous[0]), previous[1]
        if status == "reserved":
            for change in changes:
                if kind == "cancel":
                    edit_balance(db, change["handle"], change["amount"])
                elif change["recipient"]:
                    edit_balance(db, change["recipient"], change["amount"])
            db.execute(
                "UPDATE reservations SET status=? WHERE peer=? AND id=?",
                ("committed" if kind == "commit" else "cancelled", peer, reserve),
            )
        elif kind == "commit" and status == "cancelled":
            raise ValueError("Reservation cancelled")
        # A cancellation after a committed purchase never refunds it a second time.
        return {"status": kind}
    if kind == "credit":
        amount = number(item["amount"])
        if get(db, "accounts", account_key(item["handle"])) is None:
            return {"ignored": "Account deleted"}
        return {"credits": edit_balance(db, item["handle"], amount)}
    if kind == "daily_claim":
        handle = account_key(item["handle"])
        claimed = number(item["claimed"])
        db.execute(
            "INSERT INTO daily VALUES(?,?) ON CONFLICT(handle) DO UPDATE SET claimed=MAX(daily.claimed,excluded.claimed)",
            (handle, claimed),
        )
        return {"ok": True}
    if kind == "stats_batch":
        rows = item.get("rows")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 2:
            raise ValueError("Invalid stats batch")
        for row in rows:
            operation(db, peer, dict(row, id=secrets.token_hex(16), kind="stats"))
        return {"ok": True}
    if kind == "stats":
        stat_key = item["key"]
        validate("stats", [[stat_key, 0, 0, 0, 0]])
        old = get(db, "stats", key("stats", [stat_key, 0, 0, 0, 0])) or [
            stat_key,
            0,
            0,
            0,
            0,
        ]
        values = item["delta"]
        if not isinstance(values, list) or len(values) != 4:
            raise ValueError("Invalid stats delta")
        result = [old[0]] + [number(a + number(b)) for a, b in zip(old[1:], values)]
        put(db, "stats", result)
        return {"ok": True}
    if kind == "guid_seen":
        ip, guid, seen, name = item["row"]
        from mbiiez.bansync import valid_ip
        from mbiiez.guidbans import valid_guid

        if not valid_ip(ip) or not valid_guid(guid):
            raise ValueError("Invalid GUID association")
        db.execute(
            "INSERT INTO links VALUES(?,?,?,?) ON CONFLICT(ip,guid) DO UPDATE SET seen=MAX(links.seen,excluded.seen),name=excluded.name",
            (ip, guid.upper(), number(seen), str(name)[:63]),
        )
        db.execute("DELETE FROM links WHERE seen<?", (int(time.time()) - 30 * 86400,))
        return {"ok": True}
    if kind in ("ban_set", "ban_update", "ban_delete"):
        dataset = item["dataset"]
        if dataset not in ("guid_bans", "ip_bans"):
            raise ValueError("Unsupported ban dataset")
        identifier = (
            key(dataset, item["row"])
            if kind != "ban_delete"
            else (item["key"].lower() if dataset == "guid_bans" else item["key"])
        )
        previous = db.execute(
            "SELECT version FROM ban_versions WHERE kind=? AND key=?",
            (dataset, identifier),
        ).fetchone()
        if previous and number(item.get("base_revision", 0)) < previous[0]:
            return {"skipped": True}
        version = db.execute(
            "SELECT value FROM metadata WHERE key='revision'"
        ).fetchone()
        revision = (int(version[0]) if version else 0) + 1
        if kind in ("ban_set", "ban_update"):
            row = item["row"]
            if kind == "ban_update" and get(db, dataset, identifier) is None:
                return {"skipped": True}
            if dataset == "guid_bans" and kind == "ban_set":
                parent = re.search(r"as banned ([a-fA-F0-9]{16,64})", str(row[7]))
                if parent and get(db, dataset, parent[1].lower()) is None:
                    return {"skipped": True}
                ip_version = (
                    db.execute(
                        "SELECT version FROM ban_versions WHERE kind='ip_bans' AND key=?",
                        (row[6],),
                    ).fetchone()
                    if row[6]
                    else None
                )
                if (
                    ip_version
                    and ip_version[0] > number(item.get("base_revision", 0))
                    and get(db, "ip_bans", row[6]) is None
                ):
                    return {"skipped": True}
            put(db, dataset, row)
        else:
            db.execute(
                "DELETE FROM records WHERE kind=? AND key=?", (dataset, identifier)
            )
        db.execute(
            "INSERT OR REPLACE INTO ban_versions VALUES(?,?,?)",
            (dataset, identifier, revision),
        )
        db.execute(
            "INSERT OR REPLACE INTO metadata VALUES('revision',?)", (str(revision),)
        )
        if kind == "ban_delete":
            # Unbanning a root also removes GUID aliases it created on other regions.
            removed = {identifier}
            changed = True
            while changed:
                changed = False
                for (raw,) in db.execute(
                    "SELECT data FROM records WHERE kind='guid_bans'"
                ).fetchall():
                    row = json.loads(raw)
                    parent = re.search(r"as banned ([a-fA-F0-9]{16,64})", row[7])
                    if (dataset == "ip_bans" and row[6] == identifier) or (
                        parent and parent[1].lower() in removed
                    ):
                        alias = row[0].lower()
                        removed.add(alias)
                        changed = True
                        db.execute(
                            "DELETE FROM records WHERE kind='guid_bans' AND key=?",
                            (alias,),
                        )
                        db.execute(
                            "INSERT OR REPLACE INTO ban_versions VALUES('guid_bans',?,?)",
                            (alias, revision),
                        )
        return {"ok": True}
    if kind == "admin_edit":
        handle = account_key(item["handle"])
        if not isinstance(item.get("enabled"), bool):
            raise ValueError("enabled must be a boolean")
        if not get(db, "accounts", handle):
            raise ValueError("Account not found")
        if item["enabled"]:
            db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (handle,))
        else:
            db.execute("DELETE FROM admins WHERE handle=?", (handle,))
        return {"ok": True}
    if kind == "account_edit":
        handle = account_key(item["handle"])
        row = get(db, "accounts", handle)
        if not row:
            raise ValueError("Account not found")
        action = item["action"]
        if action == "credit":
            delta = item["amount"]
            if (
                isinstance(delta, bool)
                or not isinstance(delta, int)
                or abs(delta) > MAX
            ):
                raise ValueError("Invalid credit adjustment")
            return {"credits": edit_balance(db, handle, delta)}
        if action == "unlock":
            row[4:] = [0, 0]
        elif action == "pin":
            pin = str(item["pin"])
            if not re.fullmatch(r"\d{4}", pin):
                raise ValueError("PIN must be four digits")
            db.execute("DELETE FROM sessions WHERE handle=?", (handle,))
            salt = os.urandom(16)
            row[1:3] = [
                salt.hex(),
                hmac.new(salt, pin.encode(), hashlib.md5).hexdigest(),
            ]
            row[4:] = [0, 0]
        elif action == "delete":
            for (raw,) in db.execute(
                "SELECT changes FROM reservations WHERE status='reserved'"
            ):
                if any(
                    change["handle"] == handle or change["recipient"] == handle
                    for change in json.loads(raw)
                ):
                    raise ValueError(
                        "Account has a pending purchase; retry after it settles"
                    )
            db.execute("DELETE FROM sessions WHERE handle=?", (handle,))
            db.execute("DELETE FROM admins WHERE handle=?", (handle,))
            db.execute("DELETE FROM records WHERE kind='accounts' AND key=?", (handle,))
            return {"ok": True}
        else:
            raise ValueError("Unknown account action")
        put(db, "accounts", row)
        return {"ok": True}
    if kind == "join":
        # Existing Local identities are never added twice. Remote-only records are preserved.
        datasets = item["datasets"]
        added = {}
        existing = {
            row[0]
            for row in db.execute("SELECT key FROM records WHERE kind='accounts'")
        }
        for dataset, rows in datasets.items():
            if dataset not in FORMATS:
                raise ValueError("Invalid join dataset")
            added[dataset] = 0
            for identifier, row in validate(dataset, rows).items():
                if (
                    dataset in ("guid_bans", "ip_bans")
                    and db.execute(
                        "SELECT 1 FROM ban_versions WHERE kind=? AND key=?",
                        (dataset, identifier),
                    ).fetchone()
                ):
                    continue
                if get(db, dataset, identifier) is None:
                    put(db, dataset, row)
                    added[dataset] += 1
        for handle in item.get("admin_handles", []):
            handle = account_key(handle)
            if handle not in existing and get(db, "accounts", handle):
                db.execute("INSERT OR IGNORE INTO admins VALUES(?)", (handle,))
        for handle, claimed in item.get("daily_claims", []):
            handle = account_key(handle)
            if handle not in existing:
                db.execute(
                    "INSERT OR IGNORE INTO daily VALUES(?,?)", (handle, number(claimed))
                )
        for row in item.get("guid_links", []):
            operation(
                db, peer, dict(id=secrets.token_hex(16), kind="guid_seen", row=row)
            )
        return {"added": added}
    if kind in ("register", "login"):
        handle = account_key(item["handle"])
        pin = str(item["pin"])
        if not re.fullmatch(r"\d{4}", pin):
            raise ValueError("PIN must be four digits")
        row = get(db, "accounts", handle)
        now = int(time.time())
        if kind == "register":
            if row:
                raise ValueError("That handle is already registered")
            count = db.execute(
                "SELECT COUNT(*) FROM records WHERE kind='accounts'"
            ).fetchone()[0]
            if count >= 1024:
                raise ValueError("Account storage is full")
            salt = os.urandom(16)
            bonus = number(item.get("bonus", 0))
            row = [
                item["handle"],
                salt.hex(),
                hmac.new(salt, pin.encode(), hashlib.md5).hexdigest(),
                bonus,
                0,
                0,
            ]
            db.execute("INSERT OR REPLACE INTO daily VALUES(?,?)", (handle, now))
            put(db, "accounts", row)
        else:
            if not row:
                raise ValueError("No account with that handle")
            if row[5] > now:
                return {"error": "Account temporarily locked"}
            candidate = hmac.new(
                bytes.fromhex(row[1]), pin.encode(), hashlib.md5
            ).hexdigest()
            if not hmac.compare_digest(candidate, row[2]):
                row[4] += 1
                if row[4] % 5 == 0:
                    row[5] = now + min(3600, 30 * (2 ** min(10, row[4] // 5 - 1)))
                put(db, "accounts", row)
                return {"error": "Incorrect PIN"}
            row[4:] = [0, 0]
            last = db.execute(
                "SELECT claimed FROM daily WHERE handle=?", (handle,)
            ).fetchone()
            bonus = number(item.get("bonus", 0))
            if bonus and (not last or now - last[0] >= 86400):
                row[3] = number(row[3] + bonus)
                db.execute("INSERT OR REPLACE INTO daily VALUES(?,?)", (handle, now))
            put(db, "accounts", row)
        session = secrets.token_hex(16)
        db.execute("DELETE FROM sessions WHERE handle=? AND peer=?", (handle, peer))
        db.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (hashlib.sha256(session.encode()).hexdigest(), handle, peer),
        )
        return {"handle": row[0], "credits": row[3], "session": session}
    raise ValueError("Unsupported shared operation")


def apply(peer, items):
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError("Invalid shared event batch")
    results = []
    with transaction() as db:
        for item in items:
            identifier = identity(item.get("id"))
            digest = hashlib.sha256(
                json.dumps(item, sort_keys=True).encode()
            ).hexdigest()
            epoch = item.get("journal_epoch")
            sequence = item.get("journal_sequence")
            if epoch is not None:
                identity(epoch)
                if (
                    isinstance(sequence, bool)
                    or not isinstance(sequence, int)
                    or sequence < 0
                ):
                    raise ValueError("Invalid journal sequence")
                mark = db.execute(
                    "SELECT sequence FROM watermarks WHERE peer=? AND epoch=?",
                    (peer, epoch),
                ).fetchone()
                if mark and sequence <= mark[0]:
                    results.append({"already_applied": True})
                    continue
            previous = db.execute(
                "SELECT digest,result FROM receipts WHERE peer=? AND id=?",
                (peer, identifier),
            ).fetchone()
            if previous:
                if not hmac.compare_digest(previous[0], digest):
                    raise ValueError("Operation ID reused")
                result = json.loads(previous[1])
            else:
                result = operation(db, peer, item)
                if epoch is None:
                    db.execute(
                        "INSERT INTO receipts VALUES(?,?,?,?)",
                        (peer, identifier, digest, json.dumps(result)),
                    )
            if epoch is not None:
                db.execute(
                    "INSERT OR REPLACE INTO watermarks VALUES(?,?,?)",
                    (peer, epoch, sequence),
                )
            results.append(result)
        return {"results": results, "snapshot": snapshot(db)}
