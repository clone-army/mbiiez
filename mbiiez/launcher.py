import os
import shutil
import subprocess
import time
import signal
import datetime
import shlex

from mbiiez.bcolors import bcolors
from mbiiez.conf import conf
from mbiiez import settings
from mbiiez.log_handler import log_handler
from mbiiez.process_handler import process_handler

class launcher: 

    # Names of various processes saved into database
    name_dedicated = "Dedicated Server"
    name_auto_message = "Auto Message"
    name_log_watcher = "Log Watcher"

    event_handler = None
    log_handler = None
    config = None 
    instance_name = None 
    process_handler = None
    instance = None
    
    services = []

    def __init__(self, instance):
        self.config = instance.config      
        self.log_handler = instance.log_handler
        self.process_handler = instance.process_handler
        self.instance_name = self.config['server']['name']
        self.instance = instance

    # Register a service that needs launching
    def register_service(self, name, func, auto_restart = True):
        self.services.append({"name": name, "func": func})

    # Launch all services
    def launch_services(self):
        
        for service in self.services:
            self.log_handler.log("Starting Service: " + service['name'])
            self.process_handler.start(service['func'], service['name'], self.instance_name)
            
    # Dedicated Server Thread
    def openjk_launch(self):   
      
        while(True):
            print("Checking OpenJK Dedicated...")
            
            if(self.process_handler.process_status("OpenJK")):
                print("running")
            else:
                print("not running")
            
            while(not self.process_handler.process_status("OpenJK")): 
                print("Starting OpenJK Dedicated...")
                self.log_handler.log("Starting OpenJK Dedicated Server")
                cmd = "nohup {} --quiet +set dedicated 2 +set net_port {} +set fs_game {} +exec {}".format(self.config['server']['engine'], self.config['server']['port'], settings.dedicated.game, self.config['server']['server_config_file']);       
                process = subprocess.Popen(shlex.split(cmd), shell=False)  # ,stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL   
                pid = process.pid
                self.process_handler.add_pid("OpenJK", pid, self.instance_name)
                print(pid)
                time.sleep(3)
            time.sleep(3)
        return
        
    # KILL THIS  
    def launch_dedicated_server(self):
    
        # Reason to Bail
        if(not os.path.isfile(self.config['server']['server_config_path'])):
            self.log_handler.log(bcolors.RED + "Failed to start. No config file found at {}".format(self.config['server']['server_config_path']) + bcolors.ENDC)        
            exit()
            
        # Reason to Bail  
        if(not os.path.isfile("{}/{}".format("/usr/bin", self.config['server']['engine']))):        
            self.log_handler.log(bcolors.RED + "Failed to start. No engine found at {}/{}".format("/usr/bin", self.config['server']['engine']) + bcolors.ENDC)   
            exit()
            
        # Make sure can be executed    
        os.system("chmod +x {}/{}".format("/usr/bin", self.config['server']['engine']))  
          
        # Sym Links
        if(os.path.exists("/root/.local/share/openjk")):
            if(not os.path.islink("/root/.local/share/openjk")):
                shutil.rmtree("/root/.local/share/openjk")       
                os.symlink(settings.locations.game_path, "/root/.local/share/openjk")
        
        if(os.path.exists("/root/.ja")):
            if(not os.path.islink("/root/.ja")):
                shutil.rmtree("/root/.ja")       
                os.symlink(settings.locations.game_path, "/root/.ja")  
    
        self.process_handler.start(self.launch_dedicated_server_thread, self.name_dedicated, self.instance_name)
