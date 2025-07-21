#!/usr/bin/env python3
# Copyright (c) 2012-2013, klax / Cthulhu@GBITnet.com.br
# Copyright (c) 2025, MBIIEZ Team - Python3 Port
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#################################################
#          Movie Battles II RTV/RTM             #
#                                               #
#      Rock the Vote and Rock the Mode tool     #
#      for Jedi Knight: Jedi Academy            #
#      Movie Battles II MOD.                    #
#      Original plugin and idea by:             #
#      AlliedModders LLC. All rights reserved.  #
#################################################

import sys
import os
import re
import time
import math
import random
import socket
import threading
from collections import defaultdict
from datetime import datetime
import argparse
import configparser

VERSION = "3.6c-py3"
CFG = "3.6c"
SLEEP_INTERVAL = 0.075
MAPLIST_MAX_SIZE = 750

def error(msg):
    """Error handling function."""
    print("Failed!\n")
    print(f"ERROR: {msg}")
    if sys.platform == "win32":
        input("Press any key to continue...")
    sys.exit(1)

def warning(msg, rehash=False):
    """Warning function (NON CRITICAL ERROR)."""
    print("Warning!\n")
    print(f"WARNING: {msg}")
    if rehash:
        input("Press any key to continue...")
    print()

class SortableDict(dict):
    """Dictionary subclass that can return sorted items."""
    def sorteditems(self):
        return sorted(self.items(), key=lambda x: x[1], reverse=True)

class DummyTime:
    """Dummy class to be used as a replacement for a float time object returned by time.time() on round-based votings."""
    def __iadd__(self, *args):
        return self

class Config:
    """RTV/RTM configuration class."""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.settings = {}
        self.primary_maps = []
        self.secondary_maps = []
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the custom config format
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('*') and ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    
                    # Skip example values
                    if value.startswith('PATH_TO_') or value.startswith('SERVER_'):
                        continue
                        
                    self.settings[key] = value
                        
        except Exception as e:
            error(f"Could not load config file: {e}")
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.settings.get(key.lower().replace(' ', '_'), default)
    
    def create_maplist(self, bsps):
        """Create maplist from BSP files"""
        self.primary_maps = []
        self.secondary_maps = []
        
        # Load from files if they exist
        maps_file = os.path.join(os.path.dirname(self.config_path), 'maps.txt')
        secondary_file = os.path.join(os.path.dirname(self.config_path), 'secondary_maps.txt')
        
        if os.path.exists(maps_file):
            with open(maps_file, 'r') as f:
                self.primary_maps = [line.strip() for line in f if line.strip()]
        
        if os.path.exists(secondary_file):
            with open(secondary_file, 'r') as f:
                self.secondary_maps = [line.strip() for line in f if line.strip()]

class Rcon:
    """Send commands to the server via rcon. Wrapper class."""
    
    def __init__(self, address, bindaddr, rcon_pwd):
        self.address = address
        self.bindaddr = bindaddr
        self.rcon_pwd = rcon_pwd
        self.host, self.port = address.split(':')
        self.port = int(self.port)
    
    def _send(self, payload, buffer_size=1024):
        """Send command via UDP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if self.bindaddr:
                sock.bind((self.bindaddr, 0))
            sock.settimeout(5)
            
            full_payload = f"\xFF\xFF\xFF\xFFrcon {self.rcon_pwd} {payload}"
            sock.sendto(full_payload.encode('utf-8'), (self.host, self.port))
            
            response = sock.recv(buffer_size)
            sock.close()
            return response.decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Rcon send error: {e}")
            return ""
    
    def say(self, msg):
        """Send say command"""
        return self._send(f'say "{msg}"')
    
    def svsay(self, msg):
        """Send svsay command"""
        return self._send(f'svsay "{msg}"')
    
    def mbmode(self, cmd):
        """Send mode change command"""
        return self._send(f'g_gametype {cmd}')
    
    def map_change(self, mapname):
        """Change map"""
        return self._send(f'map {mapname}')

class Features:
    """Feature (RTV/RTM) handler and container class."""
    
    def __init__(self, svsay):
        self.svsay = svsay
        self.rtv_enabled = True
        self.rtm_enabled = True
    
    def check(self):
        """Check which features are enabled"""
        return self.rtv_enabled, self.rtm_enabled

class RTVRTMServer:
    """Main RTVRTM server class"""
    
    def __init__(self, config_path):
        self.config = Config(config_path)
        self.config.create_maplist([])
        
        # Server connection
        address = self.config.get('address', '127.0.0.1:29070')
        bindaddr = self.config.get('bind', '')
        password = self.config.get('password', '')
        
        if not password:
            error("No rcon password configured")
        
        self.rcon = Rcon(address, bindaddr, password)
        self.features = Features(self.rcon.svsay)
        
        # Log file
        self.log_path = self.config.get('log', '')
        if not self.log_path or self.log_path.startswith('PATH_TO_'):
            error("No log file path configured")
        
        # Vote state
        self.rtv_votes = set()
        self.rtm_votes = set()
        self.rtv_active = False
        self.rtm_active = False
        self.rtv_timer = None
        self.rtm_timer = None
        self.map_votes = {}
        self.mode_votes = {}
        self.map_vote_options = []
        self.mode_vote_options = []
        self.nominations = {}
        self.next_map = None
        self.next_mode = None
        
        # Settings
        self.rtv_percentage = int(self.config.get('rtv_percentage', '50'))
        self.rtm_percentage = int(self.config.get('rtm_percentage', '50'))
        self.rtv_win_percentage = int(self.config.get('rtv_win_percentage', '50'))
        self.rtm_win_percentage = int(self.config.get('rtm_win_percentage', '50'))
        self.rtv_vote_time = int(self.config.get('rtv_vote_time', '30'))
        self.rtm_vote_time = int(self.config.get('rtm_vote_time', '30'))
        self.flood_protection = float(self.config.get('flood_protection', '3'))
        
        # Flood protection
        self.last_command_time = {}
        
        # Player tracking
        self.players = {}
        self.current_map = ""
        self.current_mode = "0"
        
        # Game modes
        self.game_modes = {
            '0': 'Open',
            '1': 'Semi-Authentic', 
            '2': 'Full-Authentic',
            '3': 'Duel',
            '4': 'Legends'
        }
        
        print(f"RTVRTM {VERSION} initialized")
        print(f"Primary maps: {len(self.config.primary_maps)}")
        print(f"Secondary maps: {len(self.config.secondary_maps)}")
    
    def fix_line(self, line):
        """Fix line encoding issues"""
        # Remove color codes and clean up line
        line = re.sub(r'\^[0-9]', '', line)
        return line.strip()
    
    def remove_color(self, text):
        """Remove color codes from text"""
        return re.sub(r'\^[0-9]', '', text)
    
    def get_player_count(self):
        """Get current player count from players dict"""
        return len([p for p in self.players.values() if p.get('connected', False)])
    
    def can_run_command(self, player_id):
        """Check if player can run command (flood protection)"""
        if self.flood_protection <= 0:
            return True
        
        now = time.time()
        last_time = self.last_command_time.get(player_id, 0)
        
        if now - last_time < self.flood_protection:
            return False
        
        self.last_command_time[player_id] = now
        return True
    
    def handle_chat_command(self, player_id, player_name, message):
        """Handle chat commands"""
        if not message.startswith('!'):
            return
        
        cmd = message[1:].lower()
        
        # Check flood protection
        if not self.can_run_command(player_id):
            return
        
        # RTV commands
        if cmd == 'rtv' and self.features.rtv_enabled:
            self.handle_rtv(player_id, player_name)
        elif cmd == 'unrtv' and self.features.rtv_enabled:
            self.handle_unrtv(player_id, player_name)
        elif cmd.startswith('maplist'):
            self.handle_maplist(player_id, cmd)
        elif cmd.startswith('nominate '):
            map_name = cmd[9:]
            self.handle_nominate(player_id, map_name)
        
        # RTM commands
        elif cmd == 'rtm' and self.features.rtm_enabled:
            self.handle_rtm(player_id, player_name)
        elif cmd == 'unrtm' and self.features.rtm_enabled:
            self.handle_unrtm(player_id, player_name)
        elif cmd == 'modelist':
            self.handle_modelist(player_id)
        
        # Vote commands
        elif cmd.isdigit():
            vote_num = int(cmd)
            self.handle_vote(player_id, player_name, vote_num)
    
    def handle_rtv(self, player_id, player_name):
        """Handle RTV command"""
        if player_id in self.rtv_votes:
            return  # Already voted
        
        self.rtv_votes.add(player_id)
        player_count = self.get_player_count()
        required = max(1, math.ceil(player_count * self.rtv_percentage / 100))
        
        self.rcon.say(f"{player_name} wants to rock the vote ({len(self.rtv_votes)}/{required})")
        
        if len(self.rtv_votes) >= required and not self.rtv_active:
            self.start_rtv_vote()
    
    def handle_unrtv(self, player_id, player_name):
        """Handle unRTV command"""
        if player_id in self.rtv_votes:
            self.rtv_votes.remove(player_id)
            player_count = self.get_player_count()
            required = max(1, math.ceil(player_count * self.rtv_percentage / 100))
            self.rcon.say(f"{player_name} removed RTV vote ({len(self.rtv_votes)}/{required})")
    
    def handle_rtm(self, player_id, player_name):
        """Handle RTM command"""
        if player_id in self.rtm_votes:
            return  # Already voted
        
        self.rtm_votes.add(player_id)
        player_count = self.get_player_count()
        required = max(1, math.ceil(player_count * self.rtm_percentage / 100))
        
        self.rcon.say(f"{player_name} wants to rock the mode ({len(self.rtm_votes)}/{required})")
        
        if len(self.rtm_votes) >= required and not self.rtm_active:
            self.start_rtm_vote()
    
    def handle_unrtm(self, player_id, player_name):
        """Handle unRTM command"""
        if player_id in self.rtm_votes:
            self.rtm_votes.remove(player_id)
            player_count = self.get_player_count()
            required = max(1, math.ceil(player_count * self.rtm_percentage / 100))
            self.rcon.say(f"{player_name} removed RTM vote ({len(self.rtm_votes)}/{required})")
    
    def handle_maplist(self, player_id, cmd):
        """Handle maplist command"""
        parts = cmd.split()
        if len(parts) == 2 and parts[1] in ('1', '2'):
            maps = self.config.primary_maps if parts[1] == '1' else self.config.secondary_maps
            if maps:
                # Send in chunks of 5
                for i in range(0, len(maps), 5):
                    chunk = ', '.join(maps[i:i+5])
                    self.rcon.say(f"^2[to {player_id}]^7 {chunk}")
        else:
            self.rcon.say(f"^2[to {player_id}]^7 Usage: !maplist <1|2>")
    
    def handle_modelist(self, player_id):
        """Handle modelist command"""
        modes = list(self.game_modes.values())
        for i in range(0, len(modes), 5):
            chunk = ', '.join(modes[i:i+5])
            self.rcon.say(f"^2[to {player_id}]^7 {chunk}")
    
    def handle_nominate(self, player_id, map_name):
        """Handle nominate command"""
        if map_name in self.config.primary_maps or map_name in self.config.secondary_maps:
            if map_name not in self.nominations:
                self.nominations[map_name] = set()
            self.nominations[map_name].add(player_id)
            self.rcon.say(f"^2[to {player_id}]^7 Nominated {map_name}")
        else:
            self.rcon.say(f"^2[to {player_id}]^7 Unknown map: {map_name}")
    
    def start_rtv_vote(self):
        """Start RTV vote"""
        self.rtv_active = True
        
        # Build vote options from nominations + random maps
        nominated_maps = list(self.nominations.keys())
        remaining_maps = [m for m in self.config.primary_maps if m not in nominated_maps]
        
        # Take up to 4 nominated maps, fill remainder from primary maps
        vote_options = nominated_maps[:4]
        if len(vote_options) < 4 and remaining_maps:
            needed = 4 - len(vote_options)
            vote_options.extend(random.sample(remaining_maps, min(needed, len(remaining_maps))))
        
        self.map_vote_options = vote_options
        self.map_votes = {m: set() for m in self.map_vote_options}
        
        # Show vote options
        options_text = ', '.join(f'{i+1}:{m}' for i, m in enumerate(self.map_vote_options))
        self.rcon.svsay(f'Map vote: {options_text}')
        self.rcon.svsay(f'Vote with !<number>. {self.rtv_vote_time}s remaining.')
        
        # Start vote timer
        self.rtv_timer = threading.Timer(self.rtv_vote_time, self.end_rtv_vote)
        self.rtv_timer.start()
    
    def start_rtm_vote(self):
        """Start RTM vote"""
        self.rtm_active = True
        
        self.mode_vote_options = list(self.game_modes.values())
        self.mode_votes = {m: set() for m in self.mode_vote_options}
        
        # Show vote options
        options_text = ', '.join(f'{i+1}:{m}' for i, m in enumerate(self.mode_vote_options))
        self.rcon.svsay(f'Mode vote: {options_text}')
        self.rcon.svsay(f'Vote with !<number>. {self.rtm_vote_time}s remaining.')
        
        # Start vote timer
        self.rtm_timer = threading.Timer(self.rtm_vote_time, self.end_rtm_vote)
        self.rtm_timer.start()
    
    def handle_vote(self, player_id, player_name, vote_num):
        """Handle numeric vote"""
        if self.rtm_active:
            # RTM vote takes priority
            if 1 <= vote_num <= len(self.mode_vote_options):
                selected_mode = self.mode_vote_options[vote_num - 1]
                
                # Remove from any existing votes
                for votes in self.mode_votes.values():
                    votes.discard(player_id)
                
                # Add to selected mode
                self.mode_votes[selected_mode].add(player_id)
                vote_count = len(self.mode_votes[selected_mode])
                
                self.rcon.say(f'{player_name} voted for {selected_mode} ({vote_count})')
        
        elif self.rtv_active:
            # RTV vote
            if 1 <= vote_num <= len(self.map_vote_options):
                selected_map = self.map_vote_options[vote_num - 1]
                
                # Remove from any existing votes
                for votes in self.map_votes.values():
                    votes.discard(player_id)
                
                # Add to selected map
                self.map_votes[selected_map].add(player_id)
                vote_count = len(self.map_votes[selected_map])
                
                self.rcon.say(f'{player_name} voted for {selected_map} ({vote_count})')
    
    def end_rtv_vote(self):
        """End RTV vote"""
        self.rcon.svsay('RTV vote ended')
        
        player_count = self.get_player_count()
        required = max(1, math.ceil(player_count * self.rtv_win_percentage / 100))
        
        if not self.map_votes:
            self.rcon.svsay('No votes received')
            self.next_map = None
        else:
            vote_counts = {m: len(votes) for m, votes in self.map_votes.items()}
            max_votes = max(vote_counts.values())
            
            if max_votes < required:
                self.rcon.svsay('Not enough votes to change map')
                self.next_map = None
            else:
                winners = [m for m, count in vote_counts.items() if count == max_votes]
                winner = random.choice(winners)
                self.rcon.svsay(f'Map will change to {winner} next round')
                self.next_map = winner
        
        self.reset_rtv()
    
    def end_rtm_vote(self):
        """End RTM vote"""
        self.rcon.svsay('RTM vote ended')
        
        player_count = self.get_player_count()
        required = max(1, math.ceil(player_count * self.rtm_win_percentage / 100))
        
        if not self.mode_votes:
            self.rcon.svsay('No votes received')
            self.next_mode = None
        else:
            vote_counts = {m: len(votes) for m, votes in self.mode_votes.items()}
            max_votes = max(vote_counts.values())
            
            if max_votes < required:
                self.rcon.svsay('Not enough votes to change mode')
                self.next_mode = None
            else:
                winners = [m for m, count in vote_counts.items() if count == max_votes]
                winner = random.choice(winners)
                # Convert mode name to number
                mode_num = None
                for num, name in self.game_modes.items():
                    if name == winner:
                        mode_num = num
                        break
                
                self.rcon.svsay(f'Mode will change to {winner} next round')
                self.next_mode = mode_num
        
        self.reset_rtm()
    
    def reset_rtv(self):
        """Reset RTV state"""
        self.rtv_votes.clear()
        self.rtv_active = False
        if self.rtv_timer:
            self.rtv_timer.cancel()
            self.rtv_timer = None
        self.map_vote_options = []
        self.map_votes = {}
        self.nominations.clear()
    
    def reset_rtm(self):
        """Reset RTM state"""
        self.rtm_votes.clear()
        self.rtm_active = False
        if self.rtm_timer:
            self.rtm_timer.cancel()
            self.rtm_timer = None
        self.mode_vote_options = []
        self.mode_votes = {}
    
    def apply_map_change(self):
        """Apply pending map change"""
        if self.next_map:
            self.rcon.svsay(f'Changing map to {self.next_map}')
            self.rcon.map_change(self.next_map)
            self.next_map = None
    
    def apply_mode_change(self):
        """Apply pending mode change"""
        if self.next_mode:
            mode_name = self.game_modes.get(self.next_mode, 'Unknown')
            self.rcon.svsay(f'Changing mode to {mode_name}')
            self.rcon.mbmode(self.next_mode)
            self.next_mode = None
    
    def parse_log_line(self, line):
        """Parse a log file line"""
        line = self.fix_line(line)
        
        # Player connection
        if 'ClientConnect:' in line:
            match = re.search(r'ClientConnect: (\d+)', line)
            if match:
                player_id = match.group(1)
                self.players[player_id] = {'connected': True, 'name': ''}
        
        # Player disconnect
        elif 'ClientDisconnect:' in line:
            match = re.search(r'ClientDisconnect: (\d+)', line)
            if match:
                player_id = match.group(1)
                if player_id in self.players:
                    self.players[player_id]['connected'] = False
                
                # Remove from votes
                self.rtv_votes.discard(player_id)
                self.rtm_votes.discard(player_id)
                for votes in self.map_votes.values():
                    votes.discard(player_id)
                for votes in self.mode_votes.values():
                    votes.discard(player_id)
        
        # Player info
        elif 'ClientUserinfoChanged:' in line:
            match = re.search(r'ClientUserinfoChanged: (\d+) n\\([^\\]+)', line)
            if match:
                player_id = match.group(1)
                player_name = self.remove_color(match.group(2))
                if player_id in self.players:
                    self.players[player_id]['name'] = player_name
        
        # Chat messages
        elif 'say:' in line:
            match = re.search(r'say: ([^:]+): (.+)', line)
            if match:
                player_name = self.remove_color(match.group(1))
                message = match.group(2)
                
                # Find player ID by name
                player_id = None
                for pid, pinfo in self.players.items():
                    if pinfo.get('name') == player_name and pinfo.get('connected'):
                        player_id = pid
                        break
                
                if player_id:
                    self.handle_chat_command(player_id, player_name, message)
        
        # Round start/end
        elif 'InitGame:' in line:
            # Apply any pending changes
            self.apply_map_change()
            self.apply_mode_change()
        
        # Map change
        elif 'Loading map:' in line:
            match = re.search(r'Loading map: (.+)', line)
            if match:
                self.current_map = match.group(1)
    
    def run(self):
        """Main run loop"""
        print("Starting RTVRTM log monitoring...")
        
        # Open log file
        try:
            with open(self.log_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Seek to end
                f.seek(0, 2)
                
                while True:
                    line = f.readline()
                    if line:
                        self.parse_log_line(line)
                    else:
                        time.sleep(SLEEP_INTERVAL)
        
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            error(f"Error reading log file: {e}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='RTVRTM Server for MBII')
    parser.add_argument('config', nargs='?', default='rtvrtm.cfg', 
                        help='Configuration file path')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config):
        error(f"Configuration file not found: {args.config}")
    
    server = RTVRTMServer(args.config)
    server.run()

if __name__ == "__main__":
    main()
