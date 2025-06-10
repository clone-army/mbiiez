from mbiiez.db import db
from mbiiez.instance import instance as Instance

class controller:

    controller_bag = {}

    def __init__(self, instance = None):

        self.controller_bag['instance'] = instance

        # Get instance status using new status() method
        inst = Instance(instance)
        status = inst.status()
        self.controller_bag['status'] = status
        self.controller_bag['engine_running'] = status.get('server_running', False)
        self.controller_bag['status_text'] = 'Running' if status.get('server_running', False) else 'Stopped'
        self.controller_bag['players'] = status.get('players', [])
