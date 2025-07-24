## Movie Battles II EZ

MBIIEZ is a python wrapper for running instances of Movie Battles II. 
The wrapper acts as both a CLI (Command Line Interface) as well as a Web GUI for managing instances. 

In a sense, you should not need to edit server configs, RTV/RTM configs, understand installing any of the components needed to run an MBII server. Using the WebGUI to manage everything instead and basic JSON config files. 

## Features
- Simple to use Web GUI 
- Simple CLI for running automated commands
- Plugin System for creating additional plugins 
- Included plugins include 
- - Auto Server Messages, Unlimited rotating service messages  
- - RTV/RTM, integrated as a plugin  
- - Discord Bot, allow certain roles in your discord channel, to restart instances, change map, kick players, etc

## Installing

- Clone this repo into your home directory using `git clone https://github.com/clone-army/mbiiez` 
- Run `chmod +x install.sh` on the installation bash script
- Run `./install.sh` which will install all required depedencies
- Amend the mbiiez.conf file to ensure paths are correctly set to your MBIIEZ path
- Installation is a simple step by step process
- Movie Battles II is downloaded automatically, as well as the most recent build of OpenJK For Linux

## Updating
- Run the included update.sh to update MBII
- Recommend putting this into a crontab every 10 minutes
- It will automatically restart instances once update is done, unless there are players, then it will wait until empty 
- git pull to grab updates from this repo for MBIIEZ

## Adding Base files

Base files are downloaded automatically


## Instances
"Instances" are a single game servers. Most modern virtual servers or bare metal servers can support a number of instances running together. These instances will normally have a name. such as **open** or **duel**. Each instance will have a different port number

## Creating an Instance

All that is needed to create an instance is to create your own instance json file located in the `config` folder of the project. There is a template file already included in the config file.

The format is very easy to understand. (Easier than the OpenJK Server Config Files)

Edit the file and make any changes to the config which you want. Should you make any mistakes in the formatting. The server will not start and will warn you about JSON errors. 

Ensure the port you use in the config file is one you have not already assigned to another instance otherwise the program will have trouble monitoring and RTV/RTM will not work as the game will automatically assign it a different port. 

You need to also ensure any ports you do use are forwarded correctly and no firewall is blocking them

## Using the CLI

the CLI Enables simple commands to be executed against an instance. Most actions are in this format

`mbii -i [Name of your instance] ACTION`

There a number of actions that can be used when specifying an "instance" 

#### start 
start an instance
#### stop
stop an instance
#### restart
restart an instance
#### status
show stats such as players, the map, uptime, port, ip 
#### say [message] 
executes svsay on the server
`mbii -i dueling say "Hello Everyone"` would say "Server: Hello Everyone"
#### rcon [rcon_commands]
`mbii -i legends rcon "myrconcommand argument"` would send this rcon command to the server
#### cvar key value
You can change CVAR values or just see what the value is using cvar command, for example 
`mbii -i open cvar g_authenticity 1` would change the mode
`mbii -i open cvar g_authenticity` would print the current the mode

## Plugins

Plugins allow for new functionality for a server to be built as a seperate python script and added to the server. 

A plugin has access to the instance that is running it and could be used to, for example. Do a certain action when a command is said by a user, or once every 2 minutes. 
It can even be used to do actions on the server based on external factors, such as coming from discord.

Plugins must be enabled in the config section, must have a number of additional config options need to be added to the config. Any plugin can request additional config information. The Example server json has the RTV plugin enabled by default. 

leaving your plugin line in config as `"plugins":{},` will disable all plugins

### Events

Plugins can "register" actions against events. For example, the plugin will have a method called "register_events" and adding a line such as 

`self.instance.event_handler.register_event("player_chat_command", self.say_hello)`

Will, if the plugin is enabled on an instance, call the method within the plugin `say_hello` when a user in game does a chat starting with `!` 

Some events come with additional arguements that you can use.  Here is a current list of events plugins can use, They come in a dictionary object as the first arguement

|Name|Arguements  |Description |
|--|--|--|
|before_dedicated_server_launch| None |  Runs before dedicated server starts
|after_dedicated_server_launch | None  |   Runs after dedicated server starts
|new_log_line                  | log_line | Log File changed
|player_chat_command           | message, player, player_id | ! prefix chat 
|player_chat                   | type, message, player, player_id | any and all chats, type is either TEAM or PUBLIC 
|player_connects               | player, player_id |  A new player connected
|player_disconnects            | player, player_id |  A player disconnected
|player_killed                 | fragger_id fragger, fragged_id, fragged, weapon | A player was killed
|player_begin                  |  player,player_id | A player entered the map (once per round, not per life)
|map_change                    |current_map, new_map|


### Services

You can also register services in your plugin. These are methods you want to start as a seperate process and for them to persist while the instance runs. Otherwise methods are only called when events happen. This allows you to potentially create your own events. 

For example using 
`self.instance.event_handler.run_event("my_custom_event",{"type": "NEW", "message": message, "player_id": player_id, "player": player}) `

The process handler will automatically start your service, and shut it down when the instance is stopped by keeping track of its PID. 

## Database

A small SQLite database is used to store ALL log lines, all kills, keep track of services, and keep track of player connections in a way that persists. 

For this reason the database can be used by external processes to query this information, or in a plugin, if for example, a discord bot wants to show when the last time a given player connected. 

Usablity is limited as there is no way beyond a name, to track a player between connections. 

## Useful Included Plugins

There is an updater plugin, and it is active on the default version. This plugin will, based on the config scan for updates to MBII. It is recomended you only run the updater plugin on one instance. Although it can run on all instances
There is a chance you could have 3 updaters all checking files at the same time. Ideally the updater would be moved to the core, but the core doesnt have it's own processes management like instances does. 

## Get Involved
This is still a little rough round the edges, i am NOT a full python dev, if anyone is interested in doing further development on this or pushing pull requests into this thats all fine with me. 

## WebUI

- The webui can be installed using `bash install_web.sh` it will try to install as a service called `mbii-web`
- Run manually with `bash mbii-web.py`
- defaults to port 8080

### Still to do

- [x] Write an Update.sh file for updating MBII
- [x] Make process handler auto restart a failed service unless instance is being stopped
- [x] Make process handler auto restart instances at a given time rather than using crontab
- [x] Create the Web GUI
- [X] Web to edit server.json files
- [x] Web to show database logs
- [X] Web to handle bans
- [X] Web to handle plugins
- [X] Web to start / stop / restart instances


