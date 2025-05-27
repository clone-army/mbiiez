#!/usr/bin/env bash
#
# update.sh — MBII updater only, with consolidated log, spinner & colors
#                Conditional update if more than 2 files changed

set -o errexit      # -e
set -o nounset      # -u
set -o pipefail     # fail on any pipe member
set -o errtrace     # ERR trap inherited by functions/subshells
IFS=$'\n\t'

# ─── Colors ───────────────────────────────────────────────────────────────
RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[33m'; BLUE='\033[36m'; NC='\033[0m'

# ─── Single log file ──────────────────────────────────────────────────────
readonly LOG_FILE="/tmp/update_mbii.log"
: > "$LOG_FILE"

# ─── Globals for trap ─────────────────────────────────────────────────────
current_step=""

# ─── Error handler ─────────────────────────────────────────────────────────
error_exit() {
  echo
  printf "${RED}✗ Error during: %s${NC}\n" "$current_step"
  printf "${YELLOW}See full log at: %s${NC}\n" "$LOG_FILE"
  exit 1
}
trap error_exit ERR

# ─── Spinner (0.2s) ────────────────────────────────────────────────────────
spinner(){
  local pid=$1 chars='|/-\\' i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "${YELLOW}%c${NC}" "${chars:i++%${#chars}:1}"
    sleep 0.2
    printf "\b"
  done

}

# ─── run_step: wrap a long command with spinner + log ─────────────────────
run_step(){
  current_step="$1"
  printf "${BLUE}→ %s...${NC} " "$current_step"
  bash -c "$2" >>"$LOG_FILE" 2>&1 & local pid=$!
  spinner "$pid"
  wait "$pid"
  printf "${GREEN}✔${NC}\n"
}

# ─── Require root ─────────────────────────────────────────────────────────
(( EUID == 0 )) || { printf "${RED}Error:${NC} must run as root (sudo \$0)\n"; exit 1; }

# ─── Paths ────────────────────────────────────────────────────────────────
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BASE="/opt/openjk"
readonly MBII_DIR="/opt/openjk/MBII"

# ─── Check update count ────────────────────────────────────────────────────
current_step="Checking MBII update count"
printf "${BLUE}→ %s...${NC} " "$current_step"
# Run updater with -c to get count of files needing update
update_count=$(dotnet "${SCRIPT_DIR}/updater/MBII_CommandLine_Update_XPlatform.dll" -c -path "$BASE")

# ─── Conditional Update ────────────────────────────────────────────────────
if (( update_count > 2 )); then
  run_step "Updating MBII" \
    "dotnet \"${SCRIPT_DIR}/updater/MBII_CommandLine_Update_XPlatform.dll\" -path \"$BASE\""
  printf "
${GREEN}✅ MBII update applied (${update_count} files updated)!${NC}
"
  # Restart all instances defined by config JSON files
  for cfg in "$SCRIPT_DIR/config"/*.json; do
    name=$(basename "$cfg" .json)
    run_step "Restarting instance $name" \
      "mbii -i \"$name\" restart"
  done
  
# ─── Rename MBII engine library ─────────────────────────────────────────
run_step "Renaming JAMP Library" \

  "if [ -f \"$MBII_DIR/jampgamei386.nopp.so\" ]; then \
     mv -f \"$MBII_DIR/jampgamei386.nopp.so\" \"$MBII_DIR/jampgamei386.so\"; \
   else \
     echo \"${YELLOW}Warning:${NC} jampgamei386.nopp.so not found, skipping rename\"; \
   fi"  
  

fi

if (( update_count < 3 )); then

printf "\n${BLUE}→ %s...${NC} No Update Needed: $update_count \n"

fi
