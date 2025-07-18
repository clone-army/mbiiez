from mbiiez.bcolors import bcolors
from mbiiez.process import process
from mbiiez.db import db
import os
import datetime
import time
import subprocess

import asyncio
import inspect


class event_handler:

    instance = None

    events = {}

    def __init__(self, instance):
        self.instance = instance
    
    def register_event(self, event_name, func):
        if(not event_name in self.events):
            self.events[event_name] = []
        
        self.events[event_name].append(func)
        
    def run_event(self, event_name, args = None):

        if(event_name in self.events):
            for event in self.events[event_name]:
                try: 
                    if(args == None):
                        
                        if inspect.iscoroutinefunction(event):
                            asyncio.run(event())
                        else:
                            event()
                        
                    else:
                    
                        if inspect.iscoroutinefunction(event):
                            asyncio.run(event(args))
                        else:
                            event(args)
                         
                except Exception as e:
                    self.instance.exception_handler.log(e)

    # Designed to allow server to restart after a given number of hours automatically providing its empty
    def restarter(self):
        try:
            restart_hours = self.instance.config['server']['restart_instance_every_hours']
            
            # Validate configuration
            if not isinstance(restart_hours, (int, float)) or restart_hours <= 0:
                self.instance.log_handler.log("Invalid restart_instance_every_hours config: {}. Scheduled restarter disabled.".format(restart_hours))
                return
                
            self.instance.log_handler.log("Scheduled restarter started. Restart interval: {} hours".format(restart_hours))
            
            while(True):
                next_restart = datetime.datetime.now() + datetime.timedelta(hours=restart_hours)
                self.instance.log_handler.log("Next scheduled restart will be at: {}".format(next_restart.strftime("%Y-%m-%d %H:%M:%S")))
                
                time.sleep(restart_hours * 60 * 60)
                self.instance.log_handler.log("Attempting scheduled restart")
                
                # If Server is not empty when due to restart, then check every 10 minutes
                while(not self.instance.is_empty()):
                    self.instance.log_handler.log("Server not empty, restart postponed for 10 minutes...")
                    time.sleep(600)
                    
                # Does the restart using subprocess for better control and logging
                try:
                    self.instance.log_handler.log("Server is empty, executing restart command")
                    result = subprocess.run(
                        ["mbii", "-i", self.instance.name, "restart"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        self.instance.log_handler.log("Scheduled restart command executed successfully")
                        if result.stdout:
                            self.instance.log_handler.log("Restart output: {}".format(result.stdout.strip()))
                    else:
                        self.instance.log_handler.log("Scheduled restart command failed with exit code: {}".format(result.returncode))
                        if result.stderr:
                            self.instance.log_handler.log("Restart error: {}".format(result.stderr.strip()))
                            
                except subprocess.TimeoutExpired:
                    self.instance.log_handler.log("Scheduled restart command timed out after 60 seconds")
                except Exception as restart_error:
                    self.instance.log_handler.log("Error executing scheduled restart: {}".format(str(restart_error)))
                    
        except Exception as e:
            self.instance.log_handler.log("Critical error in scheduled restarter: {}".format(str(e)))
            self.instance.exception_handler.log(e)    
        

    # Internal Events
    # These are methods used by MBII to record internal events

    def player_chat_command(self, args):
        return
    
    def player_chat(self, args):
        d = {"added": str(datetime.datetime.now()), "player":args['player'], "instance": self.instance.name, "type": "PUBLIC", "message": args['message']}
        return db().insert("chatter", d)    
        
    def player_chat_team(self, args):
        d = {"added": str(datetime.datetime.now()), "player":args['player'], "instance": self.instance.name, "type": "TEAM", "message": args['message']}
        return db().insert("chatter", d)    
    
    def player_killed (self, args):
        d = {"added": str(datetime.datetime.now()), "instance": self.instance.name, "fragger": args['fragger'], "fragged": args['fragged'], "weapon": args['weapon']}
        return db().insert("frags", d)
        
    def player_connected (self, args):    
        d = {"added": str(datetime.datetime.now()), "player": args['player'], "player_id": args['player_id'], "instance": self.instance.name, "ip": args['ip'], "type": "CONNECT"}
        return db().insert("connections", d)
    
    def player_disconnected (self, args):  
        d = {"added": str(datetime.datetime.now()), "player": args['player'], "player_id": args['player_id'], "instance": self.instance.name, "ip": args['ip'], "type": "DISCONNECT"}
        return db().insert("connections", d)

    def player_begin (self, args):
        return 
        
    def player_info_change(self, args):
        try:
            game_classes = [
                "None",
                "Storm Trooper",
                "Solder",
                "Commander",
                "Elite Solder",
                "Sith",
                "Jedi",
                "Bounty Hunter",
                "Hero",
                "Super Battle Droid",
                "Wookie",
                "Deka",
                "Clone",
                "Mando",
                "Arc Trooper"
            ]    
        
            line = args['data']
            
            # Safe parsing of player info line
            line_parts = line.split(" ")
            if len(line_parts) < 3:
                self.instance.log_handler.log("Invalid player info line format - not enough space-separated parts: {}".format(line[:100]))
                return
            
            info_split = line.split("\\")
            if len(info_split) < 20:
                self.instance.log_handler.log("Invalid player info line format - not enough backslash-separated parts: {}".format(line[:100]))
                return
            
            player_id = line_parts[2]
            player = info_split[1] if len(info_split) > 1 else "Unknown"
            model = info_split[5] if len(info_split) > 5 else "Unknown"
            
            try:
                class_id = int(info_split[19]) if len(info_split) > 19 else 0
                class_name = game_classes[class_id] if 0 <= class_id < len(game_classes) else "Unknown"
            except (ValueError, IndexError):
                class_id = 0
                class_name = "Unknown"
     
            d = {"added": str(datetime.datetime.now()), "player": player, "player_id": player_id, "instance": self.instance.name, "class_name": class_name, "class_id": class_id, "model": model}
            return db().insert("player_info", d)
            
        except Exception as e:
            self.instance.log_handler.log("Error processing player info change: {} - Line: {}".format(str(e), args.get('data', '')[:100]))
            self.instance.exception_handler.log(e)    
      
                