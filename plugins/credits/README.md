# Credits Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK). Needs the **Accounts** plugin.

Players earn credits while logged in - kills, rounds, games - check them with `!balance` and give them away
with `!gift <player> <credits>`. Balances live on the account, so they're the same on every server. What
credits buy are their own plugins: **Shop**, **Bounties**, **Cantina Bar**, **Jukebox**, **Casino**.

Adds the **Credits** page (outside any instance): every balance, and giving or taking credits.

Engine: `g_creditSystemEnable 1` (set by this plugin).

| Setting | Default | |
|---|---|---|
| `cvars.g_economyRegisterBonus` | `100` | Credits for registering |
| `cvars.g_economyDailyBonus` | `25` | Credits for the first login each day, on any server (0 = off) |

Also editable under **Settings** in the web panel.
