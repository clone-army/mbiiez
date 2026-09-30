"""Config migrations for plugins that have been split or renamed.

The Credit System ("creditsystem") was one plugin doing everything; it's now
separate plugins with dependencies between them:

    accounts   - !register / !login, admins, the login reminder
    credits    - earning credits, !balance, !gift, bonuses       (needs accounts)
    shop       - !buy and its prices                             (needs credits)
    bounties   - !bounty                                         (needs credits)
    bar        - !bar drinks, and the AI bartender               (needs credits)
    jukebox    - !jukebox                                        (needs credits)
    casino     - blackjack, pazaak, chance, raffle, duel betting (needs credits)

migrate(config) turns an old "creditsystem" block into those, keeping exactly
what was switched on and every setting. The runtime applies it to any config
still in the old shape; `python3 -m mbiiez.plugin_migrations` rewrites the
files once.
"""
import copy
import json
import shutil
import os
import sys

# Which new plugin owns each old cvar (by prefix or exact name), and the
# switch that decided whether that plugin was on.
_OWNERS = [
    ("accounts", ["g_economyLoginReminder"]),
    ("credits", ["g_creditSystemEnable", "g_economyRegisterBonus", "g_economyDailyBonus"]),
    ("shop", ["g_economyShopEnable", "g_shopCost_"]),
    ("bounties", ["g_economyBountyEnable"]),
    ("bar", ["g_economyBarEnable", "g_barTabMinutes", "g_barPassOutDrinks", "g_barPoisoningDrinks",
             "g_barSpiceOverdose", "g_barCost_", "g_bartenderCost", "g_bartenderCooldown",
             "g_bartenderDailyCap", "g_bartenderPublic"]),
    ("jukebox", ["g_economyJukeboxEnable", "g_jukeboxCost", "g_jukeboxCooldown", "g_jukeboxAutoplay",
                 "g_jukeboxAutoplayMax"]),
    ("casino", ["g_economyPazaakEnable", "g_economyChanceEnable", "g_economyBlackjackEnable",
                "g_blackjackMaxBet", "g_economyBetEnable", "g_betWindowSeconds", "g_betMax",
                "g_betWinBonus", "g_betLoserRefund", "g_economyRaffleEnable", "g_raffleIntervalMinutes",
                "g_raffleOpenMinutes", "g_raffleTicketPrice", "g_raffleMinEntrants"]),
]
_SWITCH = {
    "shop": "g_economyShopEnable",
    "bounties": "g_economyBountyEnable",
    "bar": "g_economyBarEnable",
    "jukebox": "g_economyJukeboxEnable",
}
_CASINO_SWITCHES = ["g_economyPazaakEnable", "g_economyChanceEnable", "g_economyBlackjackEnable",
                    "g_economyBetEnable", "g_economyRaffleEnable"]
# Order new plugins go in, where creditsystem was.
_ORDER = ["accounts", "credits", "shop", "bounties", "bar", "jukebox", "casino"]


def _on(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _owner(cvar):
    for plugin, keys in _OWNERS:
        for k in keys:
            if cvar == k or (k.endswith("_") and cvar.startswith(k)):
                return plugin
    return None


def split_creditsystem(block):
    """{new plugin name: its config} for an old creditsystem block."""
    block = block or {}
    cvars = dict(block.get("cvars", {}) or {})
    economy_on = _on(cvars.get("g_creditSystemEnable", "1"))
    if not economy_on:
        return {}  # it was all off (logins too): so's everything that replaces it
    out = {"accounts": {"cvars": {}}}
    grouped = {name: {} for name in _ORDER}
    for key, value in cvars.items():
        owner = _owner(key)
        if owner:
            grouped[owner][key] = value
    out["accounts"]["cvars"] = grouped["accounts"]
    out["credits"] = {"cvars": {k: v for k, v in grouped["credits"].items() if k != "g_creditSystemEnable"}}
    for name, switch in _SWITCH.items():
        if _on(cvars.get(switch, "0")):
            out[name] = {"cvars": {k: v for k, v in grouped[name].items() if k != switch}}
    bartender = block.get("bartender")
    if bartender and bartender.get("api_key"):
        out.setdefault("bar", {"cvars": {}})["bartender"] = bartender
        for k, v in grouped["bar"].items():
            if k != "g_economyBarEnable":
                out["bar"]["cvars"].setdefault(k, v)
    if any(_on(cvars.get(s, "0")) for s in _CASINO_SWITCHES):
        # Every game's switch as it was: the Casino defaults some on.
        casino = dict(grouped["casino"])
        for s in _CASINO_SWITCHES:
            casino[s] = "1" if _on(cvars.get(s, "0")) else "0"
        out["casino"] = {"cvars": casino}
    return out


def migrate(config):
    """(new_config, changed). Doesn't touch the config passed in."""
    plugins = (config or {}).get("plugins") or {}
    if "creditsystem" not in plugins:
        return config, False
    new = copy.deepcopy(config)
    replaced = split_creditsystem(plugins["creditsystem"])
    ordered = {}
    for name, value in new["plugins"].items():
        if name == "creditsystem":
            for n in _ORDER:
                if n in replaced and n not in new["plugins"]:
                    ordered[n] = replaced[n]
        else:
            ordered[name] = value
    new["plugins"] = ordered
    return new, True


def migrate_files(config_dir, write=True):
    report = []
    for f in sorted(os.listdir(config_dir)):
        if not f.endswith(".json"):
            continue
        path = os.path.join(config_dir, f)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (OSError, ValueError) as e:
            report.append("{}: skipped ({})".format(f, e))
            continue
        new, changed = migrate(cfg)
        if not changed:
            continue
        report.append("{}: creditsystem -> {}".format(f, ", ".join(
            n for n in _ORDER if n in (new.get("plugins") or {}))))
        if write:
            backup = path + ".pre-split.bak"
            if not os.path.exists(backup):
                shutil.copy2(path, backup)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(new, fh, indent=4, ensure_ascii=False)
                fh.write("\n")
    return report


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from mbiiez import settings
    dry = "--dry-run" in sys.argv
    for line in migrate_files(settings.locations.config_path, write=not dry) or ["nothing to migrate"]:
        print(("[dry run] " if dry else "") + line)
