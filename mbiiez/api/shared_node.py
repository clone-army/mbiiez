"""Per-node durable outbox and local projections of the shared authority."""

import hashlib
import fcntl
import contextlib
import json
import os
from pathlib import Path
import secrets
import threading
import time
import logging
import requests
import psutil
from mbiiez import settings
from .storage import state_dir, read, write, locked
from . import shared_ledger
from .sync import FORMATS, engine_file, decode, encode
from .client import validate_url

log = logging.getLogger("mbiiez.shared")
_started = False


def configuration():
    return read(state_dir() / "shared_node.json", {})


def enabled():
    return bool(
        configuration().get("enabled")
        and read(state_dir() / "shared_engine.json", {}).get("enabled")
    )


def new_id():
    return secrets.token_hex(16)


def call(items):
    config = configuration()
    if not enabled():
        raise ValueError("Shared data is disabled")
    bootstrap = config.get("bootstrap")
    batch = ([bootstrap] if bootstrap else []) + items
    if config.get("authority"):
        if config.get("seed"):
            shared_ledger.seed(config["seed"])
        response = shared_ledger.apply(config["peer"], batch)
    else:
        reply = requests.post(
            config["hub"] + "/shared/v1/exchange",
            json={"events": batch},
            headers={
                "Authorization": "Bearer " + config["token"],
                "X-MBIIEZ-Peer": config["peer"],
            },
            timeout=(2, 4),
            allow_redirects=False,
        )
        if not reply.ok:
            raise ValueError(
                reply.json().get("error", "Shared authority rejected the operation")
            )
        response = reply.json()
    if bootstrap or config.get("seed"):
        # A lost reply repeats the identical enrollment ID. The hub commits all
        # datasets and subsequent events atomically, and receipts prevent copies.
        config.pop("bootstrap", None)
        config.pop("seed", None)
        write(state_dir() / "shared_node.json", config)
        if bootstrap:
            response["results"] = response["results"][1:]
    return response


def safety():
    from .sync import engine_shared_marker

    unsafe = []
    installed = Path("/usr/bin/caded.i386")
    if (
        not installed.exists()
        or b"MBIIEZ_SHARED_LEDGER_V2" not in installed.read_bytes()
    ):
        unsafe.append("installed engine")
    for proc in psutil.process_iter(["name", "create_time"], ad_value=None):
        if proc.info["name"] == "caded.i386":
            try:
                if not engine_shared_marker(proc.pid, proc.info["create_time"]):
                    unsafe.append(proc.pid)
            except (OSError, psutil.Error):
                unsafe.append(proc.pid)
    return {
        "shared_protocol": 2,
        "ready": not unsafe,
        "upgrade_required": bool(unsafe),
        "note": (
            "Stage the shared-ledger CADED build and use a planned game restart before enabling shared data."
            if unsafe
            else ""
        ),
    }


@contextlib.contextmanager
def auxiliary_file(filename):
    path = Path(settings.locations.mbii_path) / filename
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as stream:
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ValueError("Account data is busy; retry shortly")
                time.sleep(0.01)
        if os.fstat(fd).st_size > 128 * 1024:
            raise ValueError("Auxiliary account file is too large")
        yield stream


def activate(peer, hub="", token="", authority=False):
    if not safety()["ready"]:
        raise ValueError(safety()["note"])
    if not isinstance(peer, str) or not __import__("re").fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,31}", peer
    ):
        raise ValueError("Invalid peer ID")
    if not authority:
        hub = validate_url(hub)
    if not authority and (not isinstance(token, str) or not 32 <= len(token) <= 200):
        raise ValueError("Invalid peer token")
    from . import keys

    with locked(state_dir() / "shared_exchange"):
        current = configuration()
        if enabled():
            if (current.get("peer"), current.get("authority"), current.get("hub")) != (
                peer,
                authority,
                hub,
            ):
                raise ValueError(
                    "Unlink this node before changing its shared authority"
                )
            if not authority:
                current["token"] = token
                write(state_dir() / "shared_node.json", current)
            return {
                "enabled": True,
                "protocol": 2,
                "pending": bool(current.get("bootstrap")),
            }
        # Snapshot and change mode at one native transaction boundary. Network
        # enrollment happens afterwards: every new change is already journalled.
        with contextlib.ExitStack() as stack:
            opened = {
                name: stack.enter_context(engine_file(name, writable=True))
                for name in ("ip_bans", "guid_bans", "accounts", "stats")
            }
            initial = {
                "protocol": 1,
                "datasets": {
                    name: list(decode(name, item[1])[0].values())
                    for name, item in opened.items()
                },
            }
            from .sync import guid_links, seen_text

            initial["guid_links"] = list(guid_links(seen_text()).values())
            admins = stack.enter_context(auxiliary_file("economy_admins.dat"))
            daily = stack.enter_context(auxiliary_file("economy_daily.dat"))
            initial["admin_handles"] = sorted(
                {shared_ledger.account_key(handle) for handle in admins.read().split()}
            )
            initial["daily_claims"] = []
            for line in daily:
                fields = line.split()
                if len(fields) == 2:
                    initial["daily_claims"].append(
                        [shared_ledger.account_key(fields[0]), int(fields[1])]
                    )
            directory = state_dir() / "shared_initial_backups" / new_id()
            write(directory / "snapshot.json", initial)
            write(state_dir() / "shared_epoch.json", {"id": new_id()})
            snapshot = dict(initial, protocol=2, revision=0)
            config = {
                "enabled": True,
                "peer": peer,
                "hub": hub,
                "token": token,
                "authority": authority,
                "protocol": 2,
            }
            if authority:
                config["seed"] = initial
            if not authority:
                config["bootstrap"] = {"id": new_id(), "kind": "join", **initial}
            # Start a new outbox only after the previous group was safely drained.
            offset = journal().stat().st_size if journal().exists() else 0
            write(
                state_dir() / "shared_view.json",
                {"offset": offset, "intents": {}, "snapshot": snapshot},
            )
            key_id, key = keys.generate("engine", "shared-engine")
            old = read(state_dir() / "shared_engine.json", {})
            write(state_dir() / "shared_node.json", config)
            write(
                state_dir() / "shared_engine.json",
                {
                    "enabled": True,
                    "key": key,
                    "key_id": key_id,
                    "port": int(os.environ.get("MBIIEZ_API_PORT", "8081")),
                    "protocol": 2,
                },
            )
            if old.get("key_id"):
                keys.revoke(old["key_id"])
    try:
        exchange()
    except (requests.RequestException, ValueError):
        write(
            state_dir() / "shared_status.json",
            {
                "error": "Enrollment pending; spending is paused and events are retained.",
                "checked_at": time.time(),
            },
        )
    return {
        "enabled": True,
        "protocol": 2,
        "pending": bool(configuration().get("bootstrap")),
    }


def deactivate():
    if not enabled():
        return {"enabled": False}
    # Switching an active game from a central wallet to a local file would race
    # purchases. Never stop games automatically to make this transition.
    if any(
        proc.info["name"] == "caded.i386"
        for proc in psutil.process_iter(["name"], ad_value=None)
    ):
        raise ValueError(
            "Unlink shared data during a planned stop of all CADED instances on this node; games have not been stopped."
        )
    if configuration().get("authority"):
        raise ValueError(
            "Local remains the shared authority; unlink remote nodes instead"
        )
    exchange()
    with locked(state_dir() / "shared_exchange"), contextlib.ExitStack() as stack:
        for name in ("ip_bans", "guid_bans", "accounts", "stats"):
            stack.enter_context(engine_file(name, writable=True))
        rows, _ = pending()
        if rows or read(state_dir() / "shared_view.json", {}).get("intents"):
            raise ValueError("Pending shared transactions must settle before unlinking")
        engine = read(state_dir() / "shared_engine.json", {})
        engine["enabled"] = False
        write(state_dir() / "shared_engine.json", engine)
        config = configuration()
        config["enabled"] = False
        write(state_dir() / "shared_node.json", config)
    return {"enabled": False}


def journal():
    return state_dir() / "shared-events.jsonl"


def append(event):
    identity = event.setdefault("id", new_id())
    path = journal()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.write(json.dumps(event) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return identity


def pending(position=None):
    position = (
        position
        if position is not None
        else read(state_dir() / "shared_view.json", {"offset": 0})["offset"]
    )
    try:
        stream = open(journal(), "rb")
    except FileNotFoundError:
        return [], position
    rows = []
    end = position
    with stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        stream.seek(position)
        for _ in range(400):
            line = stream.readline(16385)
            if not line or not line.endswith(b"\n"):
                break
            if len(line) > 16384:
                raise ValueError("Shared journal record too large")
            try:
                row = json.loads(line.decode("utf-8"))
            except UnicodeDecodeError:
                row = json.loads(line.decode("latin-1"))
            row["journal_epoch"] = read(state_dir() / "shared_epoch.json", {}).get(
                "id", "initial_shared_epoch"
            )
            row["journal_sequence"] = stream.tell()
            rows.append(row)
            end = stream.tell()
    return rows, end


def recover_compaction():
    marker = state_dir() / "shared_compaction.json"
    if not marker.exists():
        return
    recovery = read(marker, {})
    fd = os.open(journal(), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        old = hashlib.sha256(stream.readline()).hexdigest() == recovery["first_line"]
        view = recovery["view"].copy()
        if not old:
            view["offset"] = 0
        write(state_dir() / "shared_view.json", view)
        write(
            state_dir() / "shared_epoch.json",
            {"id": recovery["old_epoch"] if old else recovery["new_epoch"]},
        )
        marker.unlink()
        directory = os.open(state_dir(), os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def compact():
    # Keep the same inode: a native writer may already have it open and be
    # waiting for flock. A durable marker distinguishes both sides of a crash.
    view = read(state_dir() / "shared_view.json", {})
    if (
        view.get("intents")
        or configuration().get("bootstrap")
        or view.get("offset", 0) < 8 * 1024 * 1024
    ):
        return
    fd = os.open(journal(), os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, "r+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        if os.fstat(fd).st_size != view["offset"]:
            return
        old_epoch = read(state_dir() / "shared_epoch.json", {})["id"]
        new_epoch = new_id()
        marker = state_dir() / "shared_compaction.json"
        write(
            marker,
            {
                "view": view,
                "old_epoch": old_epoch,
                "new_epoch": new_epoch,
                "first_line": hashlib.sha256(stream.readline()).hexdigest(),
            },
        )
        stream.truncate(0)
        stream.flush()
        os.fsync(fd)
        view["offset"] = 0
        write(state_dir() / "shared_view.json", view)
        write(state_dir() / "shared_epoch.json", {"id": new_epoch})
        marker.unlink()
        directory = os.open(state_dir(), os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def project(snapshot):
    if snapshot.get("protocol") != 2:
        raise ValueError("Shared protocol mismatch")
    # Native locks protect projections; journalled deltas are the source of truth.
    # Replaying a projection after a crash is safe and never emits a new data event.
    for name, rows in snapshot["datasets"].items():
        from .sync import validate

        records = validate(name, rows)
        with engine_file(name, writable=True) as (stream, content, path):
            _, document = decode(name, content)
            encoded = encode(name, records, document)
            if name == "guid_bans":
                from .sync import guid_links, seen_text

                links = guid_links(seen_text())
                for row in snapshot.get("guid_links", []):
                    link = (row[0], row[1].upper())
                    if link not in links or row[2] > links[link][2]:
                        links[link] = row
                keep = sorted(links.values(), key=lambda row: row[2], reverse=True)[
                    :16384
                ]
                path_seen = Path(settings.locations.mbii_path) / "guidseen.txt"
                from .storage import write as private_write

                # Native uses the ban lock above for both files.
                with open(path_seen, "w", encoding="latin-1") as seen:
                    os.chmod(path_seen, 0o600)
                    seen.write(
                        "".join("\t".join(str(v) for v in row) + "\n" for row in keep)
                    )
                    seen.flush()
                    os.fsync(seen.fileno())
            if name == "guid_bans":
                encoded = (
                    "# MBIIEZ_SHARED_REVISION="
                    + str(snapshot.get("revision", 0))
                    + "\n"
                    + encoded
                )
            if name == "ip_bans":
                doc = json.loads(encoded)
                doc["shared_revision"] = snapshot.get("revision", 0)
                encoded = json.dumps(doc)
            if name in ("guid_bans", "ip_bans"):
                with open(
                    path, "w", encoding="utf-8" if name == "ip_bans" else "latin-1"
                ) as out:
                    os.chmod(path, 0o600)
                    out.write(encoded)
                    out.flush()
                    os.fsync(out.fileno())
            else:
                stream.seek(0)
                stream.write(encoded)
                stream.truncate()
                stream.flush()
                os.fsync(stream.fileno())
    # Engine admin privileges are part of the same shared account group.
    path_admins = Path(settings.locations.mbii_path) / "economy_admins.dat"
    fd = os.open(path_admins, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        handles = [
            shared_ledger.account_key(value)
            for value in snapshot.get("admin_handles", [])
        ]
        stream.seek(0)
        stream.write("".join(handle + "\n" for handle in handles))
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    write(state_dir() / "shared_projection.json", snapshot)


def exchange():
    if not enabled():
        config = configuration()
        if config.get("enabled"):
            activate(
                config["peer"],
                config.get("hub", ""),
                config.get("token", ""),
                config.get("authority", False),
            )
        return
    from mbiiez import bansync

    # Capture in-game IP edits before replacing the master cache with a hub view.
    bansync.sync()
    with locked(state_dir() / "shared_exchange"):
        recover_compaction()
        rows, end = pending()
        events = [row for row in rows if row.get("kind") != "intent"]
        # An intent without a commit/cancel is retained separately for crash recovery.
        intents = read(state_dir() / "shared_view.json", {}).get("intents", {})
        for row in rows:
            if row.get("kind") == "intent":
                intents[row["id"]] = row
            elif row.get("kind") in ("commit", "cancel"):
                intents.pop(row["reservation"], None)
        caught_up = not journal().exists() or journal().stat().st_size == end
        for identifier, row in list(intents.items()):
            # A dead game's durable commit may be beyond this bounded batch.
            # Never refund until its entire journal has been read.
            if not caught_up:
                continue
            try:
                proc = psutil.Process(row["pid"])
                alive = proc.status() != psutil.STATUS_ZOMBIE and Path(
                    f'/proc/{row["pid"]}/stat'
                ).read_text().rsplit(")", 1)[1].split()[19] == str(row["started"])
            except (psutil.Error, KeyError, OSError, IndexError):
                alive = False
            if not alive:
                events.append(
                    {
                        "kind": "cancel",
                        "id": "recovery_" + identifier,
                        "reservation": identifier,
                    }
                )
                del intents[identifier]
        response = call(events)
        # Persist receipts before projecting. Native counters are not authoritative; a
        # stopped API can replay the hub snapshot without adding any event twice.
        write(
            state_dir() / "shared_view.json",
            {"offset": end, "intents": intents, "snapshot": response["snapshot"]},
        )
        project(response["snapshot"])
        write(
            state_dir() / "shared_status.json",
            {
                "last_success": time.time(),
                "pending_reservations": len(intents),
                "enabled": True,
            },
        )
        compact()
    bansync.sync()


def acknowledge(rows, end, snapshot):
    intents = read(state_dir() / "shared_view.json", {}).get("intents", {})
    for row in rows:
        if row.get("kind") == "intent":
            intents[row["id"]] = row
        elif row.get("kind") in ("commit", "cancel"):
            intents.pop(row["reservation"], None)
    write(
        state_dir() / "shared_view.json",
        {"offset": end, "intents": intents, "snapshot": snapshot},
    )


def engine_operation(data):
    if not enabled():
        raise ValueError("Shared data is not enabled")
    kind = data.get("kind")
    if kind not in ("reserve", "register", "login", "balance"):
        raise ValueError("Invalid engine operation")
    if kind == "balance":
        if (state_dir() / "shared_compaction.json").exists():
            raise ValueError("Shared journal recovery is pending")
        fd = os.open(journal(), os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "rb") as journal_lock:
            fcntl.flock(journal_lock.fileno(), fcntl.LOCK_SH)
            if (state_dir() / "shared_compaction.json").exists():
                raise ValueError("Shared journal recovery is pending")
            return cached_balance(data)

    if kind == "reserve" and any(
        not row.get("session") for row in data.get("changes", [])
    ):
        return {"error": "Please log in to your shared account", "relogin": True}
    # Settle locally recorded winnings before evaluating an authoritative debit.
    with locked(state_dir() / "shared_exchange"):
        recover_compaction()
        recover_compaction()
        rows, end = pending()
        events = [row for row in rows if row.get("kind") != "intent"]
        try:
            response = call(events + [data])
        except ValueError as error:
            if "session" in str(error).lower():
                return {"error": "Please log in again", "relogin": True}
            raise
        acknowledge(rows, end, response["snapshot"])
        result = response["results"][-1]
    return result


def cached_balance(data):
    handle = shared_ledger.account_key(data["handle"])
    view = read(state_dir() / "shared_view.json", {})
    snapshot = view.get(
        "snapshot",
        read(state_dir() / "shared_projection.json", {"datasets": {"accounts": []}}),
    )
    row = next(
        (row for row in snapshot["datasets"]["accounts"] if row[0].lower() == handle),
        None,
    )
    if row is None:
        return {"error": "Account not found"}
    # Give the local session its durable, not-yet-acknowledged earnings immediately.
    rows, _ = pending(view.get("offset", 0))
    extra = sum(
        row["amount"]
        for row in rows
        if row.get("kind") == "credit" and row["handle"].lower() == handle
    )
    intents = read(state_dir() / "shared_view.json", {}).get("intents", {}).copy()
    for item in rows:
        if item.get("kind") == "intent":
            intents[item["id"]] = item
        elif item.get("kind") == "commit":
            extra += sum(
                change["amount"]
                for change in intents.get(item["reservation"], {}).get("changes", [])
                if (change.get("recipient") or "").lower() == handle
            )
    return {"credits": row[3] + extra}


def edit(kind, **values):
    event = dict(id=new_id(), kind=kind, **values)
    with locked(state_dir() / "shared_exchange"):
        recover_compaction()
        recover_compaction()
        rows, end = pending()
        events = [row for row in rows if row.get("kind") != "intent"]
        response = call(events + [event])
        acknowledge(rows, end, response["snapshot"])
        project(response["snapshot"])
    return response["results"][-1]


def start():
    global _started
    if _started:
        return
    _started = True

    def loop():
        # One agent worker across process replicas.
        path = state_dir() / "shared_worker.lock"
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR, 0o600), "w") as stream:
            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(2)
            while True:
                began = time.monotonic()
                try:
                    exchange()
                except Exception:
                    log.exception("Shared data exchange failed")
                    write(
                        state_dir() / "shared_status.json",
                        {
                            "error": "Shared authority unavailable; spending is paused. Pending events are retained.",
                            "checked_at": time.time(),
                        },
                    )
                time.sleep(max(0.1, 1 - (time.monotonic() - began)))

    threading.Thread(target=loop, name="shared-agent", daemon=True).start()
