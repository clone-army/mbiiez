from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Credits"
    plugin_description = ("Players earn credits while logged in (kills, rounds, games), check them with !balance and "
                          "!gift them. What they spend them on are their own plugins: Shop, Bounties, Cantina Bar, "
                          "Jukebox, Casino. Balances are on the Accounts page.")
    plugin_requires = ["accounts"]
    config_key = "credits"
    switches = {"g_creditSystemEnable": "1"}
    default_cvars = {
        'g_economyRegisterBonus': '100',
        'g_economyDailyBonus': '25',
    }
    section_hints = {'Credits': 'Earning and balances - balances are shared by every server, and managed on the Accounts page.'}
    sections = [
        ("Credits", [
            ("g_economyRegisterBonus", "number", "Welcome Bonus for Registering (credits)",
             'Credits a new account starts with when a player registers.'),
            ("g_economyDailyBonus", "number", "Daily Login Bonus (credits, first !login in 24h on any server; 0 = off)",
             "Paid on a player's first login each day - once a day across all servers, not per server."),
        ]),
    ]

    def announce(self):
        # Line 2 leads with !register/!login: credits are only earned while
        # logged in, so a player who never sees it could play all game and
        # wonder why their balance stayed at 0.
        return [
            "^5Credits are enabled! Earn them while logged in - from kills, rounds and games - and spend them on any of our servers.",
            "^7!register <handle> <pin> ^5(new - free welcome credits!) or ^7!login <handle> <pin> ^5(returning - daily bonus!) to get started.",
            "^7!balance ^5to check your credits, ^7!gift <player> <credits> ^5to give some to a friend.",
        ]
