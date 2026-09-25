#!/usr/bin/env bash
# install_scheduled_reboot.sh — installs the "reboot only when empty" daily
# scheduled reboot (mbii-scheduled-reboot.sh, same directory) as a root cron
# job.
#
# Run this once after cloning/copying this mbiiez directory onto a (new)
# server to recreate the whole setup with one command:
#   sudo ./install_scheduled_reboot.sh
#
# Safe to re-run: the script is copied into place (overwriting any existing
# copy), and the crontab entry is a sentinel-delimited block
# (BEGIN/END mbii-scheduled-reboot) that gets fully replaced, not
# duplicated, on each run.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SCRIPT="$SCRIPT_DIR/mbii-scheduled-reboot.sh"
DEST_SCRIPT="/usr/local/bin/mbii-scheduled-reboot.sh"
CRON_TIME="0 5 * * *"
BEGIN_MARKER="# BEGIN mbii-scheduled-reboot (managed by install_scheduled_reboot.sh - do not edit by hand)"
END_MARKER="# END mbii-scheduled-reboot"

if (( EUID != 0 )); then
	echo "Error: must run as root (sudo $0)" >&2
	exit 1
fi

if [ ! -f "$SOURCE_SCRIPT" ]; then
	echo "Error: $SOURCE_SCRIPT not found - run this from inside the mbiiez directory." >&2
	exit 1
fi

echo "-> Installing $DEST_SCRIPT..."
cp "$SOURCE_SCRIPT" "$DEST_SCRIPT"
chmod +x "$DEST_SCRIPT"

echo "-> Updating root's crontab..."
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

# Strip any existing sentinel-delimited block from a prior run (so re-running
# this installer replaces it cleanly instead of duplicating), plus the old
# raw reboot job this setup replaces on a fresh/legacy box - a bare
# "0 13 * * * /usr/sbin/reboot" line and a preceding CRON_TZ=Europe/London
# line, if present (see mbii-scheduled-reboot.sh's header for why that
# approach silently ran at the wrong time).
crontab -l 2>/dev/null \
	| sed "/^${BEGIN_MARKER//\//\\/}$/,/^${END_MARKER//\//\\/}$/d" \
	| grep -v '^CRON_TZ=Europe/London$' \
	| grep -v '^0 13 \* \* \* /usr/sbin/reboot$' \
	> "$TMP_CRON" || true

{
	cat "$TMP_CRON"
	echo ""
	echo "$BEGIN_MARKER"
	echo "# Daily reboot - only when every instance is empty (defers 30 min at a"
	echo "# time, up to 10 attempts / 5 hours, then skips for the day). Runs at"
	echo "# 5am in this box's own system-local timezone."
	echo "$CRON_TIME $DEST_SCRIPT"
	echo "$END_MARKER"
} | crontab -

echo "Done. Current crontab:"
crontab -l
echo
echo "Reboot check runs daily at 5am system-local time ($(date +%Z) right now)."
echo "Log: /var/log/mbii-scheduled-reboot.log"
