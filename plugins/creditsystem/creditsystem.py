import time


class plugin:

    plugin_name = "Credit System"
    plugin_author = "Louis Varley"
    plugin_url = ""

    # Default shop costs sourced from clone-army/OpenJK README.
    # Any of these (and g_creditSystemEnable) can be overridden via the
    # instance JSON plugin config's "cvars" section.
    default_cvars = {
        "g_creditSystemEnable": "1",
        # Pistols
        "g_shopCost_bryar": "8",
        "g_shopCost_clone_pistol": "8",
        "g_shopCost_bryar_old": "8",
        "g_shopCost_mando_pistol": "10",
        "g_shopCost_heavy_pistol": "10",
        "g_shopCost_ee3": "10",
        # Rifles
        "g_shopCost_blaster": "12",
        "g_shopCost_dc_carbine": "15",
        "g_shopCost_cr2": "15",
        "g_shopCost_e22": "15",
        "g_shopCost_trad_bowcaster": "15",
        "g_shopCost_t21": "15",
        "g_shopCost_dlt19": "18",
        "g_shopCost_clone_rifle": "18",
        "g_shopCost_a280": "18",
        "g_shopCost_dlt20a": "18",
        "g_shopCost_m5": "18",
        "g_shopCost_ee4": "18",
        "g_shopCost_bowcaster": "20",
        "g_shopCost_repeater": "20",
        "g_shopCost_sbd": "20",
        "g_shopCost_disruptor": "22",
        "g_shopCost_proj": "22",
        "g_shopCost_amban": "25",
        # Special
        "g_shopCost_shotgun": "18",
        "g_shopCost_thrower": "20",
        "g_shopCost_flechette": "22",
        "g_shopCost_concussion": "22",
        "g_shopCost_minigun": "30",
        # Launchers
        "g_shopCost_rocket_launcher": "35",
        "g_shopCost_plx1": "35",
        # Grenades / explosives
        "g_shopCost_frag_nade": "8",
        "g_shopCost_pulse_nade": "8",
        "g_shopCost_thermal": "10",
        "g_shopCost_real_td": "10",
        "g_shopCost_fire_nade": "10",
        "g_shopCost_sonic_nade": "10",
        "g_shopCost_cryo_nade": "10",
        "g_shopCost_conc_nade": "10",
        "g_shopCost_trip_mine": "12",
        "g_shopCost_det_pack": "15",
        # Melee
        "g_shopCost_saber": "30",
        # Gadgets
        "g_shopCost_bacta": "5",
        "g_shopCost_stimpack": "8",
        "g_shopCost_100_armor": "10",
        "g_shopCost_seeker": "10",
        "g_shopCost_sentry": "15",
        "g_shopCost_protocol": "15",
        "g_shopCost_250_armor": "20",
        "g_shopCost_cloak": "20",
        "g_shopCost_forcefield": "20",
        "g_shopCost_shockfield": "20",
        "g_shopCost_jetpack": "22",
        "g_shopCost_eweb": "25",
        "g_shopCost_spawner": "25",
        # Size changes
        "g_shopCost_size_s": "8",
        "g_shopCost_size_xs": "10",
        "g_shopCost_size_l": "12",
        "g_shopCost_size_xl": "18",
        # Ammo
        "g_shopCost_ammo": "6",
    }

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('creditsystem', {})

        # Start from defaults, then apply any per-instance overrides from the
        # plugin's "cvars" JSON config key.
        cvars = dict(self.default_cvars)
        cvars.update(self.config.get('cvars', {}))
        for key, value in cvars.items():
            self.instance.register_plugin_cvar(key, value)

        if self.instance.has_plugin("auto_message"):
            msgs = self.instance.config['plugins']['auto_message']['messages']
            msgs.append("^5Credit system is enabled! Earn credits from kills.")
            msgs.append("^7!balance ^5- Shows your credits and any active bounty.")
            msgs.append("^7!buy ^5- Lists shop items or buys one by ID.")
            msgs.append("^7!bounty <player> <amount> ^5- Place a bounty on a player.")

    def register(self):
        self.instance.process_handler.register_service("Credit System Service", self._enforce_service)

    def _enforce_service(self):
        time.sleep(15)
        while True:
            try:
                self.instance.cvar("g_creditSystemEnable", "1")
            except Exception as e:
                self.instance.exception_handler.log(e)
            time.sleep(60)
