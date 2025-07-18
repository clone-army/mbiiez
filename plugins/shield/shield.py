import random
import datetime
import requests
import time

from mbiiez.client import client

class plugin:

    plugin_name = "VPN Shield"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['shield']

    def register(self):
        self.instance.event_handler.register_event("player_connected", self.vpn_check)

    def vpn_check(self, args):
    
        player_id = args['player_id']
        ip = args['ip']
        player = args['player']
        vpn = False

        if self.ip_api_is_vpn(ip):
            vpn = True

        if self.geo_ip_is_vpn(ip):
            vpn = True
            
        if vpn:
            print(f"VPN Detected for player {player}")
            self.instance.log_handler.log(f"VPN Detected for player {player} with ip {ip}")

            countdown_start = 60
            while countdown_start > 0:
                if countdown_start <= 10:
                    self.instance.tell(player_id, f"VPN Detected! You will be removed from the server in {countdown_start} seconds.")
                time.sleep(1)
                countdown_start -= 1

            # After countdown, kick the player using RCON command
            self.instance.console.rcon(f"clientkick {player_id}")

            self.instance.say(f"A Player {player} was kicked for using a VPN")
            self.instance.log_handler.log(f"A Player {player} was kicked for using a VPN")

    def ip_api_is_vpn(self, ip):
        url = f"http://ip-api.com/json/{ip}?fields=16973829"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses
            data = response.json()
            if data.get('proxy', False):
                return True
        except requests.RequestException as e:
            self.instance.log_handler.log(f"Error checking IP {ip} with ip-api: {e}")
        return False

    def geo_ip_is_vpn(self, ip):

        url = f"https://api.ipgeolocation.io/ipgeo?apiKey={self.config['ipgeolocation_apikey']}&ip={ip}"
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses
            data = response.json()
            if data.get('security', {}).get('is_vpn', False):
                return True
        except requests.RequestException as e:
            self.instance.log_handler.log(f"Error checking IP {ip} with geo_ip: {e}")
        return False
