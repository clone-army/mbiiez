import discord
from discord.ext import commands
from mbiiez.helpers import helpers
import asyncio
import re
import time
import uuid

class plugin:

    plugin_name = "Discord Bot"
    plugin_author = "Your Name"
    plugin_url = ""
    
    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['discord_bot']
        
        # Initialise the Discord bot
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        self.bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
        self.bot.add_listener(self.on_ready)
        
        # Chat Functionality 
        self.chatter_enabled = False # Is Chat Enabled
        self.chatter_channel = None # Chatter Channel  
                
        self.instance.chatter_buffer = [];


    def register(self):
        self.chat_buffer = chatBuffer()
        self.instance.process_handler.register_service("Discord Bot Service", self.start_discord_bot) # The Discord Bot for Commands        
        #self.instance.event_handler.register_event("player_chat", self.handle_chat) # Adds new chat to the buffer
       
            
    async def handle_chat(self, args):
        await self.bot.start(self.config['token'])
        await self.bot.wait_until_ready()  # Ensure bot is ready
        message = f"{args['player']}: {args['message']}"
        
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.name.endswith(f"server-{self.instance.name}-chat"):
                    await channel.send(message)
                    print(f"Message sent to {channel.name}: {message}")


    async def testing(self):
        print("testing testing")

        for guild in self.bot.guilds:
            print("guids")
            for channel in guild.text_channels:
                print("channels")
                if channel.name.endswith(f"server-{self.instance.name}-chat"):
                    print(channel.name)
                    await channel.send("hello world 2")  # Send each message  


    async def start_discord_bot(self):
    
        await self.bot.add_cog(ServerBot(self.bot, self.instance))
        # This blocks the service thread, so ensure this is what you want
        await self.bot.start(self.config['token'])

    async def on_ready(self):

        print(f'Logged in as {self.bot.user}')       
        await self.bot.add_cog(ServerBot(self.bot, self.instance))
        await self.bot.change_presence(activity=discord.Game(name='Powered by MBIIEZ'))
        
class chatBuffer:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(chatBuffer, cls).__new__(cls)
            cls._instance.buffers = {}

        return cls._instance

    def add_message(self, instance_name, message):
        print("new message was sent....")
        if instance_name not in self.buffers:
            print("setup new instance in buffer")
            self.buffers[instance_name] = []
        self.buffers[instance_name].append(message)
        print("message added to buffer")
        print(f"P {str(len(self.buffers[instance_name]))} messages in buffer")
        
    def get_id(self):
        """Returns the unique identifier of the singleton instance."""
        return id(self)
        
    def set_thing(self, thing):
        self.thing = thing
        
    def get_thing(self):
        return self.thing
        
    def get_messages(self, instance_name):
        print("getting messages")
        print(f"G {str(len(self.buffers[instance_name]))} messages in buffer")
        if instance_name in self.buffers:
            messages = self.buffers[instance_name][:]
            self.buffers[instance_name].clear()
            return messages
        return []

    def clear(self, instance_name):
        if instance_name in self.buffers:
            self.buffers[instance_name].clear()

    def is_empty(self, instance_name):
        return len(self.buffers.get(instance_name, [])) == 0
       


class ServerBot(commands.Cog):
    def __init__(self, bot, instance):
        self.bot = bot
        self.instance = instance
        self.rs = ServerBotResponse()

    @commands.command(name="server")
    async def commands_all(self, ctx, *args):
        self.rs.clear()
        # Commands logic remains the same as the previous version
        
    @commands.command(name="test")
    async def test_command(self, ctx):
        await ctx.send("Hello! The bot is working.")
            

class ServerBotResponse:
    def __init__(self):
        self.message = ""

    def append(self, message):
        self.message += str(message) + "\n"
    
    def get(self):
        return helpers().ansi_strip(self.message)
    
    def clear(self):
        self.message = ""
    
    def empty(self):
        return self.message.strip() == ""

# Usage of the Plugin class should be where you can ensure it's instantiated correctly.


class ServerBot(commands.Cog):
    def __init__(self, bot, instance):
        self.bot = bot
        self.instance = instance
        self.rs = ServerBotResponse()

    async def botSay(self, text):
        self.rs.clear()
        self.rs.append(f"{text}")
        await ctx.send(self.rs.get())
        
        
    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.change_presence(activity=discord.Game(name='Powered By MBIIEZ'))
        print(f"Logged in as {self.bot.user.name}")

    @commands.command(name="server")
    async def commands_all(self, ctx, *args):
        try:
            if args[0] == "list":
                await ctx.send(f"**{self.instance.name}**")

            elif args[0] == "help":
                help_message = (
                    "Full Commands Available:\n"
                    "`!server list` - This will list all available server instances running this bot you can send commands to in place of <instance>\n"
                    "`!server <instance> map <map>` - Change the map\n"
                    "`!server <instance> restart` - Currently broken! Don't use this\n"
                    "`!server <instance> status` - Dump the status of the server, including map, players, uptime, etc\n"
                    "`!server <instance> test` - Runs a ping test to various countries and locations and returns results\n"
                    "`!server <instance> player <id>` - Returns info about player with the given ID. Get ID from status\n"
                    "`!server <instance> kick <id>` - Kick a player with a given ID\n"
                    "`!server <instance> ban <ip>` - Ban a given IP. You can get player IP from status or player\n"
                    "`!server <instance> unban <ip>` - UnBan a given IP\n"
                    "`!server <instance> say <message>` - Send a message which will be seen by all in the server\n"
                    "`!server <instance> tell <id> <message>` - Send a message to a given player directly by their ID\n"
                        )
                await ctx.send(help_message)                
                 
            elif args[0] == self.instance.name:

                if args[1] == "players":
                    player_count = self.instance.players_count()
                    await ctx.send(f"**{self.instance.name}** instance currently has **{player_count}** players")
                    if player_count > 0:
                        players = self.instance.players()
                        player_names = ", ".join(player['name'] for player in players)
                        await ctx.send(f"Players: {player_names}")

                elif args[1] == "status":
                    await ctx.send(f"Fetching {self.instance.name} status...")
                    status = self.instance.status_text()
                    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
                    await ctx.send(ansi_escape.sub('', status))
                    
                elif args[1] == "player":
                    await ctx.send(f"Fetching {self.instance.name} player {args[2]} info...")
                    dump = self.instance.player(args[2])
                    await ctx.send(dump)                

                elif args[1] == "test":
                    await ctx.send(f"Running Ping Test on **{self.instance.name}**. ... Please Wait :clock1:...")
                    test = self.instance.test()
                    await ctx.send(test)

                elif args[1] == "restart":
                    await ctx.send(f"Restarting Instance **{self.instance.name}**...")
                    self.instance.restart()
                    await ctx.send(f"Instance **{self.instance.name}** restarted successfully.")

                elif args[1] == "map":
                    await ctx.send(f"Changing map on **{self.instance.name}** to **{args[2]}**. ... Please Wait :clock1:...")
                    map_result = self.instance.map(args[2])
                    await ctx.send(f"Map changed to **{args[2]}** on **{self.instance.name}** :white_check_mark:.")

                elif args[1] == "say":
                    self.instance.say(args[2])
                    await ctx.send(f"Message Sent: {args[2]}")

                elif args[1] == "tell":
                    self.instance.tell(args[2], args[3])
                    await ctx.send(f"Message Sent to {args[2]}: {args[3]}")

                elif args[1] == "kick":
                    await ctx.send(f"Kicking Player with ID {args[2]} ... Please Wait :clock1:...")                
                    self.instance.kick(args[2])
                    await ctx.send(f"Kicked Player with ID {args[2]} :white_check_mark:")
                    
                elif args[1] == "ban":
                    await ctx.send(f"Banning IP {args[2]} ... Please Wait :clock1:...")                
                    self.instance.ban(args[2])
                    await ctx.send(f"Banned IP {args[2]} :white_check_mark:")                    

                elif args[1] == "unban":
                    await ctx.send(f"Unbanning IP {args[2]} ... Please Wait :clock1:...")                
                    self.instance.ban(args[2])
                    await ctx.send(f"Unbanned IP {args[2]} :white_check_mark:")   

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
