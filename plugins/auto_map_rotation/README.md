# Auto Map Rotation Plugin

Keeps an idle server from sitting on one map. Once the server has been **empty for `rotation_minutes`**, it
moves on to the next map in the instance's own map rotation (`map_rotation_order`, via `vstr nextmap`), then
does it again every `rotation_minutes` for as long as nobody is on. As soon as anyone connects the clock
resets, so a server with players on is never touched. Works with any engine.

## Configuration

```json
{
    "plugins": {
        "auto_map_rotation": {
            "rotation_minutes": 30
        }
    }
}
```

| Key | Default | Meaning |
|---|---|---|
| `rotation_minutes` | `30` | Minutes empty before each change. `0` (or blank) turns rotation off. `rotate_minutes` is accepted too. |

The maps come from the instance's **Map Rotation** (`map_rotation_order`), edited under **Settings → Maps** in
the web panel. Every map in it must exist on the server: a name it can't find is skipped with a
"Can't find map" error in the engine log.

What it's doing shows up in the instance's log ("server is empty - next map in 30 min", "changed to the next
map", "players joined, rotation clock reset").
