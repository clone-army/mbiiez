# MBIIEZ CLI, API and WEB

MBIIEZ runs as three components. **CLI** manages the local engines and plugins. **API** exposes that node's operations with service keys. **WEB** authenticates people and calls API agents, including the local agent. EU needs CLI and API only. There is no second implementation for remote instances.

Each node owns its configs, runtime files, database, plugins and game assets. CADED accounts, wallets, statistics and moderation can join Local's shared authority through the Nodes checkbox. The web panel's users, signing secret and node credentials belong to WEB.

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

## CADED shared data

Enable the remote node's **Sync CADED data** checkbox to attach it to Local. Do not tick
Local: it is the authority. Require the installed and every running CADED binary to contain
`MBIIEZ_SHARED_LEDGER_V2`. Old engines cannot share a wallet safely; stage the new binary
and wait for planned game restarts. Agents check `/proc/<pid>/exe`, not just the disk path.

Initial snapshots are backed up privately. Local wins matching identities; remote-only
records are retained. Existing matching counters/balances are ambiguous and are not summed.
Every later earning, debit, stats delta and moderation change has a unique durable operation
ID. Local applies each exactly once in a SQLite transaction, then agents project its state
into CADED's legacy files under the same native locks. Local's daily claim history and engine
admin flags are included. PIN hashes and usable peer credentials never reach browsers.

Debits reserve centrally before game effects. A durable commit makes a purchase final;
cancellations refund uncommitted reservations once, including lost-response requests.
Recovery checks process identity and drains its journal before refunding a crashed game's
uncommitted purchase. Ban tombstones protect removals against stale peers. Positive credits
and gameplay deltas queue locally during outages. Login, registration and spending require
Local to be reachable. This deliberately prevents two regions spending the same stale funds.

API agents run the exchange worker (about one second), independent of WEB's status monitor.
Private outboxes compact only when fully acknowledged and without pending reservations;
compaction retains the inode and has durable crash recovery. Preserve the state volume.
The authoritative database is `shared-ledger.sqlite` in `MBIIEZ_STATE_DIR`; take a consistent
SQLite backup, including its WAL state, rather than copying an active database file alone.

| Endpoint | Method | Scope / purpose |
|---|---|---|
| `/api/v1/shared/status` | GET | admin; enrollment, engine readiness and last exchange status |
| `/api/v1/shared/configure` | POST | admin; `{ "enabled": true, "authority": true, "peer": "local" }` on Local, or `{ "enabled": true, "peer": "eu", "hub": "https://panel.example.com", "token": "PEER_TOKEN" }` on EU |
| `/api/v1/shared/peer` | POST | admin on Local; `{ "peer": "eu", "enabled": true }` prints a new peer credential once; `false` revokes it |
| `/api/v1/shared/engine` | POST | engine/admin service key; native login, registration, balance and wallet reservation |
| `/api/v1/shared/exchange` | POST | dedicated peer credential; `{ "events": [...] }`, requires `X-MBIIEZ-Peer` and Bearer peer token |
| `/shared/v1/exchange` | POST | same peer-authenticated exchange on API, or authenticated WEB relay to Local API |

The panel configures these automatically. API-only groups can configure Local, enroll a peer,
then configure the remote using the authority's public HTTPS **API** URL as `hub`. WEB is not
required in that deployment. CLI-generated admin keys authenticate the configuration calls;
the engine key is generated automatically and restricted to engine operations. Never supply
an admin key as the peer token. Peer keys are separately hashed at Local and can be rotated.

With WEB's relay, set `MBIIEZ_PUBLIC_WEB_URL` to its public HTTPS origin if proxy headers do
not supply it. Proxy `/shared/v1/exchange`, preserve Authorization and `X-MBIIEZ-Peer`,
allow 2 MB requests and disable caching. The API-only direct alias uses the same route.
Do not expose raw HTTP over the internet.

Unlinking requires the remote node's CADED processes to be stopped during a planned window
and the outbox to be settled. MBIIEZ never stops them automatically. Cached account data
remains as a standalone copy. Local remains the authority. Drain/unlink before deleting a
node. URL changes revoke the old peer credential and require reapproval.

### Advanced snapshot transfer

`POST /api/v1/sync/export` (admin) takes `{ "datasets": ["accounts", "guid_bans", "ip_bans", "stats"] }`.
`POST /api/v1/sync/import` (admin) takes `{ "snapshot": {...}, "preview": true }`; preview is
the default, `false` applies. `GET /api/v1/sync/info` reports native/shared compatibility.
Imports are blocked on shared nodes. For unlinked nodes these are reviewed, one-time merges:
existing accounts/PINs/balances win, stats use highest counters, bans union with local notes.
This operation is distinct from a shared wallet. Owner-only backups use `sync_backups/`;
private WEB previews expire after ten minutes and are bound to admin and destination URL.
Native text uses byte-preserving Latin-1 inside JSON; IP JSON uses UTF-8.

Connection/chat history and historical casino settlement logs remain per node. Gambling
wallet changes are shared; the public dashboard does not add repeated global gameplay totals.

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
