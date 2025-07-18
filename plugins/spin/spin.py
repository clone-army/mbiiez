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
import time

class plugin:

    plugin_name = "Spin Mode"
    plugin_author = "Louis Varley"
    plugin_url = ""

    instance = None
    plugin_config = None
    
    # LIST to hold all previous spins
    spins = {}

    ''' You must initialise instance which you can use to access the running instance '''
    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['spin']
        
        if(self.instance.has_plugin("auto_message")):
            self.instance.config['plugins']['auto_message']['messages'].append("You can run the ^3!spin^7 command in chat to get a random perk or handicap")
            self.instance.config['plugins']['auto_message']['messages'].append("^3!spin^7 has a " + str(self.config['cooldown']) + " second cooldown. Use your spins wisley",)
            self.instance.config['plugins']['auto_message']['messages'].append("You can bind spin to a key by opening the console and entering: ^3bind <KEY> 'say !spin'^7")            
            self.instance.config['plugins']['auto_message']['messages'].append("As a Jedi or Sith, you may have to set some keys to allow use of items instead of force powers") 
            self.instance.config['plugins']['auto_message']['messages'].append("Items can only be used by Jedi and Sith when their saber is out... for some reason...") 
            self.instance.config['plugins']['auto_message']['messages'].append("All is fair in Love and Spin! May the luck be with you!")
            
        v = 0    
        for k in self.config['perks_chances']:    
            v = v + self.config['perks_chances'][k] 
            
        if(v > 100 or v < 100):
            self.instance.log_handler.log("Spin Perk Chances is currently {} but should add up to 100%".format(v))

    ''' use register event to have your given method notified when the event occurs '''
    def register(self):
        self.instance.event_handler.register_event("player_chat_command", self.spin_process)
        

        
    def spin_process(self, args):
        if(args['message'].startswith("!spin")): 
        
            rand = random.randint(1,100)
            command = None
            t = 0
            
            if(args['player_id'] in self.spins):
                s = (datetime.datetime.now() - self.spins[args['player_id']]).total_seconds()
                if(s < self.config['cooldown']):
                    self.instance.tell(args['player_id'], "Spin is still in cooldown for another {} seconds".format(int(self.config['cooldown'] - s)))
                    return;
                    
            self.spins[args['player_id']] = datetime.datetime.now()        
    
            for k in self.config['perks_chances']:
                t = t + self.config['perks_chances'][k]
                if(rand <= t):
                    break;
        
            if(k=="lightsaber"): 
                self.instance.rcon("wannabe {} give weapon 1".format(args['player_id'])) 
                self.instance.tell(args['player_id'], "You win a LightSaber!")   
                
            elif(k=="disruptor"):
                self.instance.rcon("wannabe {} give weapon 4".format(args['player_id']) )  
                self.instance.tell(args['player_id'], "You win a Disruptor")
                
            elif(k=="projectile_rifle"): 
                command = "wannabe {} give weapon 5".format(args['player_id'])
                self.instance.rcon(command)  
                self.instance.tell(args['player_id'], "You win a Projectile Rifle")
                
            elif(k=="bowcaster"):
                self.instance.rcon("wannabe {} give weapon 6".format(args['player_id']))  
                self.instance.tell(args['player_id'], "You win a Bowcaster")
                
            elif(k=="dc15"):
                self.instance.rcon("wannabe {} give weapon 7".format(args['player_id']))  
                self.instance.tell(args['player_id'], "You win a DC15")
                
            elif(k=="arc_pistol"):
                self.instance.tell(args['player_id'], "You win an ARC Pistol")
                command = "wannabe {} give weapon 8".format(args['player_id'])
                self.instance.rcon(command) 
                
            elif(k=="rocket_launcher"):   
                self.instance.rcon("wannabe {} give weapon 10".format(args['player_id']))      
                self.instance.tell(args['player_id'], "You win a Rocket Launcher")   
                
            elif(k=="frag_grenades"):              
                self.instance.rcon("wannabe {} give weapon 11".format(args['player_id'])   )        
                self.instance.tell(args['player_id'], "You win a Frag Grenade")
                
            elif(k=="pulse_grenades"):              
                self.instance.rcon("wannabe {} give weapon 12".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win 2 Pulse Grenades")
                
            elif(k=="t21"):
                command = "wannabe {} give weapon 13".format(args['player_id'])              
                self.instance.rcon(command)
                self.instance.tell(args['player_id'], "You win a T21")
                
            elif(k=="arm_blaster"):
                self.instance.rcon("wannabe {} give weapon 14".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win an Arm Blaster")    
                
            elif(k=="welstar_34"): 
                self.instance.rcon("wannabe {} give weapon 15".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Welstar34")
                                
            elif(k=="armor_500"):
                self.instance.rcon("wannabe {} give armor 500".format(args['player_id']))
                self.instance.tell(args['player_id'], "Your armor is now 500")
                
            elif(k=="armor_200"):
               
                command = "wannabe {} give armor 200".format(args['player_id'])  
                self.instance.rcon(command)
                self.instance.tell(args['player_id'], "Your armor is now 200") 
                
            elif(k=="armor_0"):
                self.instance.rcon("wannabe {} give armor 0".format(args['player_id']))
                self.instance.tell(args['player_id'], "You armor is now 0")               
                     
            elif(k=="nothing"):
                self.instance.tell(args['player_id'], "You won... nothing, sorry...")
         
            elif(k=="big"):
                command = "wannabe {} set player_scale 150".format(args['player_id'])
                self.instance.rcon(command)
                self.instance.tell(args['player_id'], "You unexpectedly grew!")
 
            elif(k=="small"):
                self.instance.rcon("wannabe {} set player_scale 50".format(args['player_id']))
                self.instance.tell(args['player_id'], "Have you lost some weight?")
                                
            elif(k=="binovision"):
                self.instance.rcon("wannabe {} set zoom_mode 2".format(args['player_id']))
                self.instance.tell(args['player_id'], "Did you just glue them binoculars to your face?")

            elif(k=="seekerdroid"):
                self.instance.rcon("wannabe {} give item 1".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Padawan's Seekerdroid!")                

            elif(k=="jetpack"):
                self.instance.rcon("wannabe {} give item 7".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Jetpack!")
                
            elif(k=="sentry"):
                self.instance.rcon("wannabe {} give item 6".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Automated Sentry Gun!")                

            elif(k=="cloak"):
                self.instance.rcon("wannabe {} give item 11".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Cloaking Device!")                
             
            elif(k=="emplacement"):
                self.instance.rcon("wannabe {} give item 10".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Gun Implacement!") 	
         
            elif(k=="bacta"):
                self.instance.rcon("wannabe {} give item 4".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Tank of Bacta!") 	
       
            elif(k=="forcefield"):
                self.instance.rcon("wannabe {} give item 2".format(args['player_id']))
                self.instance.tell(args['player_id'], "You win a Forcefield Generator!") 

            elif(k=="tauntaun"):
                self.instance.tell(args['player_id'], "You win a Taun Taun!. You have 5 seconds to get to a place it can spawn")  
                time.sleep(5)
                self.instance.rcon("wannacheat 1")
                time.sleep(0.5)
                self.instance.rcon("wannabe {} give tauntaun".format(args['player_id']))                
                self.instance.rcon("wannacheat 0")               
                               
                
            elif(k=="swoop"):
                self.instance.tell(args['player_id'], "You win a Swoopbike!. You have 5 seconds to get to a place it can spawn")  
                time.sleep(5)
                self.instance.rcon("wannacheat 1")
                time.sleep(0.5)
                self.instance.rcon("wannabe {} give swoop".format(args['player_id']))                
                self.instance.rcon("wannacheat 0")               
                
            # Log This Spin
            self.spins[args['player_id']] = datetime.datetime.now()
         
           
