# MBIIEZ CLI, API and WEB

MBIIEZ runs as three components. **CLI** manages the local engines and plugins. **API** exposes that node's operations with service keys. **WEB** authenticates people and calls API agents, including the local agent. EU needs CLI and API only. There is no second implementation for remote instances.

Each node owns its configs, runtime files, database, plugins, accounts, bans and game assets. Accounts and bans are shared across instances on a node, not automatically across different nodes. The web panel's users, signing secret and node credentials belong to WEB.

## Native installation

Install MBIIEZ normally. Install/start the API without touching game processes:

```sh
sudo ./install_api.sh
```

This installs a loopback-only `mbii-api` systemd service and registers an NA local node for WEB if none exists. `install_web.sh` now calls this first. A running legacy web service needs a web-only restart after upgrading. Check game processes' cgroups before stopping any legacy service: old installations may have launched games inside its cgroup.

On an API-only machine, create a key from its CLI:

```sh
mbii api keygen --scope admin --label central-web
mbii api keys
mbii api revoke KEY_ID
mbii api serve --host 127.0.0.1 --port 8081
```

The new key is printed once. Copy it into WEB's **API Nodes** page. Use `viewer`, `mod` or `admin` scopes. Generate a replacement, update the panel, test it, then revoke the old ID. The agent stores only digests. The panel must store the usable service credential in its owner-only `web_nodes.json`; it is never returned to the browser. `MBIIEZ_STATE_DIR` defaults to `/var/lib/mbiiez`.

Use a private VPN/LAN endpoint or a TLS reverse proxy. Public HTTP endpoints are rejected by the node registry. Certificate verification is always enabled and redirects are refused. Bind API to loopback behind a local proxy, or a private interface when the proxy is on another host. Do not forward its raw port from the internet.

## API v1 contract

All `/api/v1/*` routes require `Authorization: Bearer KEY`. `/health` contains no server data and is unauthenticated. Acting user and role headers (`X-MBIIEZ-Actor`, `X-MBIIEZ-Role`) are trusted assertions from the service key holder; the role can restrict the key but cannot elevate it. Keep human authentication in WEB.

| Endpoint | Method | Scope | Response / input |
|---|---|---|---|
| `/api/v1/info` | GET | viewer | API major version, git revision, capabilities |
| `/api/v1/instances` | GET | viewer | Instance names on this node |
| `/api/v1/instances/{name}/status` | GET | viewer | Structured runtime status |
| `/api/v1/instances/{name}/players` | GET | viewer | Current players |
| `/api/v1/instances/{name}/{start,stop,restart}` | POST | admin | `{ "force": false }`; 202 means queued, poll status |
| `/api/v1/instances/{name}/config` | GET / PUT | admin | `{ "content": "JSON text" }`; saving never restarts engines |
| `/api/v1/instances/{name}/rcon` | POST | admin | `{ "command": "status" }` |
| `/api/v1/chat` | GET / POST | viewer / mod | GET filters instance/limit; POST instance/message |
| `/api/v1/logs` | GET | viewer | Filters instance/limit/search/tag; limit capped at 500 |
| `/api/v1/menus` | GET | admin | Instance and plugin navigation metadata |
| `/api/v1/views/{name}` | POST | per view | `{ "args": [...] }`; presentation data for existing WEB pages |
| `/api/v1/actions/{operation}` | POST | per action | `{ "args": [...] }`; allowlisted plugin/config/moderation operations |

The complete view/action contract and minimum scopes are in `mbiiez/api/backend.py`. These are explicit allowlists, never arbitrary module/method execution. Configs and plugin descriptions stay on the API agent, which renders plugin-specific template sections into its response; WEB renders the common page shell. This lets nodes supply their installed plugins without installing those plugins' runtime dependencies in a separate panel.

WEB uses request-specific node identity (`node` query parameter or `X-MBIIEZ-Node` header). Navigation and fetch calls retain the page's node identity even if another browser tab changes the session's default. Instance names can be the same on different nodes. Offline API errors become HTTP 502 and leave other nodes selectable. The Nodes page checks the API major version and shows online/offline status and revision. API reads have timeouts, and failed authentication attempts are bounded per peer. Mutations are audited without request bodies/credentials; install `deploy/api-logrotate` under `/etc/logrotate.d/` on native agents.

Raw RCON is admin-only because it can bypass dedicated moderation permissions. Starts/stops run outside the agent's cgroup using a transient systemd service, or outside its worker in a supervised container. Occupied servers need an explicit `force: true`; default requests refuse to interrupt players. The CLI independently rechecks occupancy. Restarting an API worker does not restart a running game. Restarting the whole node container **does** interrupt its engines.

## Docker

The Dockerfile has separate `node` (CLI + API + built caded engine) and `web` targets. Its engine stage clones the OpenJK fork at `OPENJK_REF` and builds without running `build.sh` or restarting any production server. No credentials or runtime configs enter the image. Build from a checkout, or directly from git:

```sh
git clone -b test https://github.com/clone-army/mbiiez
cd mbiiez
docker build --target node -t mbiiez-node:latest .
# Or: docker build --target node -t mbiiez-node:latest https://github.com/clone-army/mbiiez.git#test
```

`compose.eu.yml` runs only CLI/API/game on EU; `compose.web.yml` runs a standalone panel. Configs, logs, accounts and SQLite files persist in mounted state directories. Supply valid MBII and Jedi Academy assets under `eu-game/MBII` and `eu-game/base` (for this deployment they were copied from NA). Do not copy NA's accounts, bans, statistics or runtime files just to create a new instance. Place its instance config in `eu-state/configs/`, generate a new RCON password, and adjust the public hostname. The image does not embed redistributable game data or auto-download it during build.

```sh
# Generate a service key before starting the node; stores its digest in the state volume.
docker compose -f compose.eu.yml run --rm node mbii api keygen --scope admin --label na-web
MBIIEZ_API_BIND=10.25.0.166 docker compose -f compose.eu.yml up -d
# Register the private URL or TLS proxy URL on the central panel's API Nodes page.
```

Host UDP 29072 maps to the Legends server, while host TCP 18081 maps to its API. By default the API maps to loopback; set `MBIIEZ_API_BIND` to the host LAN IP for an external LAN proxy. Forward **UDP** for the game on your router; HTTP nginx proxying handles the API only. API autostart defaults off for ad hoc containers; the EU compose explicitly enables starting configured instances on container boot. API process restart is independent of that boot action.

Example nginx TLS location (certificate/server_name configuration belongs to your proxy):

```nginx
location / {
    proxy_pass http://10.25.0.166:18081;
    proxy_set_header Host $host;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 30s;
    client_max_body_size 2m;
}
```

For Nginx Proxy Manager: domain `mb2-eu-api.lcho.me`, HTTP upstream `10.25.0.166`, port `18081`, a valid certificate, force SSL, no caching. Bind the container port to the LAN interface and restrict it to the proxy/VPN peers with your host/network firewall. WEB never disables TLS verification.

## Validation and rollout

`python -m pytest` tests keys, scopes, actor restrictions, path/symlink traversal, safe dispatch, config saves without restarts, occupied-server rejection, auth throttling, auditing, node routing and CSRF. Live rollout should first test read-only status/config/plugin endpoints on NA, then enable the local agent and switch only the web service. Preserve existing game PIDs/start times and verify them afterwards. Keep a previous git revision for rollback; rollback WEB code and restart WEB only, leaving game engines untouched.
