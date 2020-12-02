import os
import json
import time

class conf:

    name = None
    mbii_path = None
    embii_path = None
    config_path = None   
    config = None

    def __init__(self, name, script_path, mbii_path):
        self.name = name
        self.mbii_path = mbii_path
        self.script_path = script_path
        self.config_path = "{}/configs".format(script_path)
        self.get_config()
    
    # Fetch Config, add additionals and save as dictionary
    def get_config(self):

        config_file_path = self.config_path + "/" + self.name + ".json"
        
        if(not os.path.isfile(config_file_path)):
            return False

        with open(config_file_path) as config_data:
            data = json.load(config_data)
            
        data['server']['name'] = self.name
            
        data['server']['rtvrtm_config_file'] = "{}-rtvrtm.cfg".format(self.name)
        data['server']['rtvrtm_config_path'] = "{}/{}".format(self.mbii_path, data['server']['rtvrtm_config_file'])
        
        data['server']['server_config_file'] = "{}-server.cfg".format(self.name) 
        data['server']['server_config_path'] = "{}/{}".format(self.mbii_path, data['server']['server_config_file'])
        
        data['server']['primary_maplist_file'] = "{}-primary.txt".format(self.name) 
        data['server']['primary_maplist_path'] = "{}/{}".format(self.mbii_path, data['server']['primary_maplist_file'])  
        
        data['server']['secondary_maplist_file'] = "{}-secondary.txt".format(self.name) 
        data['server']['secondary_maplist_path'] = "{}/{}".format(self.mbii_path, data['server']['secondary_maplist_file']) 
        
        data['server']['log_file'] = "{}-games.log".format(self.name)  
        data['server']['log_path'] = "{}/{}".format(self.mbii_path, data['server']['log_file'])
            
        data['server']['pid_file'] = "{}/pids/{}.pid".format(self.script_path, self.name)  
        
        self.config = data
        
        return self.config

    # Generate a server.cfg from JSON config   
    def generate_server_config(self):
        with open("{}/server.template".format(self.config_path), 'r') as file:
            data = file.read()
            
            # Server
            data = data.replace("[host_name]",self.config['server']['host_name'])
            data = data.replace("[discord]",self.config['server']['discord'])
            data = data.replace("[rcon_password]",self.config['security']['rcon_password'])
            data = data.replace("[log_name]",self.config['server']['log_file'])
            
            # Messages
            data = data.replace("[message_of_the_day]",self.config['messages']['message_of_the_day'].replace("\n","\\n"))
            
            # Game
            data = data.replace("[server_password]",self.config['security']['server_password'])
            data = data.replace("[map_win_limit]",str(self.config['game']['map_win_limit']))
            data = data.replace("[map_round_limit]",str(self.config['game']['map_round_limit']))
            data = data.replace("[balance_mode]",str(self.config['game']['balance_mode']))
            data = data.replace("[competitive_config]",str(self.config['game']['competitive_config']))
            
            # SMOD
            data = data.replace("[admin_1_password]",self.config['smod']['admin_1']['password']) 
            data = data.replace("[admin_1_config]",str(self.config['smod']['admin_1']['config']))
            
            data = data.replace("[admin_2_password]",self.config['smod']['admin_2']['password']) 
            data = data.replace("[admin_2_config]",str(self.config['smod']['admin_2']['config']))
            
            data = data.replace("[admin_3_password]",self.config['smod']['admin_3']['password']) 
            data = data.replace("[admin_3_config]",str(self.config['smod']['admin_3']['config']))   
            
            data = data.replace("[admin_4_password]",self.config['smod']['admin_4']['password']) 
            data = data.replace("[admin_4_config]",str(self.config['smod']['admin_4']['config']))
            
            data = data.replace("[admin_5_password]",self.config['smod']['admin_5']['password']) 
            data = data.replace("[admin_5_config]",str(self.config['smod']['admin_5']['config']))
            
            data = data.replace("[admin_6_password]",self.config['smod']['admin_6']['password']) 
            data = data.replace("[admin_6_config]",str(self.config['smod']['admin_6']['config']))
            
            data = data.replace("[admin_7_password]",self.config['smod']['admin_7']['password']) 
            data = data.replace("[admin_7_config]",str(self.config['smod']['admin_7']['config']))
            
            data = data.replace("[admin_8_password]",self.config['smod']['admin_8']['password']) 
            data = data.replace("[admin_8_config]",str(self.config['smod']['admin_8']['config']))
            
            data = data.replace("[admin_9_password]",self.config['smod']['admin_9']['password']) 
            data = data.replace("[admin_9_config]",str(self.config['smod']['admin_9']['config']))
            
            data = data.replace("[admin_10_password]",self.config['smod']['admin_10']['password']) 
            data = data.replace("[admin_10_config]",str(self.config['smod']['admin_10']['config']))

            # Maps
            data = data.replace("[map_1]",self.config['map_rotation_order'][0])
            data = data.replace("[map_2]",self.config['map_rotation_order'][1])
            data = data.replace("[map_3]",self.config['map_rotation_order'][2])
            data = data.replace("[map_4]",self.config['map_rotation_order'][3])
            data = data.replace("[map_5]",self.config['map_rotation_order'][4])
            data = data.replace("[map_6]",self.config['map_rotation_order'][5])
            data = data.replace("[map_7]",self.config['map_rotation_order'][6])
            data = data.replace("[map_8]",self.config['map_rotation_order'][7])
            data = data.replace("[map_9]",self.config['map_rotation_order'][8])
            
            # 0 = Open mode, 1 = Semi-Authentic, 2 = Full-Authentic, 3 = Duel, 4 = Legends
            
            # Mode
            if(self.config['game']['mode'].lower() == "open"):
                data = data.replace("[mode]","0")   
                
            if(self.config['game']['mode'].lower() == "semi-authentic"):
                data = data.replace("[mode]","1") 
                
            if(self.config['game']['mode'].lower() == "full-authentic"):
                data = data.replace("[mode]","2") 
                
            if(self.config['game']['mode'].lower() == "duel"):
                data = data.replace("[mode]","3") 
                
            if(self.config['game']['mode'].lower() == "legends"):
                data = data.replace("[mode]","4")    

            # Default if no matches were made
            data = data.replace("[mode]","0")                
            
            # Class Limits
            cl_string = ""
            for x in self.config['class_limits']:
                limit = self.config['class_limits'][x]
                if(limit < 10):
                    limit = "0" + str(limit)
                    
                cl_string = cl_string + str(limit) + "-"
                
            cl_string = cl_string.rstrip("-")
            data = data.replace("[class_limits]",cl_string)
            
            # Save to MBII Folder
            f = open(self.config['server']['server_config_path'], "w")
            f.write(data)
            f.close()

    # Generate an RTV RTM Config from JSON config
    def generate_rtvrtm_config(self):
    
        if(self.config['server']['enable_rtv'] or self.config['server']['enable_rtm']):
    
            with open("{}/rtvrtm.template".format(self.config_path), 'r') as file:
            
                data = file.read()
                data = data.replace("[log_path]", self.config['server']['log_path'])
                data = data.replace("[rcon_password]",self.config['security']['rcon_password'])          
                data = data.replace("[primary_maps_path]",  self.config['server']['primary_maplist_path'])    
                data = data.replace("[secondary_maps_path]", self.config['server']['secondary_maplist_path'])            
                data = data.replace("[mbii_path]", self.mbii_path)           
                data = data.replace("[port]",str(self.config['server']['port']))  

                if(self.config['server']['enable_rtv']):
                    data = data.replace("[rtv_mode]","1")  
                else:
                    data = data.replace("[rtv_mode]","0")  
 
                if(self.config['server']['enable_rtm']):
                    data = data.replace("[rtm_mode]",str(self.config['server']['rtm_mode'])) 
                else:
                    data = data.replace("[rtm_mode]","0")                     
                    
            f = open(self.config['server']['rtvrtm_config_path'], "w")
            f.write(data)
            f.close()
            time.sleep(0.3)
       
    # Generate RTV RTM Maps List from JSON config
    def generate_rtvrtm_map_lists(self):
    
        if(self.config['server']['enable_rtv']):
            f = open(self.config['server']['primary_maplist_path'], "w")
            f.write("\n".join(self.config['primary_maps']))
            f.close()             
        
            f = open(self.config['server']['secondary_maplist_path'], "w")
            f.write("\n".join(self.config['secondary_maps']))
            f.close()           
      