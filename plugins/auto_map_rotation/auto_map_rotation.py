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



'''

import datetime
import os
import time

class plugin:

    plugin_name = "Auto Map Rotation"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None
    discord_bot = None

    ''' You must initialise instance which you can use to access the running instance '''
    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['auto_map_rotation']

    ''' use register event to have your given method notified when the event occurs '''
    def register(self):
        self.instance.process_handler.register_service("Auto Map Rotation Service", self.auto_map_changes)
        
      # Auto Map Changes Thread       
    def auto_map_changes(self):             
    
        time.sleep(60)
    
        while(True):
            time.sleep(self.config['rotate_minutes'] * 60)
            if(self.instance.is_empty()):
                self.instance.rcon("vstr nextmap")
                self.instance.log_handler.log("Changing Map..")
            else:
                self.instance.log_handler.log("NOT Changing Map..")               

        return
       