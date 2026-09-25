# Gun Game Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#gun-game).
On any other engine it does nothing.

Everyone has one weapon and moves up a fixed 17-step ladder (Bryar pistol → ... → rocket launcher →
lightsaber) with each kill. Reaching the lightsaber wins. Dying never moves you down.

To keep it fair, while Gun Game is on the plugin also **limits which classes can be picked**: it rewrites the
live `g_classlimits` so only the classes in `gungame_restrict_classes` are open (default: the two basic
soldier classes, one per team) and every other class is set to 0. When Gun Game is switched off, the
instance's normal `class_limits` come back. It re-applies all of this every minute.

## Configuration

Unlike most plugins, the settings live in the instance's **`game`** section:

```json
"game": {
    "gungame_enable": 1,
    "gungame_announce": 1,
    "gungame_restrict_classes": ["Solder", "Trooper"]
},
"plugins": {
    "gungame": {}
}
```

| `game` key | Default | Meaning |
|---|---|---|
| `gungame_enable` | `0` | Turn Gun Game on |
| `gungame_announce` | `1` | Broadcast each step up and the winner |
| `gungame_restrict_classes` | `["Solder", "Trooper"]` | Classes that stay open while Gun Game is on. Keep `Solder` and `Trooper` together: they're the basic class for each team. |

The restriction uses the class order from the instance's `class_limits`, so that section needs to be present.
