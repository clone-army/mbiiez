from flask import request, jsonify
from mbiiez.db import db
from mbiiez.instance import instance as MBInstance

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        # Load last 100 chat messages for this instance
        conn = db().connect()
        cur = conn.cursor()
        if instance:
            q = "SELECT * FROM chatter WHERE instance = ? ORDER BY added DESC LIMIT 100"
            cur.execute(q, (instance,))
        else:
            q = "SELECT * FROM chatter ORDER BY added DESC LIMIT 100"
            cur.execute(q)
        rows = cur.fetchall()
        # Reverse for chat order (oldest at top)
        self.controller_bag['messages'] = list(reversed(rows))
        self.controller_bag['instance'] = instance

    @staticmethod
    def send_message(instance, message):
        inst = MBInstance(instance)
        inst.say(message)
        return True
