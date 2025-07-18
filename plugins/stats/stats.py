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

import random
import datetime

from mbiiez.client import client

class plugin:

    plugin_name = "Stats"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None
    
    # LIST to hold all previous spins
    spins = {}

    ''' You must initialise instance which you can use to access the running instance '''
    def __init__(self, instance):
        self.instance = instance
        
        if(self.instance.has_plugin("auto_message")):
            self.instance.config['plugins']['auto_message']['messages'].append("You can use !stats to see your current player stats across all our servers")   
            
    ''' use register event to have your given method notified when the event occurs '''
    def register(self):
        self.instance.event_handler.register_event("player_chat_command", self.stats_process)
        
    def stats_process(self, args):
        if(args['message'].startswith("!stats")): 
        
            player = args['player']
            my_client = client(player)
            self.instance.tell(args['player_id'], "Your stats on our Servers")
            self.instance.tell(args['player_id'], "^5Kills:^7 {}".format(my_client.global_stats.kills))
            self.instance.tell(args['player_id'], "^5Deaths:^7 {}".format(my_client.global_stats.deaths))           
            self.instance.tell(args['player_id'], "^5Suicides:^7 {}".format(my_client.global_stats.suicides))	
