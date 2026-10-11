"""Print how many players are on this node's running servers.

deploy/node-updater.sh pipes this into the node (python3 - in the mbiiez
directory), so it only uses helpers every release has had. It exits non-zero
when a running server doesn't answer: the updater then waits rather than
restart a server that might be full.
"""
import sys
sys.path.insert(0, ".")
from mbiiez.api.backend import runtime
from mbiiez.api.paths import names

total = 0
for name in names():
    instance = runtime(name)
    if not instance.server_running():
        continue
    # players() reads an unanswered rcon as nobody on, so check the server answered first.
    reply = instance.console.rcon("status notrunc") or ""
    if "cl score ping name" not in reply:
        sys.exit(name + " did not answer rcon status")
    total += len(instance.players())
print(total)
