import shutil
import sys, getopt
import os
import subprocess
import re
import urllib.request
import shlex
import psutil
import time
import prettytable

from mbiiez.bcolors import bcolors
from mbiiez.helpers import helpers
from mbiiez.testing import testing
from mbiiez.conf import conf
from mbiiez.console import console
from mbiiez.db import db
from mbiiez.launcher import launcher
from mbiiez.log_handler import log_handler
from mbiiez.exception_handler import exception_handler
from mbiiez.process_handler import process_handler
from mbiiez.event_handler import event_handler
from mbiiez.plugin_handler import plugin_handler
from mbiiez.models import chatter, log
from mbiiez import settings

# An Instance of MBII                        
class instance:

    name = None
    config = None
    external_ip = None
    console = None
    conf = None
    db = None
    
    log_handler = None
    exception_handler = None
    event_handler = None
    process_handler = None
    plugin_handler = None
    launcher = None
    
    # Constructor
    def __init__(self, name):
    
        self.name = name
        self.external_ip = urllib.request.urlopen('https://www.myexternalip.com/raw').read().decode()       

        self.start_cmd = None

        # Generate Config for this instance 
        self.conf = conf(self.name, settings)       
        self.config = self.conf.config

        if(self.config == None):
            print("No Instance config for {}".format(name))
            exit()
            
        self.plugins = self.config['plugins']
        self.plugins_registered = []

        self.log_handler = log_handler(self)
        self.exception_handler = exception_handler(self)
        self.process_handler = process_handler(self)
        self.launcher = launcher(self)
        self.event_handler = event_handler(self)        
        self.db = db()
        
        # Create a UDP / RCON Client
        self.console = console(self.config['security']['rcon_password'], str(self.config['server']['port']))
        
        # Load Internal Services
        self.services_internal()

        # Load Internal Events
        self.events_internal()

        #Load Plugins
        self.plugin_hander = plugin_handler(self)
        
        ''' Add any configs to external plugins if they are enabled '''    
        if(self.has_plugin("auto_message")):
            self.config['plugins']['auto_message']['messages'].append("This server is powered by MBIIEZ, visit bit.ly/2JhJRpO")    

    def services_internal(self):
        ''' Internal Services we wish to start on an instance start ''' 

        ''' Runs the Dedicated OpenJK Server ''' 
        cmd = "{} --quiet +set dedicated 2 +set net_port {} +set fs_game {} +set fs_homepath {} +exec {}".format(self.config['server']['engine'], self.config['server']['port'], self.get_game(), self.config['server']['home_path'], self.config['server']['server_config_file']);       

        self.start_cmd = cmd
        
        #print(bcolors.CYAN + cmd  + bcolors.ENDC )  
        print()  
      
        self.process_handler.register_service("OpenJK", cmd, 1) 
        
        ''' Log Watcher Service ''' 
        self.process_handler.register_service("Log Watcher", self.log_handler.log_watcher)
        
        ''' Restarter Service '''
        self.process_handler.register_service("Scheduled Restarter", self.event_handler.restarter)

            
    def events_internal(self):
        ''' Events we wish to run internal methods on '''
        self.event_handler.register_event("player_chat_command", self.event_handler.player_chat_command)
        self.event_handler.register_event("player_chat", self.event_handler.player_chat)
        self.event_handler.register_event("player_chat_team", self.event_handler.player_chat_team)
        self.event_handler.register_event("player_killed", self.event_handler.player_killed)       
        self.event_handler.register_event("player_connected", self.event_handler.player_connected)               
        self.event_handler.register_event("player_disconnected", self.event_handler.player_disconnected)       
        self.event_handler.register_event("player_begin", self.event_handler.player_begin)          
        self.event_handler.register_event("player_info_change", self.event_handler.player_info_change)          
        return
        
    # Use netstat to get the port used by this instance
    def get_port(self):  
        port = 0
        response =  os.system("netstat -tulpn | grep {}".format(settings.dedicated.engine))
        for item in response.splitlines():
            if settings.dedicated.engine in item:
                port = item.split()[3].split(":")[1];   

        if(int(port) > 0):
            return str(port)  

        return None  

    # Is the chosen engine running an instance
    def get_ded_engine_status(self):  

        response =  os.system('ps ax | grep {}'.format(settings.dedicated.engine))
        for item in response.splitlines():
            if(settings.dedicated.engine in item):
                return(True) 
                
        return False  

    # Run an RCON command
    def rcon(self, command):
        print(self.console.rcon(str(command), False))
        
     # Return an RCON command
    def rconResponse(self, command):
        return(self.console.rcon(str(command), False))       
       
    # Run a console command
    def cmd(self, command):
        print(self.console.console(str(command), False))      
       
    # Get / Set a CVAR
    def cvar(self, key, value = None):
       return self.console.cvar(key, value)   
       
    # Run an SVSAY command
    def say(self, message):
        self.console.say(message)
        # Log to logs table
        log().new(f"Server: {message}", self.name)
        # Log to chatter table as PUBLIC
        chatter().new("Server", self.name, "PUBLIC", message)

    # Run an SVTELL command
    def tell(self, player_id, message):
        self.console.tell(player_id, message)
        # Log to logs table
        log().new(f"Server -> {player_id}: {message}", self.name)
        # Log to chatter table as TELL
        chatter().new("Server", self.name, "TELL", message)
       
    # Get / Set current map
    def map(self, map_name = None):
    
         if(not map_name == None):
            self.console.rcon("map " + map_name, True)
            print("Map change requested to {}".format(map_name))
            return True
         else:
            try:
                server_map = self.cvar("mapname")
               
            except:
                server_map = "Error while fetching"
            
            return server_map        
        
    # Get / Set current mode
    def mode(self, mode = None):   

        if(not mode == None):
            self.cvar("mbmode", mode)
            self.console.rcon("mbmode " + mode,True)
            print("Mode change requested to Mode {}".format(mode))
            return True
        else:   
            mode = self.cvar("g_authenticity")

        try:
            
            #0 = Open mode, 1 = Semi-Authentic, 2 = Full-Authentic, 3 = Duel, 4 = Legends
            if(mode == "0"):
                return "Open"
            if(mode == "1"):
                return "Semi-Authentic"
            if(mode == "2"):
                return "Full-Authentic"
            if(mode == "3"):
                return "Duel"
            if(mode == "4"):                
                return "Legends"     
                    
        except:
           mode = "Error while fetching"
        
        return mode  

    # Server uptime as a string
    def uptime(self):

        uptime = "unknown"      
        result = subprocess.run(['ps', 'aux'], stdout=subprocess.PIPE)
        output = str(result.stdout.decode())
        
        for item in output.splitlines():
            if(self.config['server']['server_config_file'] in item):
                uptime = (item.split()[9])      

        return uptime 
 
    # Kick a player
    def kick(self, player):
        self.console.rcon("kick " + player)
        
    # Ban a player    
    def ban(self, ip):
        self.console.rcon("addip " + ip)
       
    # Unban a player
    def unban(self, ip):
        self.console.rcon("removeip " + ip)
       
    # List banned players
    def listbans(self):
        self.console.rcon("g_banips")
           
    # True / False is server empty       
    def is_empty(self):
        if(self.players_count() > 0):
            return False
        else:
            return True
           
    # Int of the number of players in game        
    def players_count(self):
        return len(self.players())
            
    # Get Details about a specific player        
    def player(self,id):
        dump = self.console.rcon(f"dumpuser {id}")
        print(dump)
        return dump
            
    # Get list of players in game - Avoid client for quickness
    def players(self):
        """
        Get list of players in game - robustly parse status output using the last ^7 as player name delimiter.
        """
        players = []
        status = self.console.rcon("status notrunc")
        if not status:
            return []
        lines = status.split("\n")
        # Remove everything before the player table (find the last 'cl score ping name' header)
        start_idx = 0
        for idx, line in enumerate(lines):
            if line.strip().startswith("cl score ping name"):
                start_idx = idx + 2  # skip header and dashes
        player_lines = [l for l in lines[start_idx:] if l.strip() and not l.strip().startswith('print')]
        for line in player_lines:
            if len(line.strip()) < 5:
                continue
            last_caret = line.rfind('^7')
            if last_caret == -1:
                continue
            before_name = line[:last_caret+2].rstrip()  # include ^7
            after_name = line[last_caret+2:].strip()
            # before_name: cl, score, ping, name (with color codes and spaces)
            # after_name: ip:port rate
            parts = before_name.split()
            if len(parts) < 4:
                continue
            cl = parts[0]
            score = parts[1]
            ping = parts[2]
            name = ' '.join(parts[3:])
            if not after_name:
                continue
            ip_rate = after_name.split()
            if len(ip_rate) < 2:
                continue
            ip = ip_rate[0].split(':')[0]
            rate = ip_rate[1]
            try:
                ping_int = int(ping)
                if ping_int < 100:
                    ping_color = f"{bcolors.GREEN}{ping}{bcolors.ENDC}"
                elif ping_int < 200:
                    ping_color = f"{bcolors.YELLOW}{ping}{bcolors.ENDC}"
                else:
                    ping_color = f"{bcolors.RED}{ping}{bcolors.ENDC}"
            except Exception:
                ping_color = ping
            players.append({
                "id": cl,
                "score": score,
                "ping": ping_color,
                "name": bcolors().color_convert(name),
                "name_raw": name,  # Keep original with ^-codes for web interface
                "ip": ip,
                "rate": rate
            })
        return players
            
    # Print the server log
    def log(self):
        print("do to")
        
    # Run an automated test on a number of things printing results
    def test(self):
        output = []

        lookup = helpers().ip_info()
        output.append(f"Server IP {self.external_ip}")
        output.append(f"Server Location {lookup['region']}")
        output.append("-------------------------------------------")
        output.append("CA Central: " + testing().ping_test("35.182.0.251"))
        output.append("EU East: " + testing().ping_test("35.178.0.253"))
        output.append("EU Central: " + testing().ping_test("18.196.0.253"))
        output.append("EU West: " + testing().ping_test("34.240.0.253"))
        output.append("US WEST: " + testing().ping_test("52.52.63.252"))
        output.append("US EAST: " + testing().ping_test("35.153.128.254"))
        output.append("-------------------------------------------")
        output.append(f"CPU Usage: {psutil.cpu_percent()}%")
        output.append(f"Memory Usage: {psutil.virtual_memory().percent}%")

        final_output = "\n".join(output)
        print(final_output)  # Print all at once
        return final_output 
         
    # Start this instance
    def start(self):
    
        if(self.server_running()):
             print(bcolors.OK + "Instance is already running" + bcolors.ENDC)
             return;
   
        # Generate our configs
        self.conf.generate_server_config()
        
        # Can Instance Can Start?
        if(os.path.exists(self.config['server']['server_config_path'])): 

            # Reason to Bail  
            if(not os.path.isfile("{}/{}".format("/usr/bin", self.config['server']['engine']))):        
                self.log_handler.log(bcolors.RED + "Failed to start. No engine found at {}/{}".format("/usr/bin", self.config['server']['engine']) + bcolors.ENDC)   
                print(bcolors.FAIL + "[Error] " + bcolors.ENDC + "Failed to start. No engine found at {}/{}".format("/usr/bin", self.config['server']['engine']))
                exit()
                
            # Make sure can be executed    
            os.system("chmod +x {}/{}".format("/usr/bin", self.config['server']['engine']))  
              
            # Sym Links
            if(os.path.exists("/root/.local/share/openjk")):
                if(not os.path.islink("/root/.local/share/openjk")):
                    shutil.rmtree("/root/.local/share/openjk")       
                    os.symlink(settings.locations.game_path, "/root/.local/share/openjk")
            
            if(os.path.exists("/root/.ja")):
                if(not os.path.islink("/root/.ja")):
                    shutil.rmtree("/root/.ja")       
                    os.symlink(settings.locations.game_path, "/root/.ja")  
        
                           
            self.event_handler.run_event("before_launch_server")
            self.process_handler.launch_services()
     
      
        else:
            print(bcolors.FAIL + "[Error] " + bcolors.ENDC + "Unable to Load a SERVER config at " + self.config['server']['server_config_path'])
            print(bcolors.FAIL + "Unable to proceed without a valid Server Config File" + bcolors.ENDC)
            
    def server_running(self):
    
        if(self.process_handler.process_status_name("OpenJK")):
            return True
        else:
            return False
                
        
    def has_plugin(self, plugin_name):
    
        if(plugin_name in self.config['plugins']):
            return True
        else:
            return False
            
    def get_game(self):
    
         # Allows GAME override using JSON
        game = settings.dedicated.game
        
        if("game" in self.config['server'].keys()):           
            game = self.config['server']['game']
            
        return game    
                
    # Instance Status Information
    def status(self):
        """
        Return all status information as a dictionary for programmatic use.
        """
        info = {
            "instance_name": self.name,
            "server_name": bcolors().color_convert(self.config['server']['host_name']),
            "game": self.get_game(),
            "engine": self.config['server']['engine'],
            "port": self.config['server']['port'],
            "full_address": f"{self.external_ip}:{self.config['server']['port']}",
            "mode": self.mode(None),
            "map": self.map(None),
            "plugins": self.plugins_registered,
            "uptime": self.uptime(),
            # Use player['name'] for web, not player['player']
            "players": self.players(),
            "players_count": self.players_count(),
            # Only include minimal info for services to avoid recursion
            "services": [
                {
                    "name": row["name"],
                    "running": self.process_handler.process_status_pid(row["pid"])
                }
                for row in db().select("processes", {"instance": self.name})
            ],
            "server_running": self.server_running(),
        }
        return info

    def status_print(self):
        """
        Return status as a text block for CLI or Discord bot.
        """
        info = self.status()
        output = []
        output.append("------------------------------------")
        if info['server_running']:
            output.append(f"{bcolors.CYAN}Instance Name: {bcolors.ENDC}{info['instance_name']}")
            output.append(f"{bcolors.CYAN}Server Name: {bcolors.ENDC}{info['server_name']}")
            output.append(f"{bcolors.CYAN}Game: {bcolors.ENDC}{info['game']}")
            output.append(f"{bcolors.CYAN}Engine: {bcolors.ENDC}{info['engine']}")
            output.append(f"{bcolors.CYAN}Port: {bcolors.ENDC}{info['port']}")
            output.append(f"{bcolors.CYAN}Full Address: {bcolors.ENDC}{info['full_address']}")
            output.append(f"{bcolors.CYAN}Mode: {bcolors.ENDC}{info['mode']}")
            output.append(f"{bcolors.CYAN}Map: {bcolors.ENDC}{info['map']}")
            output.append(f"{bcolors.CYAN}Plugins: {bcolors.ENDC}{','.join(info['plugins'])}")
            output.append(f"{bcolors.CYAN}Uptime: {bcolors.ENDC}{info['uptime']}")
            output.append(f"{bcolors.CYAN}Version: {bcolors.ENDC}{self.version()}")

            if info['players_count'] > 0:
                output.append(f"{bcolors.CYAN}Players: {bcolors.ENDC}{bcolors.GREEN}{info['players_count']}/32{bcolors.ENDC}")
            else:
                output.append(f"{bcolors.CYAN}Players: {bcolors.ENDC}{bcolors.RED}{info['players_count']}/32{bcolors.ENDC}")
        else:
            output.append(f"{bcolors.RED}Server is not running.{bcolors.ENDC}")
        output.append("------------------------------------")
        for service in info['services']:
            if service['running']:
                output.append(f"[{bcolors.GREEN}Yes{bcolors.ENDC}] {service['name']} Running")
            else:
                output.append(f"[{bcolors.RED}No{bcolors.ENDC}] {service['name']} Running")
        if info['server_running']:
            if info['players_count'] > 0:
                try:
                    import prettytable
                    x = prettytable.PrettyTable()
                    x.field_names = ["ID", "Ping", "IP", "Name"]
                    for player in info['players']:
                        x.add_row([
                            player.get('id', ''),
                            player.get('ping', ''),
                            player.get('ip', ''),
                            player.get('name', '')
                        ])
                    output.append(str(x))
                except Exception:
                    output.append("[Error displaying player table]")
            else:
                output.append("-------------------------------------------")
                output.append(f"{bcolors.RED}No one is playing{bcolors.ENDC}")
            output.append("-------------------------------------------")
        return "\n".join(output)


    def version(self):
        """Return the MBII version string from RCON 'gamename'."""
        try:
            return self.cvar('gamename')
        except Exception:
            return "Unknown"


 # Stop the instance
    def stop(self, force = False):
    
        if(self.server_running()):   
            players = self.players()
            confirm = 'n'
            
            # Check if we're being called from a web interface context
            # by checking if stdin is not a TTY (terminal)
            import sys
            is_web_context = not sys.stdin.isatty()
            
            if len(players) >= 2 and not force and not is_web_context:
                confirm = input(bcolors.RED + "There are more than 2 active players. Are you sure you want to stop the instance? (y/n): " + bcolors.ENDC).lower()

            if len(players) < 2 or confirm == 'y' or is_web_context:
                self.process_handler.stop_all()

                if os.path.exists(self.config['server']['log_path']):
                    os.remove(self.config['server']['log_path'])
        else:
            self.process_handler.stop_all()
       
    # Stop then start the instance
    def restart(self):     
        self.stop()
        time.sleep(2)
        self.start()    