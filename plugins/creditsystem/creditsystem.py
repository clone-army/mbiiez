import time


class plugin:

    plugin_name = "Credit System"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance

        if(self.instance.has_plugin("auto_message")):
            self.instance.config['plugins']['auto_message']['messages'].append("Credit system is enabled on this server.")
            self.instance.config['plugins']['auto_message']['messages'].append("!balance - Shows your current credits and any bounty on you.")
            self.instance.config['plugins']['auto_message']['messages'].append("!buy - Lists available items or buys the selected one by ID.")
            self.instance.config['plugins']['auto_message']['messages'].append("!bounty - Places a credit bounty on another player.")

    def register(self):
        self.instance.process_handler.register_service("Credit System Service", self.credit_system_service)

    def credit_system_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_creditSystemEnable", "1")
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
