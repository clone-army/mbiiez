import time


class plugin:

    plugin_name = "Chaos Mode"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('chaos', {})
        self.cooldown = int(self.config.get('cooldown', 20))

        self.instance.cvar("g_chaosEnable", "1")
        self.instance.cvar("g_chaosCooldown", str(self.cooldown))

    def register(self):
        self.instance.process_handler.register_service("Chaos Mode Service", self.chaos_service)

    def chaos_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_chaosEnable", "1")
                self.instance.cvar("g_chaosCooldown", str(self.cooldown))
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
