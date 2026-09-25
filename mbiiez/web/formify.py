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

# RTVRTM's "RTM" value: one number standing for a set of MBII modes
# (0 Open, 1 Semi Authentic, 2 Full Authentic, 3 Duel, 4 Legends). Must
# match the lookup table in plugins/rtvrtm/rtvrtm_original.py exactly -
# 0-21 are the original script's codes, 22-31 were added so every
# combination has one.
RTM_MODE_NAMES = ["Open", "Semi Authentic", "Full Authentic", "Duel", "Legends"]
RTM_MODE_CODES = {
    1: (0,), 2: (1,), 3: (2,), 4: (0, 1), 5: (0, 2), 6: (1, 2), 7: (0, 1, 2),
    8: (3,), 9: (0, 3), 10: (1, 3), 11: (2, 3), 12: (0, 2, 3), 13: (1, 2, 3),
    14: (0, 1, 2, 3), 15: (4,), 16: (0, 4), 17: (2, 4), 18: (0, 3, 4),
    19: (0, 2, 4), 20: (0, 2, 3, 4), 21: (0, 1, 2, 3, 4), 22: (1, 4),
    23: (3, 4), 24: (0, 1, 4), 25: (0, 1, 3), 26: (1, 2, 4), 27: (1, 3, 4),
    28: (2, 3, 4), 29: (0, 1, 2, 4), 30: (0, 1, 3, 4), 31: (1, 2, 3, 4),
}


def _split_composite(value, parts):
    """Split a space-separated compound value (e.g. RTVRTM's "1 5") into
    one value per part, in order. A part with a "match" regex only takes
    the next token if it fits - so an optional leading part (default_game's
    mode number) can be absent without shifting the map name into it.
    A part that gets no token is None."""
    tokens = str("" if value is None else value).split()
    out = []
    for part in parts:
        pattern = part.get("match")
        if tokens and (not pattern or re.fullmatch(pattern, tokens[0])):
            out.append(tokens.pop(0))
        else:
            out.append(None)
    return out


def _label(key):
    return key.replace("_", " ").replace("-", " ").strip().title()


def _infer_help(key):
    """A short, plain-English hint for a number/text field whose bare key
    name won't mean much to a non-technical admin - inferred from the key
    itself (unit suffixes, "port", "rate") so it scales to any plugin's
    config instead of needing a hand-maintained list per field. Returns
    None (shown as no hint at all) when nothing confident applies."""
    lower = key.lower()

    if lower.endswith("_hours"):
        return "In hours."
    if lower.endswith("_minutes"):
        return "In minutes."
    if lower.endswith("_seconds") or lower.endswith("cooldown"):
        return "In seconds."
    if lower == "port" or lower.endswith("_port"):
        return "Network port - changing this needs a restart, and must not collide with another instance's port."
    if "rate" in lower:
        return "Usually a percentage (0-100) unless the plugin says otherwise."
    return None


def _count_fields(node):
    """How many actual leaf fields (not sub-groups) live under a group
    node, recursively - used for the "N settings" hint on the config
    page's collapsed section headers so an admin has some idea what's
    inside before they open it."""
    if node.get("kind") != "group":
        return 1
    return sum(_count_fields(child) for child in node.get("children", []))


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


def _bool_as(value):
    """Which JSON shape a 0/1-ish value should round-trip back as on save
    - native True/False, the string "1"/"0" (plenty of plugin cvars, e.g.
    creditsystem's g_creditSystemEnable, are stored as strings since
    that's how they're written out as real game cvars), or the int 1/0.
    Getting this wrong doesn't break rendering, only silently changes the
    saved file's value type even though nothing about it "changed"."""
    if isinstance(value, bool):
        return "native"
    if isinstance(value, str):
        return "str01"
    return "int01"


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
        node["field_count"] = sum(_count_fields(child) for child in node["children"])
        return node

    if isinstance(value, list):
        if all(item is None or isinstance(item, (str, int, float, bool)) for item in value):
            is_maps = _is_maps_list(key, ancestor_keys)
            node["kind"] = "maplist" if is_maps else "list"
            node["value"] = ["" if item is None else str(item) for item in value]
            if is_maps:
                # Only the main rotation's order is meaningful to a human -
                # a holiday's or RTV's own map pool is just a set, so it
                # doesn't get up/down reorder controls. See "reorderable"
                # on the chip-list-widget in form-field.html.
                node["reorderable"] = key == "map_rotation_order"
            return node
        node["kind"] = "raw"
        node["value"] = json.dumps(value, indent=2)
        return node

    if _is_boolean_like(key, value):
        node["kind"] = "checkbox"
        node["bool_as"] = _bool_as(value)
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
        node["help"] = _infer_help(key)
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


def describe_field_spec(spec, config_dict, plugin_name):
    """Build a render-ready field node from a plugin-declared field spec,
    instead of describe()'s value-shape heuristics - so a plugin can say
    exactly what widget a field should use (a 0/1 toggle instead of a bare
    number, a 0-100 rate instead of an unbounded one, a reorderable maps
    picker) rather than being at the mercy of a guess. Used by both the
    Config page's promoted plugin sections (plugin_loader.
    call_web_config_sections) and a plugin's own page's "config_form"
    sections (plugin_loader.call_web_page).

    spec is {
        "key": "rtv_rate",              # required - the field's own JSON key
        "path": ["rtv", "rtv_rate"],    # required - relative to this plugin's own config dict
        "type": "percent",              # optional - a widget kind below; omitted falls back to describe()'s heuristics
        "label": "...",                 # optional
        "help": "...",                  # optional
        "options": [...],               # required for type == "select"
        "reorderable": True,            # optional, for type == "map_list"
        "true_label" / "false_label":   # optional, for type == "bool_select"
        "depends_on": {"path": [...], "equals": value},  # optional - path relative to this plugin's own config dict, like "path" above
    }

    Widget kinds: text, password, textarea, number, percent, bool_select,
    checkbox, select, choice, composite, rtm_modes, map_list, list. For
    "choice", "options" is [[value, label], ...]. For "composite", "parts"
    is a list of {"label", "help", "kind": "choice"|"number"|"text",
    "options", "min", "default", "match", "show_when": {"part": i,
    "in": [...]}}. An unrecognised or omitted "type" falls
    back to describe()'s normal heuristics on the field's current value,
    so a plugin only needs to hand-type the fields it wants to improve.
    """
    path = spec["path"]
    abs_path_keys = ["plugins", plugin_name] + path
    dotted_path = ".".join(abs_path_keys)

    value = config_dict
    for k in abs_path_keys:
        value = (value or {}).get(k) if isinstance(value, dict) else None

    # A field missing from this instance's JSON isn't necessarily "off" or
    # "0" - the plugin's own Python code usually has its own fallback
    # (e.g. killstreak/chaos default `enabled` to 1, not 0, when the key
    # is absent). "default" in the spec lets the widget show what the
    # plugin will actually do, not a generic zero value, without writing
    # anything to disk until the admin actually changes it.
    if value is None and "default" in spec:
        value = spec["default"]

    field_type = spec.get("type")
    label = spec.get("label") or _label(spec["key"])

    if field_type is None:
        node = describe(value, spec["key"], abs_path_keys[:-1])
        node["label"] = label
        if spec.get("help"):
            node["help"] = spec["help"]
    else:
        node = {"path": dotted_path, "key": spec["key"], "label": label, "help": spec.get("help")}

        if field_type == "percent":
            node["kind"] = "percent"
            node["value"] = value if isinstance(value, (int, float)) else 0

        elif field_type == "bool_select":
            node["kind"] = "bool_select"
            node["bool_as"] = _bool_as(value)
            node["value"] = bool(value) if isinstance(value, bool) else bool(int(value or 0))
            node["true_label"] = spec.get("true_label", "Enabled")
            node["false_label"] = spec.get("false_label", "Disabled")

        elif field_type == "checkbox":
            node["kind"] = "checkbox"
            node["bool_as"] = _bool_as(value)
            node["value"] = bool(value) if isinstance(value, bool) else bool(int(value or 0))

        elif field_type == "select":
            node["kind"] = "select"
            node["value"] = "" if value is None else str(value)
            node["options"] = spec.get("options", [])

        elif field_type == "choice":
            # Like select, but options are [value, label] pairs, so a
            # 0/1/2 setting can show what each number means. Saves back as
            # a number when every option value is one.
            options = spec.get("options", [])
            node["kind"] = "choice"
            node["value"] = "" if value is None else str(value)
            node["options"] = [[str(v), label] for v, label in options]
            node["numeric"] = all(isinstance(v, int) for v, _ in options)

        elif field_type == "composite":
            # One stored string ("0 3", "1 2", "2 0 1") edited as separate
            # labelled inputs; config-form.js joins them back with spaces
            # on every change, leaving out parts whose "show_when" isn't
            # met, so a malformed value (which the RTVRTM parser would
            # reject at startup) can't be typed in the first place.
            parts = spec.get("parts", [])
            node["kind"] = "composite"
            node["value"] = "" if value is None else str(value)
            node["parts"] = []
            for part, current in zip(parts, _split_composite(value, parts)):
                p = dict(part)
                if current is None:
                    current = part.get("default", "")
                p["value"] = "" if current is None else str(current)
                if p.get("options"):
                    p["options"] = [[str(v), label] for v, label in p["options"]]
                node["parts"].append(p)

        elif field_type == "rtm_modes":
            try:
                code = int(value or 0)
            except (TypeError, ValueError):
                code = 0
            node["kind"] = "rtm_modes"
            node["value"] = code
            node["selected"] = list(RTM_MODE_CODES.get(code, ()))
            node["unknown"] = code != 0 and code not in RTM_MODE_CODES
            node["mode_names"] = RTM_MODE_NAMES
            node["codes"] = {",".join(str(m) for m in modes): c for c, modes in RTM_MODE_CODES.items()}

        elif field_type == "map_list":
            node["kind"] = "maplist"
            node["value"] = ["" if item is None else str(item) for item in (value or [])]
            node["reorderable"] = bool(spec.get("reorderable"))

        elif field_type == "list":
            node["kind"] = "list"
            node["value"] = ["" if item is None else str(item) for item in (value or [])]
            node["reorderable"] = bool(spec.get("reorderable"))

        elif field_type == "number":
            node["kind"] = "number"
            node["value"] = value if isinstance(value, (int, float)) else 0

        elif field_type == "password":
            node["kind"] = "password"
            node["value"] = "" if value is None else str(value)

        elif field_type == "textarea":
            node["kind"] = "textarea"
            node["value"] = "" if value is None else str(value)

        else:
            # Unknown declared type - fall back to plain text rather than
            # silently dropping the field.
            node["kind"] = "text"
            node["value"] = "" if value is None else str(value)

    if spec.get("depends_on"):
        dep = spec["depends_on"]
        dep_path = ".".join(["plugins", plugin_name] + dep["path"])
        node["depends_on"] = {"path": dep_path}
        # "equals": active only at that value; "not_equals": active at any
        # other value (e.g. RTM's settings, active for every non-zero code).
        for rule_key in ("equals", "not_equals"):
            if rule_key in dep:
                node["depends_on"][rule_key] = dep[rule_key]

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
