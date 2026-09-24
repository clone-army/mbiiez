# VPN Shield Plugin

Kicks players who connect through a VPN or proxy. Works with any engine.

When a player connects, their IP is checked (in the background, so joining isn't slowed down) against:

- [ip-api.com](https://ip-api.com) (no key needed)
- [ipgeolocation.io](https://ipgeolocation.io) (needs a free API key)

If either says VPN/proxy, the player is warned privately for the last 10 seconds of a 60-second countdown,
then kicked, and the server announces it. Detections are written to the instance log.

## Configuration

```json
"plugins": {
    "shield": { "ipgeolocation_apikey": "your-key" }
}
```

| Key | Meaning |
|---|---|
| `ipgeolocation_apikey` | Your ipgeolocation.io API key |

Also editable under **Settings → VPN Shield** in the web panel. There's no allow-list, so a player on a
flagged connection can't join until they turn their VPN off.
