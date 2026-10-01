# Accounts Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK).

Player accounts for every server on the box: `!register <handle> <pin>` makes one, `!login <handle> <pin>`
logs back in. One file in the game folder (`economy_accounts.dat`) holds them all, so an account works on
every server. Other plugins build on it - **Credits** (and so everything that spends credits) and **Holotable**
need it; **Social** and **Stats** use it when it's on.

Adds the **Accounts** page to the web panel (outside any one instance - accounts are shared): every account,
who's an admin (tick the box - admins run `!wp` and `!ht play`), and unlocking accounts that got
locked by wrong PINs.

Engine: `g_accountsEnable 1` (set by this plugin).

| Setting | Default | |
|---|---|---|
| `cvars.g_economyLoginReminder` | `0` | Seconds after joining to remind a player who hasn't logged in (0 = off) |

Also editable under **Settings** in the web panel.
