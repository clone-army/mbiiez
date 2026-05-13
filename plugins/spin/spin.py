import time


class plugin:

    plugin_name = "Spin Mode"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        game_config = self.instance.config.get('game', {})
        self.spin_enabled = int(game_config.get('spin_enable', 1))
        self.spin_cooldown = int(game_config.get('spin_cooldown', 20))

        if(self.instance.has_plugin("auto_message")):
            self.instance.config['plugins']['auto_message']['messages'].append("Spin mode is {} for this server.".format("enabled" if self.spin_enabled else "disabled"))
            self.instance.config['plugins']['auto_message']['messages'].append("Spin cooldown is set to {} seconds.".format(self.spin_cooldown))

    def register(self):
        self.instance.process_handler.register_service("Spin Mode Service", self.spin_service)

    def spin_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_spin", str(self.spin_enabled))
                self.instance.cvar("g_spinCooldown", str(self.spin_cooldown))
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
