# Spectator Kick Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK).
On any other engine it does nothing.

Players who sit in spectator round after round take a slot someone else could play in. At the start of
each round (a fresh map, or the next round), anyone still in spectator has a round added to their count;
anyone on a team is reset to zero. One round before the limit they are warned; at the limit they are
removed ("removed for spectating N rounds in a row"). Logged-in admins (the accounts admins) and bots are
never removed. Sets `g_specKickRounds` at startup and re-applies it every minute.

Idle players (AFK) are MBII's own job: see the instance's Game settings, *Idle To Spectator Seconds* and
*Idle Kick Seconds* (`g_InactivitySpec` / `g_InactivityKick`).

## Configuration

```json
"plugins": {
    "spectator_kick": { "rounds": 3 }
}
```

| Key | Default | Meaning |
|---|---|---|
| `rounds` | `3` | Rounds in a row in spectator before they are removed (0 = off) |
