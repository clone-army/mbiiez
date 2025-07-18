# Auto Map Rotation Plugin

Automatically rotates through a predefined list of maps at specified intervals.

## Configuration

Add to your instance config:

```json
{
    "plugins": {
        "auto_map_rotation": {
            "enabled": true,
            "maps": [
                "mp_duel1",
                "mp_duel2",
                "mp_dotf",
                "mp_deathstar"
            ],
            "rotation_minutes": 15,
            "announce_next_map": true
        }
    }
}
```

## Features

- Configurable map list
- Adjustable rotation interval
- Next map announcements
- Automatic map switching
