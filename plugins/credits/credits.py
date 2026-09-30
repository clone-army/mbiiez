from mbiiez import accounts_store
from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Credits"
    plugin_description = ("Players earn credits while logged in (kills, rounds, games), check them with !balance and "
                          "!gift them. What they spend them on are their own plugins: Shop, Bounties, Cantina Bar, "
                          "Jukebox, Casino. Adds the Credits page.")
    plugin_requires = ["accounts"]
    config_key = "credits"
    switches = {"g_creditSystemEnable": "1"}
    default_cvars = {
        'g_economyRegisterBonus': '100',
        'g_economyDailyBonus': '25',
    }
    section_hints = {'Credits': 'Earning and balances - balances are shared by every server, and managed on the Credits page.'}
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

    # --- The Credits page (balances are shared by every server) ---

    @staticmethod
    def web_global_menu():
        return [{"label": "Credits", "icon": "fa-coins", "slug": "credits"}]

    @staticmethod
    def web_global_page(slug):
        accounts = sorted(accounts_store.read_accounts(), key=lambda a: a["credits"], reverse=True)
        return [
            {
                "type": "table",
                "title": "Balances",
                "help": "Shared across every server. Click a row to fill in Give Credits below.",
                "searchable": True,
                "columns": ["Handle", "Credits"],
                "rows": [[a["handle"], a["credits"]] for a in accounts],
                "row_action": {"fill_form": "give_credits", "fill_field": "player", "value_column": 0},
            },
            {
                "type": "action_form",
                "title": "Give Credits",
                "help": ("Changes the account's stored balance (a negative amount takes credits away). A server where "
                         "they're logged in picks the change up within a few seconds."),
                "action": "give_credits",
                "submit_label": "Give Credits",
                "fields": [
                    {"name": "player", "label": "Handle (registered account)", "type": "text", "required": True},
                    {"name": "amount", "label": "Amount (+/-)", "type": "number", "required": True},
                ],
            },
        ]

    @staticmethod
    def web_global_action(slug, action_name, form_data):
        if action_name != "give_credits":
            return False, "Unknown action."
        form_data = form_data or {}
        handle = str(form_data.get("player", "")).strip()
        try:
            amount = int(str(form_data.get("amount", "")).strip())
        except (TypeError, ValueError):
            return False, "Amount must be a whole number."
        if amount == 0:
            return False, "Amount must be nonzero."
        return accounts_store.add_credits(handle, amount)
