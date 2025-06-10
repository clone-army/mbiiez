import configparser
import os

class globals:
    # Use the directory above this file as the script path
    script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
    config = configparser.ConfigParser()
    config.read(os.path.join(script_path, "mbiiez.conf"))
    verbose = False

class locations:
    script_path = globals.script_path
    game_path = globals.config.get('locations', 'game_path')
    mbii_path = globals.config.get('locations', 'mbii_path')
    base_path = globals.config.get('locations', 'base_path')
    # Use a relative path for configs if the config value is absolute and doesn't exist
    config_path = globals.config.get('locations', 'config_path')
    if not os.path.isabs(config_path) or not os.path.exists(config_path):
        config_path = os.path.join(script_path, 'configs')
    plugins_path = os.path.join(script_path, "plugins")

class dedicated:    
    game = globals.config.get('dedicated', 'game')
    engine = globals.config.get('dedicated', 'engine')

class database:
    database = globals.config.get('database', 'database')
    if not os.path.isabs(database) or not os.path.exists(database):
        database = os.path.join(globals.script_path, 'mbiiez.db')

class web_service:
    port = globals.config.get('web_service', 'port')
    username = globals.config.get('web_service', 'username') 
    password = globals.config.get('web_service', 'password')