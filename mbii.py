#!/usr/bin/python3
import sys, getopt
import argparse
import os

from mbiiez.bcolors import bcolors
from mbiiez.instance import instance
from mbiiez import settings
from mbiiez.client import client

# Main Class
class main:

         
    # Usage Banner
    def usage(self):
        print("usage: MBII [OPTIONS]")
        print("")
        print("Option                                    Name            Meaning")
        print("-i <instance> [command] [optional args]   Instance        Use to run commands against a named instance")  
        print("-l                                        List            List all Instances available")        
        print("-u                                        Update          Check for MBII Updates, Update when ALL instances are empty")
        print("-v                                        Verbose         Enable verbose mode")     
        print("-c <name>                                 Client          Show stats from all instances for a client / player") 
        print("-a [command] [optional args]              All             Use to run a command against all instances")         
        print("-h                                        Help            Show this help screen")  
        
        print("")
        
        print("Instance Commands")
        print("Option             Description")
        print("------------------------------------")        
        print("start              Start Instance")
        print("stop               Stop Instance") 
        print("restart            Restart Instance") 
        print("status             Instance Status") 
        print("rcon               Issue RCON Command In Argument") 
        print("say                Issue a Server say to the Server")         
        print("cvar               Allows you to set or get a cvar value")         

        exit()

    # Main Function
    def main(self,argv):
    
        if(len(sys.argv) == 1):
            self.usage()
 
        parser = argparse.ArgumentParser(add_help=False)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-i", type=str, help="Action on Instance", nargs="+", metavar="INSTANCE", dest="instance")

        group.add_argument("-l", action="store_true",              help="List Instances",      dest="list")
        group.add_argument("-u", action="store_true",              help="Update MBII",         dest="update")
        group.add_argument("-c", type=str, nargs="+", metavar="CLIENT", help="Action on Client",   dest="client")  
        group.add_argument("-a", type=str, help="Action on Instances", nargs="+", metavar="INSTANCE", dest="instances")        
        group.add_argument("-h", action="store_true",              help="Help Usage",          dest="help")
        parser.add_argument("-v", action="store_true",              help="Verbose Output",      dest="verbose")


                
        args = parser.parse_args()
        
        if(args.verbose):
            settings.globals.verbose = True
            
        if(args.help):
            self.usage()
            exit()
            
        if(args.list):
            self.list()
            exit()
            
        if(args.client):
            self.client(args.client[0])
            exit()
        
        if(args.instance):
            # If the command is 'status', print the result of status_print()
            if len(args.instance) >= 2 and args.instance[1] == 'status':
                inst = self.get_instance(args.instance[0])
                print(inst.status_print())
            elif(len(args.instance) == 3):
                getattr(self.get_instance(args.instance[0]), args.instance[1])(args.instance[2])
            elif(len(args.instance) == 4):
                 getattr(self.get_instance(args.instance[0]), args.instance[1])(args.instance[2], args.instance[3])           
            else:
                getattr(self.get_instance(args.instance[0]), args.instance[1])()

        if(args.instances):
            action = args.instances[0]
            params = args.instances[1:]
            config_dir = settings.locations.config_path
            for fn in os.listdir(config_dir):
                if not fn.endswith(".json"):
                    continue
                name = fn[:-5]  # strip “.json”
                inst = instance(name)
                try:
                    if params:
                         getattr(inst, action)(*params)
                    else:
                         getattr(inst, action)()
                    print(f"Executed '{action}' on instance '{name}'")
                except Exception as e:
                    print(f"Error running '{action}' on '{name}': {e}")
            sys.exit(0)


    
    def get_instance(self, name):
        return instance(name)      
             
    
    def list(self):
        config_file_path = settings.locations.config_path
        for filename in os.listdir(config_file_path):
            if(filename.endswith(".json")):
                print(filename.replace(".json",""))
                
        
                
    def client(self, player_name):
        client(player_name).client_info_print()
      
    def restart_instances(self):

        config_file_path = settings.locations.config_path
        for filename in os.listdir(config_file_path):
            if(filename.endswith(".json")):
                name = filename.replace(".json","")
                i = instance(name)  
                if(i.players_count() == 0):
                    print(bcolors.CYAN + "Retarting " + name + bcolors.ENDC)   
                    print("------------------------------------") 
                    i.restart()
                else:
                    print(bcolors.RED + "Has Players " + name + bcolors.ENDC)   
                    print("------------------------------------") 
            
      
if __name__ == "__main__":
   main().main(sys.argv[1:])
   print(bcolors.ENDC)
