import os
import time

from mbiiez import settings


class plugin:

    plugin_name = "Stats"
    plugin_author = "Louis Varley"
    plugin_url = ""

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
    # Web UI extension hooks (see mbiiez/plugin_loader.py). Static/optional,
    # same contract as plugins/creditsystem/creditsystem.py.
    # ------------------------------------------------------------------

    @staticmethod
    def web_menu(instance_name, instance_config):
        plugin_cfg = (instance_config.get('plugins', {}) or {}).get('stats', {}) or {}
        if not int(plugin_cfg.get('enabled', 1)):
            return None

        return {"label": "Stats", "icon": "fa-chart-line", "slug": "stats"}

    @staticmethod
    def web_page(instance_name, instance_config):
        # Shared file written by the engine's native stats system - see
        # STATS_FILE in codemp/server/stats.cpp. One line per tracked
        # identity: "key|kills|deaths|suicides|playtimeSeconds". The key is
        # "h:<economyHandle>" if they were logged into an account at the
        # time (so it survives across sessions/servers), or "n:<name>" if
        # not (Stats_Key in stats.cpp) - that prefix is exactly "registered
        # or not", straight from the engine's own bookkeeping, not guessed.
        stats_path = os.path.join(settings.locations.mbii_path, "player_stats.dat")
        records = []

        if os.path.isfile(stats_path):
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
                            records.append(
                                {
                                    "name": name,
                                    "registered": registered,
                                    "kills": int(kills),
                                    "deaths": int(deaths),
                                    "suicides": int(suicides),
                                    "playtime": int(playtime),
                                }
                            )
                        except ValueError:
                            continue
            except Exception:
                records = []

        # Best-effort "last seen": mbiiez's own connection log tracks
        # in-game display name at connect time, not economy handle, so this
        # only lines up for an "n:"-keyed row, or an "h:"-keyed row whose
        # owner happens to play under a name matching their handle. Shown
        # as "-" rather than guessed when there's no match, not hidden.
        last_seen_by_name = {}
        try:
            from mbiiez.db import db

            conn = db().connect()
            cur = conn.cursor()
            cur.execute("SELECT player, MAX(added) AS last_seen FROM connections GROUP BY player")
            for row in cur.fetchall():
                player = row["player"]
                if player:
                    last_seen_by_name[player.strip().lower()] = row["last_seen"]
        except Exception:
            last_seen_by_name = {}

        records.sort(key=lambda r: r["kills"], reverse=True)

        def fmt_playtime(seconds):
            hours, minutes = divmod(seconds // 60, 60)
            return "{}h {}m".format(hours, minutes)

        rows = []
        for r in records:
            kd = (r["kills"] / r["deaths"]) if r["deaths"] > 0 else float(r["kills"])
            last_seen = last_seen_by_name.get(r["name"].strip().lower(), "-")
            rows.append(
                [
                    r["name"],
                    "Yes" if r["registered"] else ("No" if r["registered"] is False else "?"),
                    r["kills"],
                    r["deaths"],
                    r["suicides"],
                    "{:.2f}".format(kd),
                    fmt_playtime(r["playtime"]),
                    last_seen,
                ]
            )

        return [
            {
                "type": "table",
                "title": "Player Stats",
                "help": (
                    "Shared across every instance. \"Registered\" means they were logged into their "
                    "account (!login/!register) at the time these stats were recorded, so the row is "
                    "keyed by their account handle rather than whatever name they happened to be using. "
                    "\"Last Seen\" is a best-effort name match against connection logs and may show \"-\" "
                    "for a registered handle whose owner played under a different display name."
                ),
                "searchable": True,
                "columns": ["Name", "Registered", "Kills", "Deaths", "Suicides", "K/D", "Playtime", "Last Seen"],
                "rows": rows,
            }
        ]
