"""
Turns an instance's plain-JSON config into a tree of field descriptors the
config page can render as a form, without needing a schema. This is a
heuristic best-effort renderer, not a validator - anything it can't
confidently classify falls back to a raw-JSON textarea for just that
subtree, so an unrecognised shape never blocks editing/saving the rest of
the form. The JSON file on disk stays the actual source of truth: the
browser reconstructs the full config object from the ORIGINAL parsed JSON
plus whatever the form fields changed, and saves it through the same
save path as the existing raw-JSON editor (see controllers/config.py).
"""

import json
import re

BOOLEAN_HINT = re.compile(r"enable", re.IGNORECASE)
MAP_LIST_KEYS = {"primary_maps", "secondary_maps", "map_rotation_order"}
GAME_MODES = ["open", "semi-authentic", "full-authentic", "duel", "legends"]


def _label(key):
    return key.replace("_", " ").replace("-", " ").strip().title()


def _is_password_field(key):
    return "password" in key.lower()


def _is_maps_list(key, ancestor_keys):
    if key in MAP_LIST_KEYS:
        return True
    if key == "maps" and "holiday_maps" in ancestor_keys:
        return True
    return False


def _is_boolean_like(key, value):
    if isinstance(value, bool):
        return True
    if not BOOLEAN_HINT.search(key):
        return False
    try:
        return int(value) in (0, 1)
    except (TypeError, ValueError):
        return False


def describe(value, key, ancestor_keys):
    """Recursively describe one JSON value. `ancestor_keys` is the list of
    parent keys (not including `key` itself); the dotted path used as the
    field's `data-path` is ancestor_keys + [key] joined with '.'."""
    path_keys = ancestor_keys + [key]
    path = ".".join(path_keys)
    node = {"path": path, "key": key, "label": _label(key)}

    if isinstance(value, dict):
        node["kind"] = "group"
        node["children"] = [describe(v, k, path_keys) for k, v in value.items()]
        return node

    if isinstance(value, list):
        if all(item is None or isinstance(item, (str, int, float, bool)) for item in value):
            node["kind"] = "maplist" if _is_maps_list(key, ancestor_keys) else "list"
            node["value"] = ["" if item is None else str(item) for item in value]
            return node
        node["kind"] = "raw"
        node["value"] = json.dumps(value, indent=2)
        return node

    if _is_boolean_like(key, value):
        node["kind"] = "checkbox"
        node["bool_as"] = "native" if isinstance(value, bool) else "int01"
        node["value"] = bool(value) if isinstance(value, bool) else bool(int(value))
        return node

    if isinstance(value, (int, float)) and key == "config" and ancestor_keys[:1] == ["smod"]:
        # smod.admin_N.config - a bitmask of the 16 command rights an admin
        # slot has (kick, nextmap, map, ... settk - see SMOD_RIGHTS in
        # config.html). Rendered as a normal number field plus a "Pick
        # rights..." button that opens a checkbox picker and computes the
        # value, same scheme as the community's mbsmod.js calculator
        # (https://puppytine.github.io/) - ported client-side rather than
        # linked out to, so it keeps working offline and matches this
        # page's own styling.
        node["kind"] = "smod_bitmask"
        node["value"] = value
        return node

    if isinstance(value, (int, float)):
        node["kind"] = "number"
        node["value"] = value
        return node

    # Remaining case: string (or None, treated as an empty string).
    str_value = "" if value is None else str(value)

    if key == "mode" and str_value.lower() in GAME_MODES:
        node["kind"] = "select"
        node["value"] = str_value
        node["options"] = GAME_MODES
        return node

    if _is_password_field(key):
        node["kind"] = "password"
        node["value"] = str_value
        return node

    if "\n" in str_value:
        node["kind"] = "textarea"
        node["value"] = str_value
        return node

    node["kind"] = "text"
    node["value"] = str_value
    return node


def describe_top(config_dict, skip_keys=None):
    """Build one descriptor per top-level config key, skipping any named in
    skip_keys (the config page handles 'plugins' separately - see
    describe_plugins - so it isn't rendered twice)."""
    skip_keys = skip_keys or set()
    return [
        describe(value, key, [])
        for key, value in config_dict.items()
        if key not in skip_keys
    ]


def describe_plugins(config_dict, all_plugin_names, plugin_meta_by_name):
    """Build one card descriptor per plugin known on disk: whether this
    instance currently enables it, its display metadata, and a 'group'
    field descriptor for whatever options dict it currently has (empty for
    a plugin that isn't enabled yet)."""
    plugins_cfg = config_dict.get("plugins", {}) or {}
    cards = []

    for name in all_plugin_names:
        enabled = name in plugins_cfg
        options_value = plugins_cfg.get(name, {}) or {}
        options_node = describe(options_value, name, ["plugins"])
        meta = plugin_meta_by_name.get(name, {})
        cards.append(
            {
                "name": name,
                "enabled": enabled,
                "label": meta.get("plugin_name", name),
                "author": meta.get("plugin_author", ""),
                "options": options_node,
            }
        )

    return cards
