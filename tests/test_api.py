import importlib.util
import json
import os
from pathlib import Path
import pytest
from mbiiez.api import keys, backend
from mbiiez.api.server import create_app
from mbiiez.api.paths import config_path
from mbiiez.api.client import validate_url, save_node, selected_node
from mbiiez import settings


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv('MBIIEZ_STATE_DIR', str(tmp_path / 'state'))
    configs = tmp_path / 'configs'; configs.mkdir()
    (configs / 'legends.json').write_text(json.dumps({'server': {'host_name': 'test'}}))
    monkeypatch.setattr(settings.locations, 'config_path', str(configs))
    return tmp_path


@pytest.fixture
def api(environment):
    return create_app().test_client()


def auth(scope='admin', role=None):
    _, token = keys.generate(scope)
    headers = {'Authorization': 'Bearer ' + token}
    if role:
        headers['X-MBIIEZ-Role'] = role
    return headers


def test_auth_and_rotation(api):
    assert api.get('/api/v1/instances').status_code == 401
    identifier, token = keys.generate('viewer')
    header = {'Authorization': 'Bearer ' + token}
    assert api.get('/api/v1/instances', headers=header).json == ['legends']
    assert token not in keys.path().read_text()
    keys.revoke(identifier)
    assert api.get('/api/v1/instances', headers=header).status_code == 401


def test_scope_and_actor_cannot_escalate(api, monkeypatch):
    called = []
    monkeypatch.setattr(backend, 'launch', lambda *a: called.append(a))
    for header in [auth('viewer'), auth('mod'), auth('admin', 'viewer'), auth('mod', 'admin')]:
        assert api.post('/api/v1/instances/legends/restart', json={}, headers=header).status_code == 403
        assert api.get('/api/v1/instances/legends/config', headers=header).status_code == 403
    assert called == []


def test_paths(environment):
    for name in ('../legends', '../../etc/passwd', '', 'legends/..', 'a.json', '/legends'):
        with pytest.raises(ValueError): config_path(name)
    with pytest.raises(FileNotFoundError): config_path('missing')
    (environment / 'configs' / 'escape.json').symlink_to(environment / 'outside.json')
    with pytest.raises(ValueError): config_path('escape', existing=False)


def test_config_write_no_restart(api, monkeypatch):
    def forbidden(*a): raise AssertionError('Must not restart')
    monkeypatch.setattr(backend, 'launch', forbidden)
    headers = auth()
    new = json.dumps({'server': {'host_name': 'updated'}, 'plugins': {}})
    assert api.put('/api/v1/instances/legends/config', json={'content': new}, headers=headers).json[0]
    assert 'updated' in api.get('/api/v1/instances/legends/config', headers=headers).json['content']
    assert api.put('/api/v1/instances/legends/config', json={'content': 'broken'}, headers=headers).json[0] is False


def test_command_dispatch_and_force(api, monkeypatch):
    called = []
    monkeypatch.setattr(backend, 'launch', lambda *a: called.append(a) or {'async': True})
    assert api.post('/api/v1/instances/legends/restart', json={}, headers=auth()).status_code == 202
    assert called == [('legends', 'restart', False)]
    assert api.post('/api/v1/instances/legends/restart', json={'force': 'yes'}, headers=auth()).status_code == 400


def test_busy_launch_refused(environment, monkeypatch):
    monkeypatch.setattr(backend, 'runtime', lambda name: type('Busy', (), {'players_count': lambda s: 3})())
    with pytest.raises(ValueError, match='Players are online'):
        backend.launch('legends', 'restart')


def test_arbitrary_dispatch_rejected(api):
    assert api.post('/api/v1/actions/os.system', json={'args': ['whoami']}, headers=auth()).status_code == 404
    assert api.post('/api/v1/views/missing', json={'args': []}, headers=auth()).status_code == 404


def test_auth_rate_limit(api):
    for _ in range(20): assert api.get('/api/v1/instances').status_code == 401
    assert api.get('/api/v1/instances').status_code == 429


def test_audit_has_actor_no_secrets(api):
    headers = auth('viewer'); headers['X-MBIIEZ-Actor'] = 'rex-user'
    response = api.post('/api/v1/views/config', json={'args': ['legends']}, headers=headers)
    assert response.status_code == 403
    # Successful authenticated requests are audited; rejected scope requests don't get identities.
    headers = auth(); headers['X-MBIIEZ-Actor'] = 'rex-user'
    response = api.put('/api/v1/instances/legends/config', json={'content': '{}'}, headers=headers)
    assert response.status_code == 200
    text = (keys.path().parent / 'api_audit.jsonl').read_text()
    assert 'rex-user' in text and 'key_id' in text and 'Bearer' not in text and 'digest' not in text


def test_urls_and_explicit_nodes(environment):
    for url in ('http://public.example', 'http://0.0.0.0', 'https://user:pass@host', 'ftp://host', 'https://host/path'):
        with pytest.raises(ValueError): validate_url(url)
    assert validate_url('https://mb2-eu-api.lcho.me/') == 'https://mb2-eu-api.lcho.me'
    assert validate_url('http://127.0.0.1:8081') == 'http://127.0.0.1:8081'
    save_node('na', 'NA', 'http://127.0.0.1:8081', 'secret-na')
    save_node('eu', 'EU', 'http://10.25.0.166:8082', 'secret-eu')
    from flask import Flask, g
    app = Flask(__name__)
    with app.test_request_context('/?node=na', headers={'X-MBIIEZ-Node': 'eu'}):
        g.node_id = 'na'
        assert selected_node()[0] == 'eu'


def test_web_api_adapters_and_csrf(environment, monkeypatch):
    monkeypatch.setattr(settings.web_service, 'users_file', str(environment / 'users.json'))
    monkeypatch.setattr(settings.database, 'database', str(environment / 'web.db'))
    from werkzeug.security import generate_password_hash
    Path(settings.web_service.users_file).write_text(json.dumps({'users': [
        {'username': 'admin', 'password': generate_password_hash('testing'), 'role': 'admin'}]}))
    spec = importlib.util.spec_from_file_location('web_app', Path(__file__).parents[1] / 'mbii-web.py')
    web = importlib.util.module_from_spec(spec); spec.loader.exec_module(web)
    save_node('na', 'NA', 'http://127.0.0.1:8081', 'secret-na')
    save_node('eu', 'EU', 'http://10.25.0.166:8082', 'secret-eu')
    web.app.config['TESTING'] = True
    client = web.app.test_client()
    with client.session_transaction() as sess:
        sess['mbiiez_user'] = 'admin'
        sess['mbiiez_pw'] = web._password_fingerprint(web._load_users()['admin']['password']) if hasattr(web, '_password_fingerprint') else ''
    # Use the actual login path to create a session with the existing authentication format.
    client.post('/login', data={'username': 'admin', 'password': 'testing'})
    calls = []
    from mbiiez.api.client import Client
    def fake(self, method, path, data=None, params=None):
        calls.append((self.identifier, method, path, data))
        if path == 'menus': return {'instances': ['legends'], 'plugins': {}, 'global': []}
        if path == 'instances/legends/status': return {'server_running': True, 'players_count': 2}
        if path == 'views/dashboard': return {'instances': [], 'summary': {'total': 0}}
        return {'async': True}
    monkeypatch.setattr(Client, 'call', fake)
    response = client.get('/dashboard?node=eu')
    assert response.status_code == 200
    assert b'Nodes' in response.data
    assert Path(web.app.template_folder).is_absolute()
    node_page = client.get('/nodes')
    assert node_page.status_code == 200
    assert b'>Edit</button>' in node_page.data
    assert b'secret-na' not in node_page.data and b'secret-eu' not in node_page.data
    assert b'/nodes/na/delete' not in node_page.data
    assert b'/nodes/eu/delete' in node_page.data
    with client.session_transaction() as sess: token = sess['csrf_token']
    assert client.post('/instance/legends/command', json={'command': 'restart'}).status_code == 403
    headers = {'X-MBIIEZ-CSRF': token, 'X-MBIIEZ-Node': 'na'}
    assert client.post('/instance/legends/command', json={'command': 'restart'}, headers=headers).status_code == 202
    assert calls[-1][0] == 'na' and calls[-1][3]['force'] is False
    assert client.post('/nodes/na/delete', headers=headers).status_code == 400
    assert client.post('/nodes/save', headers=headers, data={
        'id': 'na', 'name': 'Renamed Local', 'url': 'http://127.0.0.1:8081', 'key': ''
    }).status_code == 302
    from mbiiez.api.client import nodes
    assert nodes()['na']['name'] == 'Renamed Local'
    assert nodes()['na']['key'] == 'secret-na' and nodes()['na']['local'] is True
    assert client.post('/nodes/eu/delete', headers=headers).status_code == 302
    assert b'onchange="location.href=' not in client.get('/dashboard?node=na').data
    assert client.post('/instance/legends/command', json={'command': 'restart', 'force': True}, headers=headers).status_code == 202
    assert calls[-1][3]['force'] is True


def test_legacy_exit_does_not_kill_api_worker(api, monkeypatch):
    def legacy(*args):
        raise SystemExit(1)
    monkeypatch.setattr(backend, 'status', legacy)
    assert api.get('/api/v1/instances/legends/status', headers=auth()).status_code == 400
    assert api.get('/api/v1/instances', headers=auth()).status_code == 200


def test_info_reports_contract_and_software_version(api):
    response = api.get('/api/v1/info', headers=auth('viewer'))
    assert response.status_code == 200
    assert response.json['api_version'] == 1
    assert response.json['version'] == '3.0.0'
    assert 'revision' in response.json
