"""Explicit CADED snapshot merge. Engine locks, bounded records and no destructive replacement."""
import contextlib
import copy
import fcntl
import functools
import tempfile
import json
import ipaddress
import os
from pathlib import Path
import re
import time
import uuid
import psutil
from mbiiez import settings
from .paths import config_path
from .storage import state_dir, write

FORMATS = {
    'accounts': ('economy_accounts.dat', ' ', 1024),
    'stats': ('player_stats.dat', '|', 4096),
    'guid_bans': ('guidbans.txt', '\t', 1024),
    'ip_bans': ('banlist.json', None, 4096),
}
MAX_BYTES = 1500 * 1024
MARKER = b'MBIIEZ_STATS_TRANSACTION_V1'


@functools.lru_cache(maxsize=256)
def engine_stats_marker(pid, created):
    with open(f'/proc/{pid}/exe', 'rb') as stream:
        return MARKER in stream.read(32 * 1024 * 1024)


def capabilities():
    configs = Path(settings.locations.config_path)
    caded = []
    for file in sorted(configs.glob('*.json')):
        with open(config_path(file.stem)) as stream:
            if json.load(stream).get('server', {}).get('engine') == 'caded.i386':
                caded.append(file.stem)
    safe_stats = True
    # Inspect the binary mapped by each process, rather than the newly installed path.
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] == 'caded.i386':
                safe_stats = safe_stats and engine_stats_marker(proc.pid, proc.create_time())
        except (psutil.NoSuchProcess, FileNotFoundError):
            continue
        except (PermissionError, psutil.AccessDenied):
            safe_stats = False
    return {'protocol': 1, 'caded_instances': caded, 'datasets': list(FORMATS) if caded else ['ip_bans'],
            'live_stats_safe': safe_stats,
            'stats_note': '' if safe_stats else 'Live stats import requires the new CADED transaction build at the next planned game restart.'}


def selected(datasets):
    if not isinstance(datasets, list) or not datasets or len(datasets) != len(set(datasets)):
        raise ValueError('Select at least one dataset, without duplicates')
    if any(name not in FORMATS for name in datasets):
        raise ValueError('Unsupported sync dataset')
    if any(name != 'ip_bans' for name in datasets) and not capabilities()['caded_instances']:
        raise ValueError('This node has no configured CADED instances')
    return datasets


def number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or not re.fullmatch(r'\d+', str(value)):
        raise ValueError('Invalid sync counter')
    value = int(value)
    if value > 2147483647:
        raise ValueError('Sync counter exceeds engine range')
    return value


def text(value, limit, native=False):
    if not isinstance(value, str) or len(value.encode('latin-1' if native else 'utf-8')) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid sync text field')
    return value


def validate(name, records):
    if not isinstance(records, list) or len(records) > FORMATS[name][2]:
        raise ValueError('Sync dataset exceeds engine record limit')
    normalized = {}
    for row in records:
        if name == 'ip_bans':
            from mbiiez.bansync import valid_ip
            if not isinstance(row, dict) or not valid_ip(row.get('ip')):
                raise ValueError('Invalid IP ban record')
            key = row['ip']
            item = {'ip': key, 'note': text(row.get('note', ''), 200),
                    'added': number(row.get('added', 0)), 'by': text(row.get('by', ''), 100)}
        else:
            width = {'accounts': 6, 'stats': 5, 'guid_bans': 8}[name]
            if not isinstance(row, list) or len(row) != width:
                raise ValueError('Invalid sync record width')
            item = list(row)
            if name == 'accounts':
                if not isinstance(item[0], str) or not re.fullmatch(r'[A-Za-z0-9_]{1,23}', item[0]):
                    raise ValueError('Invalid account handle')
                if any(not isinstance(v, str) or not re.fullmatch(r'[a-fA-F0-9]{32}', v) for v in item[1:3]):
                    raise ValueError('Invalid account credential encoding')
                item[3:] = [number(v) for v in item[3:]]
            elif name == 'stats':
                text(item[0], 39, native=True)
                if not item[0] or '|' in item[0]:
                    raise ValueError('Invalid stats key')
                item[1:] = [number(v) for v in item[1:]]
            else:
                from mbiiez.guidbans import valid_guid
                if not valid_guid(item[0]):
                    raise ValueError('Invalid GUID ban')
                item[0] = item[0].upper()
                for index in [1, 2, 5]: item[index] = number(item[index])
                for index, limit in [(3, 63), (4, 47), (6, 47), (7, 200)]: text(item[index], limit, native=True)
            key = item[0].translate(str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))
        if key in normalized:
            raise ValueError('Duplicate identity in sync dataset')
        normalized[key] = item
    return normalized


@contextlib.contextmanager
def engine_file(name, writable=False):
    filename = FORMATS[name][0]
    path = Path(settings.locations.mbii_path) / filename
    if path.is_symlink():
        raise ValueError('Sync data files cannot be symlinks')
    separate_lock = name in ('guid_bans', 'ip_bans')
    lock_path = Path(str(path) + '.lock') if separate_lock else path
    flags = os.O_RDWR | os.O_CREAT if writable or separate_lock else os.O_RDONLY
    try:
        fd = os.open(lock_path, flags | os.O_NOFOLLOW, 0o600)
    except FileNotFoundError:
        yield None, '', path
        return
    encoding = 'utf-8' if name == 'ip_bans' else 'latin-1'
    with os.fdopen(fd, 'r+' if writable or separate_lock else 'r', encoding=encoding) as locked:
        # Bound contention: a sync request must not stall game threads indefinitely.
        deadline = time.monotonic() + 2
        while True:
            try:
                fcntl.flock(locked.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ValueError('Game data is busy; retry sync shortly')
                time.sleep(.01)
        if separate_lock:
            try:
                with open(path, encoding=encoding) as data:
                    content = data.read(MAX_BYTES + 1)
            except FileNotFoundError:
                content = ''
        else:
            content = locked.read(MAX_BYTES + 1)
        if len(content.encode(encoding)) > MAX_BYTES:
            raise ValueError('Sync file exceeds size limit')
        yield locked, content, path


def decode(name, content):
    if name == 'ip_bans':
        document = json.loads(content or '{}')
        return validate(name, [dict(ip=ip, **info) for ip, info in document.get('bans', {}).items()]), document
    delimiter = FORMATS[name][1]
    rows = [line.split() if name == 'accounts' else line.split(delimiter)
            for line in content.splitlines() if line and not line.startswith('#')]
    return validate(name, rows), None


def encode(name, records, document):
    if name == 'ip_bans':
        document = copy.deepcopy(document or {})
        document['bans'] = {key: {k: v for k, v in row.items() if k != 'ip'} for key, row in records.items()}
        document.setdefault('seen', {})
        return json.dumps(document, indent=2, sort_keys=True) + '\n'
    delimiter = FORMATS[name][1]
    return ''.join(delimiter.join(str(v) for v in row) + '\n' for row in records.values())


def guid_links(content, allowed=None, days=30):
    links = {}
    for line in content.splitlines():
        row = line.split('\t', 3)
        if len(row) != 4:
            raise ValueError('Invalid GUID link record')
        ipaddress.ip_address(row[0])
        from mbiiez.guidbans import valid_guid
        if not valid_guid(row[1]):
            raise ValueError('Invalid linked GUID')
        row[1] = row[1].upper()
        row[2] = number(row[2]); text(row[3], 63, native=True)
        if row[2] > time.time() + 300:
            raise ValueError('GUID link timestamp is in the future')
        if allowed is not None and row[1].lower() not in allowed:
            raise ValueError('GUID links must belong to exported bans')
        if row[2] >= time.time() - days * 86400:
            key = (row[0], row[1])
            if key not in links or links[key][2] < row[2]: links[key] = row
    if len(links) > 16384:
        raise ValueError('GUID link limit exceeded')
    return links


def seen_text():
    path = Path(settings.locations.mbii_path) / 'guidseen.txt'
    if path.is_symlink():
        raise ValueError('GUID link file cannot be a symlink')
    try:
        with path.open(encoding='latin-1') as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content.encode('latin-1')) > MAX_BYTES:
            raise ValueError('GUID link file exceeds size limit')
        return content
    except FileNotFoundError:
        return ''


def export(datasets):
    datasets = selected(datasets)
    result = {'protocol': 1, 'datasets': {}}
    for name in datasets:
        with engine_file(name) as (_, content, _):
            records, _ = decode(name, content)
            result['datasets'][name] = list(records.values())
            if name == 'guid_bans':
                links = guid_links(seen_text())
                result['guid_links'] = [row for row in links.values() if row[1].lower() in records and row[2] >= time.time() - 7 * 86400]
    if len(json.dumps(result).encode()) > MAX_BYTES:
        raise ValueError('Combined snapshot too large; sync fewer datasets at a time')
    return result


def merge(name, local, incoming):
    merged = copy.deepcopy(local)
    summary = {'added': 0, 'updated': 0, 'unchanged': 0, 'conflicts': 0}
    for key, row in incoming.items():
        if key not in merged:
            merged[key] = row
            summary['added'] += 1
        elif name == 'accounts':
            # Never overwrite a live balance, PIN, lockout or privilege.
            summary['conflicts' if merged[key][1:3] != row[1:3] else 'unchanged'] += 1
        elif name == 'stats':
            before = merged[key]
            merged[key] = [before[0]] + [max(a, b) for a, b in zip(before[1:], row[1:])]
            summary['updated' if before != merged[key] else 'unchanged'] += 1
        else:
            # Ban merge is additive; local notes, drop history and metadata win.
            summary['unchanged'] += 1
    if len(merged) > FORMATS[name][2]:
        raise ValueError('Merged dataset exceeds engine record limit')
    return merged, summary


def import_snapshot(snapshot, preview=True):
    if not isinstance(preview, bool) or not isinstance(snapshot, dict) or snapshot.get('protocol') != 1:
        raise ValueError('Invalid sync protocol')
    datasets = snapshot.get('datasets')
    if not isinstance(datasets, dict):
        raise ValueError('Invalid sync datasets')
    selected(list(datasets))
    # Validate the entire payload before mutating any file.
    incoming = {name: validate(name, rows) for name, rows in datasets.items()}
    links = snapshot.get('guid_links', [])
    if not isinstance(links, list) or len(links) > 16384:
        raise ValueError('Invalid GUID link snapshot')
    if links and 'guid_bans' not in incoming:
        raise ValueError('GUID links require GUID bans')
    for row in links:
        if not isinstance(row, list) or len(row) != 4:
            raise ValueError('Invalid GUID link snapshot')
        text(row[0], 47); text(row[1], 63); number(row[2]); text(row[3], 63, native=True)
    incoming_links = guid_links(''.join('\t'.join(str(v) for v in row) + '\n' for row in links), incoming.get('guid_bans', {}), days=7)
    result = {'preview': preview, 'datasets': {}, 'backup_id': None}
    backup_id = uuid.uuid4().hex
    for name, records in incoming.items():
        if name == 'stats' and not capabilities()['live_stats_safe']:
            result['datasets'][name] = {'blocked': True, 'reason': capabilities()['stats_note']}
            continue
        with engine_file(name, writable=not preview) as (handle, content, path):
            local, document = decode(name, content)
            merged, summary = merge(name, local, records)
            result['datasets'][name] = summary
            merged_links = None
            if name == 'guid_bans':
                existing_seen = seen_text()
                merged_links = guid_links(existing_seen)
                link_changes = 0
                for key, row in incoming_links.items():
                    if key not in merged_links or merged_links[key][2] < row[2]:
                        merged_links[key] = row
                        link_changes += 1
                if len(merged_links) > 16384:
                    raise ValueError('Merged GUID links exceed engine limit')
                summary['links_updated'] = link_changes
                if not preview and link_changes:
                    write(state_dir() / 'sync_backups' / backup_id / 'guidseen.txt.json', {'content': existing_seen, 'encoding': 'latin-1'})
                    path_seen = Path(settings.locations.mbii_path) / 'guidseen.txt'
                    fd, temporary = tempfile.mkstemp(dir=path_seen.parent)
                    try:
                        with os.fdopen(fd, 'w', encoding='latin-1') as stream:
                            stream.write(''.join('\t'.join(str(v) for v in row) + '\n' for row in merged_links.values()))
                            stream.flush(); os.fsync(stream.fileno())
                        os.replace(temporary, path_seen)
                    finally:
                        if os.path.exists(temporary): os.unlink(temporary)
                    result['backup_id'] = backup_id
            if preview or not (summary['added'] or summary['updated']):
                continue
            # Private pre-change backup, before in-place writes matching the engine's inode lock.
            write(state_dir() / 'sync_backups' / backup_id / (FORMATS[name][0] + '.json'), {'content': content, 'encoding': 'utf-8' if name == 'ip_bans' else 'latin-1'})
            encoded = encode(name, merged, document)
            encoding = 'utf-8' if name == 'ip_bans' else 'latin-1'
            if len(encoded.encode(encoding)) > MAX_BYTES:
                raise ValueError('Merged sync file too large')
            if name in ('guid_bans', 'ip_bans'):
                with open(path, 'w', encoding=encoding) as stream:
                    os.chmod(path, 0o600)
                    stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            else:
                os.fchmod(handle.fileno(), 0o600)
                handle.seek(0); handle.write(encoded); handle.truncate()
                handle.flush(); os.fsync(handle.fileno())
            result['backup_id'] = backup_id
    if not preview and result['datasets'].get('ip_bans', {}).get('added'):
        from mbiiez import bansync
        bansync.sync()  # Existing RCON propagation; never a game restart.
    return result
