# Stats Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#stats).
On any other engine it does nothing.

Turns on the engine's native stats: kills, deaths, suicides and playtime for every player, shared across all
servers on the machine, shown in game with `!stats`. Players logged into an economy account (`!login`) are
tracked by account, so their stats survive name changes. Everyone else is tracked by name.

The plugin:

- sets `g_statsEnable` at startup and re-applies it every minute
- adds a **Stats** page under the instance in the web panel, listing every tracked player and whether they're
  registered (read from the engine's `player_stats.dat` in the MBII folder)
- adds one line about `!stats` to Auto Messages when enabled

## Configuration

```json
"plugins": {
    "stats": { "enabled": 1 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Turn stats and the Stats page on |
