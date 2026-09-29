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
                    {"path": ["auto_spawn_seconds"], "key": "auto_spawn_seconds", "type": "number", "default": 15,
                     "label": "Put Joiners In Automatically After (seconds, 0 = off)",
                     "help": "Anyone not in the game this long after joining is spawned as !spawn would. Not people who chose to spectate."},
                    {"path": ["npcs"], "key": "npcs", "type": "text", "default": "",
                     "label": "NPCs on the Map (type x y z yaw; separate several with ;)",
                     "help": "e.g. bartender 4008 -550 -1769 169. Stand on the spot and type /viewpos for x y z (take 36 off z) and the facing."},
                    {"path": ["cvars", "g_inactivitySpec"], "key": "g_inactivitySpec", "type": "number", "default": 0,
                     "label": "Move Idle Players to Spectator After (seconds, 0 = never)",
                     "help": "MBII's g_inactivitySpec. Social servers usually leave it at 0 so people can sit and chat."},
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
        self.npcs = str(self.config.get('npcs', '') or '')
        self.auto_spawn = max(0, int(self.config.get('auto_spawn_seconds', 15)))

        self.instance.register_startup_cvar("g_socialMode", "1" if self.enabled else "0")
        self.instance.register_startup_cvar("g_socialRespawnTime", str(self.respawn_seconds))
        self.instance.register_startup_cvar("g_socialDuels", "1" if self.duels else "0")
        self.instance.register_startup_cvar("g_socialRoundTime", str(self.round_seconds))
        # Not a startup cvar: its value has spaces, which break the launch
        # command line (quoted inside screen's bash -c "..."). Set over rcon
        # by the service below instead.
        self.instance.register_startup_cvar("g_socialAutoSpawn", str(self.auto_spawn))

        if self.instance.has_plugin("auto_message") and self.enabled:
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5This is a ^7Social ^5server - nobody can take damage outside a duel, and you can spawn in any time. Just hang out!"
            )
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^7!emotes ^5- sit at the bar with ^7!sit^5, ^7!dance^5, ^7!hug^5, ^7!sleep^5, ^7!taunt ^5and more."
            )
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Type ^7!help ^5for every command on this server."
            )
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Stuck in spectator? Type ^7!spawn ^5and we'll get you in. ^7!kill ^5to respawn."
            )
            if self.duels:
                self.instance.config['plugins']['auto_message']['messages'].append(
                    "^5Fancy a fight? Face any player and bow (^7K^5). If they bow back, it's a duel to the death - any class, any weapon."
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
                # rcon directly: instance.cvar() would also make it a startup cvar.
                self.instance.console.rcon('set g_socialNpcs "{}"'.format(self.npcs.replace('"', '')), True)
                self.instance.cvar("g_socialAutoSpawn", str(self.auto_spawn))
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
