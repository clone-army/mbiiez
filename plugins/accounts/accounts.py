import datetime

from mbiiez import accounts_store
from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Accounts"
    plugin_description = ("Player accounts: !register and !login, shared by every server, and who's an admin. "
                          "Other plugins build on it (Credits, Holotable...). Adds the Accounts page.")
    config_key = "accounts"
    switches = {"g_accountsEnable": "1"}
    default_cvars = {"g_economyLoginReminder": "0"}
    section_hints = {'Accounts': 'Logins for every server - accounts are shared, and managed on the Accounts page.'}
    sections = [
        ("Accounts", [
            ("g_economyLoginReminder", "number", "Remind Players Who Haven't Logged In After (seconds, 0 = off)",
             'Anyone still not logged in this long after joining gets a chat message telling them how to register or log in. A big centre-screen reminder also shows when they first spawn.'),
        ]),
    ]

    def announce(self):
        # With Credits on, its own lines say how to register (and why).
        if self.instance.has_plugin("credits"):
            return []
        return ["^7!register <handle> <pin> ^5makes an account, ^7!login <handle> <pin> ^5logs back in - "
                "one account for all our servers."]

    # --- The Accounts page (outside any instance: accounts are shared) ---

    @staticmethod
    def web_global_menu():
        return [{"label": "Accounts", "icon": "fa-id-card", "slug": "accounts"}]

    @staticmethod
    def web_global_page(slug):
        accounts = sorted(accounts_store.read_accounts(), key=lambda a: a["handle"].lower())
        admins = accounts_store.read_admins()
        return [
            {
                "type": "table",
                "title": "Accounts",
                "help": ("Every player account, shared by all servers (one file in the game folder). Admin: can run "
                         "!barfight, record NPC routes (!wp) and play Holotable scenarios (!ht) while logged in - "
                         "takes effect within seconds, everywhere. PINs are never shown. Click a row to fill in the "
                         "forms below."),
                "searchable": True,
                "columns": ["Handle", "Admin", "Status"],
                "rows": [[a["handle"],
                          {"toggle": {"action": "set_admin", "key": a["handle"], "checked": a["handle"].lower() in admins,
                                      "title": "Admin on every server"}},
                          accounts_store.locked_text(a)]
                         for a in accounts],
                "row_action": {"fill_form": "unlock", "fill_field": "handle", "value_column": 0},
            },
            {
                "type": "action_form",
                "title": "Unlock an Account",
                "help": "Too many wrong PINs lock an account for a while (longer each time). This clears that.",
                "action": "unlock",
                "submit_label": "Unlock",
                "fields": [{"name": "handle", "label": "Handle", "type": "text", "required": True}],
            },
        ]

    @staticmethod
    def web_global_action(slug, action_name, form_data):
        form_data = form_data or {}
        if action_name == "set_admin":
            return accounts_store.set_admin(str(form_data.get("key", "")).strip(), str(form_data.get("on", "")) == "1")
        if action_name == "unlock":
            return accounts_store.unlock(str(form_data.get("handle", "")).strip())
        return False, "Unknown action."
