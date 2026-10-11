#!/usr/bin/env bash
# Install/update application components; game bootstrap runs only on a fresh host.
set -euo pipefail
TASK_REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TASK_PROFILE_FILE="$TASK_REPO_DIR/.install-profile"
TASK_MODE=""
TASK_UPDATE=auto
TASK_ENGINES=""
TASK_SELECT_ENGINES=0
TASK_ENGINE_INSTALL=0
TASK_ENGINE_EXPLICIT=0
TASK_REFRESH_ENGINES=0
usage() {
  cat <<'HELP'
Usage: sudo ./install.sh [--mode cli|api|web] [--update] [--engines openjkded,mbiided,caded] [--choose-engines] [--refresh-engines] [--dry-run]
  cli: CLI only; api: CLI + API; web: CLI + API + WEB.
  Existing installs update automatically and retain their profile.
  --update alone never downloads game assets or replaces engines.
  --engines installs only missing selected engines; defaults: openjkded,mbiided.
  --refresh-engines explicitly stages selected engine updates atomically, without restarts.
  --choose-engines opens the engine checklist; at least one engine is required.
  --dry-run prints the detected plan without changing anything.
HELP
}
TASK_DRY_RUN=0
while (( $# )); do
  case "$1" in
    --mode) [[ $# -ge 2 ]] || { usage; exit 2; }; TASK_MODE="$2"; shift 2 ;;
    --update) TASK_UPDATE=yes; shift ;;
    --engines) [[ $# -ge 2 ]] || { usage; exit 2; }; [[ -n "$2" ]] || { echo "At least one engine is required." >&2; exit 2; }; TASK_ENGINES="$2"; TASK_ENGINE_EXPLICIT=1; TASK_ENGINE_INSTALL=1; shift 2 ;;
    --refresh-engines) TASK_REFRESH_ENGINES=1; TASK_ENGINE_INSTALL=1; shift ;;
    --choose-engines) TASK_SELECT_ENGINES=1; TASK_ENGINE_INSTALL=1; shift ;;
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
if [[ -z "$TASK_ENGINES" ]]; then
  if [[ -f "$TASK_REPO_DIR/.install-engines" ]]; then
    TASK_ENGINES="$(cat "$TASK_REPO_DIR/.install-engines")"
  else
    TASK_ENGINES=openjkded,mbiided
  fi
fi
if (( TASK_BOOTSTRAP )); then
  TASK_ENGINE_INSTALL=1
  if [[ -t 0 ]] && (( ! TASK_DRY_RUN && ! TASK_ENGINE_EXPLICIT )); then TASK_SELECT_ENGINES=1; fi
fi
if (( TASK_SELECT_ENGINES && ! TASK_DRY_RUN )); then
  [[ -t 0 ]] || { echo '--choose-engines requires a terminal; use --engines in automation.' >&2; exit 2; }
  TASK_OPENJK=0; TASK_MBII=0; TASK_CADED=0
  [[ ",$TASK_ENGINES," != *,openjkded,* ]] || TASK_OPENJK=1
  [[ ",$TASK_ENGINES," != *,mbiided,* ]] || TASK_MBII=1
  [[ ",$TASK_ENGINES," != *,caded,* ]] || TASK_CADED=1
  while true; do
    TASK_TICKS=(' ' 'x')
    printf 'Select engines (enter a number to toggle; Enter to accept):\n  1 [%s] openjkded.i386\n  2 [%s] mbiided.i386\n  3 [%s] caded.i386 (download verified GitHub release)\n' "${TASK_TICKS[TASK_OPENJK]}" "${TASK_TICKS[TASK_MBII]}" "${TASK_TICKS[TASK_CADED]}"
    read -r TASK_ENGINE_CHOICE
    case "$TASK_ENGINE_CHOICE" in
      1) TASK_OPENJK=$((1-TASK_OPENJK)) ;;
      2) TASK_MBII=$((1-TASK_MBII)) ;;
      3) TASK_CADED=$((1-TASK_CADED)) ;;
      '') if (( TASK_OPENJK + TASK_MBII + TASK_CADED )); then break; fi; echo 'At least one engine must be selected.' ;;
      *) echo 'Choose 1, 2, 3 or Enter.' ;;
    esac
  done
  TASK_ENGINES=""
  if (( TASK_OPENJK )); then TASK_ENGINES=openjkded; fi
  if (( TASK_MBII )); then TASK_ENGINES="${TASK_ENGINES:+$TASK_ENGINES,}mbiided"; fi
  if (( TASK_CADED )); then TASK_ENGINES="${TASK_ENGINES:+$TASK_ENGINES,}caded"; fi
fi
# Validate without invoking Python before bootstrap has prepared the environment.
case "$TASK_ENGINES" in ''|,*|*,|*,,*) echo 'At least one valid engine is required.' >&2; exit 2 ;; esac
IFS=',' read -r -a TASK_ENGINE_NAMES <<< "$TASK_ENGINES"
TASK_SEEN=,
for TASK_ENGINE_NAME in "${TASK_ENGINE_NAMES[@]}"; do
  case "$TASK_ENGINE_NAME" in openjkded|mbiided|caded) ;; *) echo 'Unknown engine selection.' >&2; exit 2 ;; esac
  [[ "$TASK_SEEN" != *,$TASK_ENGINE_NAME,* ]] || { echo 'Duplicate engine selection.' >&2; exit 2; }
  TASK_SEEN="$TASK_SEEN$TASK_ENGINE_NAME,"
done
printf 'Engines: %s; install missing engines: %s (refresh explicitly requested: %s).\n' "$TASK_ENGINES" "$TASK_ENGINE_INSTALL" "$TASK_REFRESH_ENGINES"
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
if (( TASK_ENGINE_INSTALL )); then
  TASK_ENGINE_ARGS=(--engines "$TASK_ENGINES")
  if (( TASK_REFRESH_ENGINES )); then TASK_ENGINE_ARGS+=(--replace); fi
  /opt/openjk/venv/bin/python3 "$TASK_REPO_DIR/deploy/install-engines.py" "${TASK_ENGINE_ARGS[@]}"
fi
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
printf '%s\n' "$TASK_ENGINES" > "$TASK_REPO_DIR/.install-engines"
printf 'MBIIEZ %s installed/updated. Instance configs, keys, users, databases and game processes preserved.\n' "$TASK_MODE"
