"""Service credentials. Only a SHA-256 digest of a random 256-bit key is stored."""
import hashlib
import hmac
import secrets
import time
from .storage import state_dir, locked, read, write

ROLES = {'engine': 0, 'viewer': 10, 'mod': 20, 'admin': 30}


def path():
    return state_dir() / 'api_keys.json'


def generate(scope='admin', label='web'):
    if scope not in ROLES:
        raise ValueError('Unknown scope')
    identifier = secrets.token_hex(8)
    token = 'mbii_' + identifier + '_' + secrets.token_urlsafe(32)
    with locked(path()):
        records = read(path(), {})
        records[identifier] = {'digest': hashlib.sha256(token.encode()).hexdigest(),
                               'scope': scope, 'label': label, 'created': time.time()}
        write(path(), records)
    return identifier, token


def verify(token):
    parts = token.split('_', 2)
    records = read(path(), {})
    record = records.get(parts[1] if len(parts) == 3 else '', {})
    digest = hashlib.sha256(token.encode()).hexdigest()
    if not hmac.compare_digest(record.get('digest', '0' * 64), digest):
        return None
    return dict(record, id=parts[1])


def revoke(identifier):
    with locked(path()):
        records = read(path(), {})
        if identifier not in records:
            raise ValueError('Unknown key ID')
        del records[identifier]
        write(path(), records)


def listing():
    return [{k: v for k, v in dict(record, id=identifier).items() if k != 'digest'}
            for identifier, record in read(path(), {}).items()]
