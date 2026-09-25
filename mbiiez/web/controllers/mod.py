from flask import request, jsonify
from mbiiez.instance import instance as MBInstance
from mbiiez.bcolors import bcolors
from mbiiez.web import maps_catalog
from mbiiez import plugin_loader
from mbiiez.web.controllers.plugin_page import load_instance_config
import re

class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag['instance'] = instance
        self.controller_bag['maps_catalog'] = maps_catalog.get_maps()
        if instance:
            inst = MBInstance(instance)
            status = inst.status()
            bc = bcolors()
            # Render color tags for map and mode
            status['map_raw'] = str(status.get('map', ''))
            status['map'] = bc.html_color_convert(str(status.get('map', '')))
            status['mode_html'] = bc.html_color_convert(str(status.get('mode', '')))
            self.controller_bag['status'] = status
            # Render color tags for player names
            players = status.get('players', [])
            for p in players:
                p['name'] = bc.html_color_convert(str(p.get('name', '')))
            self.controller_bag['players'] = players
            self.controller_bag['bans'] = self.get_bans(inst)
            self.controller_bag['plugin_cards'] = self.plugin_cards(instance)

    @staticmethod
    def plugin_cards(instance):
        """Quick-action cards from every plugin enabled on this instance
        that implements web_mod_actions() - see plugin_loader.call_web_mod_actions
        for the shape. Each card is tagged with its plugin so the page can
        post back to the right one."""
        instance_config = load_instance_config(instance) or {}
        cards = []
        for plugin_name in (instance_config.get('plugins', {}) or {}).keys():
            for card in plugin_loader.call_web_mod_actions(plugin_name, instance, instance_config):
                if isinstance(card, dict) and card.get('actions'):
                    card = dict(card)
                    card['plugin'] = plugin_name
                    cards.append(card)
        return cards

    @staticmethod
    def run_plugin_action(instance, plugin_name, action_name, form_data):
        """Run a Mod page plugin action - but only one the plugin is
        actually offering for this instance right now (it must be enabled
        here, and its web_mod_actions() must list the action), so a request
        can't reach actions the page would never show."""
        instance_config = load_instance_config(instance)
        if instance_config is None:
            return False, "Could not load config for instance '{}'.".format(instance)
        if plugin_name not in (instance_config.get('plugins', {}) or {}):
            return False, "Plugin '{}' isn't enabled on {}.".format(plugin_name, instance)

        offered = set()
        for card in plugin_loader.call_web_mod_actions(plugin_name, instance, instance_config):
            for action in (card or {}).get('actions', []):
                offered.add(action.get('name'))
        if action_name not in offered:
            return False, "That action isn't available on {} right now.".format(instance)

        return plugin_loader.call_web_mod_action(plugin_name, instance, action_name, form_data or {})

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
