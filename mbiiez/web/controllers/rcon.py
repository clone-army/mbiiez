from flask import request, jsonify
from mbiiez.instance import instance as MBInstance

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        self.controller_bag['response'] = ''

    @staticmethod
    def send_rcon(instance, command):
        inst = MBInstance(instance)
        try:
            response = inst.rconResponse(command)
            return True, response
        except Exception as e:
            return False, str(e)
