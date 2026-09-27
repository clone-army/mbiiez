# Social Mode Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#social-mode).
On any other engine it does nothing.

A hang-out mode on top of the instance's normal game mode (e.g. Legends, with all its classes): players
(and NPCs) can't take damage, and anyone can spawn in at any time. Dying or joining mid-round just puts you on a short
respawn timer. Players can still fight properly by bowing at each other to start a duel (any class, any weapon). The round length can be set to replace the map's own timer. Team-kill points are off (the engine handles
that; don't set `TK_Spec`/`TK_Kick` to 0, MBII rejects it and broadcasts an error).

This plugin sets the engine's `g_social*` cvars at startup, re-applies them every minute, and adds Auto Messages
lines (how social mode and duels work) when the `auto_message` plugin is on.

## Configuration

```json
"plugins": {
    "social": { "enabled": 1, "respawn_seconds": 3, "duels": 1, "round_minutes": 60 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Turn social mode on |
| `respawn_seconds` | `3` | Seconds to wait before spawning back in |
| `duels` | `1` | Allow duels: bow at someone to challenge, they bow back to accept. Any class, any weapon |
| `round_minutes` | `0` | Round length in minutes; `0` keeps each map's own round timer |
| `bots` | `0` | Bots pick a random Legends class so they spawn. Works with `enabled: 0` too, for a normal Legends server with bots |

Also editable under **Settings → Social Mode** in the web panel.

Round length and the Economy plugin both work well alongside it; bounties don't (nobody can kill anyone outside a
duel), so leave `g_economyBountyEnable` off on a social instance.
