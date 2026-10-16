"""Database upkeep with the game servers stopped - run by
mbii-restart-on-boot.sh instead of deleting mbiiez.db: every table trimmed to
its retention (db.RETENTION_DAYS), the file compacted (VACUUM) and the query
planner's statistics refreshed. The running processes only trim, a batch at a
time, every 6 hours - a VACUUM blocks every writer until it's done.

    cd /root/mbiiez && /opt/openjk/venv/bin/python3 -m mbiiez.db_maintenance
"""
import os
import time

from mbiiez import settings
from mbiiez.db import db


def main():
    path = settings.database.database
    before = os.path.getsize(path) if os.path.exists(path) else 0
    started = time.time()
    db().clean_up(vacuum=True)
    after = os.path.getsize(path) if os.path.exists(path) else 0
    print("mbiiez.db: {:.1f} MB -> {:.1f} MB in {:.1f}s".format(before / 1e6, after / 1e6, time.time() - started))


if __name__ == "__main__":
    main()
