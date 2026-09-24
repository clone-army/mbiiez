# MBIIEZ - Movie Battles II made easy

MBIIEZ runs and manages [Movie Battles II](https://www.moviebattles.org/) dedicated servers on Linux. It is a
Python wrapper around the game server with three parts:

- **`mbii` CLI** - start/stop/restart instances, send RCON, change maps and modes, check status.
- **Web panel** - a browser UI for everything the CLI does, plus settings editing, logs, chat, moderation,
  user accounts and a new-instance wizard.
- **Plugin system** - optional features (voting, economy, chaos mode, gun game, auto messages, VPN blocking,
  an AI assistant...) that you switch on per instance. See **[PLUGINS.md](PLUGINS.md)** to write your own.

You describe each server ("instance") in one small JSON file. MBIIEZ generates the real server configs, runs
the engine, watches its log, restarts it if it crashes, and runs any plugins you've enabled.

---

## Contents

- [The engine: `caded.i386` and our OpenJK fork](#the-engine-cadedi386-and-our-openjk-fork)
- [Installing](#installing)
- [Instances](#instances)
- [Instance config reference](#instance-config-reference)
- [The `mbii` CLI](#the-mbii-cli)
- [Web panel](#web-panel)
- [Included plugins](#included-plugins)
- [Running it day to day](#running-it-day-to-day)
- [Files and folders](#files-and-folders)
- [Database](#database)
- [Contributing](#contributing)

---

## The engine: `caded.i386` and our OpenJK fork

Every instance names the dedicated-server binary it runs with (`"engine"` in its config), looked up in
`/usr/bin`. Three are supported:

| Engine | Where it comes from | Notes |
|---|---|---|
| **`caded.i386`** | Built from **our OpenJK fork: [github.com/clone-army/OpenJK](https://github.com/clone-army/OpenJK)** | Recommended. Adds the economy (credits, shop, bounties, accounts), Chaos Mode, Gun Game, kill streaks and native `!stats`. |
| `mbiided.i386` | Bundled in this repo; `install.sh` copies it to `/usr/bin` | Standard MBII dedicated server, none of the extra features. |
| `openjkded.i386` | Stock 2018 OpenJK build downloaded by `install.sh` | Plain OpenJK. |

> **Several plugins only work with `caded.i386`.** Credit System, Chaos Mode, Gun Game, Kill Streaks and Stats
> don't add features themselves: they switch features on and off in our engine with cvars
> (`g_creditSystemEnable`, `g_chaosEnable`, `g_gungame`, `g_killstreakEnable`, `g_statsEnable`...). On any
> other engine those cvars don't exist and the plugins do nothing. See [Included plugins](#included-plugins).

All of these features are compiled into the one `caded.i386` binary and controlled by cvars, so any
instance can use any combination of them just by changing its config.

### Building `caded.i386`

```bash
git clone https://github.com/clone-army/OpenJK
cd OpenJK
./build.sh --install   # first time only: also installs build dependencies
./build.sh             # later rebuilds
```

`build.sh` does a clean build, installs the result to `/usr/bin/caded.i386`, and restarts every MBIIEZ
instance whose config uses `caded.i386`. It takes several minutes on a small VPS. The player-facing commands
and cvars are documented in the [OpenJK fork's README](https://github.com/clone-army/OpenJK#readme).

---

## Installing

Debian or Ubuntu (or a derivative), as root.

```bash
git clone https://github.com/clone-army/mbiiez
cd mbiiez
sudo ./install.sh
```

`install.sh`:

- installs system packages (`screen`, `psmisc`, `git`, 32-bit runtime libraries, Python venv tooling...) and
  the .NET 6 runtime (needed by the official MBII updater)
- creates a Python virtualenv at `/opt/openjk/venv` with the Python dependencies
- downloads and installs **MBII** into `/opt/openjk/MBII` using the official MBII command-line updater
- downloads the **Jedi Academy base assets** into `/opt/openjk/base` (if any fail, it lists them at the end:
  re-run the script or copy them in yourself)
- installs **OpenJK** (`openjkded.i386`) and the bundled **`mbiided.i386`** into `/usr/bin`
- installs the **`mbii`** command into `/usr/local/bin`
- creates `mbiiez.conf` from `mbiiez.conf.example`
- offers to install the **web panel** (you can also run `sudo ./install_web.sh` later)

Then:

1. Build **`caded.i386`** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK) if you want the
   extra features (see above).
2. Check the paths in **`mbiiez.conf`** (the defaults match what `install.sh` sets up).
3. Create your first instance, either with the web panel's **New instance** wizard or by copying
   `configs/demo.json.example` to `configs/<name>.json`.
4. Open the instance's port (UDP) in your firewall.
5. `mbii -i <name> start`

### `mbiiez.conf`

| Section | Key | Meaning |
|---|---|---|
| `[locations]` | `game_path` | Game root, `/opt/openjk` |
| | `mbii_path` | MBII folder, `/opt/openjk/MBII` |
| | `config_path` | Where instance JSON files live, relative to this repo (`configs`) |
| `[dedicated]` | `engine`, `game` | Defaults used by the status helpers (`mbiided.i386`, `MBII`) |
| `[database]` | `database` | SQLite file, `mbiiez.db` |
| `[web_service]` | `port` | Web panel port (default `8080`) |
| | `auth_enabled` | `true` / `false`: require login |
| | `users_file` | Web panel accounts file (default `web_users.json`) |

---

## Instances

An **instance** is one game server: its own name (like `open`, `duel`, `legends`), port, game mode, plugins
and settings. One machine can run many at once.

**An instance is simply its config file: `configs/<name>.json`.** Every tool (the CLI, the web panel,
`update.sh` and OpenJK's `build.sh`) finds instances by listing `configs/*.json`. So:

- **To create one**, add a `.json` file (or use the web panel's wizard, which can clone an existing instance).
- **To delete one**, rename it so it no longer ends in `.json`. The web panel's Delete button renames it to
  `<name>.json.del`; rename it back to restore it.

When an instance starts, MBIIEZ:

1. generates its server config (`<name>-server.cfg`) and plugin configs under `homepaths/<name>/`
2. launches the engine in a `screen` session called `mb2_<name>`, logging to `/var/log/<name>-engine.log`
3. starts the instance's background services: log watcher, crash watchdog, scheduled restarter, and one
   service per plugin that needs one

Each instance's runtime files (generated configs, logs, per-instance data) live in its own
`homepaths/<name>/` folder, so instances never overwrite each other's files. Economy accounts and `!stats` are
shared across all instances on the machine (they live in the MBII folder), so a player's credits and stats
follow them from server to server.

### Built-in safety nets

- **Crash watchdog**: if the engine's screen session disappears unexpectedly, it's relaunched. It checks
  every `crash_watchdog_interval_seconds` (default 15) and backs off if the engine keeps crashing straight
  after starting.
- **Scheduled restart**: every `restart_instance_every_hours`, the instance restarts, but only when nobody is
  playing. If players are on, it retries every 10 minutes.
- **Self-healing plugin settings**: feature plugins re-apply their cvars about every 60 seconds, so a stray
  manual `rcon set` doesn't silently stick.

---

## Instance config reference

A trimmed example (the full template is `configs/demo.json.example`):

```json
{
  "server": {
    "host_name": "^5My^7Server|NA|^5Open",
    "port": 29071,
    "engine": "caded.i386",
    "game": "MBII",
    "discord": "https://discord.gg/example",
    "restart_instance_every_hours": 24
  },
  "security": {
    "rcon_password": "change-me",
    "server_password": ""
  },
  "game": {
    "mode": "open",
    "map_win_limit": 20,
    "map_round_limit": 20,
    "competitive_config": 0,
    "balance_mode": 1,
    "message_of_the_day": "Welcome!\n\nBe respectful."
  },
  "smod": {
    "admin_1": { "password": "change-me-too", "config": 65535 }
  },
  "class_limits": { "Jedi": 50, "Sith": 50, "Droideka": 4 },
  "map_rotation_order": ["mb2_dotf", "mb2_commtower", "mb2_deathstar"],
  "plugins": {
    "auto_message": { "messages": ["Welcome!"], "repeat_minutes": 5 },
    "rtvrtm": { }
  }
}
```

| Key | Meaning |
|---|---|
| `server.host_name` | Name in the server browser. `^0`-`^9` are colour codes. |
| `server.port` | UDP port. Must be unique per instance. |
| `server.engine` | `caded.i386`, `mbiided.i386` or `openjkded.i386` (see [The engine](#the-engine-cadedi386-and-our-openjk-fork)). |
| `server.restart_instance_every_hours` | Scheduled restart interval (only restarts when empty). |
| `server.crash_watchdog_interval_seconds` | Optional. Crash check interval; `0` disables the watchdog. Default 15. |
| `security.rcon_password` | RCON password. |
| `security.server_password` | Join password, empty for a public server. |
| `game.mode` | `open`, `semi-authentic`, `full-authentic`, `duel` or `legends`. |
| `game.map_win_limit`, `game.map_round_limit` | Round/win limits per map. |
| `game.balance_mode`, `game.competitive_config` | MBII team balance and competitive settings. |
| `game.message_of_the_day` | Shown on connect. `\n` for new lines. |
| `game.enable_spin`, `game.spin_cooldown` | MBII's own `!spin` (see the Anytime Spin plugin). |
| `game.gungame_*` | Gun Game settings (see the Gun Game plugin). |
| `smod.admin_1` ... `admin_10` | In-game admin (smod) slots: a password plus a `config` bitmask of which commands that slot may use. The web panel has a checkbox picker for it. |
| `class_limits` | Max players per class at once. |
| `map_rotation_order` | The map cycle, any length. |
| `plugins` | One key per enabled plugin with that plugin's settings. Leave it out (or `{}`) for no plugins. |

If a config file isn't valid JSON, the instance won't start and tells you where the error is. The web panel
edits these files for you, so you rarely need to touch them by hand.

---

## The `mbii` CLI

```
mbii -i <instance> <action> [arguments]
```

| Action | Example | What it does |
|---|---|---|
| `start` | `mbii -i open start` | Start the instance |
| `stop` | `mbii -i open stop --force` | Stop it (`--force` skips the confirmation) |
| `restart` | `mbii -i open restart --force` | Stop then start |
| `status` | `mbii -i open status` | Players, map, mode, uptime, port |
| `say` | `mbii -i open say "Hello"` | Server message to everyone |
| `tell` | `mbii -i open tell 3 "Hi"` | Private message to player slot 3 |
| `rcon` | `mbii -i open rcon "g_gravity 800"` | Send any RCON command |
| `cvar` | `mbii -i open cvar g_authenticity 1` | Set a cvar (omit the value to read it) |
| `map` | `mbii -i open map mb2_dotf` | Change map |
| `mode` | `mbii -i open mode 1` | Change game mode (0 Open, 1 Semi Authentic, 2 Full Authentic, 3 Duel, 4 Legends) |
| `players` | `mbii -i open players` | List connected players |
| `kick` / `ban` / `unban` / `listbans` | `mbii -i open ban 1.2.3.4` | Moderation |
| `uptime`, `version`, `log` | | Info |

Other forms:

| Command | What it does |
|---|---|
| `mbii -l` | List all instances |
| `mbii -i` | List instances that are running right now |
| `mbii -a <action>` | Run an action on **every** instance, e.g. `mbii -a restart` |
| `mbii -c <player>` | Look up a player's history (connections, kills) |
| `mbii -u` | Check for an MBII update and apply it once every instance is empty |
| `-v` | Verbose output |

> Over SSH from another machine, `start`/`restart` can keep the SSH command open after the server is up
> (the engine's `screen` session holds the terminal). Run them in the background and check with
> `mbii -i <name> status`.

---

## Web panel

Install it as a systemd service with `sudo ./install_web.sh` (or say yes when `install.sh` asks). It runs as
`mbii-web` on port `8080` by default:

```bash
sudo systemctl status mbii-web
journalctl -u mbii-web -n 100 --no-pager
```

On first visit you create the first admin account. Accounts are stored in `web_users.json`.

### Roles

| Role | Can |
|---|---|
| `viewer` | See the dashboard, instance status, logs and chat |
| `mod` | Everything a viewer can, plus the RCON console, sending chat, and the Mod page (change map/mode, kick, ban, unban, private message) |
| `admin` | Everything, plus start/stop/restart, Settings, plugin pages, new/delete instance, user management, panel update/restart and the audit log |

### Pages

- **Dashboard**: every instance at a glance (online, players, map, mode). Admins can also **update the panel**
  (`git pull`, restarting only if something changed) or restart it.
- **Instances** (sidebar, one entry per instance):
  - **Status**: live status with start / stop / restart.
  - **Logs**: the instance's log, searchable.
  - **Chat**: live in-game chat. Mods can send messages.
  - **Settings**: edit the instance's config through a form instead of raw JSON (details below).
  - **Plugin pages**: extra pages added by plugins, such as **Economy** (accounts and balances, give/remove
    credits) and **Stats** (player kills, deaths, playtime).
  - **RCON**: an RCON console.
  - **Mod**: change map or mode, kick, ban/unban, message a player.
- **+ New instance**: the new-instance wizard.
- **Admin Users**: add users, change passwords and roles, remove users.

### Settings page

The Settings page turns the instance's JSON into grouped, collapsible sections with the right input for each
value: toggles, dropdowns with explained options, percentage fields, map pickers.

- **Save as you go**: the Save bar stays at the bottom of the screen and **Ctrl+S** (Cmd+S) saves. An
  "Unsaved changes" badge shows when you've edited something, and every save shows a notification. Most
  changes need an instance restart to take effect.
- **Raw JSON** tab for anything the form doesn't cover, with live JSON validation.
- **smod admins**: a **Pick rights** checkbox picker instead of typing bitmasks, plus **Sync to instances** to
  copy an admin's password and rights to other instances in one go.
- **Maps**: the map rotation (reorder with the up/down arrows, map names autocomplete) and **holiday map
  periods** (e.g. Christmas maps in December), whose maps are added to the rotation and RTV pool whenever the
  instance restarts during the period, and drop out again afterwards.
- **Plugins**: switch plugins on or off for this instance and edit their settings. Plugins can give their
  settings a section of their own (RTV, RTM, Chaos, VPN Shield...).
- **RTV / RTM**: settings that the voting plugin stores as one compact value (like `"0 3"` or
  `"2 1 0 2 1 0"`) are split into separate labelled inputs and put back together on save, so they can't be
  saved in a form that stops the plugin starting. RTM's allowed modes are checkboxes.
- **Danger zone**: delete the instance. You have to type its name to confirm. If it's running it's stopped
  first, then its config is renamed to `<name>.json.del` (logs and player data in `homepaths/` are kept).

### New instance wizard

1. **Start from**: copy an existing instance (all its settings, plugins, maps and admins) or a clean
   template (with freshly generated admin passwords).
2. **Basics**: instance name, server name (with a live colour preview), port, game mode, engine, RCON
   password (with a generator) and optional join password. The port list shows 29070-29089 and marks which
   instance or program is already using each one.
3. **Review & create**, optionally starting the server straight away.

### Audit log

Actions that change things (saves, start/stop, instance create/delete, plugin actions, user changes) are
recorded with who did them and from which IP, and admins can read them at `/api/audit`.

---

## Included plugins

Enable a plugin by adding its key under `plugins` in the instance config (or tick it in the Settings page).
**Plugins marked *caded* need the [`caded.i386` engine](#the-engine-cadedi386-and-our-openjk-fork)** and do
nothing on other engines.

| Plugin (config key) | Engine | What it does |
|---|---|---|
| **RTVRTM** (`rtvrtm`) | any | Rock the Vote / Rock the Mode: players vote to change map (`!rtv`) or game mode (`!rtm`), with nominations, runoff votes, extend options, cooldowns, admin-called votes and round/time-limit votes. Has its own RTV, RTM and General sections in Settings. |
| **Auto Messages** (`auto_message`) | any | Rotating server messages. Settings: `messages` (list), `repeat_minutes`. Other plugins add one line each explaining themselves when enabled. |
| **Auto Map Rotation** (`auto_map_rotation`) | any | When the server is empty, moves to the next map in the rotation every `rotate_minutes` (default 30), so an idle server doesn't sit on one map. |
| **VPN Shield** (`shield`) | any | Warns, then kicks, players connecting through a VPN or proxy. Needs an [ipgeolocation.io](https://ipgeolocation.io) API key (`ipgeolocation_apikey`). |
| **Anytime Spin** (`anytime_spin`) | any | MBII's own `!spin` normally only works on Sundays. This makes the engine always think it's Sunday (`LD_PRELOAD` of `fake_sunday_32.so`). Turn spin on with `game.enable_spin` / `game.spin_cooldown`. |
| **AI Assistant** (`ai`) | any | An in-game chat assistant (`!ai <question>` by default) backed by [OpenRouter](https://openrouter.ai), with optional death commentary. Settings: `enabled`, `openrouter_api_key`, `model`, `ai_name`, `command`, `cooldown_seconds`, `max_tokens`, `temperature`, `public_replies`, `death_commentary`, `instruction`. |
| **Discord Bot** (`discord_bot`) | any | *Experimental.* Relays in-game chat to a Discord channel whose name ends in `server-<instance>-chat`. Setting: `token`. |
| **Credit System** (`creditsystem`) | ***caded*** | The economy: players earn credits for kills while logged in (`!register`, `!login`), check them with `!balance`, spend them in the `!buy` shop and put bounties on each other (`!bounty`). Shop, bounty and each shop item's price can be switched on/off or set individually through `cvars`. Adds an **Economy** page listing accounts, where admins can give or take credits. |
| **Chaos Mode** (`chaos`) | ***caded*** | Every `cooldown` seconds (default 20), everyone gets a random prize. Settings: `enabled`, `cooldown`. |
| **Gun Game** (`gungame`) | ***caded*** | Everyone moves up a fixed weapon ladder, one step per kill. Settings live in `game`: `gungame_enable`, `gungame_announce`, `gungame_restrict_classes`. |
| **Kill Streaks** (`killstreak`) | ***caded*** | Server-wide callouts for kill streaks, reset each round. Setting: `enabled`. |
| **Stats** (`stats`) | ***caded*** | Turns on the engine's `!stats` (kills, deaths, suicides, playtime, shared across all your servers) and adds a **Stats** page in the web panel. Setting: `enabled`. |

---

## Running it day to day

### Updating MBII

```bash
./update.sh                  # check for an MBII update and apply it
./update.sh -i open,duel     # ...and restart these instances afterwards
```

With no `-i`, it restarts whichever instances were running. Running it from cron (e.g. every 10 minutes)
keeps servers current automatically.

### Updating MBIIEZ

`git pull` in this folder, or use **Update** on the web panel's dashboard. Restart instances to pick up
changes to plugins or the core.

### Updating the engine

Pull and re-run `./build.sh` in your [clone-army/OpenJK](https://github.com/clone-army/OpenJK) checkout. It
reinstalls `caded.i386` and restarts every instance using it.

### Scheduled machine reboot (optional)

`sudo ./install_scheduled_reboot.sh` installs a daily cron job (`mbii-scheduled-reboot.sh`) that reboots the
machine, but only when every instance is empty.

---

## Files and folders

| Path | What it is |
|---|---|
| `mbii.py` | The CLI (`mbii` wraps it) |
| `mbii-web.py` | The web panel (Flask) |
| `mbiiez/` | Core: instance lifecycle, config generation, log parsing, events, services, plugin loading, web controllers/templates |
| `plugins/` | Plugins, one folder each (see [PLUGINS.md](PLUGINS.md)) |
| `configs/` | Instance configs (`<name>.json`, gitignored: they contain passwords) and `demo.json.example` |
| `homepaths/<name>/` | Per-instance runtime files: generated configs, logs, data (gitignored) |
| `mbiiez.conf` | Paths, database and web panel settings (gitignored; copy from `mbiiez.conf.example`) |
| `web_users.json` | Web panel accounts (gitignored) |
| `mbiiez.db` | SQLite database (gitignored) |
| `install.sh`, `install_web.sh` | Installers |
| `update.sh` | MBII updater wrapper |
| `/opt/openjk` | Game install: MBII, base assets, venv |
| `/var/log/<name>-engine.log` | Engine console output per instance |

---

## Database

`mbiiez.db` (SQLite) records log lines, chat, kills, player connections (with IPs) and web panel audit
entries across all instances. The CLI's `-c` player lookup and the web panel read from it, and plugins or
external tools can query it too. Players are only identified by name (and IP), so history can't reliably
follow someone who changes their name.

---

## Contributing

Pull requests are welcome. Plugins are the easiest place to start: see **[PLUGINS.md](PLUGINS.md)**. Engine
features (anything a plugin switches on with a cvar) live in
[clone-army/OpenJK](https://github.com/clone-army/OpenJK).
