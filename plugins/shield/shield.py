import time
import threading

import requests

from mbiiez.client import client

class plugin:

    plugin_name = "VPN Shield"
    plugin_author = "Louis Varley"
    plugin_url = ""
    plugin_description = "Warns, then kicks, players connecting through a VPN or proxy (optionally also mobile connections)."

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "VPN Shield",
                "path": [],
                "hint": "Blocks VPN/proxy connections (and optionally mobile connections) via proxycheck.io.",
                "fields": [
                    {"path": ["proxycheck_apikey"], "key": "proxycheck_apikey", "type": "password",
                     "label": "proxycheck.io API Key"},
                    {"path": ["block_mobile"], "key": "block_mobile", "type": "bool_select", "default": 0,
                     "label": "Block Mobile Connections", "true_label": "Block", "false_label": "Allow",
                     "help": "Also kicks players on a mobile/cellular network (e.g. a tethered phone), not just VPNs."},
                    {"path": ["padawan_tk"], "key": "padawan_tk", "type": "bool_select", "default": 0,
                     "label": "PadawanTK Switch", "true_label": "On", "false_label": "Off",
                     "help": "Kicks players on a mobile/cellular network, but only when their region is Texas."},
                ],
            },
        ]

    instance = None
    plugin_config = None

    # Results per IP, shared by every instance in this process, so reconnects
    # don't each use up a proxycheck query (the free key allows 1,000 a day).
    CACHE_SECONDS = 6 * 3600
    _cache = {}
    _cache_lock = threading.Lock()

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['shield']

    def register(self):
        self.instance.event_handler.register_event("player_connected", self.vpn_check_async)

    def vpn_check_async(self, args):
        thread = threading.Thread(target=self.vpn_check, args=(args,), daemon=True)
        thread.start()

    def vpn_check(self, args):

        player_id = args['player_id']
        ip = args['ip']
        player = args['player']

        reason, rule, loc = self.check_ip(ip)
        if not reason:
            return

        if rule == 'padawan_tk' and self._whitelisted(player):
            self.instance.log_handler.log(f"PadawanTK: {player} ({ip}) is whitelisted, not kicking")
            return

        print(f"{reason} detected for player {player}")
        self.instance.log_handler.log(f"{reason} detected for player {player} with ip {ip}")

        countdown_start = 60
        while countdown_start > 0:
            if countdown_start <= 10:
                self.instance.tell(player_id, f"{reason} detected! You will be removed from the server in {countdown_start} seconds.")
            time.sleep(1)
            countdown_start -= 1

        if rule == 'padawan_tk' and self._whitelisted(player):
            self.instance.log_handler.log(f"PadawanTK: {player} ({ip}) was whitelisted during the countdown, not kicking")
            return

        # After countdown, kick the player using RCON command
        self.instance.console.rcon(f"clientkick {player_id}")

        if rule == 'padawan_tk':
            try:
                from mbiiez.db import db
                db().insert("shield_kicks", {"instance": self.instance.name, "rule": rule, "player": player,
                                             "ip": ip, "city": loc.get('city_name', ''),
                                             "region": loc.get('region_name', '')})
            except Exception as e:
                self.instance.log_handler.log(f"Could not record shield kick for {player}: {e}")

        self.instance.say(f"A Player {player} was kicked: {reason} not allowed")
        self.instance.log_handler.log(f"A Player {player} was kicked: {reason} not allowed")

    def check_ip(self, ip):
        """Returns (reason, rule, location): reason is "VPN" or "Mobile connection" (None to let them in),
        rule says which setting caught them."""
        key = self.config.get('proxycheck_apikey', '')
        with self._cache_lock:
            hit = self._cache.get(ip)
        if hit and time.time() - hit[0] < self.CACHE_SECONDS:
            data = hit[1]
        else:
            data = self.lookup(ip, key)
            if data is None:
                return None, None, {}
            with self._cache_lock:
                if len(self._cache) > 5000:
                    self._cache.clear()
                self._cache[ip] = (time.time(), data)
        return self.classify(ip, data)

    def lookup(self, ip, key):
        """The proxycheck.io answer for ip, or None if it couldn't be had (the player is then let in)."""
        try:
            response = requests.get(f"https://proxycheck.io/v3/{ip}", params={"key": key}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as e:
            self.instance.log_handler.log(f"Error checking IP {ip} with proxycheck.io: {e}")
            return None

        if data.get('status') not in ('ok', 'warning'):
            self.instance.log_handler.log(f"proxycheck.io error for {ip}: {data.get('message', data.get('status'))}")
            return None
        return data

    def classify(self, ip, data):
        info = data.get(ip) or {}
        det = info.get('detections', {})
        if det.get('proxy') or det.get('vpn') or det.get('tor'):
            return "VPN", "vpn", {}

        wireless = str(info.get('network', {}).get('type', '')).lower() == 'wireless'
        loc = info.get('location', {})
        if wireless and self._on('block_mobile'):
            return "Mobile connection", "block_mobile", loc

        if wireless and self._on('padawan_tk'):
            if str(loc.get('region_code', '')).upper() == 'TX' or str(loc.get('region_name', '')).lower() == 'texas':
                return "Mobile connection", "padawan_tk", loc
        return None, None, {}

    @staticmethod
    def _whitelisted(player):
        try:
            from mbiiez import padawanwhitelist
            return padawanwhitelist.is_whitelisted(player)
        except Exception:
            return False

    def _on(self, key):
        try:
            return int(self.config.get(key, 0)) == 1
        except (TypeError, ValueError):
            return False
