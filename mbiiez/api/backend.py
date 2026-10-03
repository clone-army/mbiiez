"""Explicit operations used by the API. No arbitrary Python method dispatch."""
from contextlib import closing
import importlib
import json
import os
import subprocess
import sys
import threading
from .paths import config_path, names

# These controllers describe server-side data; only the web process renders pages.
VIEWS = {'dashboard': 'viewer', 'instance': 'viewer', 'logs': 'viewer',
         'chat': 'viewer', 'players': 'viewer', 'stats': 'viewer',
         'mod': 'mod', 'rcon': 'admin', 'config': 'admin', 'plugin_page': 'admin'}
ACTIONS = {
    'config.save_config': 'admin', 'config.sync_smod_admins': 'admin',
    'config.plugins_page': 'admin', 'chat.send_message': 'mod',
    'rcon.send_rcon': 'admin', 'mod.change_map': 'mod', 'mod.change_mode': 'mod',
    'mod.kick_player': 'mod', 'mod.tell_player': 'mod', 'mod.run_plugin_action': 'mod',
    'plugin_page.global_page': 'admin', 'plugin_page.run_global_action': 'admin',
    'plugin_page.run_action': 'admin',
    'instance_admin.wizard_bag': 'admin', 'instance_admin.create_instance': 'admin',
    'instance_admin.delete_instance': 'admin', 'instance_admin.is_running': 'viewer',
    'bansync.list_bans': 'mod', 'bansync.add_ban': 'mod', 'bansync.remove_ban': 'mod',
    'bansync.set_note': 'mod', 'guidbans.list_bans': 'mod', 'guidbans.add_ban': 'mod',
    'guidbans.remove_ban': 'mod', 'guidbans.set_note': 'mod',
}
view_lock = threading.RLock()


def controller(name):
    return importlib.import_module('mbiiez.web.controllers.' + name).controller


def validate_optional(name):
    if name and str(name).lower() != 'all':
        config_path(name)


def view(name, args):
    if name not in VIEWS:
        raise ValueError('Unknown view')
    if name not in ('dashboard', 'players') and args:
        validate_optional(args[0])
    if name == 'logs':
        args = list(args)
        args[1:3] = [max(1, int(args[1] or 1)) if len(args) > 1 else 1,
                     min(500, max(1, int(args[2] or 100))) if len(args) > 2 else 100]
    with view_lock:
        return controller(name)(*args).controller_bag


def action(name, args):
    if name not in ACTIONS:
        raise ValueError('Unknown action')
    module, method = name.split('.')
    if module in ('config', 'chat', 'rcon', 'mod') and args:
        config_path(args[0])
    if name == 'config.sync_smod_admins':
        for target in args[2]:
            config_path(target)
    if module == 'plugin_page' and method in ('run_action',):
        config_path(args[0])
    if module == 'instance_admin' and method in ('delete_instance', 'is_running'):
        config_path(args[0])
    if module in ('bansync', 'guidbans'):
        obj = importlib.import_module('mbiiez.' + module)
    elif module == 'instance_admin':
        obj = importlib.import_module('mbiiez.web.controllers.instance_admin')
    else:
        obj = controller(module)
    with view_lock:
        return getattr(obj, method)(*args)


def menus():
    from mbiiez import plugin_loader
    from mbiiez.web.controllers.plugin_page import all_instance_configs
    configs = all_instance_configs()
    return {'instances': names(), 'global': plugin_loader.global_menus(configs),
            'plugins': {name: [entry for plugin in (cfg.get('plugins') or {})
                               if (entry := plugin_loader.call_web_menu(plugin, name, cfg))]
                        for name, cfg in configs.items()}}


def runtime(name):
    config_path(name)
    from mbiiez.instance import instance
    return instance(name)


def status(name):
    return runtime(name).status()


def launch(name, command, force=False):
    from mbiiez import settings
    config_path(name)
    if command not in ('start', 'stop', 'restart'):
        raise ValueError('Unknown command')
    # Refuse occupied instances unless the caller explicitly requests force.
    if command != 'start' and not force:
        if runtime(name).players_count() > 0:
            raise ValueError('Players are online; explicit force is required')
    argv = [sys.executable, os.path.join(settings.globals.script_path, 'mbii.py'),
            '-i', name, command]
    if force:
        argv.append('--force')
    if os.environ.get('MBIIEZ_CONTAINER') != '1':
        # A transient service has its own cgroup, independent of the API process.
        subprocess.run(['systemd-run', '--quiet', '--collect', '--no-block',
                        '--property=WorkingDirectory=' + settings.globals.script_path,
                        '--property=KillMode=process', '--'] + argv,
                       check=True, capture_output=True, timeout=10)
    else:
        # Container PID 1 (supervisord) keeps game processes when API workers restart.
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         cwd=settings.globals.script_path)
    return {'output': f'{name}: {command} queued', 'async': True}


def rows(kind, instance=None, limit=100, search='', tag=None):
    from mbiiez.db import db
    validate_optional(instance)
    limit = min(500, max(1, int(limit)))
    where, params = [], []
    if instance and instance.lower() != 'all':
        where.append('LOWER(instance) = LOWER(?)')
        params.append(instance)
    if kind == 'logs':
        if search:
            where.append('log LIKE ?'); params.append('%' + search + '%')
        tags = {'SMOD': "(log LIKE '%SMOD command%' OR log LIKE '%SMOD say:%')",
                'ClientConnect': "log LIKE '%ClientConnect%'",
                'Exception': "(log LIKE 'Exception%' OR log LIKE 'Error%')"}
        if tag in tags:
            where.append(tags[tag])
    table = {'logs': 'logs', 'chat': 'chatter'}[kind]
    query = 'SELECT * FROM ' + table + (' WHERE ' + ' AND '.join(where) if where else '')
    with closing(db().connect()) as conn:
        result = conn.execute(query + ' ORDER BY added DESC LIMIT ?', params + [limit]).fetchall()
    if kind == 'chat':
        return list(reversed(result))
    return [{'log_line': row.get('log', row.get('log_line', '')), 'added': row['added']} for row in result]
