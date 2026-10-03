"""Presentation adapters: all server operations go through the node API."""
from mbiiez.api.client import Client


def controller(name):
    class RemoteController:
        def __init__(self, *args):
            self.controller_bag = Client().view(name, *args)

        @staticmethod
        def _action(method, *args):
            return Client().action(name + '.' + method, *args)

    # Only known operations are exposed, not a generic remote Python object.
    methods = {
        'config': ['save_config', 'sync_smod_admins', 'plugins_page'],
        'chat': ['send_message'], 'rcon': ['send_rcon'],
        'mod': ['change_map', 'change_mode', 'kick_player', 'tell_player', 'run_plugin_action'],
        'plugin_page': ['global_page', 'run_action', 'run_global_action'],
    }
    for method in methods.get(name, []):
        setattr(RemoteController, method, staticmethod(
            lambda *args, method=method: Client().action(name + '.' + method, *args)))
    return RemoteController


class Module:
    def __init__(self, name, methods):
        for method in methods:
            setattr(self, method, lambda *args, method=method: Client().action(name + '.' + method, *args))


instance_admin = Module('instance_admin', ['wizard_bag', 'create_instance', 'delete_instance', 'is_running'])
bansync = Module('bansync', ['list_bans', 'add_ban', 'remove_ban', 'set_note'])
guidbans = Module('guidbans', ['list_bans', 'add_ban', 'remove_ban', 'set_note'])
