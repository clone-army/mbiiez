# Plugins

Each folder here is one plugin: `plugins/<name>/<name>.py`, enabled on an instance by adding
`"<name>": { ...settings... }` under `plugins` in its config (or ticking it under **Settings → Plugins** in
the web panel).

- **What each included plugin does**, and which ones need the `caded.i386` engine from
  [clone-army/OpenJK](https://github.com/clone-army/OpenJK): see the
  [README's plugin table](../README.md#included-plugins).
- **How to write one** (events, services, engine cvars, web panel settings, menu items and pages): see
  [PLUGINS.md](../PLUGINS.md).

| Folder | Plugin | Needs `caded.i386` |
|---|---|---|
| `rtvrtm/` | Rock the Vote / Rock the Mode | |
| `auto_message/` | Rotating server messages | |
| `auto_map_rotation/` | Next map when the server is idle | |
| `shield/` | VPN / proxy blocking | |
| `anytime_spin/` | MBII `!spin` on any day | |
| `ai/` | AI chat assistant (OpenRouter) | |
| `discord_bot/` | Discord chat relay (experimental) | |
| `accounts/` | Player accounts, logins, admins - the Accounts page | yes |
| `credits/` | Credits, `!balance`, `!gift` - the Credits page (needs accounts) | yes |
| `shop/` | `!buy` (needs credits) | yes |
| `bounties/` | `!bounty` (needs credits) | yes |
| `bar/` | `!bar` drinks and the AI bartender (needs credits) | yes |
| `jukebox/` | `!jukebox` (needs credits) | yes |
| `casino/` | Blackjack, pazaak, chance, betting, raffle (needs credits) | yes |
| `chaos/` | Chaos Mode | yes |
| `gungame/` | Gun Game | yes |
| `killstreak/` | Kill streak callouts | yes |
| `stats/` | `!stats` and the Stats page | yes |
| `holotable/` | Holotable NPC scenarios (`!ht`) | yes |
