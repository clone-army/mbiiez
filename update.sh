#!/usr/bin/env bash

set -euo pipefail

# Get absolute path of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Paths
gamedir="/opt/openjk"
updater_dll="$SCRIPT_DIR/updater/MBII_CommandLine_Update_XPlatform.dll"
mbii_dir="$gamedir/MBII"
config_dir="$SCRIPT_DIR/configs"

# Optional log file
LOG_FILE="/tmp/mbii_update.log"
: > "$LOG_FILE"

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
        cp "$mbii_dir/jampgamei386.nopp.so" "$mbii_dir/jampgamei386.so"
        echo "→ Copied engine library" | tee -a "$LOG_FILE"
    fi

    shopt -s nullglob
    configs=("$config_dir"/*.json)

    if (( ${#configs[@]} == 0 )); then
        echo "⚠ No config files found in $config_dir. Skipping instance restarts." | tee -a "$LOG_FILE"
    else
        if (( ${#INSTANCES[@]} > 0 )); then
            echo -n "Restarting specified instances: " | tee -a "$LOG_FILE"
            printf "%s " "${INSTANCES[@]}" | tee -a "$LOG_FILE"
            echo | tee -a "$LOG_FILE"

            for name in "${INSTANCES[@]}"; do
                cfg="$config_dir/$name.json"
                if [[ -f "$cfg" ]]; then
                    echo "→ Restarting instance: $name" | tee -a "$LOG_FILE"
                    mbii -i "$name" restart >> "$LOG_FILE" 2>&1
                else
                    echo "⚠ Instance config not found: $name (skipping)" | tee -a "$LOG_FILE"
                fi
            done
        else
            echo "Restarting all instances..." | tee -a "$LOG_FILE"
            for cfg in "${configs[@]}"; do
                name=$(basename "$cfg" .json)
                echo "→ Restarting instance: $name" | tee -a "$LOG_FILE"
                mbii -i "$name" restart >> "$LOG_FILE" 2>&1
            done
        fi
    fi

    echo "✅ Update complete." | tee -a "$LOG_FILE"
else
    echo "No update needed ($update_count files)." | tee -a "$LOG_FILE"
fi
