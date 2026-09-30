# Holotable Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK).
On any other engine it doesn't start. Needs the **Accounts** plugin.

Turns on [Holotable](https://github.com/clone-army/holotable) scenarios for this server: NPC scenarios built on
the Holotable web app (a top-down map of any map to place spawns, routes and trigger areas on) and saved into
the game folder's `holotable/`. Works on any server, social or not.

In game, once logged in (the **Accounts** plugin's `!login` - turned on with it):

| Command | |
|---|---|
| `!ht` | List the scenarios for the map that's on |
| `!ht <n>` | About scenario *n* |
| `!ht <n> play` | Run it (admins) |
| `!ht stop` | End it (admins) |

rcon `ht`, `ht <n> play` and `ht stop` do the same without logging in. Admins are the accounts ticked on the
Accounts page (and a social server's own admins).

This plugin sets `g_holotable` at startup and re-applies it every minute.

## Configuration

```json
"plugins": {
    "holotable": { "enabled": 1 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Allow Holotable scenarios on this server |

Also editable under **Settings → Holotable** in the web panel.
