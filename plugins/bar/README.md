# Cantina Bar Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK). Needs the **Credits** plugin.

`!bar` - a drinks menu for credits: shrink, spin, get drunk (worse with every glass), low gravity, super
speed... too many and you pass out or worse. Each drink's price is a setting (`cvars.g_barCost_<drink>`, 0
takes it off the menu), as are the tab window and the pass-out / poisoning / overdose counts.

With an Anthropic API key (`bartender.api_key`), `!bartender <question>` asks an AI bartender, who answers in
character for a few credits (`bartender.model`, `max_tokens`, `personality`; `cvars.g_bartenderCost`,
`g_bartenderCooldown`, `g_bartenderDailyCap`, `g_bartenderPublic`).

Engine: `g_economyBarEnable 1`, and `g_economyBartenderEnable` while there's a key (set by this plugin).

Also editable under **Settings** in the web panel.
