#!/bin/sh
# The container's stand-in for the native nodes' "*/10 * * * * update.sh" crontab: checks
# for MBII game updates every 10 minutes; update.sh restarts each instance once it's empty.
# Instances are named from the configs because "mbii -i" can't list them in the container.
while :; do
    sleep 600
    names=$(ls /app/configs/*.json 2>/dev/null | xargs -rn1 basename | sed 's/\.json$//' | paste -sd, -)
    [ -n "$names" ] && { bash /app/update.sh -i "$names" || echo "update.sh failed (exit $?)"; }
done
