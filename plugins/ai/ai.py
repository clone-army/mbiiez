"""
OpenRouter AI Assistant Plugin for MBIIEZ
A customizable AI assistant that uses OpenRouter.ai to generate responses.
"""

import os
import json
import time
import re
import requests


class plugin:
    plugin_name = "AI Assistant"
    plugin_author = "MBIIEZ Development Team"
    plugin_version = "1.0"
    plugin_url = "https://github.com/clone-army/mbiiez"
    
    def __init__(self, instance):
        self.instance = instance
        self.config = {}
        self.last_response_time = {}
        self.conversation_history = {}
        self.api_key = None
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def register(self):
        """Register the AI Assistant plugin"""
        try:
            # Get plugin configuration - use 'ai' since that's the folder name
            self.config = self.instance.config.get('plugins', {}).get('ai', {})
            
            # Debug logging
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log("AI Assistant: Starting registration...")
                self.instance.log_handler.log(f"AI Assistant: Full plugins config: {self.instance.config.get('plugins', {})}")
                self.instance.log_handler.log(f"AI Assistant: AI config found: {self.config}")
                self.instance.log_handler.log(f"AI Assistant: Enabled value: {self.config.get('enabled', 'NOT_FOUND')}")
            
            if not self.config.get('enabled', False):
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("AI Assistant: Plugin disabled in configuration")
                return
            
            # Validate required configuration
            self.api_key = self.config.get('openrouter_api_key')
            if not self.api_key:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("AI Assistant: ERROR - No OpenRouter API key provided!")
                return
            
            # Set default values
            self.ai_name = self.config.get('ai_name', 'Assistant')
            self.command = self.config.get('command', '!ai')
            self.model = self.config.get('model', 'anthropic/claude-3.5-sonnet')
            self.cooldown = self.config.get('cooldown_seconds', 5)
            self.max_tokens = self.config.get('max_tokens', 150)
            self.temperature = self.config.get('temperature', 0.7)
            self.public_replies = self.config.get('public_replies', True)
            self.death_commentary = self.config.get('death_commentary', True)
            
            # Create unique instance identifier to prevent cross-server issues
            self.instance_id = f"{getattr(self.instance, 'name', 'unknown')}_{id(self.instance)}"
            
            # Build system prompt
            self.system_prompt = self.build_system_prompt()
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Plugin registered as '{self.ai_name}' with command '{self.command}'")
                self.instance.log_handler.log(f"AI Assistant: Using model: {self.model}")
                self.instance.log_handler.log(f"AI Assistant: Instance ID: {self.instance_id}")
                self.instance.log_handler.log(f"AI Assistant: Server name: {getattr(self.instance, 'name', 'Unknown Server')}")
                self.instance.log_handler.log("AI Assistant: Registration completed successfully!")

            self.instance.event_handler.register_event("player_chat_command", self.player_chat_command)
            
            # Register death commentary event if enabled
            if self.death_commentary:
                self.instance.event_handler.register_event("player_killed", self.player_killed)

        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error during registration: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant: Traceback: {traceback.format_exc()}")
    
    def build_system_prompt(self):
        """Build the system prompt from configuration"""
        base_instruction = self.config.get('instruction', 
            f"You are {self.ai_name}, a helpful AI assistant for a Movie Battles II server. "
            "Keep responses brief and friendly."
        )
        
        personality = self.config.get('personality', '')
        if personality:
            base_instruction += f" Personality: {personality}"
        
        # Load game context from external file
        game_context = self.load_game_context()
        
        return base_instruction + "\n\n" + game_context
    
    def load_game_context(self):
        """Load game context from external file"""
        try:
            # Get the directory where this plugin file is located
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            context_file = os.path.join(plugin_dir, 'game_context.txt')
            
            if os.path.exists(context_file):
                with open(context_file, 'r', encoding='utf-8') as f:
                    game_context = f.read().strip()
                    
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Loaded game context from {context_file}")
                    
                return game_context
            else:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Game context file not found at {context_file}, using default")
                
                # Fallback to default context if file doesn't exist
                return self.get_default_game_context()
                
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error loading game context: {e}")
            
            # Fallback to default context on error
            return self.get_default_game_context()
    
    def get_default_game_context(self):
        """Get default game context as fallback"""
        return (
            "Context: You are responding to players on a Movie Battles II server. "
            "Movie Battles II is a Star Wars-themed multiplayer game modification. "
        )
    
    def clean_text_encoding(self, text):
        """Clean up text encoding issues and replace problematic characters"""
        # Dictionary of common Unicode characters that cause issues
        replacements = {
            # Smart quotes
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            # Em/en dashes
            '—': '-',
            '–': '-',
            # Other common problematic characters
            '…': '...',
            '€': 'EUR',
            '£': 'GBP',
            '©': '(c)',
            '®': '(r)',
            '™': '(tm)',
            # Accented characters - replace with basic equivalents
            'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
            'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
            'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
            'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
            'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
            'ý': 'y', 'ÿ': 'y',
            'ñ': 'n',
            'ç': 'c'
        }
        
        # Apply replacements
        cleaned_text = text
        for old_char, new_char in replacements.items():
            cleaned_text = cleaned_text.replace(old_char, new_char)
        
        # Ensure ASCII-safe encoding
        try:
            # Try to encode as ASCII, replacing problematic characters
            cleaned_text = cleaned_text.encode('ascii', 'replace').decode('ascii')
        except Exception:
            # If that fails, remove non-ASCII characters
            cleaned_text = ''.join(char for char in cleaned_text if ord(char) < 128)
        
        return cleaned_text
    
    def get_current_game_state(self):
        """Gather current game state information"""
        try:
            game_state = {
                "current_map": "unknown",
                "players": [],
                "server_info": {
                    "server_name": getattr(self.instance, 'name', 'Unknown Server'),
                    "timestamp": time.time()
                }
            }
            
            # Get current map using MBIIEZ method
            try:
                current_map = self.instance.map()
                if current_map and current_map != "Error while fetching":
                    game_state["current_map"] = current_map
            except Exception as e:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Error getting map: {e}")
            
            # Get player information using MBIIEZ method
            try:
                players_data = self.instance.players()
                for player_data in players_data:
                    player_info = {
                        "id": player_data.get('id', 'Unknown'),
                        "name": player_data.get('name', 'Unknown'),
                        "name_raw": player_data.get('name_raw', ''),
                        "score": player_data.get('score', '0'),
                        "ping": player_data.get('ping', '0'),
                        "ip": player_data.get('ip', 'Unknown'),
                        "rate": player_data.get('rate', '0'),
                        "kills": 0,
                        "deaths": 0,
                        "suicides": 0
                    }
                    
                    # Convert score to int for sorting
                    try:
                        player_info["score_int"] = int(player_info["score"])
                    except:
                        player_info["score_int"] = 0
                    
                    # Try to get kill/death statistics from database
                    try:
                        from mbiiez.models import frag
                        frag_model = frag()
                        kd_stats = frag_model.get_kd(player_info["name"])
                        if kd_stats:
                            player_info["kills"] = kd_stats.get("kills", 0)
                            player_info["deaths"] = kd_stats.get("deaths", 0)
                            player_info["suicides"] = kd_stats.get("suicides", 0)
                    except Exception as stats_error:
                        # Don't log this error as it's not critical and might spam logs
                        pass
                    
                    game_state["players"].append(player_info)
                
                # Sort players by score (descending)
                game_state["players"].sort(key=lambda x: x.get('score_int', 0), reverse=True)
                
            except Exception as e:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Error getting players: {e}")
            
            return game_state
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error getting game state: {e}")
            
            # Return minimal game state on error
            return {
                "current_map": "unknown",
                "players": [],
                "server_info": {"timestamp": time.time()}
            }
    
    def player_chat_command(self, data):
        """Handle player chat commands"""
        try:
            # Debug logging
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Received chat command: {data}")
            
            message = data.get('message', '').strip()
            player_name = data.get('player', 'Unknown')  # Use 'player' not 'player_name'
            player_id = data.get('player_id', 0)
            
            # Debug logging - check what we received
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Received data: {data}")
                self.instance.log_handler.log(f"AI Assistant: Message: '{message}', Player: '{player_name}', PlayerID: '{player_id}'")
            
            # Always get the server-side player ID from current players (ignore database player_id)
            server_player_id = None
            try:
                current_players = self.instance.players()
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Current players list: {current_players}")
                
                for player_info in current_players:
                    player_name_raw = player_info.get('name_raw', '').strip()
                    player_name_clean = player_info.get('name', '').strip()
                    
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"AI Assistant: Checking player - Raw: '{player_name_raw}', Clean: '{player_name_clean}', Looking for: '{player_name}'")
                    
                    # Try multiple matching approaches
                    if (player_name_raw == player_name or 
                        player_name_clean == player_name or
                        player_name_raw.strip() == player_name.strip() or
                        player_name_clean.strip() == player_name.strip()):
                        
                        server_player_id = player_info.get('id')
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"AI Assistant: MATCH! Found server_player_id {server_player_id} for player {player_name}")
                        break
                        
                if server_player_id is None:
                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                        self.instance.log_handler.log(f"AI Assistant: No player ID match found for '{player_name}', will use fallback to say()")
                        
            except Exception as e:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Error looking up server player_id: {e}")
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Final server_player_id: {server_player_id}")
            
            # Check if message starts with our command
            if not message.lower().startswith(self.command.lower()):
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Message doesn't start with command '{self.command}', ignoring")
                return
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Command matched! Processing request from {player_name}")
            
            # Extract the question/prompt
            prompt = message[len(self.command):].strip()
            if not prompt:
                help_msg = f"^6{self.ai_name}: ^7Please ask me something! Example: {self.command} What is the best lightsaber form?"
                if self.public_replies:
                    self.instance.say(help_msg)
                else:
                    if server_player_id is not None:
                        try:
                            self.instance.tell(server_player_id, help_msg)
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Sent help message via tell to server_player_id {server_player_id}")
                        except Exception as e:
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Tell failed, falling back to say: {e}")
                            self.instance.say(help_msg)
                    else:
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"AI Assistant: No server_player_id available, using say for help message")
                        self.instance.say(help_msg)
                return
            
            # Check cooldown
            current_time = time.time()
            # Use server_player_id for cooldown tracking, fallback to player_name if no ID
            cooldown_key = server_player_id if server_player_id is not None else player_name
            
            if cooldown_key in self.last_response_time:
                time_since_last = current_time - self.last_response_time[cooldown_key]
                if time_since_last < self.cooldown:
                    remaining = int(self.cooldown - time_since_last)
                    cooldown_msg = f"^6{self.ai_name}: ^7Please wait {remaining} more seconds before asking another question."
                    
                    if server_player_id is not None:
                        try:
                            self.instance.tell(server_player_id, cooldown_msg)
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Sent cooldown message via tell to server_player_id {server_player_id}")
                        except Exception as e:
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Tell failed for cooldown message, falling back to say: {e}")
                            self.instance.say(f"^6{self.ai_name}: ^7{player_name}, please wait {remaining} more seconds before asking another question.")
                    else:
                        self.instance.say(f"^6{self.ai_name}: ^7{player_name}, please wait {remaining} more seconds before asking another question.")
                    return
            
            # Update cooldown
            self.last_response_time[cooldown_key] = current_time
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Generating response for: '{prompt}'")
            
            # Generate AI response
            response = self.generate_response(player_name, prompt)
            
            if response:
                # Format and send response
                formatted_response = f"^6{self.ai_name}: ^7{response}"
                
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Sending response: {formatted_response}")
                
                # Chunk response if too long
                max_length = 100  # Adjust based on your server settings
                if len(formatted_response) > max_length:
                    chunks = self.chunk_message(formatted_response, max_length)
                    for chunk in chunks:
                        if self.public_replies:
                            self.instance.say(chunk)
                        else:
                            if server_player_id is not None:
                                try:
                                    self.instance.tell(server_player_id, chunk)
                                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                        self.instance.log_handler.log(f"AI Assistant: Sent chunk via tell to server_player_id {server_player_id}")
                                except Exception as e:
                                    if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                        self.instance.log_handler.log(f"AI Assistant: Tell failed for chunk, falling back to say: {e}")
                                    self.instance.say(chunk)
                            else:
                                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                    self.instance.log_handler.log(f"AI Assistant: No server_player_id for chunk, using say")
                                self.instance.say(chunk)
                        time.sleep(0.5)  # Small delay between chunks
                else:
                    if self.public_replies:
                        self.instance.say(formatted_response)
                    else:
                        if server_player_id is not None:
                            try:
                                self.instance.tell(server_player_id, formatted_response)
                                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                    self.instance.log_handler.log(f"AI Assistant: Sent response via tell to server_player_id {server_player_id}")
                            except Exception as e:
                                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                    self.instance.log_handler.log(f"AI Assistant: Tell failed for response, falling back to say: {e}")
                                self.instance.say(formatted_response)
                        else:
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: No server_player_id for response, using say")
                            self.instance.say(formatted_response)
            else:
                error_msg = f"^6{self.ai_name}: ^7I'm having trouble thinking right now. Please try again later!"
                if self.public_replies:
                    self.instance.say(error_msg)
                else:
                    if server_player_id is not None:
                        try:
                            self.instance.tell(server_player_id, error_msg)
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Sent error message via tell to server_player_id {server_player_id}")
                        except Exception as e:
                            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                                self.instance.log_handler.log(f"AI Assistant: Tell failed for error message, falling back to say: {e}")
                            self.instance.say(error_msg)
                    else:
                        if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                            self.instance.log_handler.log(f"AI Assistant: No server_player_id for error message, using say")
                        self.instance.say(error_msg)
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("AI Assistant: No response generated, sent error message")
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error in chat command: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant: Chat command traceback: {traceback.format_exc()}")
    
    def player_killed(self, data):
        """Handle player deaths and comment on silly deaths"""
        if not self.death_commentary:
            return
            
        try:
            # Extract data using the correct field names from MBIIEZ event_handler
            fragger = data.get('fragger', 'Unknown')
            fragged = data.get('fragged', 'Unknown') 
            weapon = data.get('weapon', '')
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death event - Fragger: {fragger}, Fragged: {fragged}, Weapon: {weapon}")
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Full death data: {data}")
            
            # Skip if we don't have enough data
            if not fragged or fragged == 'Unknown':
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Skipping death commentary - no fragged data")
                return
            
            commentary = None
            
            # Self-kills - MBIIEZ sets fragger to "SELF" for self-kills and world kills
            if fragger == "SELF":
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Detected self-kill/world kill")
                
                if 'MOD_ROCKET' in weapon or 'ROCKET_SPLASH' in weapon or 'rocket' in weapon.lower():
                    commentary = self.generate_death_commentary(fragged, "rocket_suicide")
                elif 'MOD_SUICIDE' in weapon or 'suicide' in weapon.lower():
                    commentary = self.generate_death_commentary(fragged, "suicide")
                elif 'MOD_FALLING' in weapon or 'falling' in weapon.lower():
                    commentary = self.generate_death_commentary(fragged, "falling")
                elif 'MOD_SABER' in weapon or 'saber' in weapon.lower():
                    commentary = self.generate_death_commentary(fragged, "youngling")
                elif 'MOD_CRUSH' in weapon or 'crush' in weapon.lower():
                    commentary = self.generate_death_commentary(fragged, "crushed")
                else:
                    # Generic self-kill or environmental death
                    commentary = self.generate_death_commentary(fragged, "environmental")
            
            # Send commentary publicly (always public for death commentary)
            if commentary:
                formatted_commentary = f"^6{self.ai_name}: ^7{commentary}"
                
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Sending death commentary: {formatted_commentary}")
                
                # Small delay to let the death message appear first
                time.sleep(1)
                self.instance.say(formatted_commentary)
            else:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: No commentary generated for death")
                
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Error in death commentary: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary traceback: {traceback.format_exc()}")
    
    def generate_death_commentary(self, victim_name, death_type):
        """Generate commentary about a silly death"""
        try:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Generating {death_type} commentary for {victim_name}")
            
            # Create prompt based on death type
            death_prompts = {
                "rocket_suicide": f"A player named {victim_name} just blew themselves up with their own rocket/explosive. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.",
                "suicide": f"A player named {victim_name} just took their own life in the game. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.",
                "self_kill": f"A player named {victim_name} somehow just killed themselves. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.",
                "falling": f"A player named {victim_name} just died from falling damage. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.",
                "youngling": f"A player named {victim_name} just got killed by a youngling (NPC with lightsaber). Make a brief, humorous comment about this. Reference Star Wars youngling memes if appropriate. Keep it light and funny, max 1 sentence.",
                "crushed": f"A player named {victim_name} just got crushed to death. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.",
                "environmental": f"A player named {victim_name} just died to the environment/world. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence."
            }
            
            prompt = death_prompts.get(death_type, f"A player named {victim_name} just died in an unfortunate way. Make a brief, humorous comment about this. Keep it light and funny, max 1 sentence.")
            
            # Clean up player name for more natural reference
            clean_victim_name = self.clean_player_name_for_ai(victim_name)
            prompt = prompt.replace(victim_name, clean_victim_name)
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary prompt: {prompt}")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/clone-army/mbiiez",
                "X-Title": f"MBIIEZ AI Assistant - {getattr(self.instance, 'name', 'Unknown Server')} - Death Commentary"
            }
            
            # Get current game state for context
            game_state = self.get_current_game_state()
            
            # Create game data JSON similar to regular chat
            game_data = {
                "death_commentary_request": prompt,
                "victim_player": clean_victim_name,
                "death_type": death_type,
                "current_map": game_state["current_map"],
                "players": game_state["players"],
                "server_info": game_state["server_info"],
                "instance_id": self.instance_id
            }
            
            # Convert to JSON string for the AI
            game_data_json = json.dumps(game_data, indent=2)
            
            # Use the same system prompt as regular chat but with death commentary context
            death_system_prompt = f"{self.system_prompt}\n\nDEATH COMMENTARY MODE: You are now making a brief, humorous comment about a player death. The JSON contains 'death_commentary_request' with the specific request. Use the player name, map, and server context to make your comment more engaging. Keep it light-hearted and never mean-spirited. Max 1 sentence."
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": death_system_prompt},
                    {"role": "user", "content": game_data_json}
                ],
                "max_tokens": 50,
                "temperature": 0.8
            }
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Making death commentary API request")
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                commentary = result['choices'][0]['message']['content'].strip()
                # Clean up encoding issues
                commentary = self.clean_text_encoding(commentary)
                
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Generated death commentary: {commentary}")
                
                return commentary
            else:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary API error: {response.status_code} - {response.text}")
            
        except requests.exceptions.Timeout:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary API timeout")
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Error generating death commentary: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Death commentary generation traceback: {traceback.format_exc()}")
        
        return None
    
    def clean_player_name_for_ai(self, player_name):
        """Clean player name for AI commentary by removing clan tags"""
        # Remove common clan tag patterns
        import re
        
        # Remove brackets and their contents: [TAG], (TAG), {TAG}
        cleaned = re.sub(r'[\[\(\{][^\]\)\}]*[\]\)\}]', '', player_name)
        
        # Remove common separators and prefixes
        cleaned = re.sub(r'^[-_=\|]*', '', cleaned)
        cleaned = re.sub(r'[-_=\|]*$', '', cleaned)
        
        # Remove color codes (^1, ^2, etc.)
        cleaned = re.sub(r'\^[0-9]', '', cleaned)
        
        # Clean up extra spaces and dashes
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = re.sub(r'-+', '-', cleaned)
        cleaned = cleaned.strip(' -_')
        
        # If name becomes empty or too short, use original
        if len(cleaned) < 2:
            return player_name
            
        return cleaned
    
    def generate_response(self, player_name, prompt):
        """Generate AI response using OpenRouter API"""
        try:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant [{self.instance_id}]: Starting API call for prompt: '{prompt}'")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/clone-army/mbiiez",
                "X-Title": f"MBIIEZ AI Assistant - {getattr(self.instance, 'name', 'Unknown Server')}"
            }
            
            # Get current game state
            game_state = self.get_current_game_state()
            
            # Create comprehensive game data JSON
            game_data = {
                "player_message": prompt,
                "requesting_player": player_name,
                "current_map": game_state["current_map"],
                "players": game_state["players"],
                "server_info": game_state["server_info"],
                "instance_id": self.instance_id  # Add instance ID for better isolation
            }
            
            # Convert to JSON string for the AI
            game_data_json = json.dumps(game_data, indent=2)
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Game data JSON: {game_data_json}")
            
            # Build conversation context
            conversation = [
                {"role": "system", "content": f"{self.system_prompt}\n\nSERVER CONTEXT: You are responding on server '{getattr(self.instance, 'name', 'Unknown Server')}' (Instance ID: {self.instance_id}). Only respond to players on THIS specific server instance.\n\nREMINDER: The user message contains JSON data. Parse it and use 'requesting_player' for the player's name and 'player_message' for what to respond to. Reference 'current_map' and 'players' data when appropriate."},
                {"role": "user", "content": game_data_json}
            ]
            
            # Add conversation history if enabled
            if self.config.get('remember_conversation', False):
                # Use instance-specific player name to prevent cross-server memory issues
                instance_player_key = f"{self.instance_id}_{player_name}"
                if instance_player_key in self.conversation_history:
                    # Add last few exchanges for context
                    history = self.conversation_history[instance_player_key][-4:]  # Last 2 exchanges
                    conversation = [conversation[0]] + history + [conversation[1]]
            
            payload = {
                "model": self.model,
                "messages": conversation,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": 0.9,
                "frequency_penalty": 0.1,
                "presence_penalty": 0.1
            }
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Making API request to OpenRouter with model: {self.model}")
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result['choices'][0]['message']['content'].strip()
                
                # Clean up common encoding issues and special characters
                ai_response = self.clean_text_encoding(ai_response)
                
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: Generated response: '{ai_response}'")
                
                # Store in conversation history
                if self.config.get('remember_conversation', False):
                    # Use instance-specific player name to prevent cross-server memory issues
                    instance_player_key = f"{self.instance_id}_{player_name}"
                    if instance_player_key not in self.conversation_history:
                        self.conversation_history[instance_player_key] = []
                    
                    self.conversation_history[instance_player_key].extend([
                        {"role": "user", "content": f"Player asked: {prompt}"},  # Simplified for history
                        {"role": "assistant", "content": ai_response}
                    ])
                    
                    # Keep only recent history
                    if len(self.conversation_history[instance_player_key]) > 10:
                        self.conversation_history[instance_player_key] = self.conversation_history[instance_player_key][-10:]
                
                return ai_response
            else:
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log(f"AI Assistant: API error {response.status_code}: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log("AI Assistant: Request timeout")
            return None
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error generating response: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant: API traceback: {traceback.format_exc()}")
            return None
    
    def chunk_message(self, message, max_length):
        """Split long messages into chunks"""
        chunks = []
        words = message.split()
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + " " + word) <= max_length:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def player_connects(self, data):
        """Handle player connections"""
        if not self.config.get('welcome_message', False):
            return
            
        try:
            player_name = data.get('player_name', 'Unknown')
            welcome_msg = self.config.get('welcome_text', f"Welcome! Type {self.command} <question> to chat with me!")
            
            # Small delay to ensure player sees the message
            time.sleep(2)
            self.instance.say(f"^6{self.ai_name}: ^7{player_name}, {welcome_msg}")
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error in welcome message: {e}")
    
    def map_change(self, data):
        """Handle map changes with optional commentary"""
        if not self.config.get('map_commentary', False):
            return
            
        try:
            map_name = data.get('map_name', 'unknown')
            
            # Generate map commentary
            commentary = self.generate_map_commentary(map_name)
            if commentary:
                time.sleep(3)  # Wait a bit after map change
                self.instance.say(f"^6{self.ai_name}: ^7{commentary}")
                
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error in map commentary: {e}")
    
    def generate_map_commentary(self, map_name):
        """Generate commentary about the map"""
        try:
            prompt = f"Make a brief, encouraging comment about the Movie Battles II map '{map_name}'. Keep it to one sentence and make it engaging for players."
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/clone-army/mbiiez",
                "X-Title": f"MBIIEZ AI Assistant - {getattr(self.instance, 'name', 'Unknown Server')} - Map Commentary"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 50,
                "temperature": 0.8
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                commentary = result['choices'][0]['message']['content'].strip()
                # Clean up encoding issues
                commentary = self.clean_text_encoding(commentary)
                return commentary
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error generating map commentary: {e}")
        
        return None
    
    def stop(self):
        """Clean up when plugin is stopped"""
        try:
            self.conversation_history.clear()
            self.last_response_time.clear()
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log("AI Assistant: Plugin stopped and cleaned up")
                
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error during cleanup: {e}")