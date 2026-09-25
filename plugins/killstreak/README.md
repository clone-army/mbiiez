# Kill Streaks Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#kill-streaks).
On any other engine it does nothing.

Server-wide callouts when a player racks up kills without dying: at 3, 5, 7, 10 and 15 kills, then every 5
after that. Streaks reset each round. This plugin sets `g_killstreakEnable` at startup, re-applies it every
minute, and adds one line to Auto Messages when enabled.

## Configuration

```json
"plugins": {
    "killstreak": { "enabled": 1 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Turn kill streak callouts on |

Also editable under **Settings → Kill Streaks** in the web panel.
