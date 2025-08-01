from mbiiez.db import db
from mbiiez.instance import instance as Instance
from mbiiez.bcolors import bcolors

class controller:

    controller_bag = {}

    def __init__(self, instance = None):

        self.controller_bag['instance'] = instance
        inst = Instance(instance)
        status = None
        try:
            status = inst.status()
            # Get MBII version via RCON
            version = inst.version() if status.get('server_running', False) else ''
        except ConnectionRefusedError:
            status = {
                'server_running': False,
                'server_name': instance,
                'map': '',
                'mode': '',
                'players': [],
                'uptime': '',
                'services': [],
            }
            version = ''
        bc = bcolors()
        self.controller_bag['status'] = status
        self.controller_bag['engine_running'] = status.get('server_running', False)
        self.controller_bag['status_text'] = 'Running' if status.get('server_running', False) else 'Stopped'
        self.controller_bag['uptime'] = status.get('uptime', '')
        self.controller_bag['version'] = version
        # Only process map/mode/players if running
        if status.get('server_running', False):
            # Convert color codes in server name for HTML
            if 'server_name' in status and status['server_name']:
                status['server_name_html'] = bc.html_color_convert(status['server_name'])
            else:
                status['server_name_html'] = ''
            # Convert map and mode for HTML (in case of color tags)
            if 'map' in status and status['map']:
                status['map_html'] = bc.html_color_convert(str(status['map']))
            else:
                status['map_html'] = ''
            if 'mode' in status and status['mode']:
                status['mode_html'] = bc.html_color_convert(str(status['mode']))
            else:
                status['mode_html'] = ''
            # Convert player names
            players = status.get('players', [])
            for p in players:
                if 'name_raw' in p:
                    # Use name_raw (with ^-codes) for web interface HTML conversion
                    p['player_html'] = bc.html_color_convert(p['name_raw'])
                elif 'name' in p:
                    # Fallback to name if name_raw not available
                    p['player_html'] = bc.html_color_convert(p['name'])
                else:
                    p['player_html'] = 'Unknown'
            self.controller_bag['players'] = players
            self.controller_bag['map'] = status.get('map_html', '')
            self.controller_bag['mode'] = status.get('mode_html', '')
        else:
            status['server_name_html'] = ''
            status['map_html'] = ''
            status['mode_html'] = ''
            self.controller_bag['players'] = []
            self.controller_bag['map'] = ''
            self.controller_bag['mode'] = ''
