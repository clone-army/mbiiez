import os
import json
from flask import request, jsonify

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        self.controller_bag['config_path'] = None
        self.controller_bag['config_content'] = ''
        if instance:
            config_path = self._get_config_path(instance)
            self.controller_bag['config_path'] = config_path
            if config_path and os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.controller_bag['config_content'] = f.read()

    def _get_config_path(self, instance):
        # Try to find the config file for the instance
        # Looks for configs/[instance].json or configs/instance.txt
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../configs'))
        json_path = os.path.join(base, f'{instance}.json')
        txt_path = os.path.join(base, 'instance.txt')
        if os.path.exists(json_path):
            return json_path
        elif os.path.exists(txt_path):
            return txt_path
        return None

    @staticmethod
    def save_config(instance, content):
        # Validate JSON before saving
        try:
            json.loads(content)
        except Exception as e:
            return False, str(e)
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../configs'))
        config_path = os.path.join(base, f'{instance}.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, 'Saved successfully.'
