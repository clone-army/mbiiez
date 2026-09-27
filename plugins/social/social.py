import time


class plugin:

    plugin_name = "Social Mode"
    plugin_author = "Louis Varley"
    plugin_url = ""

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "Social Mode",
                "path": [],
                "fields": [
                    {"path": ["enabled"], "key": "enabled", "type": "bool_select", "default": 1,
                     "label": "Enable Social Mode (no damage, spawn any time)"},
                    {"path": ["respawn_seconds"], "key": "respawn_seconds", "type": "number", "default": 3,
                     "label": "Respawn Wait (seconds)"},
                    {"path": ["duels"], "key": "duels", "type": "bool_select", "default": 1,
                     "label": "Duels (bow at someone to challenge)"},
                    {"path": ["round_minutes"], "key": "round_minutes", "type": "number", "default": 0,
                     "label": "Round Length (minutes, 0 = map default)"},
                    {"path": ["bots"], "key": "bots", "type": "bool_select", "default": 0,
                     "label": "Bots Pick Legends Classes (works with social mode off too)"},
                ],
            },
        ]

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('social', {})
        self.enabled = int(self.config.get('enabled', 1))
        self.respawn_seconds = max(1, int(self.config.get('respawn_seconds', 3)))
        self.duels = int(self.config.get('duels', 1))
        self.round_seconds = max(0, int(self.config.get('round_minutes', 0))) * 60
        self.bots = int(self.config.get('bots', 0))

        self.instance.register_startup_cvar("g_socialMode", "1" if self.enabled else "0")
        self.instance.register_startup_cvar("g_socialRespawnTime", str(self.respawn_seconds))
        self.instance.register_startup_cvar("g_socialDuels", "1" if self.duels else "0")
        self.instance.register_startup_cvar("g_socialRoundTime", str(self.round_seconds))
        self.instance.register_startup_cvar("g_socialBots", "1" if self.bots else "0")

        if self.instance.has_plugin("auto_message") and self.enabled:
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Social mode is on! Nobody can take damage and you can spawn in any time."
            )
            if self.duels:
                self.instance.config['plugins']['auto_message']['messages'].append(
                    "^5Want a real fight? Bow at someone to challenge them to a duel - they bow back to accept."
                )

    def register(self):
        self.instance.process_handler.register_service("Social Mode Service", self.social_service)

    def social_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_socialMode", "1" if self.enabled else "0")
                self.instance.cvar("g_socialRespawnTime", str(self.respawn_seconds))
                self.instance.cvar("g_socialDuels", "1" if self.duels else "0")
                self.instance.cvar("g_socialRoundTime", str(self.round_seconds))
                self.instance.cvar("g_socialBots", "1" if self.bots else "0")
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
