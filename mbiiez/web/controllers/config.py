from mbiiez import settings
import os
import json
import copy

from mbiiez import plugin_loader
from mbiiez.web import formify
from mbiiez.web import maps_catalog


class controller:
    controller_bag = {}

    def __init__(self, instance=None):
        self.controller_bag = {}
        self.controller_bag['instance'] = instance
        self.controller_bag['config_path'] = None
        self.controller_bag['config_content'] = ''
        self.controller_bag['sections'] = []
        self.controller_bag['plugin_sections'] = []
        self.controller_bag['plugin_cards'] = []
        self.controller_bag['maps_catalog'] = []
        self.controller_bag['rotation_node'] = None
        self.controller_bag['holidays'] = []
        self.controller_bag['rtvrtm_enabled'] = False
        self.controller_bag['load_error'] = None

        if not instance:
            return

        config_path = self._get_config_path(instance)
        self.controller_bag['config_path'] = config_path
        if not config_path or not os.path.exists(config_path):
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        self.controller_bag['config_content'] = raw_content

        try:
            config_dict = json.loads(raw_content)
        except Exception as e:
            # Raw JSON tab still works off raw_content above; the Form tab
            # just can't render until the file is valid JSON again.
            self.controller_bag['load_error'] = str(e)
            return

        # 'map_rotation_order' is pulled out of the generic top-level list
        # and rendered as part of the bespoke Maps section below instead
        # (reorderable, with holiday maps alongside it) rather than as its
        # own bare, hint-less accordion item.
        self.controller_bag['sections'] = formify.describe_top(
            config_dict, skip_keys={'plugins', 'map_rotation_order'}
        )

        # Enabled plugins can promote named subtrees of their own config
        # (e.g. RTVRTM's "rtv"/"rtm") to top-level Config sections instead
        # of everything living nested inside the generic Plugins card -
        # see plugin_loader.call_web_config_sections(). Each promoted
        # subtree is excluded from that plugin's own card below so it
        # isn't editable in two places at once. An entry can either hand
        # back explicit "fields" (typed via formify.describe_field_spec -
        # toggles instead of bare 0/1, a 0-100 rate, a maps picker, fields
        # that grey out when another one's off, ...) or just a "path" to
        # auto-describe the whole subtree the same way the Config page
        # always has, for a plugin that doesn't need the extra control.
        promoted_keys_by_plugin = {}
        hidden_plugin_cards = set()
        plugin_sections = []
        for plugin_name in (config_dict.get('plugins') or {}).keys():
            declared = plugin_loader.call_web_config_sections(plugin_name, instance, config_dict)
            promoted = set()
            for entry in declared:
                path = entry.get('path') or []
                # An empty path means "this whole plugin is one flat
                # section" - for a plugin whose config has no natural
                # subtree to nest under (e.g. auto_map_rotation's single
                # "rotation_minutes"), rather than forcing an artificial
                # one-key wrapper just to have a "path".
                if path:
                    promoted.add(path[0])
                elif not entry.get('fields'):
                    continue  # nothing to auto-describe without a subtree or explicit fields

                abs_ancestor_keys = ['plugins', plugin_name] + path[:-1]
                section_key = path[-1] if path else plugin_name

                if entry.get('fields'):
                    children = [
                        formify.describe_field_spec(field_spec, config_dict, plugin_name)
                        for field_spec in entry['fields']
                    ]
                    node = {
                        'path': '.'.join(abs_ancestor_keys + [section_key]) if path else '.'.join(['plugins', plugin_name]),
                        'key': section_key,
                        'kind': 'group',
                        'children': children,
                        'field_count': len(children),
                    }
                else:
                    value = config_dict
                    for k in ['plugins', plugin_name] + path:
                        value = (value or {}).get(k) if isinstance(value, dict) else None
                    node = formify.describe(value or {}, path[-1], abs_ancestor_keys)

                node['label'] = entry.get('label') or node.get('label') or section_key
                node['section_hint'] = entry.get('hint') or (
                    plugin_loader.get_plugin_requirements(plugin_name)['description']
                    if not any(p.get('plugin') == plugin_name for p in plugin_sections) else None)
                node['plugin'] = plugin_name
                plugin_sections.append(node)
            promoted_keys_by_plugin[plugin_name] = promoted

            if plugin_loader.call_web_hide_default_card(plugin_name):
                hidden_plugin_cards.add(plugin_name)

        self.controller_bag['plugin_sections'] = plugin_sections

        # The RTVRTM plugin's holiday map periods are folded into the Maps
        # section (with a button to inject a holiday's maps into the
        # rotation) rather than shown a third time inside its Plugins card.
        promoted_keys_by_plugin.setdefault('rtvrtm', set()).add('holiday_maps')

        all_plugin_names = plugin_loader.discover_plugin_names()
        plugin_meta = {name: dict(plugin_loader.get_plugin_meta(name), **plugin_loader.get_plugin_requirements(name))
                       for name in all_plugin_names}

        config_dict_for_cards = copy.deepcopy(config_dict)
        for plugin_name, promoted in promoted_keys_by_plugin.items():
            plugin_cfg = (config_dict_for_cards.get('plugins') or {}).get(plugin_name)
            if isinstance(plugin_cfg, dict):
                for key in promoted:
                    plugin_cfg.pop(key, None)

        self.controller_bag['plugin_cards'] = formify.describe_plugins(
            config_dict_for_cards, all_plugin_names, plugin_meta
        )
        for card in self.controller_bag['plugin_cards']:
            card['hide_body'] = card['name'] in hidden_plugin_cards

        self.controller_bag['rotation_node'] = formify.describe(
            config_dict.get('map_rotation_order') or [], 'map_rotation_order', []
        )

        rtvrtm_enabled = 'rtvrtm' in (config_dict.get('plugins') or {})
        self.controller_bag['rtvrtm_enabled'] = rtvrtm_enabled
        if rtvrtm_enabled:
            rtvrtm_cfg = (config_dict.get('plugins') or {}).get('rtvrtm') or {}
            holiday_maps_node = formify.describe(
                rtvrtm_cfg.get('holiday_maps') or {}, 'holiday_maps', ['plugins', 'rtvrtm']
            )
            self.controller_bag['holidays'] = holiday_maps_node.get('children', [])

        self.controller_bag['maps_catalog'] = maps_catalog.get_maps()

    @staticmethod
    def plugins_page(instance):
        """The per-instance Plugins page: every plugin on disk, grouped, with
        whether it's on here and what it needs."""
        from mbiiez.api.paths import config_path
        path = config_path(instance)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        cfg = json.loads(content)
        enabled = (cfg.get("plugins") or {}).keys()
        names = plugin_loader.discover_plugin_names()
        meta = {}
        cards = {}
        for name in names:
            m = dict(plugin_loader.get_plugin_meta(name), **plugin_loader.get_plugin_requirements(name))
            meta[name] = {"label": m.get("plugin_name", name), "requires": m["requires"], "engine": m["engine"] or ""}
            cards[name] = {"name": name, "label": meta[name]["label"], "enabled": name in enabled,
                           "description": m["description"], "engine": m["engine"] or "",
                           "requires": [{"name": r, "label": plugin_loader.get_plugin_meta(r).get("plugin_name", r)} for r in m["requires"]],
                           "uses": [{"name": r, "label": plugin_loader.get_plugin_meta(r).get("plugin_name", r)} for r in m["uses"]]}
        groups, placed = [], set()
        for title, members in plugin_loader.PLUGIN_GROUPS:
            group = [cards[n] for n in members if n in cards]
            placed.update(c["name"] for c in group)
            if group:
                groups.append({"title": title, "cards": group})
        rest = [cards[n] for n in names if n not in placed]
        if rest:
            groups.append({"title": "Other", "cards": rest})
        engine = (cfg.get("server") or {}).get("engine", "")
        return {"instance": instance, "groups": groups, "meta": meta, "config_content": content,
                "engine": engine, "engine_description": plugin_loader.engine_description(engine)}

    def _get_config_path(self, instance):
        from mbiiez.api.paths import config_path
        return config_path(instance)

    @staticmethod
    def save_config(instance, content):
        # Validate JSON before saving
        try:
            if not isinstance(json.loads(content), dict):
                return False, "Config must be a JSON object"
        except Exception as e:
            return False, str(e)
        from mbiiez.api.paths import config_path as checked_path
        from mbiiez.api.storage import locked, write
        config_path = checked_path(instance)
        with locked(config_path):
            write(config_path, json.loads(content))
        return True, 'Saved successfully.'

    @staticmethod
    def sync_smod_admins(source_instance, admin_keys, target_instances):
        # Copies one or more smod admin slots' password + rights straight
        # from the source instance's config file on disk to the same
        # slot(s) in each target instance's file, so a server owner can
        # set an admin's password/rights once (or set up every SMOD
        # account at once) and push it out to other instances instead of
        # retyping it into each config by hand. Used by both the
        # per-admin "Sync to instances..." button (one admin_key) and the
        # "Sync all admins..." button (every smod.admin_N key at once).
        # Reads/writes the files directly (not through the browser's own-
        # config reconstruction used by /config/save) since this touches
        # configs other than the one currently open in the form.
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../configs'))

        from mbiiez.api.paths import config_path as checked_path
        source_path = checked_path(source_instance)
        for target in target_instances:
            checked_path(target)
        if not os.path.exists(source_path):
            return False, f'Source instance "{source_instance}" not found.'
        with open(source_path, 'r', encoding='utf-8') as f:
            try:
                source_cfg = json.load(f)
            except Exception as e:
                return False, f'Source instance "{source_instance}" config is not valid JSON: {e}'

        source_smod = source_cfg.get('smod') or {}
        admin_cfgs = {}
        missing = []
        for admin_key in admin_keys:
            if admin_key in source_smod:
                admin_cfgs[admin_key] = source_smod[admin_key]
            else:
                missing.append(admin_key)

        if not admin_cfgs:
            return False, f'None of the requested admin slot(s) were found in {source_instance}\'s smod config.'

        updated = []
        errors = []
        for target in target_instances:
            if target == source_instance:
                continue
            target_path = os.path.join(base, f'{target}.json')
            if not os.path.exists(target_path):
                errors.append(f'{target}: config file not found')
                continue
            try:
                with open(target_path, 'r', encoding='utf-8') as f:
                    target_cfg = json.load(f)
            except Exception as e:
                errors.append(f'{target}: {e}')
                continue

            target_smod = target_cfg.setdefault('smod', {})
            for admin_key, admin_cfg in admin_cfgs.items():
                target_smod[admin_key] = json.loads(json.dumps(admin_cfg))
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(target_cfg, f, indent=4)
            updated.append(target)

        if not updated:
            return False, 'No instances were updated. ' + '; '.join(errors)

        label = list(admin_cfgs.keys())[0] if len(admin_cfgs) == 1 else f'{len(admin_cfgs)} admin slots'
        msg = f'Applied {label} to: {", ".join(updated)}.'
        if missing:
            msg += f' (not in {source_instance}, skipped: {", ".join(missing)})'
        if errors:
            msg += ' Failed: ' + '; '.join(errors)
        return True, msg
