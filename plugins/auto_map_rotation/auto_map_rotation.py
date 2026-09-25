'''
Auto Map Rotation plugin for MBIIEZ.

Once the server has been EMPTY for `rotation_minutes`, moves it on to the next
map in the instance's own map rotation (`map_rotation_order`, which the
generated server config turns into a "vstr nextmap" chain), then keeps doing
so every `rotation_minutes` for as long as it stays empty. Anyone connecting
resets the clock, so a populated server is never touched.

Configuration in instance JSON:

    "plugins": {
        "auto_map_rotation": { "rotation_minutes": 30 }
    }

`rotation_minutes` 0 switches rotation off. `rotate_minutes` is accepted as
an older spelling of the same key.
'''

import time

# How often to look at the player count. The rotation itself only ever
# happens after a full `rotation_minutes` of emptiness - this just sets how
# precisely "empty since" is measured.
CHECK_EVERY_SECONDS = 30
DEFAULT_MINUTES = 30


def _rotation_minutes(config):
    """The configured interval, or 0 for "off". A missing key means the
    default, but an explicit 0 (or blank) means off - matching the web
    panel's help text."""
    for key in ('rotation_minutes', 'rotate_minutes'):
        if key in config:
            value = config.get(key)
            if value in (None, ''):
                return 0
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                return DEFAULT_MINUTES
    return DEFAULT_MINUTES


class plugin:

    plugin_name = "Auto Map Rotation"
    plugin_author = "Louis Varley"
    plugin_url = ""

    @staticmethod
    def web_hide_default_card():
        return True

    @staticmethod
    def web_config_sections(instance_name, instance_config):
        return [
            {
                "label": "Auto Map Rotation",
                "path": [],
                "hint": "Moves an empty server on to the next map in its rotation.",
                "fields": [
                    {"path": ["rotation_minutes"], "key": "rotation_minutes", "type": "number", "default": DEFAULT_MINUTES,
                     "label": "Rotate After (minutes empty)",
                     "help": "Once nobody has been on for this long, change to the next map in Map Rotation, then again "
                             "every this-many minutes while it stays empty. 0 turns rotation off."},
                ],
            },
        ]

    instance = None

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get('auto_map_rotation', {}) or {}
        self.minutes = _rotation_minutes(self.config)

    def register(self):
        if self.minutes > 0:
            self.instance.process_handler.register_service("Auto Map Rotation Service", self.auto_map_changes)
        else:
            self.instance.log_handler.log("Auto Map Rotation: rotation_minutes is 0, rotation is off.")

    def _is_empty(self):
        """True/False, or None if the server couldn't be asked (e.g. RCON
        not up yet during a map load) - treated as "don't know", which
        neither starts nor resets the empty clock."""
        try:
            return self.instance.is_empty()
        except Exception:
            return None

    def auto_map_changes(self):
        interval = self.minutes * 60
        log = self.instance.log_handler.log
        log("Auto Map Rotation: started - next map after {:g} min empty, then every {:g} min while empty.".format(
            self.minutes, self.minutes))

        # Timestamp the current empty stretch (or the last rotation within
        # it) started - None while anyone is on.
        empty_since = None

        while True:
            time.sleep(CHECK_EVERY_SECONDS)

            empty = self._is_empty()
            if empty is None:
                continue

            now = time.time()
            if not empty:
                if empty_since is not None:
                    log("Auto Map Rotation: players joined, rotation clock reset.")
                empty_since = None
                continue

            if empty_since is None:
                empty_since = now
                log("Auto Map Rotation: server is empty - next map in {:g} min unless someone joins.".format(self.minutes))
                continue

            if now - empty_since >= interval:
                try:
                    self.instance.rcon("vstr nextmap")
                    log("Auto Map Rotation: empty for {:g} min, changed to the next map in the rotation.".format(self.minutes))
                except Exception as e:
                    log("Auto Map Rotation: failed to send vstr nextmap - {}.".format(e))
                # Count the next interval from this change, not from when
                # the server first emptied.
                empty_since = now
