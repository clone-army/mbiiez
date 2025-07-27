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
            
            # Build system prompt
            self.system_prompt = self.build_system_prompt()
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Plugin registered as '{self.ai_name}' with command '{self.command}'")
                self.instance.log_handler.log(f"AI Assistant: Using model: {self.model}")
                self.instance.log_handler.log("AI Assistant: Registration completed successfully!")

            self.instance.event_handler.register_event("player_chat_command", self.player_chat_command)

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
        
        # Add game context and JSON format explanation
        game_context = (
            "\n\nContext: You are responding to players on a Movie Battles II server. "
            "Movie Battles II is a Star Wars-themed multiplayer game modification. "
            "Keep responses concise (1-2 sentences max) as this is a fast-paced gaming environment. "
            "You can reference Star Wars lore when appropriate."
            "\n\nIMPORTANT: You will receive game data as a JSON object containing:"
            "\n- 'player_message': The actual text/question from the player you should respond to"
            "\n- 'requesting_player': Name of the player asking the question - USE THIS NAME when addressing them"
            "\n- 'current_map': Name of the current map being played - mention this when relevant"
            "\n- 'players': Array of current players with their scores, kills, deaths, and other stats"
            "\n- 'server_info': Additional server information"
            "\n\nAlways use the 'requesting_player' name when addressing the person who asked the question. "
            "You can reference the current map, player scores, and other game data in your responses when relevant "
            "(e.g., 'Nice work on {current_map}, {requesting_player}!' or congratulate top scorers). "
            "Always primarily respond to the 'player_message' content."
            "\n\nExample: If JSON contains 'requesting_player': 'JediMaster' and 'player_message': 'hello', "
            "respond like: 'Hello JediMaster! Welcome to the server!' (not 'Hello player unknown')"
        )
        
        return base_instruction + game_context
    
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
            player_name = data.get('player_name', 'Unknown')
            player_id = data.get('player_id', 0)
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Message: '{message}', Command: '{self.command}'")
            
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
                self.instance.say(f"^6{self.ai_name}: ^7Please ask me something! Example: {self.command} What is the best lightsaber form?")
                return
            
            # Check cooldown
            current_time = time.time()
            if player_id in self.last_response_time:
                time_since_last = current_time - self.last_response_time[player_id]
                if time_since_last < self.cooldown:
                    remaining = int(self.cooldown - time_since_last)
                    self.instance.tell(player_id, f"^6{self.ai_name}: ^7Please wait {remaining} more seconds before asking another question.")
                    return
            
            # Update cooldown
            self.last_response_time[player_id] = current_time
            
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
                        self.instance.say(chunk)
                        time.sleep(0.5)  # Small delay between chunks
                else:
                    self.instance.say(formatted_response)
            else:
                error_msg = f"^6{self.ai_name}: ^7I'm having trouble thinking right now. Please try again later!"
                self.instance.say(error_msg)
                if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                    self.instance.log_handler.log("AI Assistant: No response generated, sent error message")
            
        except Exception as e:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Error in chat command: {e}")
                import traceback
                self.instance.log_handler.log(f"AI Assistant: Chat command traceback: {traceback.format_exc()}")
    
    def generate_response(self, player_name, prompt):
        """Generate AI response using OpenRouter API"""
        try:
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Starting API call for prompt: '{prompt}'")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/clone-army/mbiiez",
                "X-Title": "MBIIEZ AI Assistant"
            }
            
            # Get current game state
            game_state = self.get_current_game_state()
            
            # Create comprehensive game data JSON
            game_data = {
                "player_message": prompt,
                "requesting_player": player_name,
                "current_map": game_state["current_map"],
                "players": game_state["players"],
                "server_info": game_state["server_info"]
            }
            
            # Convert to JSON string for the AI
            game_data_json = json.dumps(game_data, indent=2)
            
            if hasattr(self.instance, 'log_handler') and self.instance.log_handler:
                self.instance.log_handler.log(f"AI Assistant: Game data JSON: {game_data_json}")
            
            # Build conversation context
            conversation = [
                {"role": "system", "content": f"{self.system_prompt}\n\nREMINDER: The user message contains JSON data. Parse it and use 'requesting_player' for the player's name and 'player_message' for what to respond to. Reference 'current_map' and 'players' data when appropriate."},
                {"role": "user", "content": game_data_json}
            ]
            
            # Add conversation history if enabled
            if self.config.get('remember_conversation', False):
                if player_name in self.conversation_history:
                    # Add last few exchanges for context
                    history = self.conversation_history[player_name][-4:]  # Last 2 exchanges
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
                    if player_name not in self.conversation_history:
                        self.conversation_history[player_name] = []
                    
                    self.conversation_history[player_name].extend([
                        {"role": "user", "content": f"Player asked: {prompt}"},  # Simplified for history
                        {"role": "assistant", "content": ai_response}
                    ])
                    
                    # Keep only recent history
                    if len(self.conversation_history[player_name]) > 10:
                        self.conversation_history[player_name] = self.conversation_history[player_name][-10:]
                
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
                "X-Title": "MBIIEZ AI Assistant"
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