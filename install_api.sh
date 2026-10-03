#!/usr/bin/env bash
set -euo pipefail
TASK_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_PYTHON=/opt/openjk/venv/bin/python3
"$TASK_PYTHON" -m pip install 'waitress>=3,<4'
mkdir -p /var/lib/mbiiez
chmod 700 /var/lib/mbiiez
# Generate the local service credential without printing it or overwriting existing nodes.
cd "$TASK_REPO_DIR"
"$TASK_PYTHON" - <<'PY'
from mbiiez.api.keys import generate
from mbiiez.api.client import nodes, save_node
if 'na' not in nodes():
    _, token = generate('admin', 'local-web')
    save_node('na', 'North America', 'http://127.0.0.1:8081', token)
PY
sed "s|/root/mbiiez|$TASK_REPO_DIR|g" deploy/mbii-api.service > /etc/systemd/system/mbii-api.service
systemctl daemon-reload
systemctl enable --now mbii-api
printf 'MBIIEZ API installed on 127.0.0.1:8081. Game instances were not restarted.\n'
