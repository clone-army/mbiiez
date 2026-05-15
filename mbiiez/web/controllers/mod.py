from flask import request, jsonify
from mbiiez.instance import instance as MBInstance
from mbiiez.bcolors import bcolors
import re

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        if instance:
            inst = MBInstance(instance)
            status = inst.status()
            bc = bcolors()
            # Render color tags for map and mode
            status['map'] = bc.html_color_convert(str(status.get('map', '')))
            status['mode_html'] = bc.html_color_convert(str(status.get('mode', '')))
            self.controller_bag['status'] = status
            # Render color tags for player names
            players = status.get('players', [])
            for p in players:
                p['name'] = bc.html_color_convert(str(p.get('name', '')))
            self.controller_bag['players'] = players
            self.controller_bag['bans'] = self.get_bans(inst)

    @staticmethod
    def get_bans(inst):
        """Parse banned IPs from g_banips output."""
        try:
            output = inst.rconResponse("g_banips") or ""
            ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", output)
            # Preserve insertion order while removing duplicates.
            return list(dict.fromkeys(ips))
        except Exception:
            return []

    @staticmethod
    def change_map(instance, mapname):
        inst = MBInstance(instance)
        try:
            inst.map(mapname)
            return True, 'Map changed.'
        except Exception as e:
            return False, str(e)

    @staticmethod
    def change_mode(instance, mode):
        inst = MBInstance(instance)
        try:
            inst.mode(mode)
            return True, 'Mode changed.'
        except Exception as e:
            return False, str(e)

    @staticmethod
    def kick_player(instance, player_id):
        inst = MBInstance(instance)
        try:
            inst.kick(player_id)
            return True, 'Player kicked.'
        except Exception as e:
            return False, str(e)

    @staticmethod
    def ban_player(instance, ip):
        inst = MBInstance(instance)
        try:
            inst.ban(ip)
            return True, 'Player banned.'
        except Exception as e:
            return False, str(e)

    @staticmethod
    def unban_ip(instance, ip):
        inst = MBInstance(instance)
        try:
            inst.unban(ip)
            return True, 'IP unbanned.'
        except Exception as e:
            return False, str(e)

    @staticmethod
    def tell_player(instance, player_id, message):
        inst = MBInstance(instance)
        try:
            inst.tell(player_id, message)
            return True, 'Message sent.'
        except Exception as e:
            return False, str(e)
