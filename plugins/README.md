# MBIIEZ Plugins

This directory contains plugins for the MBIIEZ server management system.

## Plugin Structure

All plugins are now organized in folders with clean names:

```
plugins/
├── auto_message/
│   ├── auto_message.py
│   └── README.md
├── auto_map_rotation/
│   ├── auto_map_rotation.py
│   └── README.md
├── chatgpt/
│   ├── chatgpt.py
│   └── README.md
├── discord_bot/
│   ├── discord_bot.py
│   └── README.md
├── r2d11/
│   ├── r2d11.py
│   ├── install_r2d11.sh
│   ├── update_r2d11.sh
│   ├── README.md
│   └── config files...
├── rtvrtm/
│   ├── rtvrtm.py
│   └── README.md
├── shield/
│   ├── shield.py
│   └── README.md
├── spin/
│   ├── spin.py
│   └── README.md
├── stats/
│   ├── stats.py
│   └── README.md
└── updater/
    ├── updater.py
    └── README.md
```

## How Plugin Loading Works

The plugin system automatically detects and loads plugins using this priority:

1. **Folder-based (new)**: Looks for `plugin_name/plugin_name.py`
2. **Legacy file-based**: Looks for `plugin_name.py` in the plugins directory
3. **Legacy with prefix**: Looks for `plugin_plugin_name.py` in the plugins directory

## Available Plugins

### Core Plugins
- `auto_message/` - Automatic server messages
- `auto_map_rotation/` - Automatic map rotation
- `chatgpt/` - ChatGPT integration (requires API key)
- `discord_bot/` - Discord bot integration
- `rtvrtm/` - RTV/RTM voting system
- `shield/` - Player protection
- `spin/` - Spin effects
- `stats/` - Player statistics
- `updater/` - Auto-updater

### Advanced Plugins
- `r2d11/` - R2-D11 LLM Bot with Ollama (Star Wars themed, offline AI)

## Creating New Plugins

### For Simple Plugins
Create a single Python file:
```python
# plugins/plugin_mybot.py
class plugin:
    plugin_name = "My Bot"
    plugin_author = "Your Name"
    
    def __init__(self, instance):
        self.instance = instance
        
    def register(self):
        # Register events here
        pass
```

### For Complex Plugins
Create a folder structure:
```
plugins/plugin_mybot/
├── plugin_mybot.py         # Main plugin file
├── install_mybot.sh        # Installation script
├── update_mybot.sh         # Update script
├── README.md               # Documentation
├── config_example.json     # Example config
└── requirements.txt        # Dependencies
```

## Plugin Configuration

Add plugin configuration to your instance config file:

```json
{
    "plugins": {
        "plugin_name": {
            "enabled": true,
            "setting1": "value1",
            "setting2": "value2"
        }
    }
}
```

## Plugin Events

Plugins can register for these events:

- `before_dedicated_server_launch` - Before server starts
- `after_dedicated_server_launch` - After server starts
- `new_log_line` - New log line detected
- `player_chat_command` - Chat command (!command)
- `player_chat` - Any player chat
- `player_connects` - Player joins
- `player_disconnects` - Player leaves
- `player_killed` - Player death
- `player_begin` - Player spawns
- `map_change` - Map changes

## Plugin Development

### Basic Plugin Template
```python
class plugin:
    plugin_name = "Your Plugin Name"
    plugin_author = "Your Name"
    plugin_url = "https://github.com/your/repo"
    
    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins']['your_plugin']
        
    def register(self):
        self.instance.event_handler.register_event("player_chat_command", self.on_chat)
        
    def on_chat(self, args):
        player = args['player']
        message = args['message']
        # Handle chat commands
```

### Plugin Methods Available
- `self.instance.say(message)` - Send public message
- `self.instance.tell(player_id, message)` - Send private message
- `self.instance.rcon(command)` - Execute RCON command
- `self.instance.players()` - Get player list
- `self.instance.map()` - Get current map
- `self.instance.mode()` - Get current game mode

## Installing Complex Plugins

For folder-based plugins with installation scripts:

```bash
cd plugins/plugin_name/
chmod +x install_plugin.sh
./install_plugin.sh
```

## Migration from Single File to Folder

To migrate a single file plugin to folder structure:

1. Create folder: `mkdir plugins/plugin_name/`
2. Move file: `mv plugin_name.py plugins/plugin_name/`
3. Add installation scripts, README, etc.
4. The plugin loader will automatically detect the new structure

## Troubleshooting

### Plugin Not Loading
- Check plugin name matches folder name
- Ensure `plugin_name.py` exists in the folder
- Check for syntax errors in the plugin
- Look at MBIIEZ logs for error messages

### Plugin Errors
- Check instance config has plugin enabled
- Verify plugin dependencies are installed
- Check plugin-specific documentation in plugin folder

## Contributing

When creating new plugins:

1. Use folder structure for complex plugins
2. Include installation scripts for dependencies
3. Provide clear documentation
4. Include example configurations
5. Handle errors gracefully
6. Follow the existing plugin patterns
