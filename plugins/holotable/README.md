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
| `!ht page <n>` | The next page of that list (5 a page - the whole list is in your console too) |
| `!ht <n>` | About scenario *n* |
| `!ht <n> play` | Run it (admins) |
| `!ht restart` | Reload the running one from its file and start it over - after saving a change (admins) |
| `!ht stop` | End it (admins) |

rcon `ht`, `ht <n> play`, `ht restart` and `ht stop` do the same without logging in. Admins are the accounts ticked on the
Accounts page (and a social server's own admins).

## Playing by themselves

Each server with the plugin on gets a **Holotable** page under it in the web panel:

- **When scenarios play** - *Only when asked* (`!ht`), *Random, every so often* (every so many minutes after the
  last one ended, once enough players are in - the cantina's bar fights), or *Every round* (one starts as each round
  begins, picked at random if a map has several).
- **Restart a running scenario when the round restarts** - a new round clears every NPC; with this on, whatever was
  running starts again.
- **Scenarios by map** - every map in the server's rotation (and, folded away, the other maps that have scenarios),
  with *All of them (new ones too)* or the ones ticked.

They play in the mode the server's in (no map reload). One that comes with a round doesn't stretch the round clock.

The plugin writes the ticked scenario ids to `holotable_auto.txt` in the instance's own game folder
(`homepaths/<instance>/MBII/`), where the engine reads them, and sets `g_holotable`, `g_holotableAuto`,
`g_holotableAutoMinutes`, `g_holotableAutoPlayers` and `g_holotableAutoRestart`. A save on the page applies
straight away; the plugin also re-applies everything every minute, so a scenario made on Holotable since is
picked up without a restart.

## Configuration

```json
"plugins": {
    "holotable": {
        "enabled": 1,
        "auto": "round",
        "auto_minutes": 30,
        "auto_players": 2,
        "auto_restart": 1,
        "maps": { "mb2_jeditemple": ["clone_ambush", "children"], "mb2_dotf": "all" }
    }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `1` | Allow Holotable scenarios on this server |
| `auto` | `"off"` | `"off"`, `"timer"` (random, every `auto_minutes`) or `"round"` (every round) |
| `auto_minutes` | `30` | Timer: minutes after the last scenario ended |
| `auto_players` | `2` | Players needed for one to start by itself |
| `auto_restart` | `1` | Start a running scenario again when the round restarts |
| `maps` | `{}` | Per map: `"all"` or a list of scenario ids. A map not listed is `"all"`. |

Also editable under **Settings → Holotable** in the web panel.
