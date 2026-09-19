import os
import json

from mbiiez import plugin_loader
from mbiiez.web import formify
from mbiiez.web import maps_catalog


class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        self.controller_bag['config_path'] = None
        self.controller_bag['config_content'] = ''
        self.controller_bag['sections'] = []
        self.controller_bag['plugin_cards'] = []
        self.controller_bag['maps_catalog'] = []
        self.controller_bag['load_error'] = None

        if not instance:
            return

        config_path = self._get_config_path(instance)
        self.controller_bag['config_path'] = config_path
        if not config_path or not os.path.exists(config_path):
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        self.controller_bag['config_content'] = raw_content

        try:
            config_dict = json.loads(raw_content)
        except Exception as e:
            # Raw JSON tab still works off raw_content above; the Form tab
            # just can't render until the file is valid JSON again.
            self.controller_bag['load_error'] = str(e)
            return

        self.controller_bag['sections'] = formify.describe_top(config_dict, skip_keys={'plugins'})

        all_plugin_names = plugin_loader.discover_plugin_names()
        plugin_meta = {name: plugin_loader.get_plugin_meta(name) for name in all_plugin_names}
        self.controller_bag['plugin_cards'] = formify.describe_plugins(config_dict, all_plugin_names, plugin_meta)

        self.controller_bag['maps_catalog'] = maps_catalog.get_maps()

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
