import os
import re
import time

from mbiiez import settings


class plugin:

    plugin_name = "Stats"
    plugin_author = "Louis Varley"
    plugin_url = ""
    plugin_uses = ["accounts"]
    plugin_engine = "caded"
    plugin_description = "!stats and the Stats page. Tracks logged-in players by their account (Accounts), everyone else by name."

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('stats', {})
        self.enabled = int(self.config.get('enabled', 1))

        # !stats itself is now handled natively by the engine (kills/deaths/
        # suicides/playtime tracked in real time and shared across every
        # instance via a locked flat file - see stats.cpp) - this plugin's
        # only job is to control the g_statsEnable cvar the same way
        # chaos/gungame do for theirs.
        self.instance.register_startup_cvar("g_statsEnable", "1" if self.enabled else "0")

        if self.instance.has_plugin("auto_message") and self.enabled:
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5!stats ^7shows your kills, deaths, suicides and playtime across all CA servers - "
                "^5!login ^7first to make sure they're always kept."
            )

    def register(self):
        self.instance.process_handler.register_service("Stats Service", self.stats_service)

    def stats_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_statsEnable", "1" if self.enabled else "0")
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)

    # ------------------------------------------------------------------
    # Web UI: one Player Stats page for every server (the stats are shared),
    # in the main menu - see web_global_menu in PLUGINS.md.
    # ------------------------------------------------------------------

    @staticmethod
    def web_global_menu():
        return [{"label": "Player Stats", "icon": "fa-chart-line", "slug": "stats"}]

    @staticmethod
    def web_global_page(slug):
        # Shared file written by the engine's native stats system - see
        # STATS_FILE in codemp/server/stats.cpp. One line per tracked
        # identity: "key|kills|deaths|suicides|playtimeSeconds". The key is
        # "h:<economyHandle>" if they were logged into an account at the
        # time (so it survives across sessions/servers), or "n:<name>" if
        # not (Stats_Key in stats.cpp) - that prefix is exactly "registered
        # or not", straight from the engine's own bookkeeping, not guessed.
        stats_path = os.path.join(settings.locations.mbii_path, "player_stats.dat")
        records = []
        try:
            with open(stats_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.rstrip("\n").split("|")
                    if len(parts) != 5:
                        continue
                    key, kills, deaths, suicides, playtime = parts
                    if key.startswith("h:"):
                        registered, name = True, key[2:]
                    elif key.startswith("n:"):
                        registered, name = False, key[2:]
                    else:
                        registered, name = None, key
                    try:
                        records.append({"name": name, "registered": registered, "kills": int(kills),
                                        "deaths": int(deaths), "suicides": int(suicides), "playtime": int(playtime)})
                    except ValueError:
                        continue
        except OSError:
            records = []

        # Best-effort "last seen": mbiiez's connection log has the in-game
        # name at connect time (with some colour codes, not all), not the
        # account handle - so it's matched with every code stripped from
        # both, and lines up for a name-keyed row or a handle its owner also
        # plays under. Empty when there's no match, not guessed.
        last_seen = {}
        try:
            from mbiiez.db import db

            conn = db().connect()
            cur = conn.cursor()
            cur.execute("SELECT player, MAX(added) AS last_seen FROM connections GROUP BY player")
            for row in cur.fetchall():
                if row["player"]:
                    key = _plain(row["player"]).lower()
                    if row["last_seen"] > last_seen.get(key, ""):
                        last_seen[key] = row["last_seen"]
        except Exception:
            last_seen = {}

        rows = []
        for r in records:
            seen = last_seen.get(_plain(r["name"]).lower(), "")
            rows.append(dict(r, plain=_plain(r["name"]), seen=seen[:16]))
        return [{"type": "template", "template": "page.html", "data": {"rows": rows}}]


def _plain(name):
    """A name without its ^ colour codes."""
    return re.sub(r"\^[0-9]", "", str(name or "")).strip()
