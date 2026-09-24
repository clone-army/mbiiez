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
