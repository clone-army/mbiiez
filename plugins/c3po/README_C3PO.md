# C-3PO Protocol Droid Plugin

## Overview
C-3PO is a Star Wars-themed LLM (Large Language Model) bot plugin for MBIIEZ that uses Ollama for offline AI responses. The bot responds to chat commands and can provide automatic announcements for kills, welcomes, and map changes with C-3PO's characteristic polite and anxious personality.

## Features
- **Offline LLM**: Uses Ollama (no API keys or usage limits required)
- **Star Wars Theme**: C-3PO protocol droid personality with authentic responses
- **Multiple Chat Commands**: `!c3po`, `!3po`, `!droid`, `!protocol`
- **Auto Responses**: Kill announcements, welcome messages, map comments
- **Rate Limiting**: Prevents spam with cooldown periods
- **Fallback Responses**: Works even when LLM is unavailable
- **Proper Protocol**: Polite, formal responses with concern for odds and safety

## Installation

### 1. Install Ollama
```bash
# On Linux
curl -fsSL https://ollama.com/install.sh | sh

# On macOS
brew install ollama

# On Windows
# Download from https://ollama.com/download/windows
```

### 2. Install Python Dependencies
```bash
pip install requests
```

### 3. Download and Start a Model
```bash
# Start Ollama service
ollama serve

# Download a lightweight model (recommended)
ollama pull llama3.2:3b

# Or use a larger model for better responses
ollama pull llama3.2:7b
```

### 4. Configure the Plugin
Add this to your instance configuration file:

```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://localhost:11434",
            "model": "llama3.2:3b",
            "max_tokens": 100,
            "temperature": 0.7,
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
| `ollama_url` | Ollama server URL | `http://localhost:11434` |
| `model` | Ollama model to use | `llama3.2:3b` |
| `max_tokens` | Maximum response length | `100` |
| `temperature` | Response creativity (0-1) | `0.7` |
| `chat_commands` | Commands that trigger the bot | `["!c3po", "!3po", "!droid", "!protocol"]` |
| `personality` | Bot personality prompt | C-3PO protocol droid character |
| `auto_responses.enabled` | Enable automatic responses | `true` |
| `auto_responses.kill_announcements` | Announce kills | `true` |
| `auto_responses.welcome_messages` | Welcome new players | `true` |
| `auto_responses.map_comments` | Comment on map changes | `true` |

## Recommended Models

### For Low-End Servers (2-4GB RAM)
- `llama3.2:1b` - Fastest, basic responses
- `llama3.2:3b` - Good balance of speed and quality

### For High-End Servers (8GB+ RAM)
- `llama3.2:7b` - Better responses, more knowledgeable
- `llama3.1:8b` - Excellent quality, slower responses

## Troubleshooting

### Bot Not Responding
1. Check if Ollama is running: `ollama serve`
2. Verify model is installed: `ollama list`
3. Check MBIIEZ logs for connection errors
4. Test Ollama directly: `curl http://localhost:11434/api/tags`

### Slow Responses
1. Use a smaller model (1b or 3b)
2. Reduce `max_tokens` to 50-75
3. Increase `temperature` to 0.9 for faster generation

### Rate Limiting
- Players have a 10-second cooldown between questions
- Auto responses have percentage chances to avoid spam

## Security Notes
- Ollama runs locally, no data sent to external servers
- Bot responses are filtered for length to prevent chat spam
- Rate limiting prevents abuse

## Example Interactions

**Player**: `!c3po What's the best class for beginners?`

**C-3PO**: `Oh my! For new combatants, I do recommend the Soldier class - reliable blaster, good armor, and straightforward controls. The odds of survival are much better with proper equipment!`

**Player**: `!3po Tell me about Jedi`

**C-3PO**: `How wonderful! Jedi are Force-users with lightsabers and special abilities. They're quite powerful, though I must warn you - the odds of mastering their techniques are approximately 3,720 to 1 against!`
