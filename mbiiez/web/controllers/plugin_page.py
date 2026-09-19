import os
import json

from mbiiez import plugin_loader, settings


def load_instance_config(instance_name):
    """Read the instance's raw config JSON directly from disk - same
    approach as controllers/config.py - rather than constructing a full
    runtime `instance` object (which sets up process/log handlers meant for
    a running server, not a web request)."""
    config_path = os.path.join(settings.locations.config_path, f"{instance_name}.json")
    if not os.path.isfile(config_path):
        return None
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_menu_entry(instance_name, instance_config, slug):
    """Find which enabled plugin (if any) owns the given nav slug, returning
    (plugin_name, menu_entry) or (None, None)."""
    plugins_cfg = (instance_config or {}).get("plugins", {}) or {}
    for plugin_name in plugins_cfg.keys():
        entry = plugin_loader.call_web_menu(plugin_name, instance_name, instance_config)
        if entry and entry.get("slug") == slug:
            return plugin_name, entry
    return None, None


class controller:
    controller_bag = {}

    def __init__(self, instance=None, slug=None):
        self.controller_bag["instance"] = instance
        self.controller_bag["slug"] = slug
        self.controller_bag["plugin_name"] = None
        self.controller_bag["menu"] = None
        self.controller_bag["sections"] = []
        self.controller_bag["error"] = None

        if not instance or not slug:
            self.controller_bag["error"] = "Missing instance or plugin."
            return

        instance_config = load_instance_config(instance)
        if instance_config is None:
            self.controller_bag["error"] = "Could not load config for instance '{}'.".format(instance)
            return

        plugin_name, entry = find_menu_entry(instance, instance_config, slug)
        if not plugin_name:
            self.controller_bag["error"] = "No enabled plugin on this instance provides the page '{}'.".format(slug)
            return

        self.controller_bag["plugin_name"] = plugin_name
        self.controller_bag["menu"] = entry
        sections = plugin_loader.call_web_page(plugin_name, instance, instance_config)
        self.controller_bag["sections"] = sections or []

    @staticmethod
    def run_action(instance, slug, action_name, form_data):
        instance_config = load_instance_config(instance)
        if instance_config is None:
            return False, "Could not load config for instance '{}'.".format(instance)

        plugin_name, entry = find_menu_entry(instance, instance_config, slug)
        if not plugin_name:
            return False, "No enabled plugin on this instance provides the page '{}'.".format(slug)

        return plugin_loader.call_web_action(plugin_name, instance, action_name, form_data)
