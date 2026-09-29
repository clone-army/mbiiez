# Credit System (Economy) Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK#economy--credit-system).
On any other engine it does nothing.

The engine's economy: players register an account (`!register`, `!login`), earn credits for kills and
rounds, check them with `!balance`, spend them in the `!buy` shop and put bounties on each other
(`!bounty`, then `!<n> <credits>`). With the bar on, `!bar` lists drinks that do something (shrink, grow, get drunk,
super speed, reversed controls, death sticks, spice...), most with an effect everyone can see; `!bar <number>` orders one. Accounts and balances are shared across every server on the machine.
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
| `g_economyJukeboxEnable` | `"0"` | The `!jukebox`: pay to change the music for everyone |
| `g_jukeboxCost` | `"10"` | Price of a jukebox track |
| `g_jukeboxAutoplay` | `"0"` | Random tracks whenever nobody's pick is playing; picks play in full, then random carries on |
| `g_jukeboxAutoplayMax` | `"300"` | Longest a random track plays, in seconds (`"0"` = the whole track) |
| `g_jukeboxCooldown` | `"60"` | Seconds a track plays before anyone can change it |
| `g_economyPazaakEnable` | `"0"` | `!pazaak <player> <credits>`: Pazaak against another player, winner takes the pot |
| `g_economyRaffleEnable` | `"0"` | The `!raffle` |
| `g_economyBetEnable` | `"0"` | `!bet` on duels in progress |
| `g_betWindowSeconds` | `"30"` | How long a duel opened with `!bet start` takes bets, with both fighters frozen |
| `g_betWinBonus` | `"20"` | Flat bonus a winning bet earns on top of its share of the losing bets, capped at the stake (`"0"` = none) |
| `g_betLoserRefund` | `"25"` | If nobody backed the winner, losing bets get this percent back (the rest is gone) |
| `g_betMax` | `"100"` | Most one player can bet on one duel (`"0"` = no limit) |
| `g_economyBlackjackEnable` | `"0"` | `!blackjack <credits>`: a hand against the dealer; blackjack pays 3:2 |
| `g_blackjackMaxBet` | `"50"` | Most credits one blackjack hand can bet |
| `g_economyChanceEnable` | `"0"` | `!chance <player> <credits>`: they pick red or blue, the server rolls, winning colour takes the pot |
| `g_raffleIntervalMinutes` | `"60"` | Minutes between draws, on the clock (60 = on the hour) |
| `g_raffleOpenMinutes` | `"10"` | Minutes before each draw that tickets go on sale |
| `g_raffleTicketPrice` | `"5"` | Credits per ticket |
| `g_raffleMinEntrants` | `"5"` | Different players who must enter, or everyone is refunded |
| `g_economyLoginReminder` | `"0"` | Seconds after joining to privately remind a player who hasn't logged in to `!register`/`!login`, naming the welcome bonus and what's on (`"0"` = off) |
| `g_economyDailyBonus` | `"25"` | Credits for the first `!login` in any 24 hours, on any server (`"0"` = off) |
| `g_economyRegisterBonus` | `"100"` | Credits given once when a player `!register`s a new account. `"0"` for none. |
| `g_barTabMinutes` | `"5"` | Minutes of drinking that count towards the three below |
| `g_barPassOutDrinks` | `"8"` | Drinks that knock you out (`"0"` = never) |
| `g_barPoisoningDrinks` | `"10"` | Drinks that kill you with alcohol poisoning (`"0"` = never) |
| `g_barSpiceOverdose` | `"3"` | Spice that kills you with an overdose (`"0"` = never) |
| `g_barCost_<drink>` | engine defaults | Price per drink. `"0"` takes it off the menu. |
| `g_shopCost_<item>` | engine defaults | Price per item. `"0"` removes it from the shop. |

Values are strings, as they're written straight into the server config.

**Give Credits works for online players too**: a logged-in session picks up changes to its stored balance
within about 5 seconds (and before any `!balance`, `!buy` or `!bar`), and tells the player they were topped up.

## AI bartender (`!bartender`)

Players ask the Cantina's bartender anything with `!bartender <question>` (or `!barkeep`) and a grumpy Mos Eisley
barkeep answers in chat, knowing the drinks menu, prices and every economy command that's switched on here. It uses
Claude's cheapest model (`claude-haiku-4-5-20251001`) through the Anthropic API, and is on only when there's a key:

```json
"creditsystem": {
    "bartender": {
        "api_key": "sk-ant-...",
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 120,
        "personality": ""
    }
}
```

| Key | Default | Meaning |
|---|---|---|
| `api_key` | | Anthropic API key; blank or missing = no bartender |
| `enabled` | `true` | `false` turns it off without removing the key |
| `model` | `claude-haiku-4-5-20251001` | Any Claude model ID |
| `max_tokens` | `120` | Longest answer; chat only fits a couple of sentences anyway |
| `personality` | | Extra character notes added to the bartender's instructions |

Each question costs the player `g_bartenderCost` credits (default 5), refunded if the API fails or doesn't answer
within 60 seconds. `g_bartenderCooldown` (60) is the wait between one player's questions, `g_bartenderDailyCap` (300)
the most this server answers a day, and `g_bartenderPublic` (1) shows questions and answers to everyone (0 = only
the asker). The bartender remembers a player's last 3 exchanges for 15 minutes. At roughly $0.001 a question, the
daily cap keeps the bill at a few dollars a month at most; set a spend limit in the Anthropic console as a backstop.
