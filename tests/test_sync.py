import fcntl
import importlib.util
import json
import os
from pathlib import Path
import time
import pytest
from mbiiez import settings
from mbiiez.api import sync, keys
from mbiiez.api.server import create_app


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setenv('MBIIEZ_STATE_DIR', str(tmp_path / 'state'))
    configs = tmp_path / 'configs'; configs.mkdir()
    (configs / 'legends.json').write_text(json.dumps({'server': {'engine': 'caded.i386'}}))
    data = tmp_path / 'MBII'; data.mkdir()
    monkeypatch.setattr(settings.locations, 'config_path', str(configs))
    monkeypatch.setattr(settings.locations, 'mbii_path', str(data))
    monkeypatch.setattr(sync.psutil, 'process_iter', lambda fields, **kwargs: [])
    return data


def account(handle='Player', salt='a', credits=100):
    return [handle, salt * 32, 'b' * 32, credits, 0, 0]


def snapshot(**datasets):
    return {'protocol': 1, 'datasets': datasets}


def test_preview_and_idempotent_accounts(game):
    file = game / 'economy_accounts.dat'
    original = ' '.join(str(v) for v in account()) + '\n'
    file.write_text(original)
    incoming = snapshot(accounts=[account('Player', 'c', 900), account('NewPlayer', credits=50)])
    report = sync.import_snapshot(incoming)
    assert report['datasets']['accounts']['conflicts'] == 1
    assert report['datasets']['accounts']['added'] == 1
    assert file.read_text() == original
    report = sync.import_snapshot(incoming, preview=False)
    assert report['backup_id']
    rows = sync.export(['accounts'])['datasets']['accounts']
    assert rows[0] == account() and rows[1] == account('NewPlayer', credits=50)
    repeat = sync.import_snapshot(incoming, preview=False)
    assert repeat['datasets']['accounts']['added'] == 0
    assert not repeat['backup_id']
    backup = Path(os.environ['MBIIEZ_STATE_DIR']) / 'sync_backups' / report['backup_id'] / 'economy_accounts.dat.json'
    assert json.loads(backup.read_text())['content'] == original
    assert backup.stat().st_mode & 0o777 == 0o600


def test_stats_maxima_and_live_engine_gate(game, monkeypatch):
    (game / 'player_stats.dat').write_text('h:Player|10|3|0|100\n')
    incoming = snapshot(stats=[['h:player', 8, 5, 1, 90]])
    sync.import_snapshot(incoming, preview=False)
    assert (game / 'player_stats.dat').read_text() == 'h:Player|10|5|1|100\n'
    assert sync.import_snapshot(incoming, preview=False)['datasets']['stats']['updated'] == 0
    real = sync.capabilities
    monkeypatch.setattr(sync, 'capabilities', lambda: {**real(), 'live_stats_safe': False, 'stats_note': 'Old engine'})
    report = sync.import_snapshot(snapshot(stats=[['h:Player', 99, 99, 99, 999]]), preview=False)
    assert report['datasets']['stats']['blocked']
    assert (game / 'player_stats.dat').read_text() == 'h:Player|10|5|1|100\n'


def test_guid_ban_link_history_and_metadata(game):
    guid = 'A' * 32
    other = 'B' * 32
    now = int(time.time())
    old_seen = now - 14 * 86400
    (game / 'guidbans.txt').write_text(f'{guid}\t5\t{now}\tLocal\t1.2.3.4\t{now}\t\tlocal note\n')
    (game / 'guidseen.txt').write_text(f'2.3.4.5\t{other}\t{old_seen}\tKeepLocalHistory\n')
    incoming = snapshot(guid_bans=[[guid, 1, 0, 'Remote', '1.2.3.4', now, '', 'remote note']])
    incoming['guid_links'] = [['1.2.3.4', guid, now, 'Remote']]
    report = sync.import_snapshot(incoming)
    assert report['datasets']['guid_bans']['links_updated'] == 1
    assert 'Remote' not in (game / 'guidseen.txt').read_text()
    sync.import_snapshot(incoming, preview=False)
    assert 'local note' in (game / 'guidbans.txt').read_text()
    assert 'KeepLocalHistory' in (game / 'guidseen.txt').read_text()
    assert guid in (game / 'guidseen.txt').read_text()
    exported = sync.export(['guid_bans'])
    assert exported['guid_links'] == incoming['guid_links']
    assert sync.import_snapshot(incoming, preview=False)['datasets']['guid_bans']['links_updated'] == 0


def test_ip_bans_keep_local_notes_and_instance_tracking(game, monkeypatch):
    from mbiiez import bansync
    calls = []
    monkeypatch.setattr(bansync, 'sync', lambda: calls.append('propagated'))
    (game / 'banlist.json').write_text(json.dumps({'bans': {'1.2.3.4': {'added': 1, 'by': 'local', 'note': 'keep'}}, 'seen': {'legends': ['1.2.3.4']}}))
    incoming = snapshot(ip_bans=[{'ip': '2.3.4.5', 'note': 'remote', 'added': 2, 'by': 'admin'}])
    sync.import_snapshot(incoming, preview=False)
    data = json.loads((game / 'banlist.json').read_text())
    assert data['seen'] == {'legends': ['1.2.3.4']}
    assert data['bans']['1.2.3.4']['note'] == 'keep'
    assert '2.3.4.5' in data['bans'] and calls == ['propagated']


def test_invalid_payload_never_partially_imports(game):
    with pytest.raises(ValueError):
        sync.import_snapshot(snapshot(accounts=[account()], stats=[['h:bad', -1, 0, 0, 0]]), preview=False)
    assert not (game / 'economy_accounts.dat').exists()
    with pytest.raises(ValueError):
        sync.import_snapshot(snapshot(accounts=[account('bad\nname')]), preview=False)
    with pytest.raises(ValueError):
        sync.import_snapshot(snapshot(accounts=[account(), account()]), preview=False)
    with pytest.raises(ValueError):
        sync.import_snapshot(snapshot(admins=['someone']), preview=False)


def test_engine_file_uses_existing_inode_lock(game):
    path = game / 'economy_accounts.dat'; path.write_text('')
    inode = path.stat().st_ino
    with sync.engine_file('accounts', writable=True):
        with path.open() as competitor:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competitor.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    sync.import_snapshot(snapshot(accounts=[account()]), preview=False)
    assert path.stat().st_ino == inode


def test_sync_authentication_and_caded_capability(game):
    client = create_app().test_client()
    _, viewer = keys.generate('viewer')
    _, admin = keys.generate('admin')
    assert client.get('/api/v1/sync/info').status_code == 401
    assert client.post('/api/v1/sync/export', json={'datasets':['accounts']}, headers={'Authorization':'Bearer '+viewer}).status_code == 403
    headers = {'Authorization':'Bearer '+admin}
    assert client.get('/api/v1/sync/info', headers=headers).json['caded_instances'] == ['legends']
    assert client.post('/api/v1/sync/import', json={'snapshot':snapshot(accounts=[account()])}, headers=headers).json['preview'] is True
    config = Path(settings.locations.config_path) / 'legends.json'
    config.write_text(json.dumps({'server':{'engine':'mbiided.i386'}}))
    assert client.post('/api/v1/sync/export', json={'datasets':['accounts']}, headers=headers).status_code == 400


def test_native_name_bytes_survive_snapshot_and_merge(game):
    raw = b'n:Name\xb1|10|2|0|60\n'
    file = game / 'player_stats.dat'; file.write_bytes(raw)
    exported = sync.export(['stats'])
    assert exported['datasets']['stats'][0][0].encode('latin-1') == b'n:Name\xb1'
    file.write_bytes(b'')
    sync.import_snapshot(exported, preview=False)
    assert file.read_bytes() == raw
    native_name = b'Player\xb1'.decode('latin-1')
    incoming = snapshot(guid_bans=[['A'*32, 0, 0, native_name, '1.2.3.4', 1, '', '']])
    sync.import_snapshot(incoming, preview=False)
    assert b'Player\xb1' in (game / 'guidbans.txt').read_bytes()


def test_automatic_unban_not_resurrected_but_new_reban_allowed(game):
    guid = 'A' * 32
    incoming = snapshot(guid_bans=[[guid,0,0,'Player','1.2.3.4',100,'','note']])
    sync.import_snapshot(incoming, preview=False, automatic=True)
    (game / 'guidbans.txt').write_text('')
    repeat = sync.import_snapshot(incoming, preview=False, automatic=True)
    assert repeat['datasets']['guid_bans']['added'] == 0
    assert not (game / 'guidbans.txt').read_text()
    newer = snapshot(guid_bans=[[guid,0,0,'Player','1.2.3.4',200,'','new note']])
    assert sync.import_snapshot(newer, preview=False, automatic=True)['datasets']['guid_bans']['added'] == 1
    # A newer peer ban observed while the old local row remains is also remembered.
    newest = snapshot(guid_bans=[[guid,0,0,'Player','1.2.3.4',300,'','newer note']])
    sync.import_snapshot(newest, preview=False, automatic=True)
    (game / 'guidbans.txt').write_text('')
    assert sync.import_snapshot(newest, preview=False, automatic=True)['datasets']['guid_bans']['added'] == 0
    assert sync.import_snapshot(incoming, preview=False)['datasets']['guid_bans']['added'] == 1


def test_automatic_backup_retention_keeps_manual_backups(game):
    from mbiiez.api.storage import write, state_dir
    root = state_dir() / 'sync_backups'
    manual = root / 'manual' / 'accounts.json'; write(manual, {'content':'private'})
    for index in range(101): write(root / str(index) / 'automatic.json', {'created':time.time()})
    sync.prune_automatic_backups()
    assert manual.exists()
    assert len(list(root.glob('*/automatic.json'))) == 100
