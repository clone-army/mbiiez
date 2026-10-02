from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Shop"
    plugin_description = "!buy - weapons, gadgets, size changes and ammo for credits."
    plugin_requires = ["credits"]
    config_key = "shop"
    switches = {"g_economyShopEnable": "1"}
    default_cvars = {
        'g_shopCost_bryar': '8',
        'g_shopCost_clone_pistol': '8',
        'g_shopCost_bryar_old': '8',
        'g_shopCost_mando_pistol': '10',
        'g_shopCost_heavy_pistol': '10',
        'g_shopCost_ee3': '10',
        'g_shopCost_blaster': '12',
        'g_shopCost_dc_carbine': '15',
        'g_shopCost_cr2': '15',
        'g_shopCost_e22': '15',
        'g_shopCost_trad_bowcaster': '15',
        'g_shopCost_t21': '15',
        'g_shopCost_dlt19': '18',
        'g_shopCost_clone_rifle': '18',
        'g_shopCost_a280': '18',
        'g_shopCost_dlt20a': '18',
        'g_shopCost_m5': '18',
        'g_shopCost_ee4': '18',
        'g_shopCost_bowcaster': '20',
        'g_shopCost_repeater': '20',
        'g_shopCost_sbd': '20',
        'g_shopCost_disruptor': '22',
        'g_shopCost_proj': '22',
        'g_shopCost_amban': '25',
        'g_shopCost_shotgun': '18',
        'g_shopCost_thrower': '20',
        'g_shopCost_flechette': '22',
        'g_shopCost_concussion': '22',
        'g_shopCost_minigun': '30',
        'g_shopCost_rocket_launcher': '35',
        'g_shopCost_plx1': '35',
        'g_shopCost_frag_nade': '8',
        'g_shopCost_pulse_nade': '8',
        'g_shopCost_thermal': '10',
        'g_shopCost_real_td': '10',
        'g_shopCost_fire_nade': '10',
        'g_shopCost_sonic_nade': '10',
        'g_shopCost_cryo_nade': '10',
        'g_shopCost_conc_nade': '10',
        'g_shopCost_trip_mine': '12',
        'g_shopCost_det_pack': '15',
        'g_shopCost_saber': '30',
        'g_shopCost_bacta': '5',
        'g_shopCost_stimpack': '8',
        'g_shopCost_100_armor': '10',
        'g_shopCost_seeker': '10',
        'g_shopCost_sentry': '15',
        'g_shopCost_protocol': '15',
        'g_shopCost_250_armor': '20',
        'g_shopCost_cloak': '20',
        'g_shopCost_forcefield': '20',
        'g_shopCost_shockfield': '20',
        'g_shopCost_jetpack': '22',
        'g_shopCost_eweb': '25',
        'g_shopCost_spawner': '25',
        'g_shopCost_size_s': '8',
        'g_shopCost_size_xs': '10',
        'g_shopCost_size_l': '12',
        'g_shopCost_size_xl': '18',
        'g_shopCost_ammo': '6',
    }
    section_hints = {"Shop Prices": "What each item costs in !buy - 0 takes it out of the shop."}
    sections = [
        ("Shop Prices", [(key, "number", key[len("g_shopCost_"):].replace("_", " ").title() + " (credits, 0 = not sold)")
                         for key in default_cvars]),
    ]

    def announce(self):
        return ["^5Spend credits on gear: ^7!buy ^5lists the shop, ^7!buy <item> ^5buys it."]
