# Auto Message Plugin

Automatically sends periodic messages to players in the server.

## Configuration

Add to your instance config:

```json
{
    "plugins": {
        "auto_message": {
            "enabled": true,
            "messages": [
                "Welcome to our server!",
                "Visit our website at example.com",
                "Type !help for commands"
            ],
            "repeat_minutes": 5
        }
    }
}
```

## Features

- Configurable message list
- Adjustable repeat interval
- Automatic startup messages
- Support for color codes
