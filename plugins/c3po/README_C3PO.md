# C-3PO Protocol Droid Plugin

## Overview
C-3PO is a Star Wars-themed LLM (Large Language Model) bot plugin for MBIIEZ that connects to an external Ollama server for AI responses. The bot responds to chat commands and can provide automatic announcements for kills, welcomes, and map changes with C-3PO's characteristic polite and anxious personality.

## Features
- **External Ollama Support**: Connects to remote Ollama servers
- **Low Memory**: Works on 1GB game servers (AI processing on separate server)
- **Smart Fallbacks**: Contextual responses when Ollama is unavailable
- **Star Wars Theme**: C-3PO protocol droid personality with authentic responses
- **Multiple Chat Commands**: `!c3po`, `!3po`, `!droid`, `!protocol`
- **Auto Responses**: Kill announcements, welcome messages, map comments
- **Rate Limiting**: Prevents spam with cooldown periods
- **Proper Protocol**: Polite, formal responses with concern for odds and safety

## Installation

### 1. Set up External Ollama Server
On your AI server (separate from game server):
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama with external access
ollama serve --host 0.0.0.0:11434

# Download a model
ollama pull llama3.2:3b
```

### 2. Install Python Dependencies
On your game server:
```bash
pip install requests
```

### 3. Configure the Plugin
Add this to your instance configuration file:

```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://your-external-server-ip:11434",
            "auth": {
                "username": "your-username",
                "password": "your-password"
            },
            "model": "llama3.2:3b",
            "max_tokens": 100,
            "temperature": 0.7,
            "rate_limit_seconds": 10,
            "chat_commands": ["!c3po", "!3po", "!droid", "!protocol"],
            "personality": "You are C-3PO, a protocol droid fluent in over six million forms of communication. You are proper, polite, sometimes anxious, and knowledgeable about Star Wars lore. You often worry about the odds and express concerns about dangerous situations. Keep responses brief and in character. Always speak in a polite, formal manner and occasionally mention odds or express worry about dangerous situations.",
            "auto_responses": {
                "enabled": true,
                "kill_announcements": true,
                "welcome_messages": true,
                "map_comments": true
            }
        }
    }
}
```

## Usage

### Chat Commands
Players can interact with C-3PO using any of these commands:
- `!c3po What's the best weapon for beginners?`
- `!3po Tell me about this map`
- `!droid How do I get better at this game?`
- `!protocol What are the odds of winning?`

### Auto Responses
- **Kill Announcements**: 15% chance to comment on kills
- **Welcome Messages**: 30% chance to welcome new players
- **Map Comments**: 50% chance to comment on map changes

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `ollama_url` | External Ollama server URL | `http://localhost:11434` |
| `auth.username` | Basic auth username (optional) | `None` |
| `auth.password` | Basic auth password (optional) | `None` |
| `api_key` | API key for authentication (fallback) | `None` |
| `model` | Ollama model to use | `llama3.2:3b` |
| `max_tokens` | Maximum response length | `100` |
| `temperature` | Response creativity (0-1) | `0.7` |
| `rate_limit_seconds` | Cooldown between player questions | `10` |
| `chat_commands` | Commands that trigger the bot | `["!c3po", "!3po", "!droid", "!protocol"]` |
| `personality` | Bot personality prompt | C-3PO protocol droid character |
| `auto_responses.enabled` | Enable automatic responses | `true` |
| `auto_responses.kill_announcements` | Announce kills | `true` |
| `auto_responses.welcome_messages` | Welcome new players | `true` |
| `auto_responses.map_comments` | Comment on map changes | `true` |

## Recommended Models

### For External Servers (4GB+ RAM recommended)
- `llama3.2:1b` - Fastest, basic responses
- `llama3.2:3b` - Good balance of speed and quality (recommended)
- `llama3.2:7b` - Better responses, more knowledgeable
- `llama3.1:8b` - Excellent quality, slower responses

## Troubleshooting

### Bot Not Responding
1. Check if external Ollama is running: `curl http://your-server:11434/api/tags`
2. Verify model is installed on external server: `ollama list`
3. Check network connectivity between game server and Ollama server
4. Check MBIIEZ logs for connection errors
5. Ensure firewall allows port 11434

### External Ollama Setup

### Basic Setup
Make sure your external Ollama server is configured for external access:
```bash
# On your external server
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Or start with explicit host binding
ollama serve --host 0.0.0.0:11434
```

### Authentication Setup
If your Ollama server is behind a reverse proxy with Basic Authentication, configure it like this:

**Basic Auth (Recommended for nginx/apache protected servers):**
```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://your-external-server:11434",
            "auth": {
                "username": "your-username",
                "password": "your-secure-password"
            },
            "model": "llama3.2:3b"
        }
    }
}
```

**API Key (Alternative method):**
```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://your-external-server:11434",
            "api_key": "your-secure-api-key-here",
            "model": "llama3.2:3b"
        }
    }
}
```

**No Authentication (Open server):**
```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://your-external-server:11434",
            "model": "llama3.2:3b"
        }
    }
}
```

The plugin will automatically detect your authentication method:
1. **Basic Auth** is tried first if `auth` object is provided
2. **API Key** is used if `api_key` is provided but no `auth` object
3. **No authentication** if neither is configured

### Setting up Basic Auth with Nginx
If you want to secure your Ollama server with Basic Auth using nginx:

```nginx
server {
    listen 11434;
    server_name your-domain.com;

    # Basic Auth
    auth_basic "Ollama Server";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://localhost:11434;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Create the password file:
```bash
# Install htpasswd utility
sudo apt-get install apache2-utils

# Create user and password
sudo htpasswd -c /etc/nginx/.htpasswd your-username
```

### Network Issues
- Ensure port 11434 is open on your external server
- Check if there's a firewall blocking the connection
- Test connection: `telnet your-server-ip 11434`

### Slow Responses
1. Use a smaller model (1b or 3b) on external server
2. Ensure external server has adequate RAM
3. Consider reducing `max_tokens` to 50-75

## Security Notes
- Data sent to your external Ollama server only (no third-party services)
- Ensure your external Ollama server is secured appropriately
- Bot responses are filtered for length to prevent chat spam
- Rate limiting prevents abuse
- Smart fallbacks work offline when external server is unavailable

## Example Interactions

**Player**: `!c3po What's the best class for beginners?`

**C-3PO**: `Oh my! For new combatants, I do recommend the Soldier class - reliable blaster, good armor, and straightforward controls. The odds of survival are much better with proper equipment!`

**Player**: `!3po Tell me about Jedi`

**C-3PO**: `How wonderful! Jedi are Force-users with lightsabers and special abilities. They're quite powerful, though I must warn you - the odds of mastering their techniques are approximately 3,720 to 1 against!`

## Smart Fallbacks

Even without the external Ollama server, C-3PO provides contextual responses:

**Player**: `!c3po What weapon should I use?`

**C-3PO (fallback)**: `^6Oh my! The E-11 blaster is quite reliable for new combatants!`

**Player**: `!c3po Help me`

**C-3PO (fallback)**: `^6Oh my! Try the tutorial modes first - most educational!`
