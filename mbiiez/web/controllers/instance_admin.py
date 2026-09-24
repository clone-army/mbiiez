"""
Creating and deleting instances from the web panel - the New Instance
wizard (pages/instance-new.html) and the Settings page's Danger Zone.

An instance *is* its configs/<name>.json file: every instance lister
(mbii.py, web/tools.py, OpenJK's build.sh) only picks up names ending in
".json". So "deleting" just renames the file to <name>.json.del - it drops
out of every list, and undoing it is renaming it back. The instance's
homepath (logs, economy accounts) is left alone.
"""

import copy
import json
import os
import re
import secrets
import string
import subprocess
import time

from mbiiez.web.formify import GAME_MODES

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../configs"))
HOMEPATH_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../homepaths"))
TEMPLATE_PATH = os.path.join(CONFIG_DIR, "demo.json.example")

# The block of ports the wizard offers - existing instances live in 29071-29078.
PORT_RANGE = range(29070, 29090)
# Engines the wizard offers, in order of preference - whichever of them are
# actually installed in /usr/bin. caded.i386 is built from clone-army/OpenJK;
# a fresh install.sh box only has mbiided.i386 and openjkded.i386.
KNOWN_ENGINES = ["caded.i386", "mbiided.i386", "openjkded.i386"]
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,23}$")


def _config_path(name):
    return os.path.join(CONFIG_DIR, name + ".json")


def _load(name):
    with open(_config_path(name)) as f:
        return json.load(f)


def _instance_names():
    return sorted(fn[:-5] for fn in os.listdir(CONFIG_DIR) if fn.endswith(".json"))


def _listening_udp_ports():
    """Every UDP port something on this box is bound to (the game server
    speaks UDP), read straight from /proc so it needs no extra tools."""
    ports = set()
    for path in ("/proc/net/udp", "/proc/net/udp6"):
        try:
            with open(path) as f:
                next(f)
                for line in f:
                    local = line.split()[1]
                    ports.add(int(local.rsplit(":", 1)[1], 16))
        except (OSError, StopIteration, ValueError, IndexError):
            pass
    return ports


def _random_password(length=14):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def is_running(name):
    """Whether the instance's engine is up - it runs in a screen session
    named mb2_<name> (see mbiiez/instance.py)."""
    try:
        out = subprocess.run(["screen", "-ls"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return False
    return re.search(r"\d+\.mb2_" + re.escape(name) + r"\s", out) is not None


def ports_overview():
    """One entry per port in PORT_RANGE: which instance's config claims it,
    and whether anything is actually bound to it right now."""
    claimed = {}
    for name in _instance_names():
        try:
            port = int(_load(name).get("server", {}).get("port", 0))
        except Exception:
            continue
        claimed.setdefault(port, []).append(name)

    listening = _listening_udp_ports()
    out = []
    for port in PORT_RANGE:
        owners = claimed.get(port, [])
        out.append({
            "port": port,
            "used_by": owners,
            "listening": port in listening,
            "free": not owners and port not in listening,
        })
    return out


def wizard_bag():
    """Everything the New Instance page needs to render."""
    sources = []
    for name in _instance_names():
        try:
            cfg = _load(name)
        except Exception:
            continue
        server = cfg.get("server", {}) or {}
        security = cfg.get("security", {}) or {}
        sources.append({
            "name": name,
            "host_name": server.get("host_name", ""),
            "port": server.get("port", ""),
            "engine": server.get("engine", ""),
            "mode": (cfg.get("game", {}) or {}).get("mode", "open"),
            "rcon_password": security.get("rcon_password", ""),
            "server_password": security.get("server_password", ""),
            "plugins": sorted((cfg.get("plugins", {}) or {}).keys()),
        })

    engines = [e for e in KNOWN_ENGINES if os.path.exists(os.path.join("/usr/bin", e))] or KNOWN_ENGINES
    return {
        "sources": sources,
        "ports": ports_overview(),
        "engines": engines,
        "modes": GAME_MODES,
        "suggested_rcon": _random_password(),
    }


def create_instance(data):
    """Validate the wizard's answers and write configs/<name>.json.
    Returns (ok, message)."""
    name = str(data.get("name", "")).strip().lower()
    if not NAME_RE.match(name):
        return False, "Instance name must be 1-24 characters: lowercase letters, numbers, - or _, starting with a letter or number."
    if os.path.exists(_config_path(name)):
        return False, "An instance called '%s' already exists." % name

    try:
        port = int(data.get("port"))
    except (TypeError, ValueError):
        return False, "Pick a port."
    if not 1024 <= port <= 65535:
        return False, "Port must be between 1024 and 65535."
    for other in _instance_names():
        try:
            if int(_load(other).get("server", {}).get("port", 0)) == port:
                return False, "Port %d is already used by instance '%s'." % (port, other)
        except Exception:
            continue
    if port in _listening_udp_ports():
        return False, "Port %d is already in use by another program on this server." % port

    host_name = str(data.get("host_name", "")).strip()
    if not host_name:
        return False, "Server name can't be empty."

    mode = str(data.get("mode", "open")).lower()
    if mode not in GAME_MODES:
        return False, "Unknown game mode '%s'." % mode

    engine = str(data.get("engine", ""))
    if engine not in KNOWN_ENGINES:
        return False, "Unknown engine '%s'." % engine
    if not os.path.exists(os.path.join("/usr/bin", engine)):
        return False, "Engine %s isn't installed in /usr/bin on this server." % engine

    rcon = str(data.get("rcon_password", "")).strip()
    if len(rcon) < 6:
        return False, "RCON password must be at least 6 characters."

    source = str(data.get("source", "")).strip()
    if source:
        if source not in _instance_names():
            return False, "Instance '%s' to copy from doesn't exist." % source
        cfg = copy.deepcopy(_load(source))
    else:
        with open(TEMPLATE_PATH) as f:
            cfg = json.load(f)
        # The template's admin passwords are public examples - never ship them.
        for admin in (cfg.get("smod", {}) or {}).values():
            if isinstance(admin, dict) and "password" in admin:
                admin["password"] = _random_password(10)

    server = cfg.setdefault("server", {})
    server["host_name"] = host_name
    server["port"] = port
    server["engine"] = engine
    cfg.setdefault("game", {})["mode"] = mode
    security = cfg.setdefault("security", {})
    security["rcon_password"] = rcon
    security["server_password"] = str(data.get("server_password", "")).strip()

    # "x" = exclusive create, so two simultaneous submits can't both win.
    try:
        with open(_config_path(name), "x") as f:
            json.dump(cfg, f, indent=2)
    except FileExistsError:
        return False, "An instance called '%s' already exists." % name

    msg = "Created instance '%s' on port %d%s." % (name, port, " (copied from %s)" % source if source else "")
    if os.path.isdir(os.path.join(HOMEPATH_DIR, name)):
        msg += " Note: homepaths/%s already existed and will be reused (old logs/accounts)." % name
    return True, msg


def delete_instance(name):
    """Rename configs/<name>.json to <name>.json.del (or, if a .del from an
    earlier delete is already there, <name>.json.<timestamp>.del so it
    isn't overwritten). Refuses while the instance is running - mbii can
    only stop an instance whose .json still exists. Returns (ok, message)."""
    name = str(name or "").strip().lower()
    if not NAME_RE.match(name) or not os.path.exists(_config_path(name)):
        return False, "No instance called '%s'." % name
    if is_running(name):
        return False, "'%s' is still running - stop it first." % name

    target = _config_path(name) + ".del"
    if os.path.exists(target):
        target = _config_path(name) + "." + time.strftime("%Y%m%d-%H%M%S") + ".del"
    os.rename(_config_path(name), target)
    return True, "Deleted '%s' (config renamed to configs/%s - rename it back to restore)." % (name, os.path.basename(target))
