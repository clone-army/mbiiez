# Accounts Plugin

**Requires the `caded.i386` engine** from [clone-army/OpenJK](https://github.com/clone-army/OpenJK).

Player accounts for every server on the box: `!register <handle> <pin>` makes one, `!login <handle> <pin>`
logs back in. One file in the game folder (`economy_accounts.dat`) holds them all, so an account works on
every server. Other plugins build on it - **Credits** (and so everything that spends credits) and **Holotable**
need it; **Social** and **Stats** use it when it's on.

Adds the **Accounts** page to the web panel's main menu (accounts are shared by every server): every account with
its credits, who's an admin (the switch - admins run `!wp` and `!ht play`) and whether it's locked by wrong PINs;
searchable, filtered to admins or locked accounts, sorted by any column. Each account's buttons add or take away
credits, change its PIN (hashed as the engine does; it unlocks the account too), unlock it, or delete it.

Engine: `g_accountsEnable 1` (set by this plugin).

| Setting | Default | |
|---|---|---|
| `cvars.g_economyLoginReminder` | `0` | Seconds after joining to remind a player who hasn't logged in (0 = off) |

Also editable under **Settings** in the web panel.
