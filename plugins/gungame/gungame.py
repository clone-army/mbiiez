import time


class plugin:

    plugin_name = "Gun Game"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        game_config = self.instance.config.get('game', {})
        self.gungame_enabled = int(game_config.get('gungame_enable', 0))
        self.gungame_announce = int(game_config.get('gungame_announce', 1))
        # "Solder" and "Trooper" are two separate internal class IDs that both
        # happen to display as "Soldier" in the MBII UI - one is Team I's
        # basic infantry class, the other Team R's (see mb_ingame_join_open_
        # classes_i/r.menu). They have to both be opened together, or
        # whichever team's basic class isn't listed here gets zero classes
        # to pick from at all.
        self.gungame_restrict_classes = game_config.get('gungame_restrict_classes', ['Solder', 'Trooper'])

        # Gun Game is only fair if every player starts from the exact same
        # loadout - otherwise class picks (jetpack, saber, force powers...)
        # stack on top of the weapon ladder as an extra advantage. Rather
        # than hand-edit each instance's own "class_limits" block, this
        # drives the live g_classlimits cvar directly: reads the instance's
        # configured class order/limits as the "normal" baseline, and builds
        # a second string that zeroes every class except the ones in
        # gungame_restrict_classes while Gun Game is on. Whichever applies is
        # re-asserted every tick, same as g_gungame/g_gungameAnnounce below,
        # so it self-heals if something else changes it and always reverts
        # to normal the moment gungame_enable goes back to 0.
        self.class_order = list(self.instance.config.get('class_limits', {}).keys())
        self.normal_classlimits = self._build_classlimits_string(self.instance.config.get('class_limits', {}))
        self.restricted_classlimits = self._build_classlimits_string({
            name: (50 if name in self.gungame_restrict_classes else 0) for name in self.class_order
        })

        if(self.instance.has_plugin("auto_message")):
            self.instance.config['plugins']['auto_message']['messages'].append("Gun Game is {} for this server.".format("enabled" if self.gungame_enabled else "disabled"))

    def _build_classlimits_string(self, limits):
        parts = []
        for name in self.class_order:
            limit = int(limits.get(name, 0))
            parts.append("{:02d}".format(limit) if limit < 10 else str(limit))
        return "-".join(parts)

    def register(self):
        self.instance.process_handler.register_service("Gun Game Service", self.gungame_service)

    def gungame_service(self):
        time.sleep(15)

        while(True):
            try:
                self.instance.cvar("g_gungame", str(self.gungame_enabled))
                self.instance.cvar("g_gungameAnnounce", str(self.gungame_announce))

                if(self.class_order):
                    if(self.gungame_enabled):
                        self.instance.cvar("g_classlimits", self.restricted_classlimits)
                    else:
                        self.instance.cvar("g_classlimits", self.normal_classlimits)
            except Exception as e:
                self.instance.exception_handler.log(e)

            time.sleep(60)
