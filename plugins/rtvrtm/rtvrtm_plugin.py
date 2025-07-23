#!/usr/bin/env python3
"""
RTVRTM Plugin for MBIIEZ
Rock the Vote/Rock the Mode plugin that runs the original RTVRTM script
while integrating with the MBIIEZ plugin system.
"""

import os
import json
import threading
import subprocess
import sys
import time
from pathlib import Path

def Plugin(instance, config_path):
    """
    RTVRTM Plugin entry point for MBIIEZ
    
    Args:
        instance: MBIIEZ instance object
        config_path: Path to the plugin configuration file
    
    Returns:
        Plugin instance
    """
    return RTVRTMPlugin(instance, config_path)

class RTVRTMPlugin:
    def __init__(self, instance, config_path):
        self.instance = instance
        self.config_path = config_path
        self.config = self.load_config()
        self.rtvrtm_process = None
        self.running = False
        
        # Generate config and map files
        self.setup_rtvrtm_files()
        
        # Start RTVRTM in a separate thread
        self.start_rtvrtm()
    
    def load_config(self):
        """Load the JSON configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.instance.log(f"RTVRTM: Error loading config: {e}")
            return {}
    
    def setup_rtvrtm_files(self):
        """Generate .cfg and map files from JSON config with instance name prefix"""
        try:
            # Get MBII folder path from MBIIEZ instance automatically
            mbii_folder = self.instance.config['server']['home_path']
            
            # Create file names with instance prefix
            instance_name = self.instance.name
            cfg_filename = f"{instance_name}_rtvrtm.cfg"
            maps_filename = f"{instance_name}_maps.txt"
            secondary_maps_filename = f"{instance_name}_secondary_maps.txt"
            
            # Full paths
            self.cfg_path = os.path.join(mbii_folder, cfg_filename)
            self.maps_path = os.path.join(mbii_folder, maps_filename)
            self.secondary_maps_path = os.path.join(mbii_folder, secondary_maps_filename)
            
            # Generate .cfg file
            self.generate_cfg_file()
            
            # Generate maps files
            self.generate_maps_files()
            
            self.instance.log(f"RTVRTM: Generated config files in {mbii_folder}")
            self.instance.log(f"RTVRTM: Config file: {cfg_filename}")
            self.instance.log(f"RTVRTM: Maps file: {maps_filename}")
            self.instance.log(f"RTVRTM: Secondary maps file: {secondary_maps_filename}")
            
        except Exception as e:
            self.instance.log(f"RTVRTM: Error setting up files: {e}")
    
    def generate_cfg_file(self):
        """Generate the RTVRTM .cfg file from JSON configuration"""
        
        # Get automatic values from MBIIEZ instance
        instance_name = self.instance.name
        mbii_folder = self.instance.config['server']['home_path']
        port = self.instance.config['server']['port']
        rcon_password = self.instance.config['security']['rcon_password']
        log_file = f"{instance_name}-games.log"
        
        # Build address and bind automatically
        address = f"127.0.0.1:{port}"
        bind = "127.0.0.1"
        
        cfg_content = """*** Configuration file for RTV/RTM. ***
*** All field names are case-insensitive. ***
*** This does not apply to all field values however. ***
*** Please read carefully the description of each field. ***

************************************************************
*                     General settings                     *
************************************************************

* Path of the log file.
Log: {log}

* Path of the MBII folder.
MBII folder: {mbii_folder}

* Server address (IP/Host:Port).
Address: {address}

* Bind IP address.
Bind: {bind}

* Server rcon password.
Password: {password}

* Flood protection (in seconds).
Flood protection: {flood_protection}

* Use say only.
Use say only: {use_say_only}

* Name protection.
Name protection: {name_protection}

* Default game.
Default game: {default_game}

* Clean log.
Clean log: {clean_log}

************************************************************
*                  Admin voting settings                   *
************************************************************

* Admin voting.
Admin voting: {admin_voting}

* Admin minimum votes.
Admin minimum votes: {admin_minimum_votes}

* Admin skip voting.
Admin skip voting: {admin_skip_voting}

************************************************************
*                   Map limit settings                     *
************************************************************

* Roundlimit.
Roundlimit: {roundlimit}

* Timelimit.
Timelimit: {timelimit}

* Map limit voting.
Limit voting: {limit_voting}

* Map limit minimum votes.
Limit minimum votes: {limit_minimum_votes}

* Map limit extend.
Limit extend: {limit_extend}

* Map limit successful wait time.
Limit successful wait time: {limit_successful_wait_time}

* Map limit failed wait time.
Limit failed wait time: {limit_failed_wait_time}

* Map limit skip voting.
Limit skip voting: {limit_skip_voting}

* Map limit second turn.
Limit second turn: {limit_second_turn}

* Map limit change immediately.
Limit change immediately: {limit_change_immediately}

************************************************************
*                 Rock the Vote settings                   *
************************************************************

* RTV.
RTV: {rtv}

* RTV rate.
RTV rate: {rtv_rate}

* RTV voting.
RTV voting: {rtv_voting}

* RTV minimum votes.
RTV minimum votes: {rtv_minimum_votes}

* RTV extend.
RTV extend: {rtv_extend}

* RTV successful wait time.
RTV successful wait time: {rtv_successful_wait_time}

* RTV failed wait time.
RTV failed wait time: {rtv_failed_wait_time}

* RTV skip voting.
RTV skip voting: {rtv_skip_voting}

* RTV second turn.
RTV second turn: {rtv_second_turn}

* RTV change immediately.
RTV change immediately: {rtv_change_immediately}

************************************************************
*                     Map settings                         *
************************************************************

* Automatic maps.
Automatic maps: {automatic_maps}

* Maps.
Maps: {maps_file}

* Secondary maps.
Secondary maps: {secondary_maps_file}

* Pick secondary maps.
Pick secondary maps: {pick_secondary_maps}

* Map priority.
Map priority: {map_priority}

* Nomination type.
Nomination type: {nomination_type}

* Enable recently played maps.
Enable recently played maps: {enable_recently_played_maps}

************************************************************
*                 Rock the Mode settings                   *
************************************************************

* RTM.
RTM: {rtm}

* Mode priority.
Mode priority: {mode_priority}

* RTM rate.
RTM rate: {rtm_rate}

* RTM voting.
RTM voting: {rtm_voting}

* RTM minimum votes.
RTM minimum votes: {rtm_minimum_votes}

* RTM extend.
RTM extend: {rtm_extend}

* RTM successful wait time.
RTM successful wait time: {rtm_successful_wait_time}

* RTM failed wait time.
RTM failed wait time: {rtm_failed_wait_time}

* RTM skip voting.
RTM skip voting: {rtm_skip_voting}

* RTM second turn.
RTM second turn: {rtm_second_turn}

* RTM change immediately.
RTM change immediately: {rtm_change_immediately}
""".format(
            # Automatic values from MBIIEZ instance
            log=log_file,
            mbii_folder=mbii_folder,
            address=address,
            bind=bind,
            password=rcon_password,
            
            # Configuration values from JSON (with defaults)
            flood_protection=self.config.get('general', {}).get('flood_protection', 0.5),
            use_say_only=self.config.get('general', {}).get('use_say_only', 0),
            name_protection=self.config.get('general', {}).get('name_protection', 1),
            default_game=self.config.get('general', {}).get('default_game', ''),
            clean_log=self.config.get('general', {}).get('clean_log', '0'),
            
            # Admin voting
            admin_voting=self.config.get('admin_voting', {}).get('admin_voting', '1 30'),
            admin_minimum_votes=self.config.get('admin_voting', {}).get('admin_minimum_votes', 51.0),
            admin_skip_voting=self.config.get('admin_voting', {}).get('admin_skip_voting', 1),
            
            # Map limit settings
            roundlimit=self.config.get('map_limit', {}).get('roundlimit', 1),
            timelimit=self.config.get('map_limit', {}).get('timelimit', 0),
            limit_voting=self.config.get('map_limit', {}).get('limit_voting', '1 10'),
            limit_minimum_votes=self.config.get('map_limit', {}).get('limit_minimum_votes', 51.0),
            limit_extend=self.config.get('map_limit', {}).get('limit_extend', '1 3'),
            limit_successful_wait_time=self.config.get('map_limit', {}).get('limit_successful_wait_time', 300),
            limit_failed_wait_time=self.config.get('map_limit', {}).get('limit_failed_wait_time', 60),
            limit_skip_voting=self.config.get('map_limit', {}).get('limit_skip_voting', 1),
            limit_second_turn=self.config.get('map_limit', {}).get('limit_second_turn', 1),
            limit_change_immediately=self.config.get('map_limit', {}).get('limit_change_immediately', 0),
            
            # RTV settings
            rtv=self.config.get('rtv', {}).get('rtv', 1),
            rtv_rate=self.config.get('rtv', {}).get('rtv_rate', 60.0),
            rtv_voting=self.config.get('rtv', {}).get('rtv_voting', '1 10'),
            rtv_minimum_votes=self.config.get('rtv', {}).get('rtv_minimum_votes', 51.0),
            rtv_extend=self.config.get('rtv', {}).get('rtv_extend', '1 3'),
            rtv_successful_wait_time=self.config.get('rtv', {}).get('rtv_successful_wait_time', 300),
            rtv_failed_wait_time=self.config.get('rtv', {}).get('rtv_failed_wait_time', 60),
            rtv_skip_voting=self.config.get('rtv', {}).get('rtv_skip_voting', 1),
            rtv_second_turn=self.config.get('rtv', {}).get('rtv_second_turn', 1),
            rtv_change_immediately=self.config.get('rtv', {}).get('rtv_change_immediately', 0),
            
            # Map settings
            automatic_maps=self.config.get('maps', {}).get('automatic_maps', 0),
            maps_file=self.maps_path,
            secondary_maps_file=self.secondary_maps_path,
            pick_secondary_maps=self.config.get('maps', {}).get('pick_secondary_maps', 5),
            map_priority=self.config.get('maps', {}).get('map_priority', '2 1 0'),
            nomination_type=self.config.get('maps', {}).get('nomination_type', 1),
            enable_recently_played_maps=self.config.get('maps', {}).get('enable_recently_played_maps', 3600),
            
            # RTM settings
            rtm=self.config.get('rtm', {}).get('rtm', 7),
            mode_priority=self.config.get('rtm', {}).get('mode_priority', '2 1 0 2 1 0'),
            rtm_rate=self.config.get('rtm', {}).get('rtm_rate', 60.0),
            rtm_voting=self.config.get('rtm', {}).get('rtm_voting', '1 10'),
            rtm_minimum_votes=self.config.get('rtm', {}).get('rtm_minimum_votes', 51.0),
            rtm_extend=self.config.get('rtm', {}).get('rtm_extend', '1 3'),
            rtm_successful_wait_time=self.config.get('rtm', {}).get('rtm_successful_wait_time', 300),
            rtm_failed_wait_time=self.config.get('rtm', {}).get('rtm_failed_wait_time', 60),
            rtm_skip_voting=self.config.get('rtm', {}).get('rtm_skip_voting', 1),
            rtm_second_turn=self.config.get('rtm', {}).get('rtm_second_turn', 1),
            rtm_change_immediately=self.config.get('rtm', {}).get('rtm_change_immediately', 0)
        )
        
        with open(self.cfg_path, 'w') as f:
            f.write(cfg_content)
    
    def generate_maps_files(self):
        """Generate the maps.txt and secondary_maps.txt files from JSON configuration"""
        # Primary maps
        primary_maps = self.config.get('primary_maps', [])
        with open(self.maps_path, 'w') as f:
            for map_name in primary_maps:
                f.write(f"{map_name}\n")
        
        # Secondary maps
        secondary_maps = self.config.get('secondary_maps', [])
        with open(self.secondary_maps_path, 'w') as f:
            for map_name in secondary_maps:
                f.write(f"{map_name}\n")
    
    def start_rtvrtm(self):
        """Start the RTVRTM script in a separate thread"""
        def run_rtvrtm():
            try:
                self.running = True
                plugin_dir = os.path.dirname(__file__)
                rtvrtm_script = os.path.join(plugin_dir, 'rtvrtm_original.py')
                
                self.instance.log(f"RTVRTM: Starting RTVRTM script with config: {self.cfg_path}")
                
                # Run the original RTVRTM script with the generated config file
                self.rtvrtm_process = subprocess.Popen([
                    sys.executable, rtvrtm_script, '-c', self.cfg_path
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                # Monitor the process
                stdout, stderr = self.rtvrtm_process.communicate()
                
                if self.rtvrtm_process.returncode != 0:
                    self.instance.log(f"RTVRTM: Process exited with code {self.rtvrtm_process.returncode}")
                    if stderr:
                        self.instance.log(f"RTVRTM: Error: {stderr}")
                
                self.running = False
                
            except Exception as e:
                self.instance.log(f"RTVRTM: Error running script: {e}")
                self.running = False
        
        # Start RTVRTM in a separate thread
        self.rtvrtm_thread = threading.Thread(target=run_rtvrtm, daemon=True)
        self.rtvrtm_thread.start()
    
    def stop(self):
        """Stop the RTVRTM plugin"""
        if self.rtvrtm_process and self.rtvrtm_process.poll() is None:
            self.instance.log("RTVRTM: Stopping RTVRTM process...")
            self.rtvrtm_process.terminate()
            
            # Wait for process to terminate
            try:
                self.rtvrtm_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.rtvrtm_process.kill()
                self.rtvrtm_process.wait()
        
        self.running = False
        self.instance.log("RTVRTM: Plugin stopped")
    
    def reload_config(self):
        """Reload the configuration and restart RTVRTM"""
        self.instance.log("RTVRTM: Reloading configuration...")
        self.stop()
        time.sleep(1)
        self.config = self.load_config()
        self.setup_rtvrtm_files()
        self.start_rtvrtm()
    
    def status(self):
        """Get plugin status"""
        if self.running and self.rtvrtm_process and self.rtvrtm_process.poll() is None:
            return "Running"
        else:
            return "Stopped"

# Plugin metadata
__plugin_name__ = "RTVRTM"
__plugin_version__ = "3.6c"
__plugin_description__ = "Rock the Vote/Rock the Mode plugin for MBII servers"
__plugin_author__ = "klax / Cthulhu (Python3 port + MBIIEZ integration)"
