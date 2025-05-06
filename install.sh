#!/usr/bin/env bash
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

# ─── 1) APT packages ──────────────────────────────────────────────────────
run_step "Installing APT packages" \
  "apt-get update && apt-get install -y \
     wget curl unzip python3-pip python3-venv python3-dev libsqlite3-dev snapd \
     libsdl2-2.0-0:i386 libc6:i386 zlib1g:i386 net-tools gnupg apt-transport-https ca-certificates"

# ─── 2) .NET 6 SDK ─────────────────────────────────────────────────────────
run_step "Installing .NET 6 SDK" \
  "if ! command -v dotnet >/dev/null; then \
     wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor \
       > /usr/share/keyrings/microsoft.gpg && \
     DISTRO=\"\$(. /etc/os-release && echo \"\$ID\")\" && \
     CODE=\"\$(. /etc/os-release && echo \"\$VERSION_CODENAME\")\" && \
     echo \"deb [signed-by=/usr/share/keyrings/microsoft.gpg] \
       https://packages.microsoft.com/repos/microsoft-\${DISTRO}-\${CODE}-prod \
       \${CODE} main\" > /etc/apt/sources.list.d/microsoft-prod.list && \
     apt-get update && apt-get install -y dotnet-sdk-6.0; \
   fi"

# ─── 3) Python venv & pip deps ─────────────────────────────────────────────
run_step "Setting up Python venv & pip packages" \
  "python3 -m venv \"$VENV_DIR\" && \
   \"$VENV_DIR/bin/pip\" install --upgrade pip && \
   \"$VENV_DIR/bin/pip\" install \
     watchgod tailer six psutil PTable ConfigParser pysqlite3 \
     flask flask_httpauth discord.py"

# ─── 4) Prepare directories ───────────────────────────────────────────────
printf "${BLUE}→ Preparing directories...${NC} "
mkdir -p "$MBII_DIR" "$BASE/base"
printf "${GREEN}✔${NC}\n"


# ─── 6) Installing MBII ───────────────────────────────────────────────────
run_step "Installing MBII" \
  "dotnet \"${SCRIPT_DIR}/updater/MBII_CommandLine_Update_XPlatform.dll\" -path \"$BASE\""


# ─── 7) RTVRTM resources ───────────────────────────────────────────────────
run_step "Installing RTVRTM" \
  "wget -qO /tmp/RTVRTM.zip https://www.moviebattles.org/download/RTVRTM.zip && \
   unzip -o /tmp/RTVRTM.zip -d \"$MBII_DIR\" && \
   rm /tmp/RTVRTM.zip"


# ─── 8) JK2 assets ────────────────────────────────────────────────────────
printf "${BLUE}→ Downloading JK2 assets...${NC}\n"
ASSETS=(
  "https://www.x-raiders.net/download/jk3/assets0/file/assets0.pk3"
  "https://www.x-raiders.net/download/jk3/assets1/file/assets1.pk3"
  "https://www.x-raiders.net/download/jk3/assets2/file/assets2.pk3"
  "https://www.x-raiders.net/download/jk3/assets3/file/assets3.pk3"
)
for url in "${ASSETS[@]}"; do
  fn=$(basename "$url")
  if wget -qO "$BASE/base/$fn" "$url"; then
    printf "   ${GREEN}✔${NC} %s\n" "$fn"
  else
    printf "   ${RED}✗${NC} %s\n" "$fn"
  fi
done


# ─── 7) OpenJK ─────────────────────────────────────────────────────────────
run_step "Installing OpenJK" \
  "wget -qO- https://builds.openjk.org/openjk-2018-02-26-e3f22070-linux.tar.gz \
     | tar xz -C $BASE && \
   cp -a $BASE/install/JediAcademy/. $BASE/ && \
   rm -rf $BASE/install"


# ─── 9) Write systemd service ─────────────────────────────────────────────
printf "${BLUE}→ Writing systemd service...${NC} "
cat >"/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=MBII Web UI
After=network.target

[Service]
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${SCRIPT_DIR}/server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
printf "${GREEN}✔${NC}\n"

# ─── 9) Enable & start ────────────────────────────────────────────────────
run_step "Enabling systemd service" \
  "systemctl daemon-reload && systemctl enable ${SERVICE_NAME} && systemctl restart ${SERVICE_NAME}"

# ─── Done ────────────────────────────────────────────────────────────────
printf "\n${GREEN}✅ Installation complete!${NC}\n"
printf " • Engines in %s:\n     - MBII installed via updater DLL into %s\n     - OpenJK under %s\n" \
  "$BASE" "$MBII_DIR" "$BASE"
printf " • Web UI: http://0.0.0.0:8080  (default Admin/Admin)\n"
