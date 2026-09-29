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
                    {"path": ["barfight"], "key": "barfight", "type": "bool_select", "default": 0,
                     "label": "Bar Fights (!barfight)"},
                    {"path": ["barfight_spawn"], "key": "barfight_spawn", "type": "text", "default": "",
                     "label": "Bar Fight Spawn Point (x y z yaw, on the floor)"},
                    {"path": ["barfight_rally"], "key": "barfight_rally", "type": "text", "default": "",
                     "label": "Bar Fight Rally Point (x y z yaw - where they head first)"},
                    {"path": ["npcs"], "key": "npcs", "type": "text", "default": "",
                     "label": "NPCs on the Map (type x y z yaw pose; separate several with ;)",
                     "help": "e.g. bartender 4008 -550 -1769 169 bartend. Pose: sit, idle, bartend, roam, or none. /viewpos on the spot gives x y z (take ~30 off z) and the facing."},
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
        self.barfight = 1 if str(self.config.get('barfight', 0)) not in ("0", "False", "false", "") else 0
        self.barfight_spawn = str(self.config.get('barfight_spawn', '') or '').replace('"', '')
        self.barfight_rally = str(self.config.get('barfight_rally', '') or '').replace('"', '')

        self.instance.register_startup_cvar("g_socialMode", "1" if self.enabled else "0")
        self.instance.register_startup_cvar("g_socialRespawnTime", str(self.respawn_seconds))
        self.instance.register_startup_cvar("g_socialDuels", "1" if self.duels else "0")
        self.instance.register_startup_cvar("g_socialRoundTime", str(self.round_seconds))
        # Not a startup cvar: its value has spaces, which break the launch
        # command line (quoted inside screen's bash -c "..."). Set over rcon
        # by the service below instead.
        self.instance.register_startup_cvar("g_socialAutoSpawn", str(self.auto_spawn))
        self.instance.register_startup_cvar("g_barFightEnable", str(self.barfight))

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

    def _npc_chunks(self):
        """The NPC list split over the four g_socialNpcs cvars (255
        characters each), at ';' boundaries; always four entries."""
        chunks, current = [], ""
        for entry in [e.strip() for e in self.npcs.replace('"', '').split(";") if e.strip()]:
            if current and len(current) + 1 + len(entry) > 240:
                chunks.append(current)
                current = entry
            else:
                current = entry if not current else current + ";" + entry
        if current:
            chunks.append(current)
        return (chunks + ["", "", "", ""])[:4]

    def register(self):
        self.instance.process_handler.register_service("Social Mode Service", self.social_service)

    def social_service(self):
        time.sleep(15)

        while(True):
            try:
                # Spaced out: the engine takes about 10 rcon commands a second
                # from one address and silently drops the rest, which lost
                # the later settings in this batch.
                for key, value in (("g_socialMode", "1" if self.enabled else "0"),
                                   ("g_socialRespawnTime", str(self.respawn_seconds)),
                                   ("g_socialDuels", "1" if self.duels else "0"),
                                   ("g_socialRoundTime", str(self.round_seconds)),
                                   ("g_socialAutoSpawn", str(self.auto_spawn)),
                                   ("g_barFightEnable", str(self.barfight))):
                    self.instance.cvar(key, value)
                    time.sleep(0.25)
                # These have spaces: rcon only, never startup cvars (they'd
                # break the launch command line).
                for name, part in zip(("g_socialNpcs", "g_socialNpcs2", "g_socialNpcs3", "g_socialNpcs4"), self._npc_chunks()):
                    self.instance.console.rcon('set {} "{}"'.format(name, part), True)
                    time.sleep(0.25)
                self.instance.console.rcon('set g_barFightSpawn "{}"'.format(self.barfight_spawn), True)
                time.sleep(0.25)
                self.instance.console.rcon('set g_barFightRally "{}"'.format(self.barfight_rally), True)
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
