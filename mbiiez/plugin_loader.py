import os
import importlib.util

from mbiiez import settings


def find_plugin_module_path(plugin_name):
    """Find the .py file for a plugin by name, trying the same naming
    conventions as the runtime plugin_handler (legacy 'plugin_<name>.py',
    a bare '<name>.py', or a '<name>/<name>.py' folder). Returns
    (module_name, file_path), or (None, None) if nothing is found.

    This is read-only discovery for the web UI (listing/describing plugins,
    not running them) - it intentionally does not touch plugin_handler.py's
    own loading path so the live game-server plugin loader is untouched.
    """
    possible_names = [f"plugin_{plugin_name}", plugin_name]

    for module_name in possible_names:
        file_path = os.path.join(settings.locations.plugins_path, f"{module_name}.py")
        if os.path.isfile(file_path):
            return module_name, file_path

        folder_file_path = os.path.join(settings.locations.plugins_path, module_name, f"{module_name}.py")
        if os.path.isfile(folder_file_path):
            return module_name, folder_file_path

    simple_folder_file_path = os.path.join(settings.locations.plugins_path, plugin_name, f"{plugin_name}.py")
    if os.path.isfile(simple_folder_file_path):
        return plugin_name, simple_folder_file_path

    return None, None


def load_plugin_module(plugin_name):
    """Import and return a plugin's module by name, or None if it can't be
    found or fails to import. Never raises - callers (web pages) shouldn't
    break because one plugin on disk is broken."""
    module_name, file_path = find_plugin_module_path(plugin_name)
    if not file_path:
        return None

    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def discover_plugin_names():
    """List every plugin available on disk - folder 'name/name.py' or a bare
    'name.py' file under plugins_path - regardless of whether any instance
    currently enables it. Used by the web UI so an instance can turn on a
    plugin it has never used before."""
    names = set()
    base = settings.locations.plugins_path
    if not os.path.isdir(base):
        return []

    for entry in os.listdir(base):
        if entry.startswith("__") or entry.startswith("."):
            continue

        full = os.path.join(base, entry)
        if os.path.isdir(full):
            if os.path.isfile(os.path.join(full, f"{entry}.py")):
                names.add(entry)
        elif entry.endswith(".py"):
            name = entry[:-3]
            if name.startswith("plugin_"):
                name = name[len("plugin_"):]
            names.add(name)

    return sorted(names)


def get_plugin_meta(plugin_name):
    """Return {'plugin_name', 'plugin_author', 'plugin_url'} for a plugin,
    read directly off the class (no instantiation - a plugin's __init__
    expects a real running instance, which the web UI must not construct
    just to list plugins)."""
    module = load_plugin_module(plugin_name)
    meta = {"plugin_name": plugin_name, "plugin_author": "", "plugin_url": ""}
    if module is None or not hasattr(module, "plugin"):
        return meta

    cls = module.plugin
    meta["plugin_name"] = getattr(cls, "plugin_name", plugin_name)
    meta["plugin_author"] = getattr(cls, "plugin_author", "")
    meta["plugin_url"] = getattr(cls, "plugin_url", "")
    return meta


def call_web_config_sections(plugin_name, instance_name, instance_config):
    """Safely call a plugin's optional web_config_sections(instance_name,
    instance_config) static hook. Lets a plugin promote named subtrees of
    its own config to top-level sections on the Config page (e.g. "RTV",
    "RTM") instead of everything living nested inside the generic
    "Plugins" card - see controllers/config.py, which also excludes each
    promoted subtree from that plugin's generic card so a field isn't
    editable in two places at once.

    Expected return shape: a list of {"label": str, "path": [key, ...]}
    dicts, where `path` is relative to the plugin's own config dict
    (instance_config['plugins'][plugin_name]) - e.g. {"path": ["rtv"]}
    for instance_config['plugins']['rtvrtm']['rtv']. Returns [] if the
    plugin doesn't implement the hook, or if it raises - a broken plugin
    must never take down the Config page."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return []

    hook = getattr(module.plugin, "web_config_sections", None)
    if hook is None:
        return []

    try:
        return hook(instance_name, instance_config) or []
    except Exception:
        return []


def call_web_hide_default_card(plugin_name):
    """Safely call a plugin's optional web_hide_default_card() static hook
    (no args - it's a blanket per-plugin choice, not per-instance). A
    plugin that fully describes its own config through
    web_config_sections()/web_page() "config_form" sections returns True
    here so the generic auto-rendered Plugins card doesn't also show
    (and duplicate) the same fields. Returns False if the plugin doesn't
    implement it, or if it raises."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return False

    hook = getattr(module.plugin, "web_hide_default_card", None)
    if hook is None:
        return False

    try:
        return bool(hook())
    except Exception:
        return False


def call_web_menu(plugin_name, instance_name, instance_config):
    """Safely call a plugin's optional web_menu(instance_name, instance_config)
    static hook. Returns None if the plugin doesn't implement it, or if it
    raises - a broken plugin must never take down the nav bar or config page."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return None

    hook = getattr(module.plugin, "web_menu", None)
    if hook is None:
        return None

    try:
        return hook(instance_name, instance_config)
    except Exception:
        return None


def call_web_page(plugin_name, instance_name, instance_config):
    """Safely call a plugin's optional web_page(instance_name, instance_config)
    static hook. Returns None if unavailable or it raises."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return None

    hook = getattr(module.plugin, "web_page", None)
    if hook is None:
        return None

    try:
        return hook(instance_name, instance_config)
    except Exception as e:
        return [{"type": "error", "message": str(e)}]


def call_web_action(plugin_name, instance_name, action_name, form_data):
    """Safely call a plugin's optional web_action(instance_name, action_name,
    form_data) static hook. Returns (False, message) if unavailable or it
    raises, instead of ever propagating an exception to the Flask route."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return False, "Plugin not found."

    hook = getattr(module.plugin, "web_action", None)
    if hook is None:
        return False, "This plugin does not support actions."

    try:
        return hook(instance_name, action_name, form_data)
    except Exception as e:
        return False, str(e)


def call_web_mod_actions(plugin_name, instance_name, instance_config):
    """Safely call a plugin's optional web_mod_actions(instance_name,
    instance_config) static hook: cards of quick actions shown on the Mod
    page (mod role and up, unlike web_page/web_action which are admin-only).

    Expected return shape: a list of
        {"title": str, "help": str (optional),
         "actions": [{"name": str, "label": str,
                      "style": "primary"|"secondary"|"success"|"warning"|"danger" (optional),
                      "confirm": str (optional - asked before running),
                      "fields": [{"name", "label", "type", "required", "placeholder"}] (optional)}]}
    Returns [] if the plugin doesn't implement it, or if it raises - a
    broken plugin must never take down the Mod page."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return []

    hook = getattr(module.plugin, "web_mod_actions", None)
    if hook is None:
        return []

    try:
        return hook(instance_name, instance_config) or []
    except Exception:
        return []


def call_web_mod_action(plugin_name, instance_name, action_name, form_data):
    """Safely call a plugin's optional web_mod_action(instance_name,
    action_name, form_data) static hook. Returns (False, message) if
    unavailable or it raises."""
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return False, "Plugin not found."

    hook = getattr(module.plugin, "web_mod_action", None)
    if hook is None:
        return False, "This plugin does not support Mod page actions."

    try:
        return hook(instance_name, action_name, form_data)
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Dependencies and engines
#
# A plugin class can declare, as class attributes:
#   plugin_description = "One line for the Settings page"
#   plugin_requires = ["accounts"]   # plugins that must be on too (hard)
#   plugin_uses = ["accounts"]       # plugins it makes use of if they're on (soft)
#   plugin_engine = "caded"          # engine family it needs (None = any)
# The runtime loader (plugin_handler) starts plugins in dependency order and
# skips any whose requirements or engine aren't there, saying why; the
# Settings page shows them and ticks requirements for you.
# ---------------------------------------------------------------------------

ENGINE_DIR = "/usr/bin"

# Engine families, by file name prefix, and what they are.
ENGINE_FAMILIES = [
    ("caded", "Clone Army OpenJK - economy, social mode, Holotable and the other caded features"),
    ("mbiided", "MBII's standard engine - none of the extra features"),
    ("openjkded", "plain 2018 OpenJK build"),
]


def engine_family(engine):
    """'caded' for caded.i386, caded-test.i386...; 'mbiided', 'openjkded';
    else the file's own name. Empty for no engine."""
    name = os.path.basename(str(engine or "")).lower()
    if not name:
        return ""
    for family, _ in ENGINE_FAMILIES:
        if name.startswith(family):
            return family
    return name.split(".")[0]


def engine_description(engine):
    fam = engine_family(engine)
    for family, text in ENGINE_FAMILIES:
        if family == fam:
            return text
    return ""


def list_engines():
    """Every dedicated-server engine installed ('*ded*.i386' in /usr/bin),
    the main caded.i386 first."""
    try:
        names = [f for f in os.listdir(ENGINE_DIR)
                 if f.endswith(".i386") and "ded" in f and os.path.isfile(os.path.join(ENGINE_DIR, f))]
    except OSError:
        names = []
    order = {"caded.i386": 0, "mbiided.i386": 1, "openjkded.i386": 2}
    return sorted(names, key=lambda n: (order.get(n, 3), n))


# How the Plugins page groups them.
PLUGIN_GROUPS = [
    ("Accounts & Credits", ["accounts", "credits", "shop", "bounties", "bar", "jukebox", "casino"]),
    ("Game Modes & Scenarios", ["social", "holotable", "chaos", "gungame"]),
    ("Server & Community", ["auto_message", "auto_map_rotation", "rtvrtm", "anytime_spin", "shield", "stats",
                            "killstreak", "ai", "discord_bot"]),
]


def get_plugin_requirements(plugin_name):
    """{'requires': [...], 'uses': [...], 'engine': str|None, 'description': str}
    read off the plugin class."""
    module = load_plugin_module(plugin_name)
    out = {"requires": [], "uses": [], "engine": None, "description": ""}
    if module is None or not hasattr(module, "plugin"):
        return out
    cls = module.plugin
    out["requires"] = list(getattr(cls, "plugin_requires", []) or [])
    out["uses"] = list(getattr(cls, "plugin_uses", []) or [])
    out["engine"] = getattr(cls, "plugin_engine", None)
    out["description"] = getattr(cls, "plugin_description", "") or ""
    return out


def plugin_problems(plugin_name, instance_config):
    """Why this plugin can't run on this instance (empty list if it can):
    requirements that aren't on, or the wrong engine."""
    cfg = instance_config or {}
    enabled = set((cfg.get("plugins") or {}).keys())
    req = get_plugin_requirements(plugin_name)
    problems = []
    for need in req["requires"]:
        if need not in enabled:
            problems.append("needs the {} plugin".format(get_plugin_meta(need).get("plugin_name", need)))
    engine = ((cfg.get("server") or {}).get("engine")) or ""
    if req["engine"] and engine_family(engine) != req["engine"]:
        problems.append("needs the {} engine (this instance runs {})".format(req["engine"] + ".i386", engine or "none"))
    return problems


def resolve_load_order(plugin_names, instance_config):
    """(order, skipped): the plugins that can run, requirements before
    whatever needs them (otherwise as listed), and {name: reason} for the
    rest - including anything whose requirement was itself skipped."""
    names = list(plugin_names)
    skipped = {}
    for name in names:
        problems = plugin_problems(name, instance_config)
        if problems:
            skipped[name] = "; ".join(problems)

    # A requirement skipped takes whatever needs it down too.
    changed = True
    while changed:
        changed = False
        for name in names:
            if name in skipped:
                continue
            for need in get_plugin_requirements(name)["requires"]:
                if need in skipped:
                    skipped[name] = "needs {}, which can't run here ({})".format(need, skipped[need])
                    changed = True
                    break

    order, placed = [], set()

    def place(name, trail=()):
        if name in placed or name in skipped or name not in names or name in trail:
            return
        for need in get_plugin_requirements(name)["requires"]:
            place(need, trail + (name,))
        placed.add(name)
        order.append(name)

    for name in names:
        place(name)
    return order, skipped


# ---------------------------------------------------------------------------
# Pages outside any one instance
#
# A plugin can add top-level menu items (e.g. Accounts, shared by every
# server) with three optional static hooks:
#   web_global_menu()                       -> [{"label", "icon", "slug"}]
#   web_global_page(slug)                   -> sections, as web_page()
#   web_global_action(slug, action, form)   -> (success, message)
# Shown while the plugin is on for at least one instance (or always, with
# plugin_global_always = True).
# ---------------------------------------------------------------------------

def _plugin_hook(plugin_name, hook_name):
    module = load_plugin_module(plugin_name)
    if module is None or not hasattr(module, "plugin"):
        return None
    return getattr(module.plugin, hook_name, None)


def call_web_global_menu(plugin_name):
    hook = _plugin_hook(plugin_name, "web_global_menu")
    if hook is None:
        return []
    try:
        entries = hook() or []
        return [e for e in entries if isinstance(e, dict) and e.get("slug")]
    except Exception:
        return []


def call_web_global_page(plugin_name, slug):
    hook = _plugin_hook(plugin_name, "web_global_page")
    if hook is None:
        return None
    try:
        return hook(slug)
    except Exception as e:
        return [{"type": "error", "message": str(e)}]


def call_web_global_action(plugin_name, slug, action_name, form_data):
    hook = _plugin_hook(plugin_name, "web_global_action")
    if hook is None:
        return False, "This plugin has no actions here."
    try:
        return hook(slug, action_name, form_data)
    except Exception as e:
        return False, str(e)


def global_menus(instance_configs):
    """[{"plugin", "label", "icon", "slug"}] from every plugin that's on for
    some instance (instance_configs: {name: config}), in plugin name order."""
    on_somewhere = set()
    for cfg in (instance_configs or {}).values():
        on_somewhere.update(((cfg or {}).get("plugins") or {}).keys())
    out = []
    for name in discover_plugin_names():
        module = load_plugin_module(name)
        if module is None or not hasattr(module, "plugin"):
            continue
        if name not in on_somewhere and not getattr(module.plugin, "plugin_global_always", False):
            continue
        for entry in call_web_global_menu(name):
            out.append(dict(entry, plugin=name))
    return out
