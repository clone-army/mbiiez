# Discord Bot Plugin (experimental)

Connects a Discord bot and relays the instance's in-game chat to a Discord text channel. Works with any
engine. **This plugin is a work in progress**: it has chat relay and test commands only, not the remote
control (restart, change map, kick) described in older docs.

- In-game chat is posted to any channel whose name ends with `server-<instance>-chat`, e.g.
  `ca-server-open-chat` for the `open` instance.
- The bot needs the **Message Content** intent enabled in the Discord developer portal and access to that
  channel.

## Configuration

```json
"plugins": {
    "discord_bot": { "token": "your-bot-token" }
}
```

| Key | Meaning |
|---|---|
| `token` | Discord bot token |

Each instance with this plugin runs its own bot connection. To relay several servers, enable it on each one
and create a channel per instance.
