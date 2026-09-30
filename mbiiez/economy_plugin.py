"""Shared by the plugins that switch caded engine features on with cvars
(accounts, credits, shop, bounties, bar, jukebox, casino...).

A plugin subclasses CvarPlugin (as its module's `plugin` class) and says:
    config_key     - its key under "plugins" in the instance config
    switches       - {cvar: "1"}: what it turns on while it's enabled,
                     set at startup and re-applied every minute
    default_cvars  - its settings' defaults ({cvar: "value"}); the instance
                     config's "cvars" overrides them
    sections       - [(title, [(cvar, "bool"|"number", label[, help]), ...])]
                     for the Settings page
    section_hints  - {title: one line shown beside the section's name}; the
                     first section gets plugin_description if it has none
and optionally announce() -> lines for Auto Messages.
"""
import time


class CvarPlugin:

    plugin_author = "Louis Varley"
    plugin_url = ""
    plugin_engine = "caded"
    plugin_requires = []
    plugin_uses = []
    plugin_description = ""

    config_key = None
    switches = {}
    default_cvars = {}
    sections = []
    section_hints = {}

    @staticmethod
    def cvar_string(value):
        # The Settings page saves numbers and true/false; the engine wants strings.
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    @classmethod
    def web_hide_default_card(cls):
        return True

    @classmethod
    def field_spec(cls, key, kind, label, help_text=None):
        spec = {"path": ["cvars", key], "key": key, "label": label,
                "help": "{} ({})".format(help_text, key) if help_text else key}
        if kind == "bool":
            spec.update({"type": "bool_select", "default": cls.default_cvars.get(key, "0")})
        else:
            spec.update({"type": "number", "default": int(cls.default_cvars.get(key, "0") or 0)})
        return spec

    @classmethod
    def extra_fields(cls, title):
        """Fields that aren't cvars, added to a section (override)."""
        return []

    @classmethod
    def web_config_sections(cls, instance_name, instance_config):
        out = []
        for n, (title, rows) in enumerate(cls.sections):
            hint = cls.section_hints.get(title) or (cls.plugin_description if n == 0 else None)
            out.append({"label": title, "path": [], "hint": hint,
                        "fields": cls.extra_fields(title) + [cls.field_spec(*row) for row in rows]})
        return out

    def __init__(self, instance):
        self.instance = instance
        self.config = self.instance.config['plugins'].get(self.config_key, {}) or {}
        cvars = dict(self.default_cvars)
        cvars.update({k: self.cvar_string(v) for k, v in (self.config.get('cvars', {}) or {}).items()})
        cvars.update(self.switches)
        self.cvars = cvars
        for key, value in cvars.items():
            self.instance.register_plugin_cvar(key, value)
        self.setup()
        if self.instance.has_plugin("auto_message"):
            self.instance.config['plugins']['auto_message'].setdefault('messages', []).extend(self.announce())

    def on(self, cvar):
        return self.cvars.get(cvar, "0") not in ("0", "", "false", "False")

    def setup(self):
        """Anything else to work out at startup (override)."""

    def announce(self):
        return []

    def register(self):
        if self.switches:
            self.instance.process_handler.register_service(self.plugin_name + " Service", self._enforce_service)

    def _enforce_service(self):
        # Kept on, in case something (a map's config, an admin) changes them.
        time.sleep(15)
        while True:
            try:
                for key, value in self.switches.items():
                    self.instance.cvar(key, value)
                    time.sleep(0.25)
            except Exception as e:
                self.instance.exception_handler.log(e)
            time.sleep(60)
