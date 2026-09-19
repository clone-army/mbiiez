import time


class plugin:

    plugin_name = "Kill Streaks"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('killstreak', {})
        self.enabled = int(self.config.get('enabled', 1))

        self.instance.register_startup_cvar("g_killstreakEnable", "1" if self.enabled else "0")

        if self.instance.has_plugin("auto_message") and self.enabled:
            self.instance.config['plugins']['auto_message']['messages'].append(
                "^5Kill streaks are on! String kills together without dying "
                "for escalating server-wide callouts - resets each round."
            )

    def register(self):
        self.instance.process_handler.register_service("Kill Streaks Service", self.killstreak_service)

    def killstreak_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_killstreakEnable", "1" if self.enabled else "0")
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
