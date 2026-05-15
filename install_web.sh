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
readonly CONFIG_FILE="${SCRIPT_DIR}/mbiiez.conf"

get_cfg_value(){
  local section="$1" key="$2" default_value="$3"
  local value=""

  if [[ -f "$CONFIG_FILE" ]]; then
    value=$(awk -F'=' -v section="$section" -v key="$key" '
      $0 ~ "^[[:space:]]*\\[" section "\\][[:space:]]*$" { in_section=1; next }
      in_section && $0 ~ "^[[:space:]]*\\[" { in_section=0 }
      in_section {
        lhs=$1
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
        if (lhs == key) {
          rhs=$2
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", rhs)
          print rhs
          exit
        }
      }
    ' "$CONFIG_FILE")
  fi

  if [[ -n "$value" ]]; then
    printf "%s" "$value"
  else
    printf "%s" "$default_value"
  fi
}

check_web_health(){
  local port="$1"
  local url="http://127.0.0.1:${port}/health"
  local health_json=""

  for _ in {1..20}; do
    if command -v curl >/dev/null 2>&1; then
      health_json=$(curl -fsS --max-time 2 "$url" 2>/dev/null || true)
    else
      health_json=$("${VENV_DIR}/bin/python3" - "$url" <<'PY'
import sys
import urllib.request

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=2) as r:
        print(r.read().decode("utf-8", errors="ignore"))
except Exception:
    pass
PY
)
    fi

    if [[ -n "$health_json" ]]; then
      printf "%s" "$health_json"
      return 0
    fi

    sleep 1
  done

  return 1
}


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

# ─── 10) Report configuration & runtime health ───────────────────────────
WEB_PORT="$(get_cfg_value web_service port 8080)"
AUTH_ENABLED="$(get_cfg_value web_service auth_enabled true)"
USERS_FILE="$(get_cfg_value web_service users_file web_users.json)"

if [[ "$USERS_FILE" != /* ]]; then
  USERS_FILE="${SCRIPT_DIR}/${USERS_FILE}"
fi

echo
printf "${BLUE}Web Service Configuration${NC}\n"
printf "  - Port: ${GREEN}%s${NC}\n" "$WEB_PORT"
printf "  - Auth Enabled: ${GREEN}%s${NC}\n" "$AUTH_ENABLED"
printf "  - Users File: ${GREEN}%s${NC}\n" "$USERS_FILE"

if systemctl is-active --quiet "${SERVICE_NAME}"; then
  printf "  - systemd Status: ${GREEN}running${NC}\n"
else
  printf "  - systemd Status: ${RED}not running${NC}\n"
  printf "${YELLOW}Check logs with: journalctl -u %s -n 100 --no-pager${NC}\n" "$SERVICE_NAME"
  exit 1
fi

if HEALTH_JSON="$(check_web_health "$WEB_PORT")"; then
  printf "  - Health Endpoint: ${GREEN}ok${NC}\n"
  printf "  - GET /health: ${GREEN}%s${NC}\n" "$HEALTH_JSON"
  printf "${GREEN}Web UI is available at: http://<server-ip>:%s/${NC}\n" "$WEB_PORT"
else
  printf "  - Health Endpoint: ${YELLOW}not responding yet${NC}\n"
  printf "${YELLOW}Service is running but /health did not respond in time. Check: journalctl -u %s -n 100 --no-pager${NC}\n" "$SERVICE_NAME"
fi
