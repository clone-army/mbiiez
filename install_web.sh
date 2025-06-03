#!/usr/bin/env bash
# Strip Windows CRs from this script so bash won’t see “\r” as a command
sed -i 's/\r$//' "$0"

#
# install.sh — MBII + OpenJK + Web UI on Debian/Ubuntu,
#             with single consolidated log, spinner, colors & .NET SDK
#

# ─── Strict modes & err‐trap inheritance ───────────────────────────────────
set -o errexit      # -e
set -o nounset      # -u
set -o pipefail     # fail on any pipe member
set -o errtrace     # ERR trap inherited by functions/subshells
IFS=$'\n\t'

# ─── Colors ───────────────────────────────────────────────────────────────
RED='\033[31m'; GREEN='\033[32m'; YELLOW='\033[33m'; BLUE='\033[36m'; NC='\033[0m'

# ─── Single log file ──────────────────────────────────────────────────────
readonly LOG_FILE="/tmp/install.log"
: > "$LOG_FILE"    # truncate or create

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
  local pid=$1 chars='|/-\' i=0
  while kill -0 "$pid" 2>/dev/null; do
    printf "${YELLOW}%c${NC}" "${chars:i++%${#chars}:1}"
    sleep 0.2
    printf "\b"
  done
}

# ─── run_step: wrap a long command with spinner + consolidated log ────────
run_step(){
  current_step="$1"
  printf "${BLUE}→ %s...${NC} " "$current_step"
  bash -c "$2" >>"$LOG_FILE" 2>&1 & local pid=$!
  spinner "$pid"
  wait "$pid"
  printf "${GREEN}✔${NC}\n"
}

# ─── Preflight ────────────────────────────────────────────────────────────
(( EUID == 0 )) || { printf "${RED}Error:${NC} must run as root (sudo \$0)\n"; exit 1; }
. /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID" != "debian" && ! "$ID_LIKE" =~ debian ]]; then
  printf "${RED}Error:${NC} only Debian/Ubuntu (or derivative) supported\n"; exit 1
fi

readonly BASE="/opt/openjk"
readonly MBII_DIR="${BASE}/MBII"
readonly VENV_DIR="${BASE}/venv"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SERVICE_NAME="mbii-web"


# ─── 9) Write systemd service ─────────────────────────────────────────────
printf "${BLUE}→ Writing systemd service...${NC} "
cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=MBII Web UI
After=network.target

[Service]
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${SCRIPT_DIR}/mbii-web.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
printf "${GREEN}✔${NC}\n"

# ─── 9) Enable & start ────────────────────────────────────────────────────
run_step "Enabling systemd service" \
  "systemctl daemon-reload && systemctl enable ${SERVICE_NAME} && systemctl restart ${SERVICE_NAME}"
