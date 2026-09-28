# Credit System (Economy) Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#economy--credit-system).
On any other engine it does nothing.

The engine's economy: players register an account (`!register`, `!login`), earn credits for kills and
rounds, check them with `!balance`, spend them in the `!buy` shop and put bounties on each other
(`!bounty`, then `!<n> <credits>`). With the bar on, `!bar` lists drinks that do something (shrink, grow, get drunk,
super speed, reversed controls...) and make you glow while they work; `!bar <number>` orders one. Accounts and balances are shared across every server on the machine.
The engine's README has the full player guide and shop catalog.

The plugin:

- writes the economy cvars into the server config at startup, and re-applies them every minute
- adds an **Economy** page under the instance in the web panel: every registered account and its balance
  (never PINs or hashes), searchable, with a **Give Credits** form (positive or negative amounts) that edits
  the stored balance directly by account handle, so it works for offline players too
- adds one line to Auto Messages describing what's switched on

## Configuration

Everything is a cvar, set through `cvars`:

```json
"plugins": {
    "creditsystem": {
        "cvars": {
            "g_creditSystemEnable": "1",
            "g_economyShopEnable": "1",
            "g_economyBountyEnable": "1",
            "g_shopCost_rocket_launcher": "50",
            "g_shopCost_minigun": "0"
        }
    }
}
```

| Cvar | Plugin default | Meaning |
|---|---|---|
| `g_creditSystemEnable` | `"1"` | Master switch: accounts, earning, `!balance`. The Economy page only shows while this is `1`. |
| `g_economyShopEnable` | `"0"` | The `!buy` shop |
| `g_economyBountyEnable` | `"0"` | Bounties |
| `g_economyBarEnable` | `"0"` | The `!bar` drinks menu |
| `g_economyRegisterBonus` | `"100"` | Credits given once when a player `!register`s a new account. `"0"` for none. |
| `g_barCost_<drink>` | engine defaults | Price per drink. `"0"` takes it off the menu. |
| `g_shopCost_<item>` | engine defaults | Price per item. `"0"` removes it from the shop. |

Values are strings, as they're written straight into the server config.

**Give Credits works for online players too**: a logged-in session picks up changes to its stored balance
within about 5 seconds (and before any `!balance`, `!buy` or `!bar`), and tells the player they were topped up.
