"""Master list of every map installed on the box, for the friendly maps
picker in the config form. Sourced from MBII/maps.txt (one .bsp filename
per line, covering every mod's maps installed under fs_basepath), not just
the mb2_/um_-prefixed Movie Battles II ones - the user asked for the full
catalog rather than a filtered one."""

import os
import time

from mbiiez import settings

_CACHE_SECONDS = 300
_cache = {"expires": 0.0, "maps": []}


def _maps_file_path():
    return os.path.join(settings.locations.mbii_path, "maps.txt")


def _load_maps():
    path = _maps_file_path()
    if not os.path.isfile(path):
        return []

    maps = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                name = line.strip()
                if not name:
                    continue
                if name.lower().endswith(".bsp"):
                    name = name[: -len(".bsp")]
                maps.append(name)
    except Exception:
        return []

    return sorted(set(maps), key=str.lower)


def get_maps():
    now = time.time()
    if now < _cache["expires"]:
        return _cache["maps"]

    _cache["maps"] = _load_maps()
    _cache["expires"] = now + _CACHE_SECONDS
    return _cache["maps"]
