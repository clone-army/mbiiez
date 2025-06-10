from flask import request, jsonify
from mbiiez.instance import instance as MBInstance

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        if instance:
            inst = MBInstance(instance)
            self.controller_bag['status'] = inst.status()
            self.controller_bag['players'] = inst.status().get('players', [])
            self.controller_bag['bans'] = []  # To be filled by listbans logic

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
