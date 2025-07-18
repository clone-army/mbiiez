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
                # Process lines directly instead of using queue
                self._process_line_safe(line)

        except Exception as e:
            self.instance.exception_handler.log(e)    
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
        Process a single log line directly
        """   
        self._process_line_safe(last_line)
        
    def _safe_split(self, text, delimiter, expected_parts=None, description=""):
        """
        Safely split text and validate the result
        """
        try:
            parts = text.split(delimiter)
            if expected_parts and len(parts) < expected_parts:
                self.instance.log_handler.log("Warning: Expected {} parts when splitting {} by '{}', got {} - Line: {}".format(
                    expected_parts, description, delimiter, len(parts), text[:100]))
                return None
            return parts
        except Exception as e:
            self.instance.log_handler.log("Error splitting {} by '{}': {} - Line: {}".format(
                description, delimiter, str(e), text[:100]))
            return None
    
    def _safe_extract_substring(self, text, start_marker, end_marker, description=""):
        """
        Safely extract substring between markers
        """
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return None
            start_idx += len(start_marker)
            
            end_idx = text.find(end_marker, start_idx)
            if end_idx == -1:
                return None
                
            return text[start_idx:end_idx]
        except Exception as e:
            self.instance.log_handler.log("Error extracting {} from text: {} - Line: {}".format(
                description, str(e), text[:100]))
            return None
        
    def _process_line_safe(self, last_line):
        """
        Safely processes a log line with comprehensive error handling
        """   
        try:
            # Always log the line first
            self.log(last_line)
            
            # Process chat messages
            if ': say: ' in last_line and 'server:' not in last_line:
                self._process_chat_message(last_line, is_team=False)
                    
            elif ': sayteam: ' in last_line:
                self._process_chat_message(last_line, is_team=True)
                
            elif 'Kill:' in last_line:
                self._process_kill_message(last_line)
                
            elif 'ClientConnect:' in last_line:
                self._process_client_connect(last_line)

            elif 'ClientDisconnect:' in last_line:
                self._process_client_disconnect(last_line)
                 
            elif 'ClientBegin:' in last_line:
                self._process_client_begin(last_line)

            elif 'ShutdownGame:' in last_line:              
                self.instance.event_handler.run_event("new_round", {"data": last_line})  

            elif 'ClientUserinfoChanged' in last_line:
                self.instance.event_handler.run_event("player_info_change",{"data": last_line})

            elif "SMOD command (" in last_line:
                self._process_smod_command(last_line)

            elif "SMOD say:" in last_line:
                self._process_smod_say(last_line)

            elif "Successful SMOD login by" in last_line:
                self._process_smod_login(last_line)

        except Exception as e:
            self.instance.log_handler.log("Critical error processing log line: {} - Line: {}".format(str(e), last_line[:100]))
            self.instance.exception_handler.log(e)
    
    def _process_chat_message(self, last_line, is_team=False):
        """Process chat messages with simplified but robust parsing for MBII logs"""
        try:
            chat_keyword = ": sayteam: " if is_team else ": say: "
            
            # MBII log format: "TIMESTAMP PLAYER_ID: say: PLAYER_NAME: \"MESSAGE\""
            # Example: "  0:28 0: say: CA^8[212]^7CE-Ricks: \"!rtv\""
            
            # Split by the chat keyword first
            if chat_keyword not in last_line:
                return
            
            # Split the line into parts by colon
            parts = last_line.split(":")
            if len(parts) < 5:  # Now we need at least 5 parts due to the extra space
                self.instance.log_handler.log("Not enough parts in chat line: {}".format(last_line[:100]))
                return
            
            # For chat: parts[0] = timestamp, parts[1] = player_id, parts[2] = " say", parts[3] = " player_name", parts[4+] = message
            
            # Extract player name (remove leading/trailing whitespace)
            if len(parts) >= 4:
                player_name_raw = parts[3].strip()
            else:
                self.instance.log_handler.log("Cannot extract player name from chat: {}".format(last_line[:100]))
                return
            
            # Extract message (join remaining parts and remove quotes)
            if len(parts) >= 5:
                message_parts = parts[4:]
                message_with_quotes = ":".join(message_parts).strip()
                
                # Remove surrounding quotes if present
                if message_with_quotes.startswith(' "') and message_with_quotes.endswith('"'):
                    message = message_with_quotes[2:-1]  # Remove ' "' at start and '"' at end
                elif message_with_quotes.startswith('"') and message_with_quotes.endswith('"'):
                    message = message_with_quotes[1:-1]  # Remove quotes
                else:
                    message = message_with_quotes.strip()
            else:
                self.instance.log_handler.log("Cannot extract message from chat: {}".format(last_line[:100]))
                return
            
            # Clean player name for database storage
            player_clean = self._clean_player_name(player_name_raw)
            
            # Validate extracted data
            if not player_clean.strip():
                self.instance.log_handler.log("Empty player name after cleaning: '{}' from line: {}".format(player_name_raw, last_line[:100]))
                return
            
            if not message.strip():
                self.instance.log_handler.log("Empty message from line: {}".format(last_line[:100]))
                return
            
            # Get player ID safely
            try:
                player_id = connection().get_player_id_from_name(player_clean)
            except Exception:
                player_id = None
            
            # Log successful parsing for debugging
            self.instance.log_handler.log("Chat parsed - Player: '{}' Message: '{}'".format(player_clean, message[:50]))
            
            # Determine event type and trigger
            if message.startswith("!") and not is_team:
                # Command event
                self.instance.log_handler.log("Triggering player_chat_command event for message: '{}'".format(message))
                self.instance.event_handler.run_event("player_chat_command", {
                    "message": message, 
                    "player_id": player_id, 
                    "player": player_clean,
                    "player_raw": player_name_raw
                })
            else:
                # Regular chat event
                event_name = "player_chat_team" if is_team else "player_chat"
                chat_type_str = "TEAM" if is_team else "PUBLIC"
                self.instance.log_handler.log("Triggering {} event for message: '{}'".format(event_name, message))
                self.instance.event_handler.run_event(event_name, {
                    "type": chat_type_str, 
                    "message": message, 
                    "player_id": player_id, 
                    "player": player_clean,
                    "player_raw": player_name_raw
                })
                
        except Exception as e:
            self.instance.log_handler.log("Error processing {} message: {} - Line: {}".format(
                "team chat" if is_team else "chat", str(e), last_line[:100]))
    
    def _clean_player_name(self, player_name):
        """Remove color codes and clean player name for database storage"""
        try:
            if not player_name:
                return ""
            
            # Remove Quake 3 color codes (^0-^9 and some letters)
            import re
            cleaned = re.sub(r'\^[0-9a-zA-Z]', '', player_name)
            
            # Remove control characters and extra whitespace
            cleaned = ''.join(char for char in cleaned if ord(char) >= 32)
            cleaned = cleaned.strip()
            
            # If cleaning resulted in empty string, try to extract something useful
            if not cleaned and player_name:
                # Extract alphanumeric characters and basic punctuation
                cleaned = re.sub(r'[^\w\-\[\]() ]', '', player_name).strip()
            
            return cleaned if cleaned else "Unknown"
            
        except Exception as e:
            # If cleaning fails completely, return a safe fallback
            return "Unknown"
    
    def _process_chat_fallback(self, last_line, is_team, after_marker):
        """Fallback chat parsing when quote-based parsing fails"""
        try:
            # Try the old split-based approach as fallback
            line_parts = self._safe_split(last_line, ":", expected_parts=4, description="chat fallback")
            if line_parts is None or len(line_parts) < 4:
                self.instance.log_handler.log("Fallback parsing failed - insufficient parts: {}".format(last_line[:100]))
                return
            
            # Try to extract player and message from the parts
            if len(line_parts) >= 4:
                player = self._clean_player_name(line_parts[3].strip())
                
                # Message might be in parts[4] or might be spread across multiple parts
                if len(line_parts) >= 5:
                    message_parts = line_parts[4:]
                    message = ":".join(message_parts).strip()
                    
                    # Remove quotes if present
                    if message.startswith('"') and message.endswith('"') and len(message) > 1:
                        message = message[1:-1]
                else:
                    message = ""
                
                if player and message:
                    try:
                        player_id = connection().get_player_id_from_name(player)
                    except Exception:
                        player_id = None
                    
                    # Trigger events
                    if message.startswith("!") and not is_team:
                        self.instance.event_handler.run_event("player_chat_command", {
                            "message": message, "player_id": player_id, "player": player
                        })
                    else:
                        event_name = "player_chat_team" if is_team else "player_chat"
                        chat_type_str = "TEAM" if is_team else "PUBLIC"
                        self.instance.event_handler.run_event(event_name, {
                            "type": chat_type_str, "message": message, "player_id": player_id, "player": player
                        })
                        
        except Exception as e:
            self.instance.log_handler.log("Fallback chat parsing also failed: {} - Line: {}".format(str(e), last_line[:100]))
    
    def _process_kill_message(self, last_line):
        """Process kill messages safely"""
        try:
            line_parts = self._safe_split(last_line, ":", expected_parts=4, description="kill message")
            if line_parts is None:
                return
                
            frag_info = line_parts[3]
            
            # Check if the format contains " by " and " killed "
            if " by " not in frag_info or " killed " not in frag_info:
                self.instance.log_handler.log("Invalid kill message format - Line: {}".format(last_line[:100]))
                return
            
            by_parts = self._safe_split(frag_info, " by ", expected_parts=2, description="kill weapon")
            if by_parts is None:
                return
                
            weapon = by_parts[1].strip()
            players_part = by_parts[0].strip()
            
            killed_parts = self._safe_split(players_part, " killed ", expected_parts=2, description="kill players")
            if killed_parts is None:
                return
                
            fragger = killed_parts[0].strip()
            fragged = killed_parts[1].strip()
            
            # Handle self-kills and world kills
            if fragger == fragged or "<world>" in fragger:
                fragger = "SELF"
            
            # Run player killed event    
            self.instance.event_handler.run_event("player_killed", {
                "fragger": fragger, "fragged": fragged, "weapon": weapon
            })
            
        except Exception as e:
            self.instance.log_handler.log("Error processing kill message: {} - Line: {}".format(str(e), last_line[:100]))
    
    def _process_client_connect(self, last_line):
        """Process client connect messages safely"""
        try:
            # Extract player name
            player = self._safe_extract_substring(last_line, "(", ")", "player name")
            if player is None:
                player = "Unknown"

            # Extract player ID
            player_id = self._safe_extract_substring(last_line, "ID: ", " ", "player ID")
            if player_id is None:
                player_id = "0"

            # Extract IP address
            ip_with_port = self._safe_extract_substring(last_line, "IP: ", ")", "IP address")
            if ip_with_port:
                ip = ip_with_port.split(':')[0] if ':' in ip_with_port else ip_with_port
            else:
                ip = "Unknown"

            self.instance.event_handler.run_event("player_connected", {
                "ip": ip, "player_id": player_id, "player": player
            })               
            self.instance.event_handler.run_event("player_ip", {
                "ip": ip, "player_id": player_id
            })
            
        except Exception as e:
            self.instance.log_handler.log("Error processing client connect: {} - Line: {}".format(str(e), last_line[:100]))

    def _process_client_disconnect(self, last_line):
        """Process client disconnect messages safely"""
        try:
            line_parts = self._safe_split(last_line, ":", expected_parts=3, description="client disconnect")
            if line_parts is None:
                return
                
            player_id = line_parts[2][1:] if len(line_parts[2]) > 1 else "0"
            
            self.instance.event_handler.run_event("player_disconnected", {
                "ip": "", "player_id": player_id, "player": ""
            })
            
        except Exception as e:
            self.instance.log_handler.log("Error processing client disconnect: {} - Line: {}".format(str(e), last_line[:100]))

    def _process_client_begin(self, last_line):
        """Process client begin messages safely"""
        try:
            line_parts = self._safe_split(last_line, ":", expected_parts=3, description="client begin")
            if line_parts is None:
                return
                
            player_id = line_parts[2][1:] if len(line_parts[2]) > 1 else "0"
            
            self.instance.event_handler.run_event("player_begin", {
                "player_id": player_id, "player": ""
            })
            
        except Exception as e:
            self.instance.log_handler.log("Error processing client begin: {} - Line: {}".format(str(e), last_line[:100]))

    def _process_smod_command(self, last_line):
        """Process SMOD command messages safely"""
        try:
            match = re.search(r'SMOD command \((.*?)\) executed by (.+?)\(adminID: (\d+)\) \(IP: (.+?)\)', last_line)
            if match:
                command = match.group(1)
                admin = match.group(2).strip()
                admin_id = match.group(3)
                ip = match.group(4)
                self.instance.event_handler.run_event("smod_command", {
                    "command": command, "admin": admin, "admin_id": admin_id, "ip": ip
                })
        except Exception as e:
            self.instance.log_handler.log("Error processing SMOD command: {} - Line: {}".format(str(e), last_line[:100]))

    def _process_smod_say(self, last_line):
        """Process SMOD say messages safely"""
        try:
            match = re.search(r'SMOD say: (.+?) \(adminID: (\d+)\) \(IP: (.+?)\) : (.+)', last_line)
            if match:
                admin = match.group(1).strip()
                admin_id = match.group(2)
                ip = match.group(3)
                message = match.group(4).strip()
                self.instance.event_handler.run_event("smod_say", {
                    "admin": admin, "admin_id": admin_id, "ip": ip, "message": message
                })
        except Exception as e:
            self.instance.log_handler.log("Error processing SMOD say: {} - Line: {}".format(str(e), last_line[:100]))

    def _process_smod_login(self, last_line):
        """Process SMOD login messages safely"""
        try:
            match = re.search(r'Successful SMOD login by (.+?) \(adminID: (\d+)\) \(IP: (.+?)\)', last_line)
            if match:
                admin = match.group(1).strip()
                admin_id = match.group(2)
                ip = match.group(3)
                self.instance.event_handler.run_event("smod_login", {
                    "admin": admin, "admin_id": admin_id, "ip": ip
                })
        except Exception as e:
            self.instance.log_handler.log("Error processing SMOD login: {} - Line: {}".format(str(e), last_line[:100]))

  
