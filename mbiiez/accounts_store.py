"""The shared accounts file and admins file, as the caded engine keeps them.

Both live in the game folder (fs_basepath/fs_game - the same for every
instance), so accounts, balances and admins are shared by every server:

  economy_accounts.dat  one account a line:
                        "handle saltHex hashHex credits failedAttempts lockoutUntil"
                        (see SV_EconomyAccountsLoad/Save in the engine's
                        codemp/server/sv_client.cpp). The salt and hash are
                        PIN material and are never shown.
  economy_admins.dat    one admin handle a line (re-read by servers every few
                        seconds).

Writes take the same flock() the engine does, so they're safe alongside
running servers.
"""
import fcntl
import hashlib
import hmac
import os
import time

from mbiiez import settings

ACCOUNTS_FILE = "economy_accounts.dat"
ADMINS_FILE = "economy_admins.dat"
HANDLE_MAX = 23   # ECONOMY_HANDLE_SIZE - 1 in the engine
PIN_LEN = 4       # ECONOMY_PIN_LEN
SALT_SIZE = 16    # ECONOMY_SALT_SIZE


def accounts_path():
    return os.path.join(settings.locations.mbii_path, ACCOUNTS_FILE)


def admins_path():
    return os.path.join(settings.locations.mbii_path, ADMINS_FILE)


def valid_handle(handle):
    handle = str(handle or "")
    return 0 < len(handle) <= HANDLE_MAX and all(c.isalnum() or c == "_" for c in handle)


def read_accounts():
    """[{handle, credits, failed, locked_until}] (no PIN material)."""
    out = []
    try:
        with open(accounts_path(), "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.split()
                if len(parts) != 6:
                    continue
                try:
                    out.append({"handle": parts[0], "credits": int(parts[3]), "failed": int(parts[4]),
                                "locked_until": int(parts[5])})
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return out


def read_admins():
    """Lower-cased admin handles."""
    try:
        with open(admins_path(), "r", encoding="utf-8", errors="ignore") as f:
            return set(w.lower() for w in f.read().split())
    except FileNotFoundError:
        return set()


def set_admin(handle, on):
    if not valid_handle(handle):
        return False, "Not a valid account handle."
    fd = os.open(admins_path(), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+", encoding="utf-8", errors="ignore") as f:
            handles = [w for w in f.read().split() if w.lower() != handle.lower()]
            if on:
                handles.append(handle)
            f.seek(0)
            f.write("".join(h + "\n" for h in handles))
            f.truncate()
    except Exception as e:
        return False, "Could not update admins: {}".format(e)
    return True, "{} is {} an admin.".format(handle, "now" if on else "no longer")


def _edit_account(handle, change):
    """Read-modify-write one account's line under the engine's lock.
    change(parts) edits the 6-part list in place, or returns an error."""
    if not valid_handle(handle):
        return False, "Not a valid account handle."
    try:
        fd = os.open(accounts_path(), os.O_RDWR)
    except FileNotFoundError:
        return False, "No accounts yet - nobody has registered."
    except Exception as e:
        return False, "Could not open the accounts file: {}".format(e)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            found = None
            for n, line in enumerate(lines):
                parts = line.split()
                if len(parts) == 6 and parts[0].lower() == handle.lower():
                    error = change(parts)
                    if error:
                        return False, error
                    lines[n] = " ".join(parts) + "\n"
                    found = parts
                    break
            if found is None:
                return False, "No account called '{}'.".format(handle)
            f.seek(0)
            f.writelines(lines)
            f.truncate()
            return True, found
    except Exception as e:
        return False, "Could not update the accounts file: {}".format(e)


def add_credits(handle, amount):
    def change(parts):
        try:
            parts[3] = str(int(parts[3]) + amount)
        except ValueError:
            return "That account's credits are corrupt."
    ok, result = _edit_account(handle, change)
    if not ok:
        return False, result
    return True, "{} now has {} credits.".format(result[0], result[3])


def unlock(handle):
    """Clears failed PIN attempts and any lockout."""
    def change(parts):
        parts[4] = "0"
        parts[5] = "0"
    ok, result = _edit_account(handle, change)
    if not ok:
        return False, result
    return True, "{} is unlocked.".format(result[0])


def set_pin(handle, pin):
    """A new PIN (4 digits), hashed as the engine does - HMAC-MD5 keyed by a
    fresh random salt (SV_EconomyHashPin) - and the account unlocked."""
    pin = str(pin or "").strip()
    if len(pin) != PIN_LEN or not pin.isdigit():
        return False, "A PIN is {} digits.".format(PIN_LEN)
    salt = os.urandom(SALT_SIZE)
    digest = hmac.new(salt, pin.encode("ascii"), hashlib.md5).hexdigest()

    def change(parts):
        parts[1] = salt.hex()
        parts[2] = digest
        parts[4] = "0"
        parts[5] = "0"
    ok, result = _edit_account(handle, change)
    if not ok:
        return False, result
    return True, "{}'s PIN is changed.".format(result[0])


def delete_account(handle):
    """Removes the account (and its admin flag). A player logged into it on a
    server keeps playing, but nothing more is saved to it."""
    if not valid_handle(handle):
        return False, "Not a valid account handle."
    try:
        fd = os.open(accounts_path(), os.O_RDWR)
    except FileNotFoundError:
        return False, "No accounts yet - nobody has registered."
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(fd, "r+", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            keep = [line for line in lines if not (len(line.split()) == 6 and line.split()[0].lower() == handle.lower())]
            if len(keep) == len(lines):
                return False, "No account called '{}'.".format(handle)
            f.seek(0)
            f.writelines(keep)
            f.truncate()
    except Exception as e:
        return False, "Could not update the accounts file: {}".format(e)
    set_admin(handle, False)
    return True, "{} is deleted.".format(handle)


def locked_text(account):
    until = account.get("locked_until", 0)
    if until and until > time.time():
        mins = int((until - time.time()) // 60) + 1
        return "Locked ({} min)".format(mins)
    if account.get("failed"):
        return "{} wrong PIN{}".format(account["failed"], "s" if account["failed"] != 1 else "")
    return ""
