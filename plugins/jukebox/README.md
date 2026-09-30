# Jukebox Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK). Needs the **Credits** plugin.

`!jukebox` - players pay credits to change the music for everyone (favourites, `!jukebox <words>` to
search ~200 tracks). Optionally plays random tracks when nobody's pick is on.

Engine: `g_economyJukeboxEnable 1` (set by this plugin).

| Setting | Default | |
|---|---|---|
| `cvars.g_jukeboxCost` | `10` | Credits a track |
| `cvars.g_jukeboxCooldown` | `60` | Seconds before the track can be changed again |
| `cvars.g_jukeboxAutoplay` | `0` | Random tracks when nobody's pick is playing |
| `cvars.g_jukeboxAutoplayMax` | `300` | Longest a random track plays (0 = whole track) |

Also editable under **Settings** in the web panel.
