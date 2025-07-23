# RTVRTM Plugin for MBIIEZ

This plugin integrates the original RTVRTM (Rock the Vote/Rock the Mode) script with the MBIIEZ plugin system while preserving its exact functionality.

## Features

- **Preserves Original Behavior**: The original RTVRTM script runs unchanged
- **Automatic Configuration**: Automatically gets server settings from MBIIEZ instance
- **JSON Configuration**: All voting and map settings managed through instance JSON config
- **Instance-Specific Files**: Generates unique config files with instance name prefixes
- **Full Integration**: Proper MBIIEZ plugin lifecycle management and logging

## Automatic Values

The plugin automatically retrieves these values from your MBIIEZ instance:

- **MBII Folder**: From `server.home_path` in instance config
- **Server Port**: From `server.port` in instance config  
- **RCON Password**: From `security.rcon_password` in instance config
- **Server Address**: Automatically set to `127.0.0.1:{port}`
- **Bind Address**: Automatically set to `127.0.0.1`
- **Log File**: Automatically set to `{instance_name}-games.log`

You don't need to specify these in your plugin configuration!

## How It Works

1. **Configuration Loading**: The plugin reads configuration from the instance JSON config
2. **File Generation**: Creates `{instance_name}_rtvrtm.cfg`, `{instance_name}_maps.txt`, and `{instance_name}_secondary_maps.txt` in the MBII folder
3. **RTVRTM Execution**: Launches the original RTVRTM script with the generated configuration file
4. **Monitoring**: Monitors the RTVRTM process and provides status through MBIIEZ logging

## Installation

1. Copy the entire `rtvrtm` folder to your `plugins/` directory
2. Add the RTVRTM configuration to your instance JSON config (see example below)
3. Restart your MBIIEZ instance

## Configuration

Add the following to your instance configuration JSON file under the `plugins` section:

```json
{
    "plugins": {
        "rtvrtm": {
            "general": {
                "log": "/opt/openjk/MBII/open-games.log",
                "mbii_folder": "/opt/openjk/MBII",
                "address": "127.0.0.1:29070",
                "bind": "127.0.0.1",
                "password": "your_rcon_password",
                "flood_protection": 0.5,
                "use_say_only": 0,
                "name_protection": 1,
                "default_game": "",
                "clean_log": "0"
            },
            "admin_voting": {
                "admin_voting": "1 30",
                "admin_minimum_votes": 51.0,
                "admin_skip_voting": 1
            },
            "map_limit": {
                "roundlimit": 1,
                "timelimit": 0,
                "limit_voting": "1 10",
                "limit_minimum_votes": 51.0,
                "limit_extend": "1 3",
                "limit_successful_wait_time": 300,
                "limit_failed_wait_time": 60,
                "limit_skip_voting": 1,
                "limit_second_turn": 1,
                "limit_change_immediately": 0
            },
            "rtv": {
                "rtv": 1,
                "rtv_rate": 60.0,
                "rtv_voting": "1 10",
                "rtv_minimum_votes": 51.0,
                "rtv_extend": "1 3",
                "rtv_successful_wait_time": 300,
                "rtv_failed_wait_time": 60,
                "rtv_skip_voting": 1,
                "rtv_second_turn": 1,
                "rtv_change_immediately": 0
            },
            "maps": {
                "automatic_maps": 0,
                "pick_secondary_maps": 5,
                "map_priority": "2 1 0",
                "nomination_type": 1,
                "enable_recently_played_maps": 3600
            },
            "rtm": {
                "rtm": 7,
                "mode_priority": "2 1 0 2 1 0",
                "rtm_rate": 60.0,
                "rtm_voting": "1 10",
                "rtm_minimum_votes": 51.0,
                "rtm_extend": "1 3",
                "rtm_successful_wait_time": 300,
                "rtm_failed_wait_time": 60,
                "rtm_skip_voting": 1,
                "rtm_second_turn": 1,
                "rtm_change_immediately": 0
            },
            "primary_maps": [
                "mb2_alderaan",
                "mb2_boc",
                "mb2_citadel",
                "mb2_cloudcity",
                "mb2_commtower",
                "mb2_deathstar",
                "mb2_dotf",
                "mb2_jeditemple",
                "mb2_kamino"
            ],
            "secondary_maps": [
                "mb2_cmp_arctic",
                "mb2_cmp_arena",
                "mb2_cmp_duel_vjun",
                "mb2_cmp_endor"
            ]
        }
    }
}
```

## Configuration Sections

### General Settings
- `log`: Path to the MBII server log file
- `mbii_folder`: Path to the MBII folder (for map detection)
- `address`: Server IP and port for RCON
- `bind`: Bind IP address for RCON communication
- `password`: Server RCON password
- `flood_protection`: Anti-flood protection in seconds
- `use_say_only`: Use only 'say' instead of 'svsay' (0=disabled, 1=enabled)
- `name_protection`: Enable name protection (0=disabled, 1=enabled)
- `default_game`: Default game mode and map
- `clean_log`: Log cleaning settings

### Admin Voting
- `admin_voting`: Admin voting settings (time/round based and duration)
- `admin_minimum_votes`: Minimum vote percentage required
- `admin_skip_voting`: Skip voting behavior

### Map Limit Settings
- `roundlimit`: Enable roundlimit-based voting (0=disabled, 1=enabled)
- `timelimit`: Enable timelimit-based voting (0=disabled, 1=enabled)
- `limit_voting`: Voting timing and method
- `limit_minimum_votes`: Minimum vote percentage
- `limit_extend`: Extension settings
- `limit_successful_wait_time`: Wait time after successful vote
- `limit_failed_wait_time`: Wait time after failed vote
- `limit_skip_voting`: Skip voting behavior
- `limit_second_turn`: Enable second turn voting
- `limit_change_immediately`: Change map immediately after vote

### Rock the Vote (RTV)
- `rtv`: Enable RTV (0=disabled, 1=enabled)
- `rtv_rate`: Percentage of players needed to trigger RTV
- `rtv_voting`: Voting timing and method
- `rtv_minimum_votes`: Minimum vote percentage
- `rtv_extend`: Extension settings
- `rtv_successful_wait_time`: Wait time after successful vote
- `rtv_failed_wait_time`: Wait time after failed vote
- `rtv_skip_voting`: Skip voting behavior
- `rtv_second_turn`: Enable second turn voting
- `rtv_change_immediately`: Change map immediately after vote

### Map Settings
- `automatic_maps`: Use automatic map detection (0=disabled, 1=enabled)
- `pick_secondary_maps`: Number of secondary maps to include in voting
- `map_priority`: Priority settings for primary/secondary/extend options
- `nomination_type`: Type of nomination system
- `enable_recently_played_maps`: Recently played maps restriction (seconds)

### Rock the Mode (RTM)
- `rtm`: RTM modes to enable (0-21, see RTVRTM documentation)
- `mode_priority`: Priority settings for different modes
- `rtm_rate`: Percentage of players needed to trigger RTM
- `rtm_voting`: Voting timing and method
- `rtm_minimum_votes`: Minimum vote percentage
- `rtm_extend`: Extension settings
- `rtm_successful_wait_time`: Wait time after successful vote
- `rtm_failed_wait_time`: Wait time after failed vote
- `rtm_skip_voting`: Skip voting behavior
- `rtm_second_turn`: Enable second turn voting
- `rtm_change_immediately`: Change mode immediately after vote

### Map Lists
- `primary_maps`: Array of primary map names
- `secondary_maps`: Array of secondary map names

## Files Generated

When the plugin starts, it creates these files in your MBII folder:
- `{instance_name}_rtvrtm.cfg`: Main RTVRTM configuration file
- `{instance_name}_maps.txt`: Primary maps list
- `{instance_name}_secondary_maps.txt`: Secondary maps list

## Troubleshooting

1. **Plugin Not Loading**: Check that the `rtvrtm` folder is in your `plugins/` directory
2. **RCON Issues**: Verify your server address and RCON password in the configuration
3. **Log File Access**: Ensure the log file path is correct and readable
4. **Map Issues**: Check that map names in the configuration match the actual map files

## Commands

All original RTVRTM commands work exactly as before:
- `!rtv` - Rock the Vote
- `!rtm` - Rock the Mode  
- `!nominate <map>` - Nominate a map
- `!maps` - List available maps
- And all other original commands

## Logging

The plugin integrates with MBIIEZ logging. Check your MBIIEZ logs for:
- Plugin initialization status
- Configuration file generation
- RTVRTM process status
- Any errors or warnings

## Original Credits

- Original RTVRTM script by klax / Cthulhu@GBITnet.com.br
- Python3 port and MBIIEZ integration
- Based on AlliedModders LLC RTV/RTM concept
