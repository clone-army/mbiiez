"""One elected WEB worker shares opt-in node data every minute; API agents own files."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import logging
import os
import threading
import time
from mbiiez.api.client import Client, nodes, is_local_node
from mbiiez.api.storage import state_dir, locked, read, write
from mbiiez.api.sync import FORMATS, validate, merge, MAX_BYTES

INTERVAL = 60
log = logging.getLogger('mbiiez.web.sync')
_started = False


def settings_path():
    return state_dir() / 'automatic_sync.json'


def settings():
    default = {'nodes': {identifier: {'enabled': True, 'url': node['url']}
                         for identifier, node in nodes().items() if is_local_node(node)}}
    return read(settings_path(), default)


def configure(identifier, enabled):
    if not isinstance(enabled, bool) or identifier not in nodes():
        raise ValueError('Choose an existing node and a boolean sync setting')
    if enabled:
        info = Client(identifier).call('GET', 'sync/info')
        if not info.get('automatic_sync'):
            raise ValueError('Update this API agent to support automatic sync')
        if not info.get('caded_instances'):
            raise ValueError('Sync CADED data requires a configured CADED instance')
    with locked(settings_path()):
        data = settings()
        data['nodes'][identifier] = {'enabled': enabled, 'url': nodes()[identifier]['url']}
        write(settings_path(), data)
    return data['nodes'][identifier]


def status():
    return read(state_dir() / 'automatic_sync_status.json', {})


def aggregate(snapshots):
    merged = {name: {} for name in FORMATS}
    links = {}
    for snapshot in snapshots:
        if snapshot.get('protocol') != 1:
            raise ValueError('Unsupported sync protocol')
        for name, rows in snapshot['datasets'].items():
            incoming = validate(name, rows)
            previous = merged[name]
            merged[name], _ = merge(name, previous, incoming)
            if name in ('guid_bans', 'ip_bans'):
                added = lambda row: row[5] if name == 'guid_bans' else row['added']
                for key, row in incoming.items():
                    if key in previous and added(row) > added(previous[key]): merged[name][key] = row
        for row in snapshot.get('guid_links', []):
            key = (row[0], row[1].upper())
            if key not in links or row[2] > links[key][2]: links[key] = row
    return {name: {'protocol': 1, 'datasets': {name: list(rows.values())},
                   **({'guid_links': list(links.values())} if name == 'guid_bans' else {})}
            for name, rows in merged.items()}


def automatic_client(identifier):
    return Client(identifier, actor="automatic-sync")


def cycle(client_factory=automatic_client):
    configured = nodes()
    policy = settings()['nodes']
    enrolled = {identifier: node for identifier, node in configured.items()
                if policy.get(identifier, {}).get('enabled') and policy[identifier]['url'] == node['url']}
    result = {'checked_at': time.time(), 'nodes': {}, 'interval': INTERVAL}
    for identifier, entry in policy.items():
        if entry.get('enabled') and identifier in configured and entry['url'] != configured[identifier]['url']:
            result['nodes'][identifier] = {'error': 'API URL changed; disable and re-enable sync to approve the new destination.'}
    if len(enrolled) < 2:
        for identifier in enrolled:
            result['nodes'][identifier] = {'waiting': 'Enable Sync CADED data on another node.'}
        write(state_dir() / 'automatic_sync_status.json', result)
        return result

    def collect(identifier):
        client = client_factory(identifier)
        info = client.call('GET', 'sync/info')
        if not info.get('automatic_sync') or not info.get('caded_instances'):
            raise ValueError('Update this agent and configure a CADED instance')
        # Keep each request bounded, even when combined datasets exceed the API body limit.
        snapshot = {'protocol': 1, 'datasets': {}, 'guid_links': []}
        for name in FORMATS:
            part = client.call('POST', 'sync/export', {'datasets': [name]})
            snapshot['datasets'].update(part['datasets'])
            snapshot['guid_links'].extend(part.get('guid_links', []))
        return snapshot

    available = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {identifier: pool.submit(collect, identifier) for identifier in enrolled}
        for identifier, future in pending.items():
            try:
                available[identifier] = future.result()
            except Exception as error:
                result['nodes'][identifier] = {'error': str(error)}
    if len(available) >= 2:
        snapshots = aggregate(available.values())
        if any(len(json.dumps(snapshot).encode()) > MAX_BYTES for snapshot in snapshots.values()):
            raise ValueError('Shared dataset exceeds the API size limit')

        def apply(identifier):
            # Honor a switch-off or URL edit that happened during export collection.
            current = settings()['nodes'].get(identifier, {})
            if not current.get('enabled') or current['url'] != nodes().get(identifier, {}).get('url'):
                return {'waiting': 'Sync disabled or destination changed.'}
            reports = {}
            for name, snapshot in snapshots.items():
                report = client_factory(identifier).call('POST', 'sync/import', {'snapshot': snapshot, 'preview': False, 'automatic': True})
                reports.update(report['datasets'])
            return {'last_success': time.time(), 'datasets': reports}

        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = {identifier: pool.submit(apply, identifier) for identifier in available}
            for identifier, future in pending.items():
                try:
                    result['nodes'][identifier] = future.result()
                except Exception as error:
                    result['nodes'][identifier] = {'error': str(error)}
    else:
        for identifier in available:
            result['nodes'][identifier] = {'waiting': 'Waiting for another enabled node to come online.'}
    previous = status().get('nodes', {})
    for identifier, report in result['nodes'].items():
        if 'last_success' not in report and previous.get(identifier, {}).get('last_success'):
            report['last_success'] = previous[identifier]['last_success']
    write(state_dir() / 'automatic_sync_status.json', result)
    return result


def start():
    global _started
    if _started: return
    _started = True

    def loop():
        path = state_dir() / 'automatic_sync_worker.lock'
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with os.fdopen(os.open(path, os.O_CREAT | os.O_RDWR, 0o600), 'w') as stream:
            while True:
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(5)
            while True:
                began = time.monotonic()
                try:
                    cycle()
                except Exception as error:
                    log.exception('Automatic CADED sync failed')
                    write(state_dir() / 'automatic_sync_status.json', {'checked_at': time.time(), 'error': str(error), 'nodes': {}})
                time.sleep(max(1, INTERVAL - (time.monotonic() - began)))

    threading.Thread(target=loop, name='caded-sync', daemon=True).start()
