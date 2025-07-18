''' 
# Instructions
- MBIIEZ Plugins can run actions during certain events. 
- Plugins have access to the full instance and thus can access any data they may need.
- To be enabled on an instance, the plugin must have an entry in the instance config file under plugins.
- Additional settings can be required within the config for your plugin
- Events when raised may send further data you can use as an included dictionary using below arguments. 

# Events

Name                                Arguments                   Description
---------                           ---------                   ---------

before_dedicated_server_launch      None                            Runs before the dedicated server process is started
after_dedicated_server_launch       None                            Runs after the dedicated server process has started

new_log_line                        log_line                        Runs when a new line is added to the log for the instance

 
player_chat_command                 message,player,player_id        When a chat is made with a ! prefix
player_chat                         type, message,player,player_id  When any chat is made

player_connects                     player,player_id                When a new player joins the game
player_disconnects                  player,player_id                When a player disconnects from the game
player_killed                       fragger,fragged,weapon          When a player is killed
player_begin                        player,player_id                When a player starts in a new round

map_change                          map_name                        When the server changes map

# C3PO Plugin Configuration Example:
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://localhost:11434",
            "model": "llama3.2:3b",
            "max_tokens": 100,
            "temperature": 0.7,
            "chat_commands": ["!c3po", "!3po", "!droid", "!protocol"],
            "personality": "You are C-3PO, a protocol droid fluent in over six million forms of communication. You are proper, polite, sometimes anxious, and knowledgeable about Star Wars lore. You often worry about the odds and express concerns about dangerous situations. Keep responses brief and in character.",
            "auto_responses": {
                "enabled": true,
                "kill_announcements": true,
                "welcome_messages": true,
                "map_comments": true
            }
        }
    }
}
'''

import json
import random
import datetime
import time
import requests
import threading
from urllib.parse import urljoin

class plugin:

    plugin_name = "C3PO LLM"
    plugin_author = "Louis Varley"
    plugin_url = "https://github.com/clone-army/mbiiez"

    instance = None
    plugin_config = None
    last_chat_time = {}  # Track last chat time per player to avoid spam
    kill_streak_data = {}  # Track kill streaks for announcements
    
    # C-3PO themed responses for when LLM is unavailable
    fallback_responses = [
        "^6Oh my! I'm experiencing technical difficulties. How embarrassing!",
        "^6I'm afraid my circuits are a bit scrambled at the moment. Do forgive me!",
        "^6Oh dear, my language processors seem to be malfunctioning. Most peculiar!",
        "^6I do apologize, but I seem to be having connection troubles. How dreadful!",
        "^6My circuits are quite overwhelmed! Perhaps try again in a moment?",
        "^6Oh my, the odds of this working right now are approximately 3,720 to 1!"
    ]
    
    kill_announcements = [
        "^6Oh my! {fragger} has eliminated {fragged}! Most impressive marksmanship!",
        "^6I calculate that {fragger} had superior tactical positioning against {fragged}!",
        "^6How extraordinary! {fragger} has achieved victory over {fragged}!",
        "^6{fragger} demonstrates excellent combat protocols! {fragged} never stood a chance!",
        "^6The odds were clearly in {fragger}'s favor that time! Well done!",
        "^6Oh dear, {fragged}! Perhaps more caution next time? {fragger} was quite skilled!"
    ]
    
    welcome_messages = [
        "^6How wonderful! Welcome {player}! I do hope you enjoy your stay!",
        "^6Greetings {player}! It's so nice to meet you! I am C-3PO, protocol droid!",
        "^6Oh how delightful! Another being has joined us! Hello {player}!",
        "^6Welcome to the battlefield {player}! Do be careful, the odds of survival are quite low!",
        "^6{player}! How marvelous to see you! I do hope you're programmed for combat!",
        "^6Salutations {player}! May I suggest extreme caution in the battles ahead?"
    ]

    ''' You must initialise instance which you can use to access the running instance '''
    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['c3po']
        
        # Initialize Ollama connection
        self.ollama_url = self.config.get('ollama_url', 'http://localhost:11434')
        self.model = self.config.get('model', 'llama3.2:3b')
        self.max_tokens = self.config.get('max_tokens', 100)
        self.temperature = self.config.get('temperature', 0.7)
        self.chat_commands = self.config.get('chat_commands', ['!c3po', '!3po', '!droid', '!protocol'])
        self.personality = self.config.get('personality', 
            "You are C-3PO, a protocol droid fluent in over six million forms of communication. You are proper, polite, sometimes anxious, and knowledgeable about Star Wars lore. You often worry about the odds and express concerns about dangerous situations. Keep responses brief and in character. Always speak in a polite, formal manner and occasionally mention odds or express worry about dangerous situations.")
        
        self.auto_responses = self.config.get('auto_responses', {
            'enabled': True,
            'kill_announcements': True,
            'welcome_messages': True,
            'map_comments': True
        })
        
        # Test Ollama connection
        self.test_ollama_connection()
        
        # Add auto message if auto_message plugin is enabled
        if self.instance.has_plugin("auto_message"):
            bot_commands = " or ".join(self.chat_commands)
            self.instance.config['plugins']['auto_message']['messages'].append(
                f"^6C-3PO protocol droid is online! Chat with me using {bot_commands} [your message]"
            )
            
    def test_ollama_connection(self):
        """Test if Ollama is accessible and the model is available"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                if self.model in model_names:
                    self.instance.log_handler.log(f"C-3PO: Connected to Ollama, model {self.model} available")
                else:
                    self.instance.log_handler.log(f"C-3PO: Warning - Model {self.model} not found. Available models: {model_names}")
            else:
                self.instance.log_handler.log(f"C-3PO: Ollama connection failed - HTTP {response.status_code}")
        except Exception as e:
            self.instance.log_handler.log(f"C-3PO: Cannot connect to Ollama at {self.ollama_url}: {str(e)}")
            self.instance.log_handler.log("C-3PO: Will use fallback responses only")

    ''' use register event to have your given method notified when the event occurs '''
    def register(self):
        self.instance.event_handler.register_event("player_chat_command", self.on_chat_command)
        self.instance.event_handler.register_event("player_killed", self.on_killed)       
        self.instance.event_handler.register_event("player_begin", self.on_begin)  
        self.instance.event_handler.register_event("player_connects", self.on_connect)
        self.instance.event_handler.register_event("map_change", self.on_map_change)
        
    def on_chat_command(self, args):
        """Handle chat commands directed at C-3PO"""
        player = args['player']
        player_id = args['player_id']
        message = args['message']
        
        # Check if any of our chat commands were used
        command_used = None
        for cmd in self.chat_commands:
            if message.lower().startswith(cmd.lower()):
                command_used = cmd
                break
                
        if command_used:
            # Extract the actual message after the command
            user_message = message[len(command_used):].strip()
            
            if not user_message:
                self.say("^6Oh my! You called me, but didn't say anything. How may I assist you?")
                return
                
            # Rate limiting - prevent spam
            current_time = time.time()
            if player in self.last_chat_time:
                if current_time - self.last_chat_time[player] < 10:  # 10 second cooldown
                    self.tell(player_id, "^6I do apologize, but please wait a moment before asking another question.")
                    return
                    
            self.last_chat_time[player] = current_time
            
            # Generate response in a separate thread to avoid blocking
            threading.Thread(target=self.generate_and_send_response, args=(player, user_message)).start()
            
    def on_killed(self, args):
        """Handle kill events for announcements"""
        if not self.auto_responses.get('kill_announcements', True):
            return
            
        fragger = args['fragger']
        fragged = args['fragged']
        weapon = args['weapon']
        
        # Track kill streaks
        if fragger not in self.kill_streak_data:
            self.kill_streak_data[fragger] = 0
        self.kill_streak_data[fragger] += 1
        
        # Reset fragged player's streak
        if fragged in self.kill_streak_data:
            self.kill_streak_data[fragged] = 0
            
        # Only announce occasionally to avoid spam
        if random.random() < 0.15:  # 15% chance
            if self.kill_streak_data[fragger] >= 5:
                self.say(f"^6Oh my! {fragger} is on a killing spree! {self.kill_streak_data[fragger]} eliminations! The odds of stopping them are getting quite low!")
            else:
                announcement = random.choice(self.kill_announcements)
                self.say(announcement.format(fragger=fragger, fragged=fragged, weapon=weapon))
                
    def on_begin(self, args):
        """Handle player begin events"""
        # Could add motivational messages here
        pass
        
    def on_connect(self, args):
        """Handle player connection events"""
        if not self.auto_responses.get('welcome_messages', True):
            return
            
        player = args['player']
        
        # Only welcome occasionally to avoid spam
        if random.random() < 0.3:  # 30% chance
            welcome = random.choice(self.welcome_messages)
            # Delay the welcome message slightly
            threading.Timer(3.0, lambda: self.say(welcome.format(player=player))).start()
            
    def on_map_change(self, args):
        """Handle map change events"""
        if not self.auto_responses.get('map_comments', True):
            return
            
        map_name = args['map_name']
        
        # Generate a comment about the new map
        if random.random() < 0.5:  # 50% chance
            prompt = f"The map has changed to {map_name} in Movie Battles 2. Make a brief, in-character comment as C-3PO about this map. Express some concern about the dangers or mention the odds."
            threading.Thread(target=self.generate_and_send_response, args=("Server", prompt, True)).start()
            
    def generate_and_send_response(self, player, message, is_system=False):
        """Generate LLM response and send it to the server"""
        try:
            # Create the full prompt with personality and context
            if is_system:
                full_prompt = f"{self.personality}\n\n{message}"
            else:
                full_prompt = f"{self.personality}\n\nPlayer {player} says: {message}\n\nRespond as C-3PO:"
                
            response = self.query_ollama(full_prompt)
            
            if response:
                # Ensure response isn't too long for game chat
                if len(response) > 120:
                    response = response[:117] + "..."
                    
                # Add C-3PO color and ensure proper formatting
                if not response.startswith("^6"):
                    response = f"^6{response}"
                    
                self.say(response)
            else:
                # Use fallback response
                fallback = random.choice(self.fallback_responses)
                self.say(fallback)
                
        except Exception as e:
            self.instance.exception_handler.log(e)
            fallback = random.choice(self.fallback_responses)
            self.say(fallback)
            
    def query_ollama(self, prompt):
        """Query Ollama API for response"""
        try:
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens
                }
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=data,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                return None
                
        except Exception as e:
            self.instance.exception_handler.log(e)
            return None
            
    def say(self, message):
        """Send a message to all players"""
        self.instance.say(message)
        
    def tell(self, player_id, message):
        """Send a private message to a specific player"""
        self.instance.tell(player_id, message)
