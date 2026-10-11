"""Software updates requested from the central panel.

The API only records a request. The node's host runs deploy/node-updater.sh
(a systemd timer, outside any container) which fetches the branch, builds,
waits until no one is playing and then restarts onto the new revision. It
reports back through update-status.json in the same state directory.
"""
import re
import time
from .storage import state_dir, read, write, locked

BRANCH = 'main'
BRANCH_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\Z')
# The updater checks every minute; a heartbeat older than this means it isn't installed or isn't running.
UPDATER_STALE = 300


def request_path():
    return state_dir() / 'update-request.json'


def status_path():
    return state_dir() / 'update-status.json'


def request_update(actor, branch=BRANCH):
    if not isinstance(branch, str) or '..' in branch or not BRANCH_NAME.fullmatch(branch):
        raise ValueError('Invalid branch')
    with locked(request_path()):
        request = {'branch': branch, 'requested_by': str(actor)[:100], 'requested_at': int(time.time())}
        write(request_path(), request)
    return request


def status():
    report = read(status_path(), {})
    heartbeat = report.get('checked_at', 0)
    return {'request': read(request_path(), None), 'updater': bool(heartbeat) and time.time() - heartbeat < UPDATER_STALE,
            'state': report.get('state', ''), 'message': report.get('message', ''), 'revision': report.get('revision', ''),
            'target': report.get('target', ''), 'updated_at': report.get('updated_at', 0), 'checked_at': heartbeat}

