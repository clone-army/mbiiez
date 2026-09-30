# Casino Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK). Needs the **Credits** plugin.

Games for credits, each switched on or off in its settings:

- **Blackjack** (`!blackjack <credits>`) against the house (`g_economyBlackjackEnable`, `g_blackjackMaxBet`)
- **Pazaak** (`!pazaak <player> <credits>`) and **Chance** (`!chance <player> <credits>`) against each other
- **Duel betting** (`!bet`) - duellists freeze while everyone bets (`g_economyBetEnable`, `g_betWindowSeconds`,
  `g_betMax`, `g_betWinBonus`, `g_betLoserRefund`)
- **Raffle** (`!raffle`) on a timer (`g_economyRaffleEnable`, `g_raffleIntervalMinutes`, `g_raffleOpenMinutes`,
  `g_raffleTicketPrice`, `g_raffleMinEntrants`)

All settings are under `cvars`. Blackjack, pazaak, chance and betting are on by default; the raffle isn't.

Also editable under **Settings** in the web panel.
