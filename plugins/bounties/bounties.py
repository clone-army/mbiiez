from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Bounties"
    plugin_description = "!bounty - put credits on someone's head; whoever kills them collects."
    plugin_requires = ["credits"]
    config_key = "bounties"
    switches = {"g_economyBountyEnable": "1"}

    def announce(self):
        return ["^5Put a price on someone's head: ^7!bounty <player> <credits> ^5- whoever kills them collects it."]
