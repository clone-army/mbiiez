import json
import os
import time

from mbiiez import settings

# How scenarios start without anyone typing !ht (g_holotableAuto).
MODES = {"off": 0, "timer": 1, "round": 2}
# The scenarios auto-play can pick, one id a line, in the instance's own game
# folder (fs_homepath/MBII) - read by the engine each time it picks.
POOL_FILE = "holotable_auto.txt"


def scenarios():
    """Every Holotable scenario in the game folder, by map then name:
    [{"id", "map", "name", "description"}, ...]."""
    folder = os.path.join(settings.locations.mbii_path, "holotable")
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for f in names:
        if not f.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, f), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            found.append({"id": f[:-5], "map": str(data.get("map", "") or ""),
                          "name": str(data.get("name") or f[:-5]),
                          "description": str(data.get("description", "") or "")})
    return sorted(found, key=lambda s: (s["map"].lower(), s["name"].lower()))


def auto_settings(cfg):
    """A holotable config block's auto-play settings, with their defaults."""
    cfg = cfg or {}
    mode = str(cfg.get("auto", "off")).lower()
    maps = cfg.get("maps") if isinstance(cfg.get("maps"), dict) else {}
    return {
        "mode": mode if mode in MODES else "off",
        "minutes": max(1, int(cfg.get("auto_minutes", 30) or 30)),
        "players": max(1, int(cfg.get("auto_players", 2) or 2)),
        "restart": 0 if str(cfg.get("auto_restart", 1)).lower() in ("0", "false", "") else 1,
        # map -> "all" (the default: new ones too) or the scenario ids ticked
        "maps": maps,
    }


def _map_pick(maps, map_name):
    for key, pick in maps.items():
        if key.lower() == map_name.lower():
            return pick
    return "all"


def allowed_ids(maps, all_scenarios):
    """The scenario ids auto-play may pick."""
    out = []
    for s in all_scenarios:
        pick = _map_pick(maps, s["map"])
        if pick == "all" or (isinstance(pick, list) and s["id"] in pick):
            out.append(s["id"])
    return out


def _config_path(instance_name):
    return os.path.join(settings.locations.config_path, "{}.json".format(instance_name))


def _read_config(instance_name):
    try:
        with open(_config_path(instance_name), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def apply(instance_name, cfg, set_cvar=None, pause=True):
    """Write the scenario pool for the engine and, given set_cvar(key, value),
    set the auto-play cvars (pause: they're going over rcon)."""
    auto = auto_settings(cfg)
    path = os.path.join(settings.locations.homepath_base, instance_name, "MBII", POOL_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# Holotable scenarios auto-play can pick (written by mbiiez's Holotable plugin)\n")
        for sid in allowed_ids(auto["maps"], scenarios()):
            f.write(sid + "\n")
    os.replace(tmp, path)
    if set_cvar:
        enabled = 0 if str(cfg.get("enabled", 1)).lower() in ("0", "false", "") else 1
        for key, value in (("g_holotable", "1" if enabled else "0"),
                           ("g_holotableAuto", str(MODES[auto["mode"]] if enabled else 0)),
                           ("g_holotableAutoMinutes", str(auto["minutes"])),
                           ("g_holotableAutoPlayers", str(auto["players"])),
                           ("g_holotableAutoRestart", str(auto["restart"]))):
            set_cvar(key, value)
            if pause:
                # The engine drops rcon past ~10 commands a second.
                time.sleep(0.25)


class plugin:

    plugin_name = "Holotable"
    plugin_author = "Louis Varley"
    plugin_url = "https://github.com/clone-army/holotable"
    plugin_requires = ["accounts"]
    plugin_engine = "caded"
    plugin_description = ("Holotable NPC scenarios for the map that's on: !ht lists them, admins !ht <n> play / !ht stop. "
                          "They can also play by themselves - at random every so often, or at the start of every round.")

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "Holotable",
                "path": [],
                "fields": [
                    {"path": ["enabled"], "key": "enabled", "type": "bool_select", "default": 1,
                     "label": "Allow Holotable Scenarios (!ht)",
                     "help": "Scenarios built on Holotable for the map that's on. Logged-in players can list them with !ht; "
                             "admins run one with !ht <n> play and end it with !ht stop. When they play by themselves, "
                             "and which ones, is set on this server's Holotable page."},
                ],
            },
        ]

    @staticmethod
    def web_menu(instance_name, instance_config):
        cfg = ((instance_config or {}).get("plugins", {}) or {}).get("holotable", {}) or {}
        if str(cfg.get("enabled", 1)).lower() in ("0", "false", ""):
            return None
        return {"label": "Holotable", "icon": "fa-chess-board", "slug": "holotable"}

    @staticmethod
    def web_page(instance_name, instance_config):
        cfg = ((instance_config or {}).get("plugins", {}) or {}).get("holotable", {}) or {}
        auto = auto_settings(cfg)
        found = scenarios()
        by_map = {}
        for s in found:
            by_map.setdefault(s["map"].lower(), []).append(s)

        def entry(map_name, in_rotation):
            pick = _map_pick(auto["maps"], map_name)
            return {"map": map_name, "in_rotation": in_rotation,
                    "scenarios": by_map.get(map_name.lower(), []),
                    "all": pick == "all",
                    "picked": pick if isinstance(pick, list) else []}

        rotation = [str(m) for m in (instance_config or {}).get("map_rotation_order", []) or [] if m]
        seen = set()
        maps = []
        for m in rotation:
            if m.lower() not in seen:
                seen.add(m.lower())
                maps.append(entry(m, True))
        others = []
        for s in found:
            if s["map"] and s["map"].lower() not in seen:
                seen.add(s["map"].lower())
                others.append(entry(s["map"], False))

        return [{
            "type": "template",
            "template": "page.html",
            "data": {
                "mode": auto["mode"], "minutes": auto["minutes"], "players": auto["players"],
                "restart": auto["restart"], "maps": maps, "others": others,
            },
        }]

    @staticmethod
    def web_action(instance_name, action_name, form_data):
        if action_name != "save":
            return False, "Unknown action."
        data = form_data or {}
        mode = str(data.get("mode", "off"))
        if mode not in MODES:
            return False, "Pick when scenarios play."
        try:
            minutes = max(1, min(1440, int(data.get("minutes", 30))))
            players = max(1, min(64, int(data.get("players", 2))))
        except (TypeError, ValueError):
            return False, "Minutes and players need to be numbers."
        known = {s["id"] for s in scenarios()}
        maps = {}
        for map_name, pick in (data.get("maps") or {}).items():
            map_name = str(map_name).strip()
            if not map_name:
                continue
            if pick == "all":
                maps[map_name] = "all"
            elif isinstance(pick, list):
                maps[map_name] = sorted({str(p) for p in pick if str(p) in known})

        config = _read_config(instance_name)
        if config is None:
            return False, "Couldn't read this server's config."
        cfg = config.setdefault("plugins", {}).setdefault("holotable", {})
        cfg["auto"] = mode
        cfg["auto_minutes"] = minutes
        cfg["auto_players"] = players
        cfg["auto_restart"] = 1 if str(data.get("restart", 1)).lower() not in ("0", "false", "") else 0
        cfg["maps"] = maps
        path = _config_path(instance_name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        os.replace(tmp, path)

        # Straight into the running server (the service re-applies it every minute anyway).
        try:
            from mbiiez.instance import instance as MBInstance
            inst = MBInstance(instance_name)
            apply(instance_name, cfg, lambda k, v: inst.cvar(k, v, True))
        except Exception:
            apply(instance_name, cfg)
        return True, "Saved - it's live on the server now."

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('holotable', {})
        self.enabled = int(self.config.get('enabled', 1))
        apply(self.instance.name, self.config, self.instance.register_startup_cvar, pause=False)

        auto = auto_settings(self.config)
        if self.enabled and auto["mode"] != "off" and self.instance.has_plugin("auto_message"):
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Holotable scenarios play on this server - log in and type ^7!ht ^5to see them."
            )

    def register(self):
        self.instance.process_handler.register_service("Holotable Service", self.holotable_service)

    # Kept set, in case something (a map's config, an admin) changes it - and
    # re-read from the config each time, so a change saved on the web panel
    # (or a new scenario on Holotable) is picked up without a restart.
    def holotable_service(self):
        time.sleep(15)

        while(True):
            try:
                config = _read_config(self.instance.name) or self.instance.config
                cfg = (config.get('plugins', {}) or {}).get('holotable', {}) or {}
                apply(self.instance.name, cfg, lambda k, v: self.instance.cvar(k, v, True))
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
