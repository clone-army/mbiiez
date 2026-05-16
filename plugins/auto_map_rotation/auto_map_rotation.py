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
        # Support both key names; fall back to 30 minutes if neither is set.
        interval = (
            self.config.get('rotate_minutes')
            or self.config.get('rotation_minutes')
            or 30
        )
        interval_secs = interval * 60

        self.instance.log_handler.log(
            "Auto Map Rotation: started, interval {} min (will rotate only when server is empty).".format(interval)
        )

        while True:
            time.sleep(interval_secs)

            try:
                empty = self.instance.is_empty()
            except Exception:
                # Can't reach RCON — assume occupied; skip this cycle.
                self.instance.log_handler.log(
                    "Auto Map Rotation: RCON unavailable, skipping rotation."
                )
                continue

            if empty:
                self.instance.log_handler.log("Auto Map Rotation: server empty, rotating map.")
                try:
                    self.instance.rcon("vstr nextmap")
                except Exception as e:
                    self.instance.log_handler.log(
                        "Auto Map Rotation: failed to send vstr nextmap — {}.".format(e)
                    )
            else:
                self.instance.log_handler.log(
                    "Auto Map Rotation: server occupied, skipping rotation."
                )
       