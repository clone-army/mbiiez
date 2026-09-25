"""Shared "is this holiday active today, and which maps does it bring"
logic - used by both the RTVRTM plugin (rtvrtm_plugin.py, for its own
primary_maps pool) and the core map rotation (conf.py). Kept as one
module so both agree on the same date-wraparound rules, and so an
instance's daily restart_instance_every_hours restart is all it takes for
a holiday's maps to appear and disappear on schedule - see conf.py and
rtvrtm_plugin.py's generate_maps_files() for where each one is applied.
"""

from datetime import date


def is_active(today, holiday_data):
    """Whether a single holiday (its own start/end month+day dict) covers
    `today`. Handles a range that wraps the new year (e.g. Dec 1 - Jan 5)
    the same way regardless of which caller asks."""
    try:
        start_month = holiday_data.get("start_month")
        start_day = holiday_data.get("start_day")
        end_month = holiday_data.get("end_month")
        end_day = holiday_data.get("end_day")

        if not all([start_month, start_day, end_month, end_day]):
            return False

        current_year = today.year
        start_date = date(current_year, start_month, start_day)
        end_date = date(current_year, end_month, end_day)

        if end_date < start_date:
            # Wraps the new year, e.g. Dec 1 -> Jan 5.
            return today >= start_date or today <= end_date
        return start_date <= today <= end_date
    except (TypeError, ValueError):
        return False


def get_active_maps(holiday_maps_config, today=None):
    """holiday_maps_config is the parsed dict at ...holiday_maps (e.g.
    instance_config['plugins']['rtvrtm']['holiday_maps']) - the same shape
    the Config page's Maps section and RTVRTM's own config.json use.
    Returns the de-duplicated list of maps for every currently-active
    holiday, in holiday-iteration-then-per-holiday-map order."""
    today = today or date.today()
    active_maps = []
    seen = set()
    for holiday_data in (holiday_maps_config or {}).values():
        if not is_active(today, holiday_data):
            continue
        for map_name in holiday_data.get("maps", []) or []:
            if map_name not in seen:
                seen.add(map_name)
                active_maps.append(map_name)
    return active_maps
