#!/usr/bin/env bash
# Daily scheduled reboot for the MB2 host - only reboots when every instance
# is empty. If any instance has players connected, defers by 30 minutes and
# checks again, up to 10 times (5 hours total), then gives up for the day
# rather than force-kick anyone.
#
# Canonical copy lives here in the mbiiez repo; install_scheduled_reboot.sh
# in this same directory copies it to /usr/local/bin and wires up the
# crontab entry. Re-run that installer after moving/cloning this repo to a
# new server rather than copying this file into place by hand.
#
# Originally replaced a root crontab entry (`CRON_TZ=Europe/London` + `0 13
# * * * /usr/sbin/reboot`) which silently ran at 1pm US Eastern instead of
# the intended 1pm London time, since this box's cron (Vixie cron 3.0pl1)
# doesn't support CRON_TZ as a per-job variable - it was rebooting the
# server (and kicking every player on every instance) at 1pm Eastern, every
# single day, regardless of who was online.
set -uo pipefail

MAX_ATTEMPTS=10
DEFER_SECONDS=1800   # 30 minutes
LOG="/var/log/mbii-scheduled-reboot.log"

log() {
	echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" >> "$LOG"
}

# Prints the player count for one instance, or nothing if it couldn't be
# determined - callers treat "couldn't determine" as busy, so a parsing
# hiccup never accidentally lets a reboot through.
player_count() {
	local instance="$1"
	mbii -i "$instance" status 2>/dev/null \
		| sed 's/\x1b\[[0-9;]*m//g' \
		| grep -oP 'Players:\s*\K[0-9]+(?=/[0-9]+)' \
		| head -1
}

# Returns 0 if every configured instance is empty, 1 otherwise (logging why
# per-instance either way). Uses `mbii -l` to enumerate instances rather
# than a hardcoded list, since instances can be added/removed over time.
all_instances_empty() {
	local busy=0
	local instance count

	for instance in $(mbii -l 2>/dev/null); do
		count=$(player_count "$instance")
		if [ -z "$count" ]; then
			log "  $instance: could not read player count - treating as busy."
			busy=1
			continue
		fi
		if [ "$count" -gt 0 ]; then
			log "  $instance: $count player(s) online."
			busy=1
		else
			log "  $instance: empty."
		fi
	done

	[ "$busy" -eq 0 ]
}

log "=== Scheduled reboot check starting ==="

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
	log "Attempt $attempt/$MAX_ATTEMPTS: checking all instances..."

	if all_instances_empty; then
		log "All instances empty - rebooting now."
		/usr/sbin/reboot
		exit 0
	fi

	if [ "$attempt" -eq "$MAX_ATTEMPTS" ]; then
		break
	fi

	log "At least one instance busy - deferring 30 min before next attempt."
	sleep "$DEFER_SECONDS"
	attempt=$((attempt + 1))
done

log "Still busy after $MAX_ATTEMPTS attempts (5 hours) - skipping reboot for today."
