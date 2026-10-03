#!/usr/bin/env bash
# Install/update application components; game bootstrap runs only on a fresh host.
set -euo pipefail
TASK_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_PROFILE_FILE="$TASK_REPO_DIR/.install-profile"
TASK_MODE=""
TASK_UPDATE=auto
usage() {
  cat <<'HELP'
Usage: sudo ./install.sh [--mode cli|api|web] [--update] [--dry-run]
  cli: CLI only; api: CLI + API; web: CLI + API + WEB.
  Existing installs update automatically and retain their profile.
  --update never downloads game assets or replaces engines.
  --dry-run prints the detected plan without changing anything.
HELP
}
TASK_DRY_RUN=0
while (( $# )); do
  case "$1" in
    --mode) [[ $# -ge 2 ]] || { usage; exit 2; }; TASK_MODE="$2"; shift 2 ;;
    --update) TASK_UPDATE=yes; shift ;;
    --dry-run) TASK_DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
TASK_EXISTING_MODE=cli
if [[ -f /etc/systemd/system/mbii-api.service ]]; then TASK_EXISTING_MODE=api; fi
if [[ -f /etc/systemd/system/mbii-web.service ]]; then TASK_EXISTING_MODE=web; fi
if [[ -f "$TASK_PROFILE_FILE" ]]; then TASK_EXISTING_MODE="$(cat "$TASK_PROFILE_FILE")"; fi
TASK_EXISTING=0
if [[ -f "$TASK_PROFILE_FILE" || -f "$TASK_REPO_DIR/mbiiez.conf" || -x /opt/openjk/venv/bin/python3 || -e /usr/local/bin/mbii || -d /opt/openjk/MBII ]]; then
  TASK_EXISTING=1
fi
if [[ -z "$TASK_MODE" ]]; then
  TASK_MODE="$TASK_EXISTING_MODE"
  if (( ! TASK_EXISTING )) && [[ -t 0 ]] && (( ! TASK_DRY_RUN )); then
    read -r -p 'Install profile (cli, api, web) [cli]: ' TASK_MODE
    TASK_MODE="${TASK_MODE:-cli}"
  fi
fi
case "$TASK_MODE" in cli|api|web) ;; *) usage >&2; exit 2 ;; esac
# Never silently downgrade an existing host and leave services with stale dependencies.
if [[ "$TASK_EXISTING_MODE" == web && "$TASK_MODE" != web || "$TASK_EXISTING_MODE" == api && "$TASK_MODE" == cli ]]; then
  echo 'Profile downgrade requires manually removing the unwanted API/web services first.' >&2
  exit 2
fi
TASK_BOOTSTRAP=0
if (( ! TASK_EXISTING )) && [[ "$TASK_UPDATE" != yes ]]; then TASK_BOOTSTRAP=1; fi
printf 'Profile: %s; game bootstrap: %s; API/web services may restart; games stay running.\n' "$TASK_MODE" "$TASK_BOOTSTRAP"
if (( TASK_DRY_RUN )); then exit 0; fi
(( EUID == 0 )) || { echo 'Run with sudo/root.' >&2; exit 1; }
cd "$TASK_REPO_DIR"
if (( TASK_BOOTSTRAP )); then
  bash "$TASK_REPO_DIR/deploy/bootstrap-game.sh"
elif [[ ! -x /opt/openjk/venv/bin/python3 ]]; then
  # A restored config is still an update: prepare Python, never touch the game install.
  apt-get update
  apt-get install -y python3-venv python3-dev build-essential
  python3 -m venv /opt/openjk/venv
fi
/opt/openjk/venv/bin/python3 -m pip install -r "$TASK_REPO_DIR/requirements.lock"
/opt/openjk/venv/bin/python3 -m pip check
if [[ ! -f mbiiez.conf ]]; then cp mbiiez.conf.example mbiiez.conf; fi
cat > /usr/local/bin/mbii <<EOF
#!/usr/bin/env bash
exec /opt/openjk/venv/bin/python3 "$TASK_REPO_DIR/mbii.py" "\$@"
EOF
chmod 755 /usr/local/bin/mbii
case "$TASK_MODE" in
  api) bash "$TASK_REPO_DIR/install_api.sh" ;;
  web) bash "$TASK_REPO_DIR/install_web.sh" ;;
esac
printf '%s\n' "$TASK_MODE" > "$TASK_PROFILE_FILE"
printf 'MBIIEZ %s installed/updated. Instance configs, keys, users, databases and game processes preserved.\n' "$TASK_MODE"
