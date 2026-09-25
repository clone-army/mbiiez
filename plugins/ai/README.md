# AI Assistant Plugin

An in-game chat assistant backed by [OpenRouter](https://openrouter.ai), so any model OpenRouter offers can be
used. Players ask it questions with a chat command, and it can also mock players who kill themselves.
Works with any engine.

Requests run in the background, so the server never waits on the AI. The assistant is given MBII background
knowledge from `game_context.txt` in this folder (edit it to teach it about your community), plus your
`instruction` and `personality`.

## Configuration

```json
"plugins": {
    "ai": {
        "enabled": true,
        "openrouter_api_key": "sk-or-...",
        "ai_name": "R2",
        "command": "!ai",
        "model": "anthropic/claude-3.5-sonnet",
        "personality": "A sarcastic astromech droid.",
        "cooldown_seconds": 5,
        "max_tokens": 150,
        "temperature": 0.7,
        "public_replies": true,
        "death_commentary": true
    }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Must be `true` for the plugin to do anything |
| `openrouter_api_key` | | Your OpenRouter API key (required) |
| `ai_name` | `Assistant` | Name the assistant answers as |
| `command` | `!ai` | Chat command, e.g. `!ai what's the best class?` |
| `model` | `anthropic/claude-3.5-sonnet` | Any OpenRouter model ID |
| `instruction` | built-in | System instruction; replaces the default |
| `personality` | | Added to the instruction |
| `cooldown_seconds` | `5` | Minimum time between one player's questions |
| `max_tokens` | `150` | Maximum reply length. Keep it short: game chat lines are small. |
| `temperature` | `0.7` | Creativity |
| `public_replies` | `true` | Reply in public chat (`false` = privately to the player who asked) |
| `death_commentary` | `true` | Publicly mock suicides and environmental deaths (falls, own rockets, being crushed...) |

OpenRouter bills per request, so set `cooldown_seconds` with your budget in mind.
