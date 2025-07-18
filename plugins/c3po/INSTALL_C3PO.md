# C-3PO Installation Scripts

This directory contains installation and update scripts for the C-3PO LLM plugin.

## Quick Start

### 1. Install C-3PO Plugin
```bash
chmod +x install.sh
./install.sh
```

### 2. Update Models
```bash
chmod +x update.sh
./update.sh
```

## Installation Script (`install.sh`)

### What it does:
- ✅ Installs Ollama (if not already installed)
- ✅ Installs Python dependencies (`requests`)
- ✅ Starts Ollama service
- ✅ Downloads and installs the default model (`llama3.2:3b`)
- ✅ Tests the model to ensure it works
- ✅ Creates example configuration file
- ✅ Checks system requirements

### Usage:
```bash
# Install with default model (llama3.2:3b)
./install.sh

# Install with specific model
./install.sh --model llama3.2:7b

# Show help
./install.sh --help
```

### Available Models:
- `llama3.2:1b` - Lightweight, fast (1GB RAM) - Good for low-end servers
- `llama3.2:3b` - Balanced, good quality (3GB RAM) - **Recommended**
- `llama3.2:7b` - High quality, slower (7GB RAM) - Good for high-end servers
- `llama3.1:8b` - Excellent quality, slower (8GB RAM) - Best quality

## Update Script (`update.sh`)

### What it does:
- ✅ Updates existing models to latest versions
- ✅ Tests models after updates
- ✅ Can update Ollama itself
- ✅ Lists installed models
- ✅ Shows model information

### Usage:
```bash
# Update default model
./update.sh

# Update specific model
./update.sh --model llama3.2:7b

# Update all installed models
./update.sh --all-models

# List installed models
./update.sh --list

# Test a model
./update.sh --test llama3.2:3b

# Show model info
./update.sh --info llama3.2:3b

# Update Ollama itself
./update.sh --update-ollama

# Show help
./update.sh --help
```

## System Requirements

### Minimum (for llama3.2:1b):
- 1GB+ RAM
- 2GB+ free disk space
- Linux/Ubuntu system

### Recommended (for llama3.2:3b):
- 3GB+ RAM
- 4GB+ free disk space
- Linux/Ubuntu system

### High-end (for llama3.2:7b+):
- 8GB+ RAM
- 10GB+ free disk space
- Linux/Ubuntu system

## Troubleshooting

### Script won't run:
```bash
chmod +x install.sh
chmod +x update.sh
```

### Ollama not starting:
```bash
# Check if Ollama is running
systemctl status ollama

# Start Ollama manually
ollama serve
```

### Model download fails:
```bash
# Check internet connection
ping -c 3 google.com

# Try downloading manually
ollama pull llama3.2:3b
```

### Test the installation:
```bash
# Test Ollama API
curl http://localhost:11434/api/tags

# Test model directly
ollama run llama3.2:3b "Hello, I am C-3PO!"
```

## Post-Installation

After running the installation script:

1. **Add plugin to your instance config** - Copy settings from `c3po_config_example.json`
2. **Restart your MBIIEZ instance** - So the plugin loads
3. **Test in-game** - Use `!c3po hello` to chat with the bot

## Example Configuration

The installation script creates `c3po_config_example.json` with the following structure:

```json
{
    "plugins": {
        "c3po": {
            "enabled": true,
            "ollama_url": "http://localhost:11434",
            "model": "llama3.2:3b",
            "max_tokens": 100,
            "temperature": 0.7,
            "chat_commands": ["!c3po", "!droid", "!bot"],
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

## Manual Installation

If the scripts don't work, you can install manually:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
ollama serve

# Install model
ollama pull llama3.2:3b

# Install Python dependencies
pip install requests
```

## Support

For issues with the C-3PO plugin, check:
1. MBIIEZ logs for error messages
2. Ollama status: `systemctl status ollama`
3. Model availability: `ollama list`
4. API connectivity: `curl http://localhost:11434/api/tags`
