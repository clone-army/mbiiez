import os
import time

from mbiiez import settings


class plugin:

    plugin_name = "Credit System"
    plugin_author = "Louis Varley"
    plugin_url = ""

    # Default shop costs sourced from clone-army/OpenJK README.
    # Any of these (and g_creditSystemEnable / g_economyShopEnable /
    # g_economyBountyEnable) can be overridden via the instance JSON plugin
    # config's "cvars" section.
    #
    # Three independent switches:
    #   g_creditSystemEnable  - master: kill rewards, accounts, !balance
    #   g_economyShopEnable   - !buy (requires the master switch too)
    #   g_economyBountyEnable - !bounty / !<n> <credits> (requires the master switch too)
    default_cvars = {
        "g_creditSystemEnable": "1",
        "g_economyShopEnable": "0",
        "g_economyBountyEnable": "0",
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

        self.economy_enabled = cvars.get("g_creditSystemEnable") == "1"
        self.shop_enabled = cvars.get("g_economyShopEnable") == "1"
        self.bounty_enabled = cvars.get("g_economyBountyEnable") == "1"

        if self.instance.has_plugin("auto_message") and self.economy_enabled:
            msgs = self.instance.config['plugins']['auto_message']['messages']
            msgs.extend(self._build_announce_messages())

    def _build_announce_messages(self):
        # auto_message broadcasts each list entry as its own standalone line
        # (no pacing/multi-line support the way the in-game "!buy" listing
        # has), so this is a short sequence of short lines rather than one
        # long one that would get cut off the same way the shop used to.
        #
        # Line 2 always leads with !register/!login: credits are only ever
        # earned while logged in (see SV_EconomyFrame's kill-reward gate),
        # so a player who never sees this line could rack up kills all game
        # and wonder why their balance stayed at 0.
        messages = [
            "^5Credits are enabled on this server! Earn credits from kills - but only while logged in.",
            "^7!register <handle> <pin> ^5(new) or ^7!login <handle> <pin> ^5(returning) to get started.",
        ]

        balanceLine = "^7!balance ^5to check your credits"
        if self.shop_enabled and self.bounty_enabled:
            messages.append(balanceLine + ", ^7!buy ^5to shop for gear, ^7!bounty ^5to put a price on someone's head.")
        elif self.shop_enabled:
            messages.append(balanceLine + ", ^7!buy ^5to shop for gear.")
        elif self.bounty_enabled:
            messages.append(balanceLine + ", ^7!bounty ^5to put a price on someone's head - whoever kills them collects it.")
        else:
            messages.append(balanceLine + ".")

        return messages

    def register(self):
        self.instance.process_handler.register_service("Credit System Service", self._enforce_service)

    def _enforce_service(self):
        time.sleep(15)
        while True:
            try:
                self.instance.cvar("g_creditSystemEnable", "1" if self.economy_enabled else "0")
                self.instance.cvar("g_economyShopEnable", "1" if self.shop_enabled else "0")
                self.instance.cvar("g_economyBountyEnable", "1" if self.bounty_enabled else "0")
            except Exception as e:
                self.instance.exception_handler.log(e)
            time.sleep(60)

    # ------------------------------------------------------------------
    # Web UI extension hooks (see mbiiez/plugin_loader.py for how these are
    # discovered/called). All three are optional and static - the web UI
    # never constructs a real running `instance` just to list/describe a
    # plugin, only the running game engine does that.
    # ------------------------------------------------------------------

    @staticmethod
    def web_menu(instance_name, instance_config):
        plugin_cfg = (instance_config.get('plugins', {}) or {}).get('creditsystem', {}) or {}
        cvars = dict(plugin.default_cvars)
        cvars.update(plugin_cfg.get('cvars', {}))

        if cvars.get("g_creditSystemEnable") != "1":
            return None

        return {"label": "Economy", "icon": "fa-coins", "slug": "economy"}

    @staticmethod
    def web_page(instance_name, instance_config):
        # Accounts are stored in one file shared by every instance (fs_basepath/
        # fs_game is the same "/opt/openjk/MBII" for all of them) - see
        # SV_EconomyAccountsPath/SV_EconomyAccountsLoad in
        # codemp/server/sv_client.cpp. Line format confirmed there:
        # "handle saltHex hashHex credits failedAttempts lockoutUntil".
        # Only handle + credits are ever shown - the salt/hash columns are
        # password material and must never be rendered.
        accounts_path = os.path.join(settings.locations.mbii_path, "economy_accounts.dat")
        rows = []

        if os.path.isfile(accounts_path):
            try:
                with open(accounts_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.split()
                        if len(parts) != 6:
                            continue
                        handle, _salt_hex, _hash_hex, credits_str, _failed, _lockout = parts
                        try:
                            rows.append((handle, int(credits_str)))
                        except ValueError:
                            continue
            except Exception:
                rows = []

        rows.sort(key=lambda r: r[1], reverse=True)

        return [
            {
                "type": "table",
                "title": "Registered Accounts",
                "help": "Shared across every instance on this box - accounts and balances aren't per-server. Click a row to fill in the Give Credits form below.",
                "searchable": True,
                "columns": ["Handle", "Credits"],
                "rows": [[handle, credits] for handle, credits in rows],
                "row_action": {"fill_form": "give_credits", "fill_field": "player", "value_column": 0},
            },
            {
                "type": "action_form",
                "title": "Give Credits",
                "help": (
                    "Edits the registered account's stored balance directly (by handle, not in-game "
                    "name - the engine's own 'givecredits' RCON command matches connected players by "
                    "display name, which has no reliable link to the account handle actually holding "
                    "the credits, and silently fails to persist for anyone not currently logged in). "
                    "Caveat: if this handle is logged in on some instance right now, that live session "
                    "will overwrite this the next time it earns or spends credits, since it still has "
                    "its balance from before this edit in memory - safest for offline/logged-out accounts."
                ),
                "action": "give_credits",
                "submit_label": "Give Credits",
                "fields": [
                    {"name": "player", "label": "Handle (registered account)", "type": "text", "required": True},
                    {"name": "amount", "label": "Amount (+/-)", "type": "number", "required": True},
                ],
            },
        ]

    @staticmethod
    def web_action(instance_name, action_name, form_data):
        if action_name != "give_credits":
            return False, "Unknown action."

        form_data = form_data or {}

        handle = str(form_data.get("player", "")).strip()
        if not handle:
            return False, "Handle is required."
        # ECONOMY_HANDLE_SIZE in sv_client.cpp is 24 (23 chars + NUL); the
        # loader's sscanf reads it with "%23s" too.
        if len(handle) > 23:
            return False, "Handle is too long (23 characters max)."

        try:
            amount = int(str(form_data.get("amount", "")).strip())
        except (TypeError, ValueError):
            return False, "Amount must be a whole number."
        if amount == 0:
            return False, "Amount must be nonzero."

        return plugin._apply_credit_delta(handle, amount)

    @staticmethod
    def _apply_credit_delta(handle, amount):
        """Read-modify-write economy_accounts.dat directly, under the same
        flock() discipline SV_EconomyAccountsLoad/Save use in
        codemp/server/sv_client.cpp, so this is a safe concurrent writer
        alongside every running instance rather than a hack around them."""
        import fcntl

        accounts_path = os.path.join(settings.locations.mbii_path, "economy_accounts.dat")

        try:
            fd = os.open(accounts_path, os.O_RDWR)
        except FileNotFoundError:
            return False, "No accounts file yet - nobody has registered on this box."
        except Exception as e:
            return False, "Could not open accounts file: {}".format(e)

        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            with os.fdopen(fd, "r+", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

                new_lines = []
                new_credits = None
                for line in lines:
                    parts = line.split()
                    if len(parts) == 6 and parts[0].lower() == handle.lower():
                        try:
                            parts[3] = str(int(parts[3]) + amount)
                        except ValueError:
                            return False, "Account '{}' has a corrupt credits field.".format(parts[0])
                        new_credits = parts[3]
                        line = " ".join(parts) + "\n"
                    new_lines.append(line)

                if new_credits is None:
                    return False, "No registered account with handle '{}'.".format(handle)

                f.seek(0)
                f.writelines(new_lines)
                f.truncate()
        except Exception as e:
            return False, "Failed to update accounts file: {}".format(e)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass

        return True, "{} now has {} credits.".format(handle, new_credits)
