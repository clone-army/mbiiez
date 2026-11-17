# VPN Shield Plugin

Kicks players who connect through a VPN or proxy, and optionally anyone on a mobile connection (e.g. a tethered phone). Works with any engine.

When a player connects, their IP is checked (in the background, so joining isn't slowed down) against
[proxycheck.io](https://proxycheck.io) (needs an API key). If it's flagged as a VPN/proxy/Tor - or, with
`block_mobile` on, as a mobile (wireless) network - the player is warned privately for the last 10 seconds
of a 60-second countdown, then kicked, and the server announces it. Detections are written to the instance log.
If proxycheck.io can't be reached, the player is let through.

## Configuration

```json
"plugins": {
    "shield": { "proxycheck_apikey": "your-key", "block_mobile": 0 }
}
```

| Key | Meaning |
|---|---|
| `proxycheck_apikey` | Your proxycheck.io API key |
| `block_mobile` | `1` also kicks players on mobile/cellular connections. Default `0` |

Also editable under **Settings → VPN Shield** in the web panel. There's no allow-list, so a player on a
flagged connection can't join until they switch connection.
