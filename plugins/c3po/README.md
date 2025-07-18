# R2-D11 LLM Bot Plugin

A Star Wars-themed LLM chatbot plugin for MBIIEZ that uses Ollama for offline AI responses.

## Files in this folder:

- `plugin_r2d11.py` - Main plugin file
- `install_r2d11.sh` - Installation script
- `update_r2d11.sh` - Update script
- `r2d11_plugin_example.json` - Example configuration
- `README_R2D11.md` - Detailed plugin documentation
- `INSTALL_R2D11.md` - Installation instructions

## Quick Install:

```bash
cd plugins/plugin_r2d11
chmod +x install_r2d11.sh
./install_r2d11.sh
```

## Features:

🤖 **Offline LLM** - Uses Ollama (no API costs)
⭐ **Star Wars Theme** - R2-D11 droid personality
💬 **Chat Commands** - `!r2d11`, `!droid`, `!bot`
🎯 **Auto Responses** - Kill announcements, welcomes, map comments
🚫 **Anti-Spam** - Built-in rate limiting
🔄 **Fallback System** - Works even when LLM is offline

## Players interact with:

- `!r2d11 What's the best weapon?` - Ask questions
- `!droid Tell me about Jedi` - Star Wars lore
- `!bot How do I get better?` - Game tips

For full installation and configuration instructions, see `INSTALL_R2D11.md`.
