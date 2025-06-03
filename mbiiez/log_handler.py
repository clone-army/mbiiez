"""
Log Handler: Handles logging, reading from log file and logging to database

Requires: An Instance

"""

import datetime
import tailer
import time
import re
import os
import random
from mbiiez.helpers import helpers

from mbiiez.models import chatter, log, frag, connection


class log_handler:
    
    instance = None

    def __init__(self, instance):
        self.instance = instance
        self.log_file = self.instance.config['server']['log_path']


    def log_await(self):
        x = 0
        
        SECONDS_TO_WAIT = 10
        MAX = (SECONDS_TO_WAIT * 2)
        
        while(not os.path.exists(self.instance.config['server']['log_path'])):
            if(x > MAX):
                break
            time.sleep(0.5)
            x = x + 1        
        
        if(x >= MAX):
            raise Exception('Dedicated server did not create a log file within 10 seconds')
        else:
            return True


    def log_watcher(self):
        """
        Watches the log file for this instance, and sends lines to be processed
        """   
        self.log_await()
            
        # When / if this process hits a problem, have it auto restart again
        try:
        
            for line in tailer.follow(open(self.instance.config['server']['log_path'])):
                self.instance.log_handler.process(line)

        except Exception as e:
            #self.instance.exception_handler.log(e)    
            self.log_watcher()

    def log_line_count(self):
        """
        Count the current # of lines in the instances log file
        """    
        f = open(self.log_file, 'rb')
        lines = 0
        buf_size = 1024 * 1024
        read_f = f.raw.read

        buf = read_f(buf_size)
        while buf:
            lines += buf.count(b'\n')
            buf = read_f(buf_size)

        return lines


    def log(self, log_line):
        """
        log to database
        """    
        log_line = log_line.lstrip().lstrip()
        log_line = helpers().ansi_strip(log_line)
        log().new(log_line, self.instance.name)
        
    def process(self, last_line):
        """
        Processes a log line in the log file
        """   
        try:
        
            self.log(last_line)
            
            # Was a chat
            if('say:' in last_line):
            
                # Ignore if sent by server
                if('server:' in last_line):
                    return
                
                player = last_line.split(":")[3].strip()
                message = last_line.split(":")[4].strip()[1:-1]
                player_id = connection().get_player_id_from_name(player)
                # Run command event
                if(message.startswith("!")):                 
                    self.instance.event_handler.run_event("player_chat_command",{"message": message, "player_id": player_id, "player": player})
                     
                else:     
                    # Run chat event     
                    self.instance.event_handler.run_event("player_chat",{"type": "PUBLIC", "message": message, "player_id": player_id, "player": player})  
                    
            if('sayteam:' in last_line):
                player = last_line.split(":")[3].strip().lstrip()
                message = last_line.split(":")[4].strip()[1:-1]
                player_id = connection().get_player_id_from_name(player)
                
                # Run chat event     
                self.instance.event_handler.run_event("player_chat_team",{"type": "TEAM", "message": message, "player_id": player_id, "player": player})  
                
            if('Kill:' in last_line):
                frag_info = last_line.split(":")[3]
                weapon = frag_info.split(" by ")[1]
                players = frag_info.split(" by ")[0]
                fragger = players.split(" killed ")[0].lstrip()
                fragged = players.split(" killed ")[1].rstrip()
                
                if(fragger == fragged or "<world>" in fragger):
                    fragger = "SELF"
                
                # Run player killed event    
                self.instance.event_handler.run_event("player_killed",{"fragger": fragger, "fragged": fragged, "weapon": weapon})  

            if 'ClientConnect:' in last_line:
                # Extract player name
                player_name_start = last_line.find('(') + 1
                player_name_end = last_line.find(')', player_name_start)
                player = last_line[player_name_start:player_name_end]

                # Extract player ID
                player_id_start = last_line.find('ID: ') + len('ID: ')
                player_id_end = last_line.find(' ', player_id_start)
                player_id = last_line[player_id_start:player_id_end]

                # Extract IP address
                ip_start = last_line.find('IP: ') + len('IP: ')
                ip_end = last_line.find(')', ip_start)
                ip_with_port = last_line[ip_start:ip_end]

                # Remove the port from the IP address
                ip = ip_with_port.split(':')[0]

                self.instance.event_handler.run_event("player_connected", {"ip": ip, "player_id": player_id, "player": player})               
                self.instance.event_handler.run_event("player_ip", {"ip": ip, "player_id": player_id})

            if('ClientDisconnect:' in last_line):
                player = ""
                player_id = last_line.split(":")[2][1:]
                ip = ""
                self.instance.event_handler.run_event("player_disconnected",{"ip": ip, "player_id": player_id, "player": player})
                 
                
            if('ClientBegin:' in last_line):
                player = ""
                player_id = last_line.split(":")[2][1:]                  
                self.instance.event_handler.run_event("player_begin",{"player_id": player_id, "player": player})  
              
            if('InitGame:' in last_line):              
                self.instance.event_handler.run_event("new_round", {"data": last_line})  

            if('ClientUserinfoChanged' in last_line):
                self.instance.event_handler.run_event("player_info_change",{"data": last_line})

        except Exception as e:
            self.instance.exception_handler.log(e)

  
