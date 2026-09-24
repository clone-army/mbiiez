''' 
RTVRTM Plugin for MBIIEZ
Rock the Vote/Rock the Mode plugin that integrates the original RTVRTM script
with the MBIIEZ plugin system while preserving exact functionality.

The plugin automatically gets these values from MBIIEZ instance:
- MBII folder path (from conf.mbii_path)
- Server port (from server.port) 
- RCON password (from security.rcon_password)
- Server address (automatically set to 127.0.0.1:port)
- Bind address (automatically set to 127.0.0.1)
- Log file (automatically set to {instance_name}-games.log)

Configuration in instance JSON:

    "rtvrtm": {
        "general": {
            "flood_protection": 0.5,
            "use_say_only": 0,
            "name_protection": 1,
            "default_game": "",
            "clean_log": "0"
        },
        "admin_voting": {
            "admin_voting": "1 30",
            "admin_minimum_votes": 51.0,
            "admin_skip_voting": 1
        },
        "map_limit": {
            "roundlimit": 1,
            "timelimit": 0,
            "limit_voting": "1 10",
            "limit_minimum_votes": 51.0,
            "limit_extend": "1 3",
            "limit_successful_wait_time": 300,
            "limit_failed_wait_time": 60,
            "limit_skip_voting": 1,
            "limit_second_turn": 1,
            "limit_change_immediately": 0
        },
        "rtv": {
            "rtv": 1,
            "rtv_rate": 60.0,
            "rtv_voting": "1 10",
            "rtv_minimum_votes": 51.0,
            "rtv_extend": "1 3",
            "rtv_successful_wait_time": 300,
            "rtv_failed_wait_time": 60,
            "rtv_skip_voting": 1,
            "rtv_second_turn": 1,
            "rtv_change_immediately": 0
        },
        "maps": {
            "automatic_maps": 0,
            "pick_secondary_maps": 2,
            "map_priority": "2 1 0",
            "nomination_type": 1,
            "enable_recently_played_maps": 3600
        },
        "rtm": {
            "rtm": 7,
            "mode_priority": "2 1 0 2 1 0",
            "rtm_rate": 60.0,
            "rtm_voting": "1 10",
            "rtm_minimum_votes": 51.0,
            "rtm_extend": "1 3",
            "rtm_successful_wait_time": 300,
            "rtm_failed_wait_time": 60,
            "rtm_skip_voting": 1,
            "rtm_second_turn": 1,
            "rtm_change_immediately": 0
        },
        "primary_maps": [
            "mb2_alderaan",
            "mb2_boc",
            "mb2_citadel",
            "mb2_cloudcity",
            "mb2_commtower",
            "mb2_corellia",
            "mb2_deathstar",
            "mb2_dotf",
            "mb2_jeditemple",
            "mb2_kamino"
        ],
        "secondary_maps": [
            "mb2_cmp_arctic",
            "mb2_cmp_arena",
            "mb2_cmp_duel_vjun",
            "mb2_cmp_endor"
        ]
    }

'''

import os
import json
import threading
import subprocess
import sys
import time
import importlib.util
from pathlib import Path

def load_rtvrtm_plugin():
    """Load the RTVRTMPlugin class"""
    plugin_dir = os.path.dirname(__file__)
    plugin_file = os.path.join(plugin_dir, 'rtvrtm_plugin.py')
    
    spec = importlib.util.spec_from_file_location("rtvrtm_plugin", plugin_file)
    rtvrtm_plugin_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rtvrtm_plugin_module)
    
    return rtvrtm_plugin_module.RTVRTMPlugin

class plugin:
    
    plugin_name = "RTVRTM"
    plugin_author = "klax / Cthulhu (Python3 port + MBIIEZ integration)"
    plugin_version = "3.6c"
    plugin_url = ""
    
    @staticmethod
    def web_hide_default_card():
        """RTV, RTM and General below cover this plugin's whole config, so
        the generic auto-rendered Plugins card would just be a second,
        untyped copy of the same fields - hide it. See
        mbiiez/plugin_loader.py:call_web_hide_default_card()."""
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        """Gives RTV, RTM and General their own top-level sections on the
        Config page, each with explicitly typed fields (a 0/1 dropdown
        instead of a bare number, a 0-100 rate, fields that greyed out
        together when their feature's off) instead of the generic
        describe()-guessed rendering every other plugin still gets - see
        mbiiez/web/formify.py:describe_field_spec() and
        mbiiez/plugin_loader.py:call_web_config_sections(). Holiday maps
        are handled separately, folded into the Config page's built-in
        Maps section (mbiiez/web/controllers/config.py) rather than here,
        since that section already owns the map rotation it injects into."""
        # generate_maps_files() in rtvrtm_plugin.py checks plugins.rtvrtm.
        # rtv.primary_maps first, falling back to plugins.rtvrtm.
        # primary_maps (plugin-root) if that's absent - and most existing
        # instances actually have their real data at the plugin-root
        # location, not nested under "rtv". Point the field at wherever
        # this instance's data actually lives (same precedence as the
        # plugin itself) instead of hard-coding one location, so the form
        # doesn't show empty for maps that are really set at the other spot.
        rtvrtm_cfg = (instance_config.get("plugins", {}) or {}).get("rtvrtm", {}) or {}
        rtv_cfg = rtvrtm_cfg.get("rtv", {}) or {}
        if "primary_maps" in rtv_cfg or "secondary_maps" in rtv_cfg:
            maps_path = ["rtv"]
        else:
            maps_path = []

        # Compound RTVRTM values ("1 5", "2 0 1", ...) are split into
        # separate labelled inputs (formify "composite") and joined back on
        # save, so they can't be typed in a shape rtvrtm_original.py's
        # parser rejects - e.g. an extend of "2 3" (a count is only allowed
        # after 1) stops the whole plugin at startup.
        def vote_length(noun):
            return [
                {"label": "Vote ends after", "kind": "choice", "default": 0,
                 "options": [[0, "A number of minutes"], [1, "A number of rounds"]]},
                {"label": "How many", "kind": "number", "min": 1, "default": 3,
                 "help": "Minutes: reminders every minute, final call 30s before the end. "
                         "Rounds: the round the vote started in doesn't count."},
            ]

        def extend_parts(noun):
            return [
                {"label": "\"Don't change\" option", "kind": "choice", "default": 2,
                 "options": [[0, "Never offer it"],
                             [1, "Offer it a limited number of times"],
                             [2, "Always offer it"]]},
                {"label": "Max times the same %s can be kept" % noun, "kind": "number", "min": 1, "default": 3,
                 "show_when": {"part": 0, "in": [1]}},
            ]

        skip_options = [
            [0, "Never - always run the full vote length"],
            [1, "Once every player has voted"],
            [2, "As soon as the winner can't be caught"],
        ]
        priority_options = [[0, "Low"], [1, "Medium"], [2, "High"]]

        def rate_help(cmd):
            return ("Share of connected players who must type %s before the vote starts. "
                    "0 = more than half (simple majority)." % cmd)

        min_votes_help = ("If fewer than this share of players actually vote, the vote fails and nothing changes. "
                          "0 = the vote never fails for lack of votes.")
        wait_help = "Seconds before %s can be called again. 0 = no cooldown."

        rtv_on = {"path": ["rtv", "rtv"], "equals": 1}
        rtm_on = {"path": ["rtm", "rtm"], "not_equals": 0}

        return [
            {
                "label": "RTV (Rock the Vote)",
                "path": ["rtv"],
                "hint": "Map-change voting and how maps get nominated.",
                "fields": [
                    {"path": ["rtv", "rtv"], "key": "rtv", "type": "bool_select", "default": 1,
                     "label": "Enable RTV", "help": "Lets players type !rtv to call a vote to change the map."},
                    {"path": ["rtv", "rtv_rate"], "key": "rtv_rate", "type": "percent", "default": 60.0,
                     "label": "Players Needed To Start A Vote", "help": rate_help("!rtv"),
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_minimum_votes"], "key": "rtv_minimum_votes", "type": "percent", "default": 51.0,
                     "label": "Minimum Turnout", "help": min_votes_help,
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_voting"], "key": "rtv_voting", "type": "composite", "default": '1 10',
                     "label": "Vote Length", "parts": vote_length("map"),
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_extend"], "key": "rtv_extend", "type": "composite", "default": '1 3',
                     "label": "Keep Current Map Option", "parts": extend_parts("map"),
                     "help": "Whether the ballot includes \"Don't change\". Extensions are counted across RTV and map-limit votes.",
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_successful_wait_time"], "key": "rtv_successful_wait_time", "type": "number", "default": 300,
                     "label": "Cooldown After The Map Changes", "help": wait_help % "RTV",
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_failed_wait_time"], "key": "rtv_failed_wait_time", "type": "number", "default": 60,
                     "label": "Cooldown After A Failed Vote",
                     "help": (wait_help % "RTV") + " Applies when players chose \"Don't change\" or too few voted.",
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_skip_voting"], "key": "rtv_skip_voting", "type": "choice", "default": 1,
                     "label": "End The Vote Early", "options": skip_options,
                     "help": "With a second round enabled, only ends early once one option has over half the players.",
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_second_turn"], "key": "rtv_second_turn", "type": "bool_select", "default": 1,
                     "label": "Runoff Vote", "true_label": "On", "false_label": "Off",
                     "help": "If no map gets over half the votes, hold a second vote between the top two.",
                     "depends_on": rtv_on},
                    {"path": ["rtv", "rtv_change_immediately"], "key": "rtv_change_immediately", "type": "bool_select", "default": 0,
                     "label": "When The Map Changes", "true_label": "Immediately after the vote", "false_label": "At the start of the next round",
                     "depends_on": rtv_on},
                    {"path": maps_path + ["primary_maps"], "key": "primary_maps", "type": "map_list", "reorderable": False,
                     "label": "Primary Maps", "help": "The main nomination pool - written out to maps.txt for the running server to read."},
                    {"path": maps_path + ["secondary_maps"], "key": "secondary_maps", "type": "map_list", "reorderable": False,
                     "label": "Secondary Maps", "help": "Extra maps players can nominate, and optionally used to fill empty ballot slots (see below). Written out to secondary_maps.txt."},
                    {"path": ["maps", "automatic_maps"], "key": "automatic_maps", "type": "bool_select", "default": 0,
                     "label": "Map Pool", "true_label": "Every map installed on the server", "false_label": "Only the Primary/Secondary lists above",
                     "help": "\"Every map\" ignores both lists (secondary maps stop working)."},
                    {"path": ["maps", "pick_secondary_maps"], "key": "pick_secondary_maps", "type": "choice", "default": 2,
                     "label": "Filling Empty Ballot Slots", "options": [
                         [0, "Primary maps only"],
                         [1, "Secondary maps only when no primary map is left"],
                         [2, "Mix primary and secondary maps equally"]],
                     "help": "A ballot has 5 map slots; any not taken by nominations are picked at random."},
                    {"path": ["maps", "map_priority"], "key": "map_priority", "type": "composite", "default": '2 1 0',
                     "label": "Tie-Break Priority",
                     "help": "When options tie on votes, the higher priority wins (equal priority = random). Also used to pick runoff options.",
                     "parts": [
                         {"label": "Primary maps", "kind": "choice", "options": priority_options, "default": 2},
                         {"label": "Secondary maps", "kind": "choice", "options": priority_options, "default": 1},
                         {"label": "\"Don't change\"", "kind": "choice", "options": priority_options, "default": 0},
                     ]},
                    {"path": ["maps", "nomination_type"], "key": "nomination_type", "type": "choice", "default": 1,
                     "label": "Nominations", "options": [
                         [0, "First come - each player nominates one map, max 5 in total"],
                         [1, "Popularity - players vote for nominations, top 5 make the ballot"]],
                     "help": "Only applies with more than 5 maps in the pool; otherwise every map goes on the ballot."},
                    {"path": ["maps", "enable_recently_played_maps"], "key": "enable_recently_played_maps", "type": "number", "default": 3600,
                     "label": "Recently-Played Cooldown", "help": "Seconds a map can't be nominated or voted for after it was played (3600 = 1 hour). 0 = off."},
                ],
            },
            {
                "label": "RTM (Rock the Mode)",
                "path": ["rtm"],
                "hint": "Game-mode voting: which modes, vote rate, timing.",
                "fields": [
                    {"path": ["rtm", "rtm"], "key": "rtm", "type": "rtm_modes", "default": 7,
                     "label": "Modes Players Can Vote For",
                     "help": "Players type !rtm to call a vote. Tick none to turn RTM off."},
                    {"path": ["rtm", "rtm_rate"], "key": "rtm_rate", "type": "percent", "default": 60.0,
                     "label": "Players Needed To Start A Vote", "help": rate_help("!rtm"),
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_minimum_votes"], "key": "rtm_minimum_votes", "type": "percent", "default": 51.0,
                     "label": "Minimum Turnout", "help": min_votes_help,
                     "depends_on": rtm_on},
                    {"path": ["rtm", "mode_priority"], "key": "mode_priority", "type": "composite", "default": '2 1 0 2 1 0',
                     "label": "Tie-Break Priority",
                     "help": "When options tie on votes, the higher priority wins (equal priority = random). Also used to pick runoff options.",
                     "parts": [
                         {"label": name, "kind": "choice", "options": priority_options, "default": d}
                         for name, d in (("Open", 2), ("Semi Authentic", 1), ("Full Authentic", 0),
                                         ("Duel", 2), ("Legends", 1), ("\"Don't change\"", 0))
                     ],
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_voting"], "key": "rtm_voting", "type": "composite", "default": '1 10',
                     "label": "Vote Length", "parts": vote_length("mode"),
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_extend"], "key": "rtm_extend", "type": "composite", "default": '1 3',
                     "label": "Keep Current Mode Option", "parts": extend_parts("mode"),
                     "help": "Whether the ballot includes \"Don't change\".",
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_successful_wait_time"], "key": "rtm_successful_wait_time", "type": "number", "default": 300,
                     "label": "Cooldown After The Mode Changes", "help": wait_help % "RTM",
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_failed_wait_time"], "key": "rtm_failed_wait_time", "type": "number", "default": 60,
                     "label": "Cooldown After A Failed Vote",
                     "help": (wait_help % "RTM") + " Applies when players chose \"Don't change\" or too few voted.",
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_skip_voting"], "key": "rtm_skip_voting", "type": "choice", "default": 1,
                     "label": "End The Vote Early", "options": skip_options,
                     "help": "With a second round enabled, only ends early once one option has over half the players.",
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_second_turn"], "key": "rtm_second_turn", "type": "bool_select", "default": 1,
                     "label": "Runoff Vote", "true_label": "On", "false_label": "Off",
                     "help": "If no mode gets over half the votes, hold a second vote between the top two.",
                     "depends_on": rtm_on},
                    {"path": ["rtm", "rtm_change_immediately"], "key": "rtm_change_immediately", "type": "bool_select", "default": 0,
                     "label": "When The Mode Changes", "true_label": "Immediately after the vote", "false_label": "At the start of the next round",
                     "depends_on": rtm_on},
                ],
            },
            {
                "label": "RTVRTM General",
                "path": ["general"],
                "hint": "Chat behaviour, admin-called votes, and votes triggered by the server's round/time limit.",
                "fields": [
                    {"path": ["general", "flood_protection"], "key": "flood_protection", "type": "number", "default": 0.5,
                     "label": "Command Flood Protection",
                     "help": "Seconds a player must wait between !rtv/!rtm-style commands (decimals allowed, e.g. 0.5). Voting itself isn't limited. 0 = off."},
                    {"path": ["general", "use_say_only"], "key": "use_say_only", "type": "bool_select", "default": 0,
                     "label": "Announcement Style",
                     "true_label": "Chat only (easy to miss)", "false_label": "Important ones on screen (recommended)",
                     "help": "The plugin's own author recommends leaving this on the on-screen setting."},
                    {"path": ["general", "name_protection"], "key": "name_protection", "type": "bool_select", "default": 1,
                     "label": "Name Protection",
                     "help": "Kick anyone using the name \"Server\" or \"Admin\" (any case/colour), so they can't fake announcements. Needs g_logClientInfo 1."},
                    {"path": ["general", "default_game"], "key": "default_game", "type": "composite", "default": '',
                     "label": "When The Server Empties",
                     "help": "What to switch to once the last player leaves. Leave both blank to do nothing.",
                     "parts": [
                         {"label": "Switch to mode", "kind": "choice", "match": r"\d+", "default": "",
                          "options": [["", "Keep current mode"], [0, "Open"], [1, "Semi Authentic"],
                                      [2, "Full Authentic"], [3, "Duel"], [4, "Legends"]]},
                         {"label": "Switch to map", "kind": "text", "default": "", "placeholder": "e.g. mb2_dotf (blank = keep current map)"},
                     ]},
                    {"path": ["general", "clean_log"], "key": "clean_log", "type": "composite", "default": '0',
                     "label": "Log File Cleanup",
                     "parts": [
                         {"label": "When the log gets big", "kind": "choice", "default": 0,
                          "options": [[0, "Do nothing"], [1, "Delete it"], [2, "Compress (tar.gz) then delete it"]]},
                         {"label": "Size limit (MB)", "kind": "number", "min": 1, "default": 10,
                          "show_when": {"part": 0, "in": [1, 2]}},
                     ]},
                    {"path": ["admin_voting", "admin_voting"], "key": "admin_voting", "type": "composite", "default": '1 30',
                     "label": "Admin-Called Vote Length", "parts": vote_length("map")},
                    {"path": ["admin_voting", "admin_minimum_votes"], "key": "admin_minimum_votes", "type": "percent", "default": 51.0,
                     "label": "Admin-Called Vote Minimum Turnout", "help": min_votes_help},
                    {"path": ["admin_voting", "admin_skip_voting"], "key": "admin_skip_voting", "type": "choice", "default": 1,
                     "label": "End Admin-Called Votes Early", "options": skip_options},
                    {"path": ["map_limit", "roundlimit"], "key": "roundlimit", "type": "bool_select", "default": 1,
                     "label": "Vote For A New Map At The Round/Frag Limit", "true_label": "On", "false_label": "Off",
                     "help": "Needs roundlimit or fraglimit set in the server config."},
                    {"path": ["map_limit", "timelimit"], "key": "timelimit", "type": "bool_select", "default": 0,
                     "label": "Vote For A New Map At The Time Limit", "true_label": "On", "false_label": "Off",
                     "help": "Needs timelimit set in the server config."},
                    {"path": ["map_limit", "limit_voting"], "key": "limit_voting", "type": "composite", "default": '1 10',
                     "label": "Limit Vote Length", "parts": vote_length("map")},
                    {"path": ["map_limit", "limit_minimum_votes"], "key": "limit_minimum_votes", "type": "percent", "default": 51.0,
                     "label": "Limit Vote Minimum Turnout", "help": min_votes_help},
                    {"path": ["map_limit", "limit_extend"], "key": "limit_extend", "type": "composite", "default": '1 3',
                     "label": "Limit Vote: Keep Current Map Option", "parts": extend_parts("map"),
                     "help": "Extensions are counted across RTV and map-limit votes."},
                    {"path": ["map_limit", "limit_successful_wait_time"], "key": "limit_successful_wait_time", "type": "number", "default": 300,
                     "label": "RTV Cooldown After A Limit Vote Changes The Map", "help": "Seconds before players can !rtv again. 0 = no cooldown."},
                    {"path": ["map_limit", "limit_failed_wait_time"], "key": "limit_failed_wait_time", "type": "number", "default": 60,
                     "label": "RTV Cooldown After A Failed Limit Vote", "help": "Seconds before players can !rtv again. 0 = no cooldown."},
                    {"path": ["map_limit", "limit_skip_voting"], "key": "limit_skip_voting", "type": "choice", "default": 1,
                     "label": "End Limit Votes Early", "options": skip_options},
                    {"path": ["map_limit", "limit_second_turn"], "key": "limit_second_turn", "type": "bool_select", "default": 1,
                     "label": "Limit Vote Runoff", "true_label": "On", "false_label": "Off",
                     "help": "If no map gets over half the votes, hold a second vote between the top two."},
                    {"path": ["map_limit", "limit_change_immediately"], "key": "limit_change_immediately", "type": "bool_select", "default": 0,
                     "label": "When The Map Changes", "true_label": "Immediately after the vote", "false_label": "At the start of the next round"},
                ],
            },
        ]

    def __init__(self, instance):
        self.instance = instance
        self.rtvrtm_plugin_instance = None
    
    def register(self):
        """Register the plugin with MBIIEZ"""
        try:
            # Get the plugin configuration
            config = self.instance.config.get('plugins', {}).get('rtvrtm', {})
            
            # Create a temporary config file for the plugin
            plugin_dir = os.path.dirname(__file__)
            config_path = os.path.join(plugin_dir, 'config.json')
            
            # Write the config from instance settings to the config file
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            # Load and initialize the RTVRTM plugin
            RTVRTMPlugin = load_rtvrtm_plugin()
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log("RTVRTM: Initializing RTVRTM plugin...")
            
            self.rtvrtm_plugin_instance = RTVRTMPlugin(self.instance, config_path)
            
            # Register RTVRTM as a service with MBIIEZ process handler
            if hasattr(self.instance, 'process_handler'):
                self.instance.process_handler.register_service("RTVRTM Service", self.start_rtvrtm_service)
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: Registered as service with MBIIEZ process handler")
            else:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: WARNING - No process_handler found, falling back to manual start")
                # Fallback to the previous method if process_handler is not available
                self.start_rtvrtm_service()
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Plugin registered with status: {self.rtvrtm_plugin_instance.status()}")

            if hasattr(self.instance, 'event_handler'):
                self.instance.event_handler.register_event("before_launch_server", self.before_dedicated_server_launch)
                self.instance.event_handler.register_event("before_debug_launch_server", self.before_dedicated_server_launch)
                self.instance.event_handler.register_event("after_debug_launch_server", self.after_dedicated_server_launch)
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: Registered launch debug hooks")
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error during registration: {e}")
                # Add full traceback for debugging
                import traceback
                self.instance.log_handler.log(f"RTVRTM: Full traceback: {traceback.format_exc()}")
            if hasattr(self.instance, 'exception_handler') and self.instance.exception_handler:
                self.instance.exception_handler.log(e)
    
    def start_rtvrtm_service(self):
        """Start the RTVRTM service - called by MBIIEZ service manager"""
        try:
            if self.rtvrtm_plugin_instance:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: Starting RTVRTM service...")
                
                # This will be managed by MBIIEZ service system
                self.rtvrtm_plugin_instance.start_rtvrtm_service()
                
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: Service started successfully")
                    
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error starting service: {e}")
                import traceback
                self.instance.log_handler.log(f"RTVRTM: Service traceback: {traceback.format_exc()}")

    def player_chat_command(self, data):
        """Handle player chat commands for RTVRTM"""
        # RTVRTM handles its own commands through log monitoring
        # This is just a placeholder for future enhancements
        pass

    def before_dedicated_server_launch(self, data):
        """Called before server starts"""
        try:
            if self.rtvrtm_plugin_instance:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    cmd = data.get('cmd', '') if isinstance(data, dict) else ''
                    mode = data.get('mode', 'unknown') if isinstance(data, dict) else 'unknown'
                    working_directory = data.get('working_directory', '') if isinstance(data, dict) else ''
                    server_config_path = data.get('server_config_path', '') if isinstance(data, dict) else ''
                    self.instance.log_handler.log(
                        "RTVRTM: Launch hook mode={} cwd={} config={} cmd={}".format(
                            mode,
                            working_directory,
                            server_config_path,
                            cmd,
                        )
                    )
                    if hasattr(self.rtvrtm_plugin_instance, 'cfg_path'):
                        rtvrtm_script = os.path.join(os.path.dirname(__file__), 'rtvrtm_original.py')
                        self.instance.log_handler.log(
                            "RTVRTM: Command: {} {} -c {}".format(
                                sys.executable,
                                rtvrtm_script,
                                self.rtvrtm_plugin_instance.cfg_path,
                            )
                        )
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error in before_dedicated_server_launch: {e}")

    def after_dedicated_server_launch(self, data):
        """Called after server starts"""
        try:
            if self.rtvrtm_plugin_instance:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    status = self.rtvrtm_plugin_instance.status()
                    returncode = data.get('returncode', 'unknown') if isinstance(data, dict) else 'unknown'
                    self.instance.log_handler.log(f"RTVRTM: Status after debug launch (returncode={returncode}): {status}")
                    
                # Check if the process is actually running (service might be managed differently)
                if hasattr(self.rtvrtm_plugin_instance, 'rtvrtm_process') and self.rtvrtm_plugin_instance.rtvrtm_process:
                    pid = self.rtvrtm_plugin_instance.rtvrtm_process.pid
                    poll_result = self.rtvrtm_plugin_instance.rtvrtm_process.poll()
                    self.instance.log_handler.log(f"RTVRTM: Process PID: {pid}, Poll result: {poll_result}")
                    
                    if poll_result is not None:
                        self.instance.log_handler.log(f"RTVRTM: WARNING - Process has exited with code: {poll_result}")
                elif hasattr(self.rtvrtm_plugin_instance, 'running') and self.rtvrtm_plugin_instance.running:
                    self.instance.log_handler.log("RTVRTM: Service is running (managed by MBIIEZ service system)")
                else:
                    self.instance.log_handler.log("RTVRTM: Service not yet started or no process found")
                    
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error checking status: {e}")
                import traceback
                self.instance.log_handler.log(f"RTVRTM: Traceback: {traceback.format_exc()}")

    def new_log_line(self, data):
        """Log line handler - RTVRTM monitors logs directly"""
        # RTVRTM monitors the log file directly, so we don't need to process here
        # This could be used for additional monitoring if needed
        pass

    def map_change(self, data):
        """Handle map changes"""
        try:
            if self.rtvrtm_plugin_instance:
                map_name = data.get('map_name', 'unknown')
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"RTVRTM: Map changed to {map_name}")
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error handling map change: {e}")

    def player_connects(self, data):
        """Handle player connections"""
        # RTVRTM handles player tracking through log monitoring
        pass

    def player_disconnects(self, data):
        """Handle player disconnections"""
        # RTVRTM handles player tracking through log monitoring
        pass
    
    def stop(self):
        """Stop the RTVRTM plugin"""
        try:
            if self.rtvrtm_plugin_instance:
                self.rtvrtm_plugin_instance.stop()
                self.rtvrtm_plugin_instance = None
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("RTVRTM: Plugin stopped and cleaned up")
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"RTVRTM: Error during cleanup: {e}")
