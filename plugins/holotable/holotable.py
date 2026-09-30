import time


class plugin:

    plugin_name = "Holotable"
    plugin_author = "Louis Varley"
    plugin_url = "https://github.com/clone-army/holotable"

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
                             "admins run one with !ht <n> play and end it with !ht stop."},
                ],
            },
        ]

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('holotable', {})
        self.enabled = int(self.config.get('enabled', 1))

        self.instance.register_startup_cvar("g_holotable", "1" if self.enabled else "0")

    def register(self):
        self.instance.process_handler.register_service("Holotable Service", self.holotable_service)

    # Kept set, in case something (a map's config, an admin) changes it.
    def holotable_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_holotable", "1" if self.enabled else "0")
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
