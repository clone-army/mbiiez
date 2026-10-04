import importlib.util
import json
from pathlib import Path
import time
import pytest
from mbiiez import settings
from mbiiez.api import public_stats, keys
from mbiiez.api.client import Client, save_node, NodeError
from mbiiez.api.server import create_app
from mbiiez.web import public_dashboard


@pytest.fixture
def public_game(tmp_path, monkeypatch):
    monkeypatch.setenv('MBIIEZ_STATE_DIR', str(tmp_path / 'state'))
    data = tmp_path / 'MBII'; data.mkdir()
    configs = tmp_path / 'configs'; configs.mkdir()
    monkeypatch.setattr(settings.locations, 'mbii_path', str(data))
    monkeypatch.setattr(settings.locations, 'config_path', str(configs))
    public_stats._cache.clear(); public_dashboard._cache.clear()
    return data


def event(**updates):
    return dict(t=int(time.time()), game='blackjack', result='win', account='Player', name='^1Player', stake=50, net=50, **updates)


def test_gameplay_projection_and_zero_deaths(public_game):
    (public_game / 'player_stats.dat').write_bytes(b'h:Player|10|2|1|3600\nn:Guest\xb1|4|0|0|60\ninvalid|a|0|0|0\n')
    result = public_stats.gameplay()
    assert result['available'] and result['totals']['kills'] == 14
    assert result['totals']['playtime_seconds'] == 3660
    assert result['players'][0]['kd'] == 5.0
    assert result['players'][1]['kd'] is None
    assert result['players'][1]['identity'] == 'nickname'
    assert result['skipped_records'] == 1


def test_casino_metrics_refunds_prizes_and_incomplete_line(public_game):
    events = [event(), {**event(), 'result':'loss', 'net':-50},
              {**event(), 'result':'refund', 'net':0},
              {**event(), 'game':'spin', 'result':'prize', 'stake':0, 'net':0}]
    (public_game / 'game_results.log').write_text('\n'.join(json.dumps(row) for row in events) + '\n{"partial":')
    data = public_stats.casino()
    assert data['totals']['results'] == 4
    assert data['totals']['credits_wagered'] == 100
    assert data['totals']['credits_won'] == 50 and data['totals']['credits_lost'] == 50
    assert data['totals']['net_credits'] == 0 and data['totals']['win_rate'] == 50
    assert data['totals']['prizes'] == 1
    assert sum(row['results'] for row in data['daily']) == 4
    assert all('account' not in row and 'details' not in row and 'vs' not in row for row in data['recent'])


def test_casino_bounded_tail_and_malformed_records(public_game, monkeypatch):
    monkeypatch.setattr(public_stats, 'MAX_LOG_LINES', 2)
    rows = [json.dumps(event()) for _ in range(3)] + ['invalid']
    (public_game / 'game_results.log').write_text('\n'.join(rows) + '\n')
    result = public_stats.casino()
    assert result['limited'] and result['totals']['results'] == 1 and result['skipped_records'] == 1
    outside = public_game.parent / 'secret'; outside.write_text(json.dumps(event()))
    (public_game / 'game_results.log').unlink(); (public_game / 'game_results.log').symlink_to(outside)
    with pytest.raises(OSError): public_stats.casino()


def test_public_api_auth_cache_and_no_private_fields(public_game, monkeypatch):
    (public_game / 'player_stats.dat').write_text('h:Player|1|1|0|60\n')
    for filename in ('economy_accounts.dat','guidbans.txt','banlist.json','guidseen.txt'):
        (public_game / filename).write_text('private-secret-must-never-be-read')
    (public_game / 'game_results.log').write_text(json.dumps({**event(), 'details':'private-detail', 'ip':'secret-ip'}) + '\n')
    client = create_app().test_client()
    assert client.get('/api/v1/public/stats').status_code == 401
    _, token = keys.generate('viewer')
    response = client.get('/api/v1/public/stats', headers={'Authorization':'Bearer '+token})
    assert response.status_code == 200
    for secret in ('private-secret', 'secret-ip', 'private-detail', token): assert secret.encode() not in response.data
    first = response.json['gameplay']['totals']['kills']
    (public_game / 'player_stats.dat').write_text('h:Player|20|1|0|60\n')
    assert client.get('/api/v1/public/stats', headers={'Authorization':'Bearer '+token}).json['gameplay']['totals']['kills'] == first


def test_private_server_never_queried(public_game, monkeypatch):
    config = Path(settings.locations.config_path) / 'private.json'
    config.write_text(json.dumps({'server':{'port':29070},'security':{'server_password':'private'}}))
    def forbidden(*args): raise AssertionError('No query of private server')
    monkeypatch.setattr(public_stats.socket, 'socket', forbidden)
    assert public_stats.server_info('private') is None
    config.write_text(json.dumps({'server':{'port':29070,'public_stats':False}}))
    assert public_stats.server_info('private') is None


def test_anonymous_web_page_data_and_admin_still_protected(public_game, monkeypatch):
    monkeypatch.setattr(settings.web_service, 'auth_enabled', True)
    monkeypatch.setattr(settings.web_service, 'users_file', str(public_game.parent / 'users.json'))
    Path(settings.web_service.users_file).write_text(json.dumps({'users':[{'username':'admin','password':'hash','role':'admin'}]}))
    save_node('na','<img src=x onerror=alert(1)>','http://127.0.0.1:8081','private-api-key')
    spec = importlib.util.spec_from_file_location('public_web_test', Path(__file__).parents[1] / 'mbii-web.py')
    web = importlib.util.module_from_spec(spec); spec.loader.exec_module(web)
    summary = public_stats.build()
    summary['api_key'] = 'never-public'
    summary['gameplay']['players'] = [dict(name='Player', identity='account', kills=1, deaths=1, suicides=0, playtime_seconds=60, kd=1, pin_hash='never-public')]
    calls = []
    def fake(self, method, path, data=None, params=None):
        calls.append(path)
        assert method == 'GET' and path == 'public/stats'
        return summary
    monkeypatch.setattr(Client, 'call', fake)
    client = web.app.test_client()
    page = client.get('/public')
    assert page.status_code == 200 and b'private-api-key' not in page.data
    assert b'&lt;img' in page.data and b'<img src=x' not in page.data
    assert calls == []  # Rendering the public page does not fetch admin menu metadata.
    assert client.get('/').location == '/public'
    assert client.get('/public/data').status_code == 200
    assert calls == ['public/stats']
    assert b'private-api-key' not in client.get('/public/data').data
    assert b'never-public' not in client.get('/public/data').data
    assert client.get('/public?node=missing').status_code == 404
    assert client.post('/nodes/na/automatic-sync',json={'enabled':True}).status_code in (302,401)
    assert client.get('/dashboard').status_code == 302
    assert client.post('/public/data').status_code in (401,405)
    public_dashboard._cache.clear()
    def offline(*args, **kwargs): raise NodeError('/private/config secret-key')
    monkeypatch.setattr(Client,'call',offline)
    response = client.get('/public/data')
    assert response.status_code == 503 and b'secret-key' not in response.data and b'/private/config' not in response.data
