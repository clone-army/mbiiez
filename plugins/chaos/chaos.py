import time


class plugin:

    plugin_name = "Chaos Mode"
    plugin_author = "Louis Varley"
    plugin_url = ""

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "Chaos Mode",
                "path": [],
                "fields": [
                    {"path": ["enabled"], "key": "enabled", "type": "bool_select", "default": 1,
                     "label": "Enable Chaos Mode"},
                    {"path": ["cooldown"], "key": "cooldown", "type": "number", "default": 20,
                     "label": "Cooldown (seconds)",
                     "depends_on": {"path": ["enabled"], "equals": 1}},
                ],
            },
        ]

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('chaos', {})
        self.enabled = int(self.config.get('enabled', 1))
        self.cooldown = int(self.config.get('cooldown', 20))

        # Register startup cvars to prevent leakage
        self.instance.register_startup_cvar("g_chaosEnable", "1" if self.enabled else "0")
        self.instance.register_startup_cvar("g_chaosCooldown", str(self.cooldown))

        if self.instance.has_plugin("auto_message") and self.enabled:
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Chaos Mode is enabled! Everyone gets a random weapon/gear prize "
                "every ^7{}^5 seconds - no need to earn it, just keep playing.".format(self.cooldown)
            )

    def register(self):
        self.instance.process_handler.register_service("Chaos Mode Service", self.chaos_service)

    def chaos_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_chaosEnable", "1" if self.enabled else "0")
                self.instance.cvar("g_chaosCooldown", str(self.cooldown))
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
