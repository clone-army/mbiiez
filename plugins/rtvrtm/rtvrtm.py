''' 
RTVRTM Plugin for MBIIEZ
Rock the Vote/Rock the Mode plugin that integrates the original RTVRTM script
with the MBIIEZ plugin system while preserving exact functionality.

The plugin automatically gets these values from MBIIEZ instance:
- MBII folder path (from server.home_path)
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
            "pick_secondary_maps": 5,
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

def player_chat_command(instance, data, config):
    """Handle player chat commands for RTVRTM"""
    # RTVRTM handles its own commands through log monitoring
    # This is just a placeholder for future enhancements
    pass

def before_dedicated_server_launch(instance, data, config):
    """Initialize RTVRTM plugin before server starts"""
    try:
        if not hasattr(instance, 'rtvrtm_plugin'):
            # Create a temporary config file for the plugin
            plugin_dir = os.path.dirname(__file__)
            config_path = os.path.join(plugin_dir, 'config.json')
            
            # Write the config from instance settings to the config file
            plugin_config = config if config else {}
            with open(config_path, 'w') as f:
                json.dump(plugin_config, f, indent=4)
            
            # Load and initialize the RTVRTM plugin
            RTVRTMPlugin = load_rtvrtm_plugin()
            instance.rtvrtm_plugin = RTVRTMPlugin(instance, config_path)
            instance.log(f"RTVRTM: Plugin initialized with status: {instance.rtvrtm_plugin.status()}")
        
    except Exception as e:
        instance.log(f"RTVRTM: Error during initialization: {e}")
        import traceback
        instance.log(f"RTVRTM: Traceback: {traceback.format_exc()}")

def after_dedicated_server_launch(instance, data, config):
    """RTVRTM is already running - log status"""
    try:
        if hasattr(instance, 'rtvrtm_plugin'):
            status = instance.rtvrtm_plugin.status()
            instance.log(f"RTVRTM: Status after server launch: {status}")
    except Exception as e:
        instance.log(f"RTVRTM: Error checking status: {e}")

def new_log_line(instance, data, config):
    """Log line handler - RTVRTM monitors logs directly"""
    # RTVRTM monitors the log file directly, so we don't need to process here
    # This could be used for additional monitoring if needed
    pass

def map_change(instance, data, config):
    """Handle map changes"""
    try:
        if hasattr(instance, 'rtvrtm_plugin'):
            map_name = data.get('map_name', 'unknown')
            instance.log(f"RTVRTM: Map changed to {map_name}")
    except Exception as e:
        instance.log(f"RTVRTM: Error handling map change: {e}")

def player_connects(instance, data, config):
    """Handle player connections"""
    # RTVRTM handles player tracking through log monitoring
    pass

def player_disconnects(instance, data, config):
    """Handle player disconnections"""
    # RTVRTM handles player tracking through log monitoring
    pass

# Plugin cleanup function (called when plugin is stopped)
def stop_plugin(instance):
    """Stop the RTVRTM plugin"""
    try:
        if hasattr(instance, 'rtvrtm_plugin'):
            instance.rtvrtm_plugin.stop()
            delattr(instance, 'rtvrtm_plugin')
            instance.log("RTVRTM: Plugin stopped and cleaned up")
    except Exception as e:
        instance.log(f"RTVRTM: Error during cleanup: {e}")

# Plugin metadata
__plugin_name__ = "RTVRTM"
__plugin_version__ = "3.6c"
__plugin_description__ = "Rock the Vote/Rock the Mode plugin for MBII servers"
__plugin_author__ = "klax / Cthulhu (Python3 port + MBIIEZ integration)"
