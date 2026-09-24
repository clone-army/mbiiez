# Chaos Mode Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#chaos-mode).
On any other engine it does nothing.

Every `cooldown` seconds, every player gets a random prize (weapon, item, armor, size change, vehicle, god
mode...). The engine does the work; this plugin sets `g_chaosEnable` / `g_chaosCooldown` at startup and
re-applies them every minute. When enabled, it adds one line about Chaos Mode to Auto Messages.

## Configuration

```json
"plugins": {
    "chaos": { "enabled": 1, "cooldown": 20 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Turn Chaos Mode on (`0` keeps the plugin but switches the mode off) |
| `cooldown` | `20` | Seconds between prizes, per player |

Also editable under **Settings → Chaos Mode** in the web panel.
