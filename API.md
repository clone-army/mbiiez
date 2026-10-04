# MBIIEZ CLI, API and WEB

MBIIEZ runs as three components. **CLI** manages the local engines and plugins. **API** exposes that node's operations with service keys. **WEB** authenticates people and calls API agents, including the local agent. EU needs CLI and API only. There is no second implementation for remote instances.

Each node owns its configs, runtime files, database, plugins, accounts, bans and game assets. Accounts and bans are shared across instances on a node, not automatically across different nodes. The web panel's users, signing secret and node credentials belong to WEB.

## Native installation

Choose a profile on a fresh host, or update/migrate an existing installation:

```sh
sudo ./install.sh --mode api   # CLI + API
sudo ./install.sh --mode web   # CLI + API + WEB
# After git pull --ff-only:
sudo ./install.sh --update
```

The installer retains the profile on updates, installs locked dependencies and refreshes API/web
services without touching game files or game processes. Existing legacy web installations migrate
to WEB + API. Only WEB setup creates a local panel service key, and existing node registrations
are preserved. Native API binding defaults to loopback port 8081; override host/port in
`/etc/default/mbii-api` using `MBIIEZ_API_HOST` and `MBIIEZ_API_PORT`. Keep the central panel's
local agent on loopback port 8081. See the [README multi-server guide](README.md#multiple-servers-in-one-web-interface).

On an API-only machine, create a key from its CLI:

```sh
mbii api keygen --scope admin --label central-web
mbii api keys
mbii api revoke KEY_ID
mbii api serve --host 127.0.0.1 --port 8081
```

The new key is printed once. Copy it into WEB's **Nodes** page. Use `viewer`, `mod` or `admin` scopes. Generate a replacement, update the panel, test it, then revoke the old ID. The agent stores only digests. The panel must store the usable service credential in its owner-only `web_nodes.json`; it is never returned to the browser. `MBIIEZ_STATE_DIR` defaults to `/var/lib/mbiiez`.

Use a private VPN/LAN endpoint or a TLS reverse proxy. Public HTTP endpoints are rejected by the node registry. Certificate verification is always enabled and redirects are refused. Bind API to loopback behind a local proxy, or a private interface when the proxy is on another host. Do not forward its raw port from the internet.

## API v1 contract

All `/api/v1/*` routes require `Authorization: Bearer KEY`. `/health` contains no server data and is unauthenticated. Acting user and role headers (`X-MBIIEZ-Actor`, `X-MBIIEZ-Role`) are trusted assertions from the service key holder; the role can restrict the key but cannot elevate it. Keep human authentication in WEB.

| Endpoint | Method | Scope | Response / input |
|---|---|---|---|
| `/api/v1/info` | GET | viewer | API major version, software version, git revision, capabilities |
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

WEB uses request-specific node identity (`node` query parameter or `X-MBIIEZ-Node` header). Navigation and fetch calls retain the page's node identity even if another browser tab changes the session's default. Instance names can be the same on different nodes. Offline API errors become HTTP 502 and leave other nodes selectable. The Nodes page checks the API major version and shows online/offline status, software version differences and revision. API reads have timeouts, and failed authentication attempts are bounded per peer. Mutations are audited without request bodies/credentials; install `deploy/api-logrotate` under `/etc/logrotate.d/` on native agents.

Raw RCON is admin-only because it can bypass dedicated moderation permissions. Starts/stops run outside the agent's cgroup using a transient systemd service, or outside its worker in a supervised container. Occupied servers need an explicit `force: true`; default requests refuse to interrupt players. The CLI independently rechecks occupancy. Restarting an API worker does not restart a running game. Restarting the whole node container **does** interrupt its engines.

## CADED data sync

WEB relays a versioned snapshot from the chosen source agent to the destination. Both keys and
acting roles must be `admin`. The source hashes/records never reach browser JavaScript.
Use **Nodes → Sync CADED data** to opt nodes into automatic one-minute merging. The WEB
service elects a single scheduler across workers. For a one-time reviewed transfer, open
**Advanced: manual data transfer → Preview sync → Apply reviewed sync**. Previews are private, bounded,
expire after ten minutes and are bound to the acting admin and destination URL.
Both agents need this API version with `data_sync` capability. A configured CADED instance is
required for accounts, stats and GUID bans; IP bans also work with the other engines.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/sync/info` | GET | Available datasets, CADED instances and live stats compatibility |
| `/api/v1/sync/export` | POST | `{ "datasets": ["accounts", "guid_bans", "ip_bans", "stats"] }`; returns a private protocol-1 snapshot |
| `/api/v1/sync/import` | POST | `{ "snapshot": {...}, "preview": true, "automatic": false }`; preview is the default; `false` performs the merge; automatic imports retain local unban history |

Accounts copy missing identities only; existing credentials and balances are never overwritten.
Stats merge each counter by maximum, not sum, making repeated transfers idempotent.
GUID/IP bans merge by union, keeping destination metadata. Ban removal, admin grants, daily
rewards, account deletion, SQLite logs and continuous shared currency are outside this operation.
Recent associations for banned GUIDs accompany GUID bans, under CADED's shared GUID lock.
This supports CADED's seven-day IP linking despite address-salted GUIDs.

Native engine text files use byte-preserving Latin-1 strings inside JSON snapshots;
this preserves names containing invalid UTF-8. IP-ban JSON remains UTF-8. Backups include
the encoding needed to reconstruct the original bytes.

Imports use the engine's same-inode account/stats locks and GUID/IP lock files. Each changed file
has an owner-only backup in `sync_backups`. Multi-file imports are not one transaction: after
a filesystem/network failure, preview again before retrying; merge operations are idempotent.
IP propagation may disconnect banned players, but never restarts engines.
Live stats imports inspect `/proc/<pid>/exe`, so replacing the on-disk binary does not pretend
already-running old engines support transaction locking. Install the new release atomically
with `./install.sh --update --engines caded --refresh-engines` and wait for planned restarts.

## Docker

The Dockerfile has separate `node` (CLI + API + built caded engine) and `web` targets. Its engine stage clones the OpenJK fork at `OPENJK_REF` and builds without running `build.sh` or restarting any production server. No credentials or runtime configs enter the image. Build from a checkout, or directly from git:

```sh
git clone -b test https://github.com/clone-army/mbiiez
cd mbiiez
docker build --build-arg MBIIEZ_REVISION="$(git rev-parse HEAD)" --target node -t mbiiez-node:latest .
# Or: docker build --target node -t mbiiez-node:latest https://github.com/clone-army/mbiiez.git#test
```

`compose.eu.yml` runs only CLI/API/game on EU; `compose.web.yml` runs a standalone panel. Configs, logs, accounts and SQLite files persist in mounted state directories. Supply valid MBII and Jedi Academy assets under `eu-game/MBII` and `eu-game/base` (for this deployment they were copied from NA). Do not copy NA's accounts, bans, statistics or runtime files just to create a new instance. Place its instance config in `eu-state/configs/`, generate a new RCON password, and adjust the public hostname. The image does not embed redistributable game data or auto-download it during build.

```sh
# Generate a service key before starting the node; stores its digest in the state volume.
docker compose -f compose.eu.yml run --rm node mbii api keygen --scope admin --label na-web
MBIIEZ_API_BIND=10.25.0.166 docker compose -f compose.eu.yml up -d
# Register the private URL or TLS proxy URL on the central panel's Nodes page.
```

The compose files use a dedicated configurable subnet (`MBIIEZ_DOCKER_SUBNET`, default `10.78.0.0/24`) to work on hosts whose automatic Docker address pools are full. Change it if that subnet overlaps your network.

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

## Public statistics

`GET /api/v1/public/stats` requires a viewer-or-higher API key. It returns a sanitized
projection of gameplay counters, a bounded casino results window and public game-query
status, cached for 60 seconds. It never reads accounts or moderation data.

The WEB routes `GET /public` and `GET /public/data?node=<id>` allow anonymous access.
WEB keeps node credentials server-side, caches summaries per node and hides raw upstream
errors. Public node selection does not change an administrator's active node or session.
Private live server cards are excluded through `security.server_password` or
`server.public_stats: false`. Per-node shared counters are shown without cross-node sums.
