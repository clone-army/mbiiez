#!/usr/bin/env bash
# server-setup.sh - rebuild the whole Clone Army MBII server on a fresh
# Debian/Ubuntu box: MBIIEZ, the caded engine, Holotable, and (from a
# server-backup.sh backup) every setting, account and scenario.
#
#   git clone -b test https://github.com/clone-army/mbiiez /root/mbiiez
#   cd /root/mbiiez
#   sudo ./server-setup.sh --restore /path/to/mbii-state-XXXX.tar.gz
#
# Without --restore it sets up the software only (you then make instances in
# the web panel). Each step says what it's doing; it's safe to re-run - done
# steps are skipped or redone harmlessly.
#
# Steps:
#   1. MBIIEZ's own installer (install.sh): packages, MBII, stock OpenJK,
#      the mbii command, the web panel (it asks whether you want it - say yes)
#   2. The caded engine: clone clone-army/OpenJK to /root/OpenJK and build it
#      (build.sh --install), which installs /usr/bin/caded.i386
#   3. Holotable: clone clone-army/holotable to /root/holotable and run its
#      install.sh (its service, port 8090)
#   4. Restore the backup: configs, accounts, bans, scenarios, Holotable
#      accounts, NPC routes, the boot/reboot scripts and root's crontab
#   5. The nightly backup and daily scheduled reboot cron jobs
#   6. Restart the web panel and Holotable, then start the instances that
#      restart on boot (mbii-restart-on-boot.sh)
#
# The GitHub repos may need logging in to clone if they're private: set
# GITHUB_TOKEN=<a personal access token> and it's used for the clones.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENJK_DIR="${OPENJK_DIR:-/root/OpenJK}"
HOLOTABLE_DIR="${HOLOTABLE_DIR:-/root/holotable}"
RESTORE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restore) RESTORE="$2"; shift 2 ;;
        -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1 (see --help)"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "Run as root (sudo ./server-setup.sh)."
    exit 1
fi
if [[ -n "$RESTORE" && ! -f "$RESTORE" ]]; then
    echo "No backup at $RESTORE"
    exit 1
fi

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

clone() {  # clone <repo> <dir> [branch]
    local url="https://github.com/$1"
    [[ -n "${GITHUB_TOKEN:-}" ]] && url="https://x-access-token:${GITHUB_TOKEN}@github.com/$1"
    if [[ -d "$2/.git" ]]; then
        echo "$2 already there - pulling"
        git -C "$2" pull --ff-only || true
    else
        git clone ${3:+-b "$3"} "$url" "$2"
        # Don't leave the token in the repo's config.
        git -C "$2" remote set-url origin "https://github.com/$1"
    fi
}

step "1/6 MBIIEZ (packages, MBII, the mbii command, the web panel)"
apt-get update -qq && apt-get install -y -qq git >/dev/null
( cd "$SCRIPT_DIR" && ./install.sh )

step "2/6 The caded engine (clone-army/OpenJK -> /usr/bin/caded.i386)"
clone clone-army/OpenJK "$OPENJK_DIR" main
( cd "$OPENJK_DIR" && ./build.sh --install )

step "3/6 Holotable (clone-army/holotable, port 8090)"
clone clone-army/holotable "$HOLOTABLE_DIR" main
if [[ -n "$RESTORE" ]]; then
    # Its .env and accounts come from the backup: don't let install.sh make
    # a fresh .env with a new admin password first.
    tar -xzf "$RESTORE" -P --wildcards "$HOLOTABLE_DIR/.env" 2>/dev/null || true
fi
( cd "$HOLOTABLE_DIR" && ./install.sh )

if [[ -n "$RESTORE" ]]; then
    step "4/6 Restoring $RESTORE"
    tar -xzf "$RESTORE" -P -C /
    echo "Restored: $(tar -tzf "$RESTORE" -P | wc -l) files (made $(cat /root/.mbii-backup/made 2>/dev/null || echo '?'))"
    if [[ -s /root/.mbii-backup/root.crontab ]]; then
        crontab /root/.mbii-backup/root.crontab
        echo "Root's crontab restored:"
        crontab -l | grep -v '^#' | grep -v '^$' | sed 's/^/  /'
    fi
    chmod +x /usr/local/bin/mbii-*.sh 2>/dev/null || true
else
    step "4/6 No backup to restore (--restore <file>) - software only"
fi

step "5/6 Nightly backup and daily scheduled reboot"
"$SCRIPT_DIR/server-backup.sh" --install-cron
[[ -x "$SCRIPT_DIR/install_scheduled_reboot.sh" ]] && "$SCRIPT_DIR/install_scheduled_reboot.sh" || true

step "6/6 Starting things up"
systemctl daemon-reload
systemctl restart mbii-web 2>/dev/null && echo "Web panel running" || echo "No web panel service (install_web.sh sets it up)"
systemctl restart holotable && echo "Holotable running on port $(grep -E '^HT_PORT=' "$HOLOTABLE_DIR/.env" | cut -d= -f2)"
if [[ -x /usr/local/bin/mbii-restart-on-boot.sh ]]; then
    echo "Starting the instances in mbii-restart-on-boot.sh (a minute or two)..."
    /usr/local/bin/mbii-restart-on-boot.sh >> /var/log/mbii-restart.log 2>&1 || true
fi

printf '\n\033[1;32mDone.\033[0m\n'
echo "  Instances:  mbii -i <name> status   (configs in $SCRIPT_DIR/configs)"
echo "  Web panel:  http://<this server>:$(grep -E '^port' "$SCRIPT_DIR/mbiiez.conf" 2>/dev/null | head -1 | grep -oE '[0-9]+' || echo 8080)"
echo "  Holotable:  http://<this server>:$(grep -E '^HT_PORT=' "$HOLOTABLE_DIR/.env" | cut -d= -f2)"
echo "  Open those ports, and the game ports in configs/*.json, in the firewall."
