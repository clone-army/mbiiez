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
                ],
            },
        ]

    instance = None
    plugin_config = None

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

        reason = self.check_ip(ip)
        if not reason:
            return

        print(f"{reason} detected for player {player}")
        self.instance.log_handler.log(f"{reason} detected for player {player} with ip {ip}")

        countdown_start = 60
        while countdown_start > 0:
            if countdown_start <= 10:
                self.instance.tell(player_id, f"{reason} detected! You will be removed from the server in {countdown_start} seconds.")
            time.sleep(1)
            countdown_start -= 1

        # After countdown, kick the player using RCON command
        self.instance.console.rcon(f"clientkick {player_id}")

        self.instance.say(f"A Player {player} was kicked: {reason} not allowed")
        self.instance.log_handler.log(f"A Player {player} was kicked: {reason} not allowed")

    def check_ip(self, ip):
        """Returns a short reason string ("VPN", "Mobile connection") or None."""
        key = self.config.get('proxycheck_apikey', '')
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

        info = data.get(ip) or {}
        det = info.get('detections', {})
        if det.get('proxy') or det.get('vpn') or det.get('tor'):
            return "VPN"

        try:
            block_mobile = int(self.config.get('block_mobile', 0))
        except (TypeError, ValueError):
            block_mobile = 0
        if block_mobile and str(info.get('network', {}).get('type', '')).lower() == 'wireless':
            return "Mobile connection"
        return None
