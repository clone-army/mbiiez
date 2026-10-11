#!/usr/bin/env bash
set -euo pipefail
TASK_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_PYTHON=/opt/openjk/venv/bin/python3
"$TASK_PYTHON" -m pip install 'waitress>=3,<4'
mkdir -p /var/lib/mbiiez
chmod 700 /var/lib/mbiiez
if [[ "${1:-}" == "--with-web" ]]; then
# Generate the local service credential without printing it or overwriting existing nodes.
cd "$TASK_REPO_DIR"
"$TASK_PYTHON" - <<'PY'
import shlex
from pathlib import Path
from mbiiez.api.keys import generate
from mbiiez.api.client import nodes, save_node, is_local_node
port = '8081'
env_file = Path('/etc/default/mbii-api')
if env_file.exists():
    for line in env_file.read_text().splitlines():
        for assignment in shlex.split(line, comments=True):
            if assignment.startswith('MBIIEZ_API_PORT='):
                port = str(int(assignment.split('=', 1)[1]))
url = 'http://127.0.0.1:' + port
for identifier, node in nodes().items():
    if node['url'] == url:
        save_node(identifier, node['name'], node['url'], '', local=True)
if not any(is_local_node(node) for node in nodes().values()):
    identifier = 'local'
    while identifier in nodes():
        identifier += '-1'
    _, token = generate('admin', 'local-web')
    save_node(identifier, 'Local', url, token, local=True)
PY
fi
sed "s|/root/mbiiez|$TASK_REPO_DIR|g" deploy/mbii-api.service > /etc/systemd/system/mbii-api.service
systemctl daemon-reload
systemctl enable mbii-api
systemctl restart mbii-api
systemctl is-active --quiet mbii-api
printf 'MBIIEZ API installed (loopback:8081 by default; /etc/default/mbii-api overrides retained). Game instances were not restarted.\n'
