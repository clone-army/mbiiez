import time


class plugin:

    plugin_name = "Spectator Kick"
    plugin_author = "Louis Varley"
    plugin_url = ""
    plugin_engine = "caded"
    plugin_description = "Removes players who sit in spectator round after round, freeing the slot - warned the round before. Admins and bots are left alone."

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "Spectator Kick",
                "path": [],
                "fields": [
                    {"path": ["rounds"], "key": "rounds", "type": "number", "default": 3,
                     "label": "Remove After This Many Rounds In Spectator (0 = off)",
                     "help": "Counted at the start of each round; joining a team resets it. They're warned the round before. Logged-in admins and bots are never removed."},
                ],
            },
        ]

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config["plugins"].get("spectator_kick", {})
        self.rounds = max(0, int(self.config.get("rounds", 3) or 0))
        self.instance.register_startup_cvar("g_specKickRounds", str(self.rounds))

    def register(self):
        self.instance.process_handler.register_service("Spectator Kick Service", self.service)

    def service(self):
        # Kept applied, as the other caded plugins do.
        time.sleep(15)
        while True:
            try:
                self.instance.cvar("g_specKickRounds", str(self.rounds))
            except Exception as e:
                self.instance.exception_handler.log(e)
            time.sleep(60)
