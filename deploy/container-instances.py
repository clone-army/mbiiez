import sys
sys.path.insert(0, "/app")
"""Container bootstrap. Starts configured instances once; API restarts do not rerun this."""
import os
import signal
import subprocess
import time
from mbiiez.api.paths import names
from mbiiez import settings

if os.environ.get('MBIIEZ_AUTOSTART', '0') == '1':
    for name in names():
        subprocess.run(['/usr/local/bin/mbii', '-i', name, 'start'],
                       stdin=subprocess.DEVNULL, check=True)
# Runtime watchdogs belong to MBIIEZ; supervisor only holds the container open.
while True:
    time.sleep(60)
