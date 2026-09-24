# Writing MBIIEZ plugins

A plugin adds a feature to an instance: react to chat commands, kills or connections, run something every few
minutes, switch on an engine feature, and optionally add settings, menu items and whole pages to the web
panel. Every included plugin (`plugins/*/`) is built this way, so they're good examples to copy.

For what the included plugins do, see the [README](README.md#included-plugins).

---

## Contents

- [Quick start](#quick-start)
- [How plugins are found and loaded](#how-plugins-are-found-and-loaded)
- [The plugin class](#the-plugin-class)
- [Events](#events)
- [Services (background loops)](#services-background-loops)
- [Talking to the server](#talking-to-the-server)
- [Engine cvars and `caded.i386`](#engine-cvars-and-cadedi386)
- [Web panel integration](#web-panel-integration)
  - [Settings sections](#settings-sections-web_config_sections)
  - [Field types](#field-types)
  - [Menu items and pages](#menu-items-and-pages-web_menu--web_page)
  - [Actions](#actions-web_action)
- [A complete example](#a-complete-example)
- [Rules of thumb](#rules-of-thumb)

---

## Quick start

1. Create `plugins/hello/hello.py`:

   ```python
   class plugin:
       plugin_name = "Hello"
       plugin_author = "You"
       plugin_url = ""

       def __init__(self, instance):
           self.instance = instance
           self.config = instance.config['plugins'].get('hello', {})

       def register(self):
           self.instance.event_handler.register_event("player_chat_command", self.on_command)

       def on_command(self, args):
           if args['message'].strip().lower() == "!hello":
               greeting = self.config.get('greeting', 'Hello')
               self.instance.say("{}, {}!".format(greeting, args['player']))
   ```

2. Enable it on an instance by adding its key under `plugins` in `configs/<instance>.json` (or tick it under
   **Settings → Plugins** in the web panel):

   ```json
   "plugins": {
     "hello": { "greeting": "Welcome" }
   }
   ```

3. Restart the instance: `mbii -i <instance> restart`. Type `!hello` in game.

---

## How plugins are found and loaded

- **Location**: `plugins/<name>/<name>.py` (preferred), or a single file `plugins/<name>.py`. The folder can
  hold anything else the plugin needs (a README, data files, a `.so`...).
- **The config key is the plugin's name.** A plugin runs on an instance only if `plugins.<name>` exists in
  that instance's JSON. Its value (usually an object) is the plugin's settings; `{}` means "on, with
  defaults".
- **Discovery for the web panel**: every folder in `plugins/` with a matching `<name>.py` shows up in the
  Settings page's Plugins list, even if no instance uses it yet.
- **When plugins load**: whenever MBIIEZ builds an instance object, each enabled plugin's class is created
  (`__init__(instance)`) and then `register()` is called. This happens when the instance starts, but also for
  short-lived commands like `mbii -i open status`. Keep `__init__` and `register` fast and free of side
  effects beyond registering things; start real work in events and services.
- A plugin that fails to import or throws in `__init__`/`register` is logged and skipped. It doesn't stop the
  instance.

---

## The plugin class

The module must define a class called `plugin`.

| Member | Required | Purpose |
|---|---|---|
| `plugin_name` | yes | Display name (logs, web panel) |
| `plugin_author`, `plugin_url` | no | Shown in the web panel |
| `__init__(self, instance)` | yes | Receives the running instance. Read your config here. |
| `register(self)` | yes | Register events and services. |
| `web_*` static methods | no | Web panel hooks: see [Web panel integration](#web-panel-integration). |

Useful things on `self.instance`:

| Attribute | What it is |
|---|---|
| `name` | Instance name, e.g. `"open"` |
| `config` | The whole instance config (a dict parsed from its JSON) |
| `config['plugins']['<name>']` | Your plugin's settings |
| `event_handler` | Register for / fire events |
| `process_handler` | Register services |
| `log_handler.log(msg)` | Write to the instance's MBIIEZ log |
| `exception_handler.log(exc)` | Log an exception with traceback |
| `has_plugin(name)` | Whether another plugin is enabled on this instance |

---

## Events

Register a handler in `register()`:

```python
self.instance.event_handler.register_event("player_killed", self.on_kill)
```

Handlers receive one dict argument (or none, for events without data). They can be normal functions or
`async def`. An exception in a handler is logged and doesn't affect other handlers.

| Event | Arguments | Fires when |
|---|---|---|
| `player_chat_command` | `message`, `player`, `player_id`, `player_raw` | A chat message starting with `!` |
| `player_chat` | `type`, `message`, `player`, `player_id`, `player_raw` | Any public chat |
| `player_chat_team` | `type`, `message`, `player`, `player_id`, `player_raw` | Any team chat |
| `player_killed` | `fragger`, `fragged`, `weapon` | A kill |
| `player_connected` | `player`, `player_id`, `ip` | A player connects |
| `player_ip` | `player_id`, `ip` | A player's IP is known (alongside `player_connected`) |
| `player_disconnected` | `player_id` (`player`, `ip` empty) | A player leaves |
| `player_begin` | `player_id` | A player enters the game (once per round, not per life) |
| `player_info_change` | `data` (raw log line) | A player's name, team or class changes |
| `new_round` | `data` (raw log line) | A new round starts |
| `smod_login` | `admin`, `admin_id`, `ip` | An smod admin logs in |
| `smod_command` | `command`, `admin`, `admin_id`, `ip` | An smod admin runs a command |
| `smod_say` | `message`, `admin`, `admin_id`, `ip` | An smod admin uses admin say |
| `before_launch_server` | launch context dict | Just before the engine is started |
| `before_debug_launch_server` / `after_debug_launch_server` | launch context dict (`returncode` after) | Around a debug (foreground) launch |

`player` is the name with colour codes stripped; `player_raw` keeps them. `player_id` is the client slot
number, which is what `tell`, `kick` etc. take.

You can also fire your own events for other plugins to listen to:

```python
self.instance.event_handler.run_event("my_plugin_thing", {"player": name})
```

---

## Services (background loops)

For anything that runs continuously (a timer, a poll, a bot connection), register a service:

```python
def register(self):
    self.instance.process_handler.register_service("Hello Service", self.loop)

def loop(self):
    while True:
        self.instance.say("Still here!")
        time.sleep(300)
```

- Services start when the instance starts and stop when it stops.
- Each service runs in its **own forked process**. It gets a copy of the plugin object: changes it makes to
  `self` aren't seen by event handlers (which run in the log-watcher process), and the other way round. Share
  state through the server (cvars), a file or the database.
- Services are **supervised** by default: if one crashes, it's restarted. Pass `supervised=False` to opt out.
- The name must be unique on the instance. It's shown in `mbii -i <name> status` and the stop output.
- Optional arguments: `priority` (lower starts first, default 99) and `awaiter` (a function called and
  waited on just before the service is launched).

---

## Talking to the server

| Call | What it does |
|---|---|
| `say(message)` | Server message to everyone |
| `tell(player_id, message)` | Private message to one player |
| `rcon(command)` | Send an RCON command |
| `rconResponse(command)` | Send an RCON command and return the server's reply |
| `cvar(key)` / `cvar(key, value)` | Read / set a cvar |
| `map()` / `map(name)` | Current map / change map |
| `mode()` / `mode(n)` | Current mode / change mode (0-4) |
| `players()`, `player(id)`, `players_count()`, `is_empty()` | Who's on |
| `kick(player)`, `ban(ip)`, `unban(ip)` | Moderation |

Messages accept Jedi Academy colour codes (`^1` red ... `^7` white, `^5` cyan).

**Adding a line to Auto Messages.** If your plugin has something players should know about, add one line
to the rotating server messages, but only when your feature is actually on:

```python
if self.instance.has_plugin("auto_message") and self.enabled:
    self.instance.config['plugins']['auto_message']['messages'].append(
        "^5!hello ^7says hello back."
    )
```

Do this in `__init__` (it only changes the in-memory config, not the file). Stick to one line per plugin.

---

## Engine cvars and `caded.i386`

Many features (the economy, Chaos Mode, Gun Game, kill streaks, `!stats`) are implemented **in the engine**,
our OpenJK fork at **[github.com/clone-army/OpenJK](https://github.com/clone-army/OpenJK)**, built as
`caded.i386`. They're switched on and configured with cvars, and the matching plugin's job is to set those
cvars. On `mbiided.i386` or `openjkded.i386` these cvars don't exist, so **a plugin that depends on them only
works when the instance's `server.engine` is `caded.i386`**. Say so in your plugin's docs and in the README's
plugin table.

Three ways to set a cvar, depending on when it has to be in place:

| Method | Takes effect | Use for |
|---|---|---|
| `instance.register_startup_cvar(key, value)` | Passed on the engine's command line (`+set key value`) | Anything the engine reads once at startup, like feature on/off switches. Call it in `__init__`. |
| `instance.register_plugin_cvar(key, value)` | Written into the generated server config | Ordinary settings. Call it in `__init__`. |
| A `"cvars"` object in the plugin's config | Written into the generated server config automatically | Letting admins set any cvar from JSON with no code at all |
| `instance.cvar(key, value)` | Immediately, over RCON | Changing things while running |

The included feature plugins (`chaos`, `killstreak`, `stats`, `creditsystem`) combine them:

1. set the cvar once at startup (`register_startup_cvar`), and
2. run a service that re-applies it with `instance.cvar()` every ~60 seconds, so a stray manual `rcon set`
   doesn't silently stick.

```python
def __init__(self, instance):
    self.instance = instance
    self.config = instance.config['plugins'].get('chaos', {})
    self.enabled = int(self.config.get('enabled', 1))
    instance.register_startup_cvar("g_chaosEnable", "1" if self.enabled else "0")

def register(self):
    self.instance.process_handler.register_service("Chaos Mode Service", self.reassert)

def reassert(self):
    time.sleep(15)                       # let the engine finish starting
    while True:
        self.instance.cvar("g_chaosEnable", "1" if self.enabled else "0")
        time.sleep(60)
```

---

## Web panel integration

All web hooks are **`@staticmethod`s** that receive the instance's **name and config dict**, not a running
instance: the web panel is a separate process and never starts your plugin to render a page. Read files and
config directly. Every hook is optional, and an exception in one is caught (logged or shown as an error box)
so a broken plugin can't take the panel down.

| Hook | Returns | Purpose |
|---|---|---|
| `web_config_sections(instance_name, instance_config)` | list of sections | Give your settings their own typed section(s) on the Settings page |
| `web_hide_default_card()` | `bool` | `True` if your sections cover all your settings, to hide the generic auto-generated card |
| `web_menu(instance_name, instance_config)` | dict or `None` | Add an item under the instance in the sidebar |
| `web_page(instance_name, instance_config)` | list of sections | Content of that item's page |
| `web_action(instance_name, action_name, form_data)` | `(ok, message)` | Handle a form submitted from your page |

Plugin pages and actions are admin-only.

### Settings sections (`web_config_sections`)

Without this hook, the Settings page still shows your plugin's config, guessing an input type for each value
from its current value. With it, you decide exactly what each field looks like.

```python
@staticmethod
def web_hide_default_card():
    return True

@staticmethod
def web_config_sections(instance_name, instance_config):
    return [
        {
            "label": "Hello",                     # section title
            "hint": "Greets players on !hello.",  # one-line description beside the title
            "path": [],                           # sub-object of your config this section covers ([] = all of it)
            "fields": [
                {"path": ["enabled"], "key": "enabled", "type": "bool_select", "default": 1,
                 "label": "Enable Hello"},
                {"path": ["greeting"], "key": "greeting", "type": "text", "default": "Hello",
                 "label": "Greeting", "help": "Said before the player's name.",
                 "depends_on": {"path": ["enabled"], "equals": 1}},
            ],
        },
    ]
```

Each field:

| Key | Meaning |
|---|---|
| `path` | Where the value lives, relative to your plugin's config (`["rtv", "rtv_rate"]` = `plugins.<name>.rtv.rtv_rate`) |
| `key` | The value's own key (the last element of `path`) |
| `type` | Input type (see below). Omit it to let the panel guess from the value. |
| `label`, `help` | Field label and the hint shown under it |
| `default` | What to show when the key isn't in the JSON yet. Match your plugin's own fallback, so the form shows what will really happen. Nothing is written until the admin saves. |
| `depends_on` | Grey the field out unless another field has a value: `{"path": [...], "equals": 1}` or `{"path": [...], "not_equals": 0}` |

### Field types

| `type` | Input | Extra keys |
|---|---|---|
| `text`, `password`, `textarea` | Text inputs | |
| `number` | Number | |
| `percent` | 0-100 with a `%` | |
| `bool_select` | On/off dropdown (saves `1`/`0` in the value's existing type) | `true_label`, `false_label` |
| `checkbox` | On/off switch | |
| `choice` | Dropdown with explained options, e.g. what 0, 1 and 2 mean | `options: [[value, "label"], ...]` |
| `select` | Dropdown of plain strings | `options: ["a", "b"]` |
| `map_list` | Map picker with autocomplete | `reorderable: true` for up/down arrows |
| `list` | List of strings | `reorderable` |
| `composite` | One space-separated value (e.g. `"1 5"`) edited as several labelled inputs and joined back on save | `parts` (below) |
| `rtm_modes` | RTVRTM's game-mode checkboxes | |

`composite` exists for settings stored as a compact string where a typo would break something. Each part:

```python
{"label": "Vote ends after", "kind": "choice",
 "options": [[0, "A number of minutes"], [1, "A number of rounds"]], "default": 0},
{"label": "How many", "kind": "number", "min": 1, "default": 3,
 "show_when": {"part": 0, "in": [1]}},   # only shown (and saved) when part 0 is 1
```

`kind` is `choice`, `number` or `text`. Other part keys: `help`, `placeholder`, and `match` (a regex a token
must match to belong to this part, for optional leading parts). A shown `number` part that's left empty
blocks saving. See `plugins/rtvrtm/rtvrtm.py` for many real examples.

### Menu items and pages (`web_menu` / `web_page`)

`web_menu` adds an entry under the instance in the sidebar. Return `None` to hide it, e.g. while the feature
is switched off:

```python
@staticmethod
def web_menu(instance_name, instance_config):
    cfg = (instance_config.get('plugins', {}) or {}).get('hello', {}) or {}
    if not int(cfg.get('enabled', 1)):
        return None
    return {"label": "Hello", "icon": "fa-hand-sparkles", "slug": "hello"}
```

- `label`: the menu text.
- `icon`: a [Font Awesome 5](https://fontawesome.com/v5/search?m=free) class.
- `slug`: the page's URL, `/plugin/<instance>/<slug>`.

`web_page` returns the page as a list of sections, drawn top to bottom:

```python
@staticmethod
def web_page(instance_name, instance_config):
    return [
        {
            "type": "table",
            "title": "Greetings sent",
            "help": "Newest first.",
            "searchable": True,                       # adds a search box
            "columns": ["Player", "When"],
            "rows": [["Rex", "12:01"], ["Fives", "12:04"]],
            # optional: clicking a row fills a field of an action_form below
            "row_action": {"fill_form": "reset", "fill_field": "player", "value_column": 0},
        },
        {
            "type": "action_form",
            "title": "Reset a player",
            "action": "reset",                        # passed to web_action as action_name
            "submit_label": "Reset",
            "fields": [
                {"name": "player", "label": "Player", "type": "text", "required": True},
                {"name": "amount", "label": "Amount", "type": "number"},
            ],
        },
        {
            "type": "config_form",                    # edits the instance JSON, with its own Save button
            "title": "Settings",
            "fields": [],                             # same field specs as web_config_sections
        },
    ]
```

| Section `type` | Shows |
|---|---|
| `table` | A table. `searchable` adds a filter box. `row_action` makes rows click-to-fill an `action_form`. |
| `action_form` | A small form posted to your `web_action`. The result appears under the form. |
| `config_form` | Settings fields (same specs as above) bound to the instance's config, with a sticky Save bar, Ctrl+S and the same save path as the Settings page. |
| `error` | A red message box (`message`) |

Only put data an admin should see in tables. For example, the Economy page shows account handles and
balances but never the password hashes stored beside them.

### Actions (`web_action`)

```python
@staticmethod
def web_action(instance_name, action_name, form_data):
    if action_name != "reset":
        return False, "Unknown action."
    player = str(form_data.get("player", "")).strip()
    if not player:
        return False, "Player is required."
    # ...do the work: write a file, send RCON, etc....
    return True, "Reset {}.".format(player)
```

Validate everything in `form_data`: it comes straight from the browser. Return `(True, message)` or
`(False, message)`; the message is shown to the admin, and successful actions go into the audit log. If you
edit a file the engine also writes (like `economy_accounts.dat`), take the same file lock the engine uses:
see `_apply_credit_delta` in `plugins/creditsystem/creditsystem.py`.

---

## A complete example

`plugins/hello/hello.py`: a `!hello` command, a message counter kept in a small file, a sidebar page with
the counts and a reset action, and typed settings.

```python
import json
import os

from mbiiez import settings

def _counts_path(instance_name):
    # Kept in the plugin's own folder: both the game-side plugin and the web
    # panel's static hooks can find it from just the instance name.
    return os.path.join(settings.locations.plugins_path, "hello", "counts_{}.json".format(instance_name))


def _load_counts(instance_name):
    try:
        with open(_counts_path(instance_name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class plugin:
    plugin_name = "Hello"
    plugin_author = "You"
    plugin_url = ""

    def __init__(self, instance):
        self.instance = instance
        self.config = instance.config['plugins'].get('hello', {})
        self.enabled = int(self.config.get('enabled', 1))
        self.greeting = self.config.get('greeting', 'Hello')

        if instance.has_plugin("auto_message") and self.enabled:
            instance.config['plugins']['auto_message']['messages'].append("^5!hello ^7says hi back.")

    def register(self):
        if self.enabled:
            self.instance.event_handler.register_event("player_chat_command", self.on_command)

    def on_command(self, args):
        if args['message'].strip().lower() != "!hello":
            return
        self.instance.say("{}, {}!".format(self.greeting, args['player']))

        counts = _load_counts(self.instance.name)
        counts[args['player']] = counts.get(args['player'], 0) + 1
        with open(_counts_path(self.instance.name), "w") as f:
            json.dump(counts, f)

    # --- web panel ---

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [{
            "label": "Hello", "hint": "Replies to !hello.", "path": [],
            "fields": [
                {"path": ["enabled"], "key": "enabled", "type": "bool_select", "default": 1,
                 "label": "Enable Hello"},
                {"path": ["greeting"], "key": "greeting", "type": "text", "default": "Hello",
                 "label": "Greeting", "depends_on": {"path": ["enabled"], "equals": 1}},
            ],
        }]

    @staticmethod
    def web_menu(instance_name, instance_config):
        cfg = (instance_config.get('plugins', {}) or {}).get('hello', {}) or {}
        if not int(cfg.get('enabled', 1)):
            return None
        return {"label": "Hello", "icon": "fa-hand-sparkles", "slug": "hello"}

    @staticmethod
    def web_page(instance_name, instance_config):
        counts = _load_counts(instance_name)
        rows = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [
            {"type": "table", "title": "!hello count", "searchable": True,
             "columns": ["Player", "Times"], "rows": [[p, n] for p, n in rows],
             "row_action": {"fill_form": "reset", "fill_field": "player", "value_column": 0}},
            {"type": "action_form", "title": "Reset a player's count", "action": "reset",
             "submit_label": "Reset",
             "fields": [{"name": "player", "label": "Player", "type": "text", "required": True}]},
        ]

    @staticmethod
    def web_action(instance_name, action_name, form_data):
        if action_name != "reset":
            return False, "Unknown action."
        player = str((form_data or {}).get("player", "")).strip()
        counts = _load_counts(instance_name)
        if player not in counts:
            return False, "No count for '{}'.".format(player)
        del counts[player]
        with open(_counts_path(instance_name), "w") as f:
            json.dump(counts, f)
        return True, "Reset {}.".format(player)
```

---

## Rules of thumb

- **Defaults in one place.** Read settings with `.get(key, default)` and use the same default in your field
  specs, so the form shows what the plugin will actually do.
- **Keep `__init__` and `register` cheap.** They also run for quick CLI commands.
- **Don't block event handlers.** They run in the log watcher: a slow handler delays every other event. Put
  slow work in a service.
- **Services don't share memory** with event handlers or each other (they're forked). Use files, cvars or
  the database.
- **Web hooks are static.** They get the instance name and config, never a running instance.
- **Never put secrets in pages.** API keys belong in `password` fields; tables should never show passwords
  or hashes.
- **Engine features need `caded.i386`.** If your plugin drives cvars from [our OpenJK
  fork](https://github.com/clone-army/OpenJK), say so in its docs.
- **One Auto Messages line per plugin**, and only when the feature is enabled.
