#!/usr/bin/env bash
# Applies software updates requested from the central panel's Nodes page.
#
# Runs on the node's host every minute (deploy/mbiiez-node-updater.timer), outside
# the container, as the node can't rebuild itself. The node API only writes
# update-request.json into its state directory; this fetches that branch, builds
# the new image while the game keeps running, waits until no one is playing and
# then restarts the node onto it. Progress goes to update-status.json, which the
# API reports back to the panel. Docker nodes only - native installs update with
# git pull --ff-only and install.sh --update.
#
# Settings come from /etc/default/mbiiez-node-updater:
#   MBIIEZ_REPO       the mbiiez checkout the image is built from
#   MBIIEZ_STATE      the node's state directory on this host (eu-state)
#   MBIIEZ_COMPOSE    compose file in MBIIEZ_REPO (compose.eu.yml)
#   MBIIEZ_SERVICE    compose service (node)
#   MBIIEZ_CONTAINER  container name (mbiiez-eu)
#   MBIIEZ_REMOTE     where to fetch from (default: the clone-army GitHub repo)
set -uo pipefail

MBIIEZ_REMOTE="https://github.com/clone-army/mbiiez"
MBIIEZ_SERVICE="node"
[[ -f /etc/default/mbiiez-node-updater ]] && . /etc/default/mbiiez-node-updater
: "${MBIIEZ_REPO:?set MBIIEZ_REPO}" "${MBIIEZ_STATE:?set MBIIEZ_STATE}" "${MBIIEZ_COMPOSE:?set MBIIEZ_COMPOSE}" "${MBIIEZ_CONTAINER:?set MBIIEZ_CONTAINER}"

STATE="$(readlink -f "$MBIIEZ_STATE")"
REQUEST="$STATE/update-request.json"
STATUS="$STATE/update-status.json"
BUILT="$STATE/.update-built"
LOG="$STATE/update.log"

exec 9>"$STATE/.update.lock"
flock -n 9 || exit 0

# Git runs as the checkout's owner so root never leaves files in it.
OWNER="$(stat -c %U "$MBIIEZ_REPO")"
git_() { runuser -u "$OWNER" -- git -C "$MBIIEZ_REPO" "$@"; }
compose() { docker compose --project-directory "$MBIIEZ_REPO" -f "$MBIIEZ_REPO/$MBIIEZ_COMPOSE" "$@"; }
running_revision() { docker exec "$MBIIEZ_CONTAINER" printenv MBIIEZ_REVISION 2>/dev/null; }

# status STATE MESSAGE [TARGET] - also the heartbeat that tells the panel this updater is installed.
status() {
    python3 - "$STATUS" "$1" "$2" "${3:-}" "$(running_revision)" <<'EOF'
import json, os, sys, tempfile, time
path, state, message, target, revision = sys.argv[1:]
try:
    with open(path) as f:
        old = json.load(f)
except (OSError, ValueError):
    old = {}
now = int(time.time())
new = {"state": state, "message": message, "target": target or old.get("target", ""), "revision": revision,
       "checked_at": now, "updated_at": old.get("updated_at", 0) if (state, message) == (old.get("state"), old.get("message")) else now}
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".update-status")
with os.fdopen(fd, "w") as f:
    json.dump(new, f, indent=2)
os.replace(tmp, path)
EOF
}

finish() {  # finish STATE MESSAGE [TARGET] - the request is done with, either way
    status "$@"
    rm -f "$REQUEST" "$BUILT"
    exit 0
}

if [[ ! -f "$REQUEST" ]]; then
    # Nothing asked for: keep the last result and just refresh the heartbeat.
    previous="$(python3 -c 'import json,sys
try: d = json.load(open(sys.argv[1]))
except Exception: d = {}
print(d.get("state", "")); print(d.get("message", ""))' "$STATUS")"
    status "$(sed -n 1p <<< "$previous")" "$(sed -n 2p <<< "$previous")"
    exit 0
fi

{ echo; echo "=== $(date -Iseconds)"; } >> "$LOG"

BRANCH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("branch") or "main")' "$REQUEST" 2>/dev/null)"
if ! git_ check-ref-format --branch "$BRANCH" >/dev/null 2>&1; then
    finish failed "Invalid branch in the update request"
fi

if ! git_ fetch -q "$MBIIEZ_REMOTE" "refs/heads/$BRANCH" >> "$LOG" 2>&1; then
    finish failed "Couldn't fetch $BRANCH from $MBIIEZ_REMOTE"
fi
TARGET="$(git_ rev-parse FETCH_HEAD)"
SHORT="${TARGET:0:7}"

if [[ "$(running_revision)" == "$TARGET" ]]; then
    finish done "Already running $BRANCH ($SHORT)" "$TARGET"
fi

PREVIOUS="$(git_ rev-parse HEAD)"
if [[ "$PREVIOUS" != "$TARGET" ]]; then
    if [[ -n "$(git_ status --porcelain --untracked-files=no)" ]]; then
        finish failed "The checkout on the host has uncommitted changes - not touching it" "$TARGET"
    fi
    # Only ever move forward: anything committed here but not on the branch would be lost.
    for ref in HEAD "refs/heads/$BRANCH"; do
        if git_ rev-parse -q --verify "$ref" >/dev/null && ! git_ merge-base --is-ancestor "$ref" "$TARGET"; then
            finish failed "The host's $ref has commits that aren't on $BRANCH - update it by hand" "$TARGET"
        fi
    done
    git_ checkout -q -B "$BRANCH" "$TARGET" >> "$LOG" 2>&1 || finish failed "Couldn't check out $SHORT" "$TARGET"
fi

# Build while the game keeps running; a failed build leaves the node as it was.
if [[ "$(cat "$BUILT" 2>/dev/null)" != "$TARGET" ]]; then
    status building "Building $BRANCH ($SHORT)" "$TARGET"
    if ! compose build --build-arg "MBIIEZ_REVISION=$TARGET" "$MBIIEZ_SERVICE" >> "$LOG" 2>&1; then
        git_ checkout -q "$PREVIOUS" >> "$LOG" 2>&1
        finish failed "Build failed - see update.log in the node's state directory" "$TARGET"
    fi
    echo "$TARGET" > "$BUILT"
fi

PLAYERS="$(docker exec -i -w /app "$MBIIEZ_CONTAINER" /opt/openjk/venv/bin/python3 - \
    < "$MBIIEZ_REPO/deploy/players-online.py" 2>> "$LOG")"
if [[ ! "$PLAYERS" =~ ^[0-9]+$ ]]; then
    status waiting "Built $SHORT - couldn't check for players, trying again shortly" "$TARGET"
    exit 0
fi
if (( PLAYERS > 0 )); then
    status waiting "Built $SHORT - restarting once the $PLAYERS player(s) on have left" "$TARGET"
    exit 0
fi

status restarting "Restarting onto $SHORT" "$TARGET"
if ! compose up -d "$MBIIEZ_SERVICE" >> "$LOG" 2>&1; then
    finish failed "Restart failed - see update.log in the node's state directory" "$TARGET"
fi
for _ in $(seq 60); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "$MBIIEZ_CONTAINER" 2>/dev/null)" == healthy ]] && break
    sleep 5
done
if [[ "$(running_revision)" != "$TARGET" ]]; then
    finish failed "Restarted, but the node isn't running $SHORT - check the container" "$TARGET"
fi
finish done "Updated to $BRANCH ($SHORT)" "$TARGET"
