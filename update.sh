#!/usr/bin/env bash

set -euo pipefail

# Get absolute path of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Paths
gamedir="/opt/openjk"
updater_dll="$SCRIPT_DIR/updater/MBII_CommandLine_Update_XPlatform.dll"
mbii_dir="$gamedir/MBII"
config_dir="$SCRIPT_DIR/configs"
MBII_BIN="${MBII_BIN:-mbii}"

# Temp dir: $MBIIEZ_TMP if set, else $TMPDIR, else /tmp - falling back to
# tmp/ next to this script when none of those can be written to. Exported as
# TMPDIR so dotnet, wget etc. use it too.
pick_tmp_dir() {
    local d probe
    for d in "${MBIIEZ_TMP:-}" "${TMPDIR:-}" /tmp "$1/tmp"; do
        [[ -n "$d" ]] || continue
        mkdir -p "$d" 2>/dev/null || continue
        probe="$d/.mbiiez_write_test.$$"
        if { : > "$probe"; } 2>/dev/null; then
            rm -f "$probe"
            printf '%s\n' "$d"
            return 0
        fi
    done
    echo "No writable temp dir (tried \$MBIIEZ_TMP, \$TMPDIR, /tmp, $1/tmp)" >&2
    return 1
}
TMPDIR="$(pick_tmp_dir "$SCRIPT_DIR")"
export TMPDIR

# Optional log file
LOG_FILE="$TMPDIR/mbii_update.log"
: > "$LOG_FILE"

# Instances updated while players were on - restarted by a later run, once
# they're empty. "mbii restart" refuses (exit 3) to restart a populated
# server, so an update never kicks anyone.
PENDING_DIR="$SCRIPT_DIR/.pending_restart"
mkdir -p "$PENDING_DIR"

restart_when_empty() {
    local name="$1"
    if $MBII_BIN -i "$name" restart >> "$LOG_FILE" 2>&1; then
        rm -f "$PENDING_DIR/$name"
        echo "→ Restarted instance: $name" | tee -a "$LOG_FILE"
    else
        touch "$PENDING_DIR/$name"
        echo "→ $name has players - will restart it once it's empty" | tee -a "$LOG_FILE"
    fi
}

for marker in "$PENDING_DIR"/*; do
    [[ -e "$marker" ]] || continue
    restart_when_empty "$(basename "$marker")"
done

get_running_instances() {
    local output
    if ! output="$($MBII_BIN -i 2>&1)"; then
        printf '%s\n' "$output" >> "$LOG_FILE"
        return 1
    fi

    local names=()
    while IFS= read -r line; do
        if [[ $line == -* ]]; then
            local name=${line#- }
            if [[ -n $name ]]; then
                names+=("$name")
            fi
        fi
    done <<< "$output"

    if (( ${#names[@]} == 0 )); then
        if grep -qi 'no instances' <<< "$output"; then
            return 2
        fi
    fi

    printf '%s\n' "${names[@]}"
}

# --- NEW: Argument parsing with safe local IFS ---
INSTANCES=()
while getopts "i:" opt; do
    case $opt in
        i)
            # Split comma list safely without touching global IFS
            localIFS=$IFS
            IFS=',' read -r -a parts <<< "$OPTARG"
            IFS=$localIFS
            INSTANCES+=("${parts[@]}")
            ;;
    esac
done
shift $((OPTIND - 1))

echo "Checking for MBII updates..." | tee -a "$LOG_FILE"
update_output=$(dotnet "$updater_dll" -c -path "$gamedir" 2>&1)
echo "$update_output" | tee -a "$LOG_FILE"

# Extract update count
update_count=$(echo "$update_output" | grep -Eo '^[0-9]+' || echo 0)

if (( update_count > 1 )); then
    echo "Update available: $update_count files to update. Applying update..." | tee -a "$LOG_FILE"
    dotnet "$updater_dll" -path "$gamedir" >> "$LOG_FILE" 2>&1

    # Copy engine library if needed (only after update)
    if [[ -f "$mbii_dir/jampgamei386.nopp.so" ]]; then
        # Copy then rename: overwriting the .so in place would change it
        # under every server still running it.
        cp "$mbii_dir/jampgamei386.nopp.so" "$mbii_dir/jampgamei386.so.new"
        mv -f "$mbii_dir/jampgamei386.so.new" "$mbii_dir/jampgamei386.so"
        echo "→ Copied engine library" | tee -a "$LOG_FILE"
    fi

    shopt -s nullglob
    configs=("$config_dir"/*.json)

    if (( ${#configs[@]} == 0 )); then
        echo "⚠ No config files found in $config_dir. Skipping instance restarts." | tee -a "$LOG_FILE"
    else
        ALL_INSTANCE_NAMES=()
        for cfg in "${configs[@]}"; do
            ALL_INSTANCE_NAMES+=("$(basename "$cfg" .json)")
        done

        TARGETS=()
        if (( ${#INSTANCES[@]} > 0 )); then
            TARGETS=("${INSTANCES[@]}")
            echo -n "Restarting specified instances: " | tee -a "$LOG_FILE"
            printf "%s " "${TARGETS[@]}" | tee -a "$LOG_FILE"
            echo | tee -a "$LOG_FILE"
        else
            if running_list=$(get_running_instances); then
                readarray -t TARGETS <<< "$running_list"
                if (( ${#TARGETS[@]} == 0 )); then
                    echo "ℹ No running instances detected; skipping restarts." | tee -a "$LOG_FILE"
                else
                    echo -n "Restarting running instances: " | tee -a "$LOG_FILE"
                    printf "%s " "${TARGETS[@]}" | tee -a "$LOG_FILE"
                    echo | tee -a "$LOG_FILE"
                fi
            else
                status=$?
                if (( status == 2 )); then
                    echo "ℹ No running instances detected; skipping restarts." | tee -a "$LOG_FILE"
                else
                    echo "⚠ Could not determine running instances (exit $status); defaulting to all configs." | tee -a "$LOG_FILE"
                    TARGETS=("${ALL_INSTANCE_NAMES[@]}")
                fi
            fi
        fi

        if (( ${#TARGETS[@]} == 0 )); then
            echo "ℹ No instances selected for restart." | tee -a "$LOG_FILE"
        else
            for name in "${TARGETS[@]}"; do
                cfg="$config_dir/$name.json"
                if [[ -f "$cfg" ]]; then
                    restart_when_empty "$name"
                else
                    echo "⚠ Instance config not found: $name (skipping)" | tee -a "$LOG_FILE"
                fi
            done
        fi
    fi

    echo "✅ Update complete." | tee -a "$LOG_FILE"
else
    echo "No update needed ($update_count files)." | tee -a "$LOG_FILE"
fi
