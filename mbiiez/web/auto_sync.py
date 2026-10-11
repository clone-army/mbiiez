"""Enrollment/status for a shared authority; data exchange belongs to API agents."""

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time
from mbiiez.api.client import Client, nodes, is_local_node
from mbiiez.api.storage import state_dir, locked, read, write

INTERVAL = 10
_started = False
log = logging.getLogger("mbiiez.web.sync")


def settings_path():
    return state_dir() / "automatic_sync.json"


def local_node():
    return next((key for key, node in nodes().items() if is_local_node(node)), None)


def settings():
    default = {
        "nodes": {
            key: {"enabled": True, "url": node["url"]}
            for key, node in nodes().items()
            if is_local_node(node)
        }
    }
    policy = read(settings_path(), default)
    for key, entry in policy.get("nodes", {}).items():
        if key != local_node() and entry.get("protocol") != 2:
            entry["enabled"] = False
    return policy


def status():
    return read(state_dir() / "automatic_sync_status.json", {})


def configure(identifier, enabled, hub=None):
    configured = nodes()
    local = local_node()
    if not isinstance(enabled, bool) or identifier not in configured:
        raise ValueError("Choose an existing node and a boolean sync setting")
    if identifier == local:
        raise ValueError("Local is always the shared data authority")
    if not local:
        raise ValueError("A Local node is required for shared data")
    if enabled:
        for peer in (local, identifier):
            info = Client(peer).call("GET", "sync/info")
            if info.get("shared_protocol") != 2 or not info.get("ready"):
                raise ValueError(
                    info.get("note")
                    or "Update both API agents and CADED engines before enabling shared data"
                )
            if not info.get("caded_instances"):
                raise ValueError("Shared data requires a configured CADED instance")
        if not hub:
            raise ValueError("A public HTTPS URL for this interface is required")
        Client(local).call(
            "POST",
            "shared/configure",
            {"enabled": True, "authority": True, "peer": local},
        )
        credential = Client(local).call(
            "POST", "shared/peer", {"peer": identifier, "enabled": True}
        )
        Client(identifier).call(
            "POST",
            "shared/configure",
            {
                "enabled": True,
                "peer": identifier,
                "hub": hub,
                "token": credential["token"],
            },
        )
    else:
        # Settle first. If an agent is offline, do not silently abandon its outbox.
        Client(identifier).call("POST", "shared/configure", {"enabled": False})
        Client(local).call(
            "POST", "shared/peer", {"peer": identifier, "enabled": False}
        )
    with locked(settings_path()):
        policy = settings()
        policy["nodes"][identifier] = {
            "enabled": enabled,
            "url": configured[identifier]["url"],
            "protocol": 2,
        }
        write(settings_path(), policy)
    return policy["nodes"][identifier]


def automatic_client(identifier):
    return Client(identifier, actor="shared-data-status")


def cycle(client_factory=automatic_client):
    configured = nodes()
    policy = settings()["nodes"]
    local = local_node()
    result = {"checked_at": time.time(), "interval": 1, "nodes": {}}
    enrolled = {
        key: node
        for key, node in configured.items()
        if policy.get(key, {}).get("enabled")
    }

    def check(identifier):
        node = enrolled[identifier]
        entry = policy.get(identifier, {})
        if entry.get("url") != node["url"]:
            if identifier != local and local:
                client_factory(local).call(
                    "POST", "shared/peer", {"peer": identifier, "enabled": False}
                )
            return {
                "error": "API URL changed. Disable and re-enable shared data to approve the new destination."
            }
        info = client_factory(identifier).call("GET", "shared/status")
        state = info.get("status", {})
        if state.get("error"):
            return {"error": state["error"], "last_success": state.get("last_success")}
        if not info.get("enabled"):
            return {
                "waiting": info.get("note")
                or "Local is the source; enable shared data on a remote node to link it."
            }
        return {
            "last_success": state.get("last_success"),
            "waiting": (
                "Initial synchronization is pending."
                if not state.get("last_success")
                else ""
            ),
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {key: pool.submit(check, key) for key in enrolled}
        for key, future in pending.items():
            try:
                result["nodes"][key] = future.result()
            except Exception:
                result["nodes"][key] = {
                    "error": "API unavailable. Shared events remain queued on the node."
                }
    write(state_dir() / "automatic_sync_status.json", result)
    return result


def start():
    global _started
    if _started:
        return
    _started = True

    def loop():
        while True:
            try:
                cycle()
            except Exception:
                log.exception("Shared data status refresh failed")
            time.sleep(INTERVAL)

    threading.Thread(target=loop, name="shared-data-status", daemon=True).start()
