import copy
import json
from pathlib import Path
import pytest
from mbiiez.api import sync
from mbiiez.api.client import save_node, nodes, Client
from mbiiez.api.storage import write, state_dir
from mbiiez.web import auto_sync


@pytest.fixture
def peers(tmp_path, monkeypatch):
    monkeypatch.setenv('MBIIEZ_STATE_DIR', str(tmp_path / 'state'))
    save_node('na','Local','http://127.0.0.1:8081','secret')
    save_node('eu','Europe','https://eu.example.com','secret-eu')
    save_node('other','Offline','https://other.example.com','secret-other')
    policy = {'nodes': {key:{'enabled':True, 'url':node['url']} for key,node in nodes().items()}}
    write(auto_sync.settings_path(), policy)
    return tmp_path


def test_cycle_merges_both_ways_is_idempotent_and_continues_past_offline(peers):
    datasets = {key:{name:[] for name in sync.FORMATS} for key in ('na','eu')}
    datasets['na']['accounts'] = [['NA', 'a'*32, 'b'*32, 50, 0, 0]]
    datasets['eu']['accounts'] = [['EU', 'c'*32, 'd'*32, 100, 0, 0]]
    datasets['na']['stats'] = [['h:player',10,2,0,100]]
    datasets['eu']['stats'] = [['h:player',8,3,1,90]]
    imports = []
    class Fake:
        def __init__(self, identifier): self.identifier = identifier
        def call(self, method, path, data=None):
            if self.identifier == 'other': raise RuntimeError('Offline')
            if path == 'sync/info': return {'automatic_sync':True,'caded_instances':['legends']}
            if path == 'sync/export': return {'protocol':1,'datasets':{name:copy.deepcopy(datasets[self.identifier][name]) for name in data['datasets']}}
            assert method == 'POST' and path == 'sync/import'
            assert data['preview'] is False and data['automatic'] is True
            reports = {}
            for name, rows in data['snapshot']['datasets'].items():
                merged, report = sync.merge(name, sync.validate(name,datasets[self.identifier][name]), sync.validate(name,rows))
                datasets[self.identifier][name] = list(merged.values()); reports[name] = report
            imports.append((self.identifier,reports))
            return {'datasets':reports}
    result = auto_sync.cycle(Fake)
    assert result['nodes']['other']['error'] == 'Offline'
    assert all(result['nodes'][key]['last_success'] for key in ('na','eu'))
    assert all(sync.validate(name,datasets['na'][name]) == sync.validate(name,datasets['eu'][name]) for name in sync.FORMATS)
    assert datasets['na']['stats'] == [['h:player',10,3,1,100]]
    assert len(datasets['na']['accounts']) == 2
    imports.clear(); auto_sync.cycle(Fake)
    assert all(not row['added'] and not row['updated'] for _,reports in imports for row in reports.values())
    stored = (state_dir() / 'automatic_sync_status.json').read_text()
    assert 'a'*32 not in stored and 'b'*32 not in stored


def test_url_edit_blocks_transfer_and_local_default_needs_second_node(peers):
    save_node('eu','Europe','https://changed.example.com','')
    policy = auto_sync.settings(); policy['nodes']['other']['enabled'] = False; write(auto_sync.settings_path(),policy)
    def forbidden(identifier): raise AssertionError('No transfer without two approved destinations')
    result = auto_sync.cycle(forbidden)
    assert 'URL changed' in result['nodes']['eu']['error']
    assert 'waiting' in result['nodes']['na']
    auto_sync.settings_path().unlink()
    assert list(auto_sync.settings()['nodes']) == ['na']
    assert auto_sync.settings()['nodes']['na']['enabled'] is True


def test_switch_off_during_export_is_honored(peers):
    policy = auto_sync.settings(); policy['nodes']['other']['enabled'] = False; write(auto_sync.settings_path(),policy)
    imports = []
    class Fake:
        def __init__(self, identifier): self.identifier = identifier
        def call(self, method, path, data=None):
            if path == 'sync/info': return {'automatic_sync':True,'caded_instances':['legends']}
            if path == 'sync/export':
                policy = auto_sync.settings(); policy['nodes']['eu']['enabled'] = False; write(auto_sync.settings_path(),policy)
                return {'protocol':1,'datasets':{data['datasets'][0]:[]}}
            imports.append(self.identifier)
            return {'datasets':{data['snapshot']['datasets'].keys().__iter__().__next__():{'added':0}}}
    result = auto_sync.cycle(Fake)
    assert 'eu' not in imports and result['nodes']['eu']['waiting']


def test_configure_validation_and_offline_disable(peers, monkeypatch):
    monkeypatch.setattr(Client,'call',lambda *args: {'automatic_sync':True,'caded_instances':['legends']})
    assert auto_sync.configure('eu',True)['enabled']
    with pytest.raises(ValueError): auto_sync.configure('eu','yes')
    with pytest.raises(ValueError): auto_sync.configure('missing',True)
    def offline(*args): raise RuntimeError('offline')
    monkeypatch.setattr(Client,'call',offline)
    assert auto_sync.configure('eu',False)['enabled'] is False
    assert auto_sync.settings_path().stat().st_mode & 0o777 == 0o600
