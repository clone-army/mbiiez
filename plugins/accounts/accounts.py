import datetime

from mbiiez import accounts_store
from mbiiez.economy_plugin import CvarPlugin


class plugin(CvarPlugin):

    plugin_name = "Accounts"
    plugin_description = ("Player accounts: !register and !login, shared by every server, and who's an admin. "
                          "Other plugins build on it (Credits, Holotable...). Adds the Accounts page: balances, admins, PINs.")
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
        admins = accounts_store.read_admins()
        rows = [{"handle": a["handle"], "credits": a["credits"], "admin": a["handle"].lower() in admins,
                 "status": accounts_store.locked_text(a)}
                for a in accounts_store.read_accounts()]
        return [{"type": "template", "template": "page.html", "data": {"rows": rows}}]

    @staticmethod
    def web_global_action(slug, action_name, form_data):
        form_data = form_data or {}
        if action_name == "set_admin":
            return accounts_store.set_admin(str(form_data.get("key", "")).strip(), str(form_data.get("on", "")) == "1")
        handle = str(form_data.get("handle", "")).strip()
        if action_name == "unlock":
            return accounts_store.unlock(handle)
        if action_name == "add_credits":
            try:
                amount = int(str(form_data.get("amount", "")).strip())
            except (TypeError, ValueError):
                return False, "The amount must be a whole number."
            if amount == 0:
                return False, "The amount can't be 0."
            return accounts_store.add_credits(handle, amount)
        if action_name == "set_pin":
            return accounts_store.set_pin(handle, form_data.get("pin", ""))
        if action_name == "delete":
            return accounts_store.delete_account(handle)
        return False, "Unknown action."
