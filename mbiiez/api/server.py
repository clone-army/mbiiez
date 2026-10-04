"""Authenticated API agent, independent of browser sessions and web users."""
import collections
import functools
import json
import logging
import os
import subprocess
import threading
import time
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from . import API_VERSION, SOFTWARE_VERSION, keys
from .storage import state_dir

log = logging.getLogger('mbiiez.api')


def create_app():
    from . import backend
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024
    failures = collections.OrderedDict()
    failure_lock = threading.Lock()

    def protected(scope):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                peer, now = request.remote_addr or '', time.monotonic()
                with failure_lock:
                    attempts = failures.get(peer, [])
                    attempts = [t for t in attempts if now - t < 60]
                    if len(attempts) >= 20:
                        return jsonify(error='Too many failed authentication attempts'), 429
                auth = request.headers.get('Authorization', '')
                record = keys.verify(auth[7:]) if auth.startswith('Bearer ') and len(auth) < 512 else None
                if record is None:
                    with failure_lock:
                        failures[peer] = attempts + [now]
                        failures.move_to_end(peer)
                        while len(failures) > 4096:
                            failures.popitem(last=False)
                    return jsonify(error='Invalid API key'), 401
                if keys.ROLES.get(record['scope'], 0) < keys.ROLES[scope]:
                    return jsonify(error='Insufficient key scope'), 403
                # A trusted service may assert a lower acting role, never a higher one.
                actor_role = request.headers.get('X-MBIIEZ-Role', record['scope'])
                if keys.ROLES.get(actor_role, 0) < keys.ROLES[scope]:
                    return jsonify(error='Insufficient actor role'), 403
                g.api_key = record
                g.actor = request.headers.get('X-MBIIEZ-Actor', record['label'])[:100]
                try:
                    return func(*args, **kwargs)
                except SystemExit as exc:
                    # Legacy CLI-oriented helpers must not terminate an API worker.
                    raise ValueError('Unable to load this instance; check its configuration') from exc
            return wrapper
        return decorator

    @app.after_request
    def audit(response):
        response.headers['Cache-Control'] = 'no-store'
        if hasattr(g, 'api_key') and request.method != 'GET' and not request.path.startswith('/api/v1/views/'):
            # Record operations, never bodies, RCON contents, credentials or config secrets.
            entry = {'time': time.time(), 'key_id': g.api_key['id'], 'actor': g.actor,
                     'peer': request.remote_addr, 'method': request.method,
                     'path': request.path, 'status': response.status_code}
            directory = state_dir(); directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(directory / 'api_audit.jsonl', os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'a') as stream:
                stream.write(json.dumps(entry) + '\n')
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, FileNotFoundError):
            return jsonify(error=str(exc)), 404
        if isinstance(exc, (ValueError, TypeError, KeyError)):
            return jsonify(error=str(exc)), 400
        log.exception('API request failed')
        return jsonify(error='Node operation failed; see agent logs'), 500

    def body():
        result = request.get_json()
        if not isinstance(result, dict):
            raise ValueError('Expected a JSON object')
        return result

    @app.get('/health')
    def health():
        return jsonify(status='ok', service='MBIIEZ-API')

    @app.get('/api/v1/info')
    @protected('viewer')
    def info():
        from mbiiez import settings
        result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=settings.globals.script_path,
                                capture_output=True, text=True, timeout=3)
        return jsonify(api_version=API_VERSION, version=SOFTWARE_VERSION,
                       revision=result.stdout.strip() or os.environ.get("MBIIEZ_REVISION", "unknown"),
                       capabilities=['instances', 'config', 'logs', 'chat', 'plugins', 'moderation', 'data_sync', 'public_stats'])

    @app.get('/api/v1/public/stats')
    @protected('viewer')
    def public_stats():
        from .public_stats import snapshot
        return jsonify(snapshot())

    @app.get('/api/v1/sync/info')
    @protected('admin')
    def sync_info():
        from .sync import capabilities
        return jsonify(capabilities())

    @app.post('/api/v1/sync/export')
    @protected('admin')
    def sync_export():
        from .sync import export
        return jsonify(export(body().get('datasets')))

    @app.post('/api/v1/sync/import')
    @protected('admin')
    def sync_import():
        from .sync import import_snapshot
        data = body()
        return jsonify(import_snapshot(data.get('snapshot'), data.get('preview', True), data.get('automatic', False)))

    @app.get('/api/v1/instances')
    @protected('viewer')
    def instances():
        return jsonify(backend.names())

    @app.get('/api/v1/menus')
    @protected('admin')
    def menus():
        return jsonify(backend.menus())

    @app.post('/api/v1/views/<name>')
    def view(name):
        if name not in backend.VIEWS:
            return jsonify(error='Unknown view'), 404
        @protected(backend.VIEWS[name])
        def run():
            args = body().get('args', [])
            if not isinstance(args, list) or len(args) > 5:
                raise ValueError('Invalid arguments')
            return jsonify(backend.view(name, args))
        return run()

    @app.post('/api/v1/actions/<name>')
    def action(name):
        if name not in backend.ACTIONS:
            return jsonify(error='Unknown action'), 404
        @protected(backend.ACTIONS[name])
        def run():
            args = body().get('args', [])
            if not isinstance(args, list) or len(args) > 5:
                raise ValueError('Invalid arguments')
            return jsonify(backend.action(name, args))
        return run()

    @app.get('/api/v1/instances/<name>/status')
    @protected('viewer')
    def status(name):
        return jsonify(backend.status(name))

    @app.get('/api/v1/instances/<name>/players')
    @protected('viewer')
    def players(name):
        return jsonify(backend.status(name).get('players', []))

    @app.post('/api/v1/instances/<name>/<command>')
    @protected('admin')
    def command(name, command):
        data = body()
        if not isinstance(data.get('force', False), bool):
            raise ValueError('force must be a boolean')
        return jsonify(backend.launch(name, command, data.get('force', False))), 202

    @app.route('/api/v1/instances/<name>/config', methods=['GET', 'PUT'])
    @protected('admin')
    def config(name):
        if request.method == 'PUT':
            return jsonify(backend.action('config.save_config', [name, body()['content']]))
        with open(backend.config_path(name)) as stream:
            return jsonify(content=stream.read())

    @app.post('/api/v1/instances/<name>/rcon')
    @protected('admin')
    def rcon(name):
        return jsonify(backend.action('rcon.send_rcon', [name, body()['command']]))

    @app.route('/api/v1/chat', methods=['GET', 'POST'])
    def chat():
        @protected('mod' if request.method == 'POST' else 'viewer')
        def run():
            if request.method == 'POST':
                data = body()
                return jsonify(success=backend.action('chat.send_message', [data['instance'], data['message']]))
            return jsonify(backend.rows('chat', request.args.get('instance'), request.args.get('limit', 100)))
        return run()

    @app.get('/api/v1/logs')
    @protected('viewer')
    def logs():
        return jsonify(backend.rows('logs', request.args.get('instance'), request.args.get('limit', 100),
                                    request.args.get('search', ''), request.args.get('tag')))

    return app
