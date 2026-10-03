"""Server-to-server transport. Credentials never reach the browser."""
import ipaddress
import os
import re
from urllib.parse import urlsplit
import requests
from flask import g, has_request_context, request
from .storage import state_dir, read, locked, write


class NodeError(Exception):
    pass


def nodes_path():
    return state_dir() / 'web_nodes.json'


def nodes():
    return read(nodes_path(), {})


def validate_url(url):
    parsed = urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError('Use a base URL without credentials, path, query or fragment')
    if not parsed.hostname:
        raise ValueError('Missing API hostname')
    if parsed.scheme == 'https':
        return url.rstrip('/')
    if parsed.scheme == 'http':
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError:
            raise ValueError('HTTP requires a literal loopback or private network IP')
        if address.is_loopback or (address.is_private and not address.is_unspecified and not address.is_link_local):
            return url.rstrip('/')
    raise ValueError('Use HTTPS for public APIs or a private IP over a trusted VPN/LAN')


def save_node(identifier, label, url, key):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,31}', identifier):
        raise ValueError('Invalid node ID')
    url = validate_url(url)
    with locked(nodes_path()):
        data = nodes()
        if not key:
            key = data.get(identifier, {}).get('key', '')
        if not key or '\n' in key or '\r' in key:
            raise ValueError('An API key is required')
        data[identifier] = {'name': str(label)[:80] or identifier, 'url': url, 'key': key}
        write(nodes_path(), data)


def remove_node(identifier):
    with locked(nodes_path()):
        data = nodes()
        data.pop(identifier, None)
        write(nodes_path(), data)


def selected_node():
    if has_request_context():
        identifier = request.headers.get('X-MBIIEZ-Node') or request.args.get('node') or getattr(g, 'node_id', None)
    else:
        identifier = None
    data = nodes()
    identifier = identifier or os.environ.get('MBIIEZ_DEFAULT_NODE', 'na')
    if identifier not in data:
        raise NodeError('Select or configure an API node on the Nodes page')
    return identifier, data[identifier]


class Client:
    def __init__(self, node=None):
        if node:
            self.identifier, self.node = node, nodes()[node]
        else:
            self.identifier, self.node = selected_node()

    def call(self, method, path, data=None, params=None):
        headers = {'Authorization': 'Bearer ' + self.node['key']}
        if has_request_context():
            headers['X-MBIIEZ-Actor'] = getattr(g, 'current_user', '') or 'web'
            headers['X-MBIIEZ-Role'] = getattr(g, 'current_role', 'viewer')
        try:
            response = requests.request(method, self.node['url'] + '/api/v1/' + path,
                                        headers=headers, json=data, params=params,
                                        timeout=(3, 25), allow_redirects=False)
            if not response.ok:
                try:
                    message = response.json().get('error', 'API request failed')
                except ValueError:
                    message = 'API request failed'
                raise NodeError(f'{self.identifier}: {message} ({response.status_code})')
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise NodeError(f'{self.identifier}: API unavailable') from exc

    def view(self, name, *args):
        return self.call('POST', 'views/' + name, {'args': list(args)})

    def action(self, name, *args):
        return self.call('POST', 'actions/' + name, {'args': list(args)})
