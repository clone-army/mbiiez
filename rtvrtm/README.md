# RTVRTM for MBII - Python3 Version

This is a Python3 port of the original RTVRTM (Rock The Vote/Rock The Mode) script for Movie Battles II servers.

## Features

- **Rock The Vote (RTV)**: Players can vote to change the current map
- **Rock The Mode (RTM)**: Players can vote to change the current game mode
- **Map Nominations**: Players can nominate maps for voting
- **Flood Protection**: Prevents command spam
- **Configurable Vote Thresholds**: Set percentage of players needed to start/win votes
- **Primary/Secondary Map Lists**: Separate map pools for voting

## Requirements

- Python 3.6 or higher
- MBII Server with RCON enabled
- Server logging enabled with proper settings

## Server Configuration

Your MBII server must have these settings in `server.cfg`:

```
seta g_logSync "1"
seta g_logExplicit "3" 
seta rconPassword "your_password_here"
```

## Installation

1. Copy all files from this `rtvrtm` folder to your server
2. Edit `rtvrtm.cfg` with your server settings:
   - Set the correct log file path
   - Set your server IP and port (usually 127.0.0.1:29070)
   - Set your RCON password
   - Configure map lists and vote settings

3. Edit `maps.txt` and `secondary_maps.txt` with your map lists
4. Run the script:
   - Windows: Run `start.bat` or `python rtvrtm.py rtvrtm.cfg`
   - Linux: Run `./start.sh` or `python3 rtvrtm.py rtvrtm.cfg`

## Configuration

Edit `rtvrtm.cfg` to customize:

- **Log**: Path to your server log file
- **Address**: Server IP:Port (usually 127.0.0.1:29070)
- **Password**: Your RCON password
- **RTV/RTM percentages**: % of players needed to start votes
- **Vote time**: How long votes last (seconds)
- **Flood protection**: Anti-spam delay (seconds)

## Commands

### Player Commands
- `!rtv` - Vote to rock the vote (change map)
- `!unrtv` - Remove your RTV vote
- `!rtm` - Vote to rock the mode (change game mode)
- `!unrtm` - Remove your RTM vote
- `!maplist 1` - Show primary maps
- `!maplist 2` - Show secondary maps  
- `!modelist` - Show available game modes
- `!nominate <mapname>` - Nominate a map for voting
- `!1`, `!2`, `!3`, `!4` - Vote for option 1, 2, 3, or 4 during active votes

### Vote Process
1. Players use `!rtv` or `!rtm` to start voting
2. When enough players vote, a map/mode vote begins
3. Players vote using `!1`, `!2`, etc. for their preferred option
4. After the vote time expires, the winning option is applied next round

## Game Modes
- 0 = Open
- 1 = Semi-Authentic  
- 2 = Full-Authentic
- 3 = Duel
- 4 = Legends

## Troubleshooting

### Common Issues:
1. **"No rcon password configured"**: Set the Password field in rtvrtm.cfg
2. **"No log file path configured"**: Set the Log field to your server's log file
3. **Commands not working**: Check that g_logSync and g_logExplicit are set correctly
4. **Connection refused**: Verify server IP/port and RCON password

### Debugging:
- Check that the log file exists and is being written to
- Verify RCON connection by testing with other RCON tools
- Make sure Python 3.6+ is installed
- Check file permissions on log file

## File Structure
```
rtvrtm/
├── rtvrtm.py          # Main Python script
├── rtvrtm.cfg         # Configuration file
├── maps.txt           # Primary map list
├── secondary_maps.txt # Secondary map list
├── start.bat          # Windows startup script
├── start.sh           # Linux startup script
└── README.md          # This file
```

## Original Credits

Based on the original RTVRTM script by klax/Cthulhu@GBITnet.com.br
Python3 port by MBIIEZ Team

## License

BSD 2-Clause License - See original script header for full license text.
