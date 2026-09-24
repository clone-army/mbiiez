# Auto Map Rotation Plugin

Keeps an idle server from sitting on one map: every `rotate_minutes`, if **nobody is playing**, it moves the
server on to the next map in the instance's own map rotation (`map_rotation_order`, via `vstr nextmap`). If
anyone is on, that cycle is skipped. Works with any engine.

## Configuration

```json
{
    "plugins": {
        "auto_map_rotation": {
            "rotate_minutes": 30
        }
    }
}
```

| Key | Default | Meaning |
|---|---|---|
| `rotate_minutes` | `30` | How often to check (`rotation_minutes` is accepted too) |

The maps themselves come from the instance's **Map Rotation** (`map_rotation_order`), edited under
**Settings → Maps** in the web panel.
