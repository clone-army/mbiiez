#!/usr/bin/env bash
# server-backup.sh - everything this server needs that isn't in git, in one
# .tar.gz, so it can be rebuilt with server-setup.sh --restore <file>.
#
#   sudo ./server-backup.sh                 # make a backup now
#   sudo ./server-backup.sh --install-cron  # ...and every night at 04:30
#
# Backups go to /root/mbiiez-backups/ (BACKUP_DIR to change it); the newest
# 14 are kept. Paths are stored absolute, so a restore puts everything back
# where it was.
#
# What's in it:
#   mbiiez      configs/*.json (each instance), mbiiez.conf, web_users.json,
#               web_secret.key, homepaths/*/MBII/*.txt (NPC routes...)
#   game folder economy accounts / admins / daily bonuses, banlist.json and
#               banIP.dat, player stats, holotable/ scenarios, the Holotable
#               runners list and NPC types, server .cfg files and map lists
#   holotable   .env and data/ (accounts, secret key; not the map cache)
#   system      /usr/local/bin/mbii-* scripts, and root's crontab
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MBIIEZ_DIR="$SCRIPT_DIR"
GAME_DIR="${GAME_DIR:-/opt/openjk/MBII}"
HOLOTABLE_DIR="${HOLOTABLE_DIR:-/root/holotable}"
BACKUP_DIR="${BACKUP_DIR:-/root/mbiiez-backups}"
KEEP=14
CRON_TIME="30 4 * * *"
BEGIN_MARKER="# BEGIN mbii-server-backup (managed by server-backup.sh - do not edit by hand)"
END_MARKER="# END mbii-server-backup"

if [[ "${1:-}" == "--install-cron" ]]; then
    current="$(crontab -l 2>/dev/null || true)"
    cleaned="$(printf '%s\n' "$current" | awk -v b="$BEGIN_MARKER" -v e="$END_MARKER" '$0==b{skip=1;next} $0==e{skip=0;next} !skip')"
    printf '%s\n%s\n%s %s >> /var/log/mbii-backup.log 2>&1\n%s\n' "$cleaned" "$BEGIN_MARKER" "$CRON_TIME" "$SCRIPT_DIR/server-backup.sh" "$END_MARKER" | crontab -
    echo "Nightly backup installed ($CRON_TIME) - backups in $BACKUP_DIR"
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
out="$BACKUP_DIR/mbii-state-$stamp.tar.gz"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

list="$work/files"
: > "$list"
add() { for f in "$@"; do [[ -e "$f" ]] && printf '%s\n' "$f" >> "$list"; done; return 0; }

# mbiiez
add "$MBIIEZ_DIR"/configs/*.json "$MBIIEZ_DIR/mbiiez.conf" "$MBIIEZ_DIR/web_users.json" "$MBIIEZ_DIR/web_secret.key"
add "$MBIIEZ_DIR"/homepaths/*/MBII/*.txt
# game folder
add "$GAME_DIR"/economy_*.dat "$GAME_DIR/banlist.json" "$GAME_DIR/banIP.dat" "$GAME_DIR/player_stats.dat" \
    "$GAME_DIR/holotable" "$GAME_DIR/holotable_runners.dat" "$GAME_DIR/ext_data/NPCs/holotable.npc" \
    "$GAME_DIR"/*.cfg "$GAME_DIR"/*_maps.txt
# holotable
add "$HOLOTABLE_DIR/.env" "$HOLOTABLE_DIR/data/users.json" "$HOLOTABLE_DIR/data/secret.key"
# system
add /usr/local/bin/mbii-restart-on-boot.sh /usr/local/bin/mbii-scheduled-reboot.sh
crontab -l > "$work/root.crontab" 2>/dev/null || true

# The crontab goes in as /root/.mbii-backup/root.crontab (server-setup.sh
# installs it from there).
mkdir -p "$work/root/.mbii-backup"
cp "$work/root.crontab" "$work/root/.mbii-backup/root.crontab"
date > "$work/root/.mbii-backup/made"

tar -czf "$out" --ignore-failed-read -P -T "$list" -C "$work" root/.mbii-backup/root.crontab root/.mbii-backup/made 2>/dev/null || true
chmod 600 "$out"
echo "Backup: $out ($(du -h "$out" | cut -f1), $(wc -l < "$list") files and folders)"

# Only the newest $KEEP.
ls -1t "$BACKUP_DIR"/mbii-state-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
