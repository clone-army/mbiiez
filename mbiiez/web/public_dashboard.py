"""Cached WEB projection of authenticated API summaries, safe for anonymous visitors."""
import threading
import time
from mbiiez.api.client import Client, nodes

_lock = threading.Lock()
_cache = {}
_locks = {}


def projection(summary):
    """Keep a fixed public contract even if a future agent adds private fields."""
    def fields(row, names):
        return {key: row[key] for key in names.split() if key in row}
    gameplay = summary['gameplay']
    casino = summary['casino']
    counters = 'results wins losses pushes refunds prizes credits_wagered credits_won credits_lost net_credits win_rate'
    return dict(
        generated_at=summary['generated_at'],
        gameplay=dict(**fields(gameplay, 'available skipped_records'),
                      totals=fields(gameplay['totals'], 'players kills deaths suicides playtime_seconds kd'),
                      players=[fields(row, 'name identity kills deaths suicides playtime_seconds kd') for row in gameplay['players'][:4096]]),
        casino=dict(**fields(casino, 'available limited players_limited skipped_records first_record last_record'),
                    totals=fields(casino['totals'], counters),
                    players=[fields(row, 'name identity ' + counters) for row in casino['players'][:1000]],
                    games=[fields(row, 'id name ' + counters) for row in casino['games'][:20]],
                    daily=[fields(row, 'date ' + counters) for row in casino['daily'][-30:]],
                    recent=[fields(row, 'time player game result stake net_credits') for row in casino['recent'][:20]]),
        servers=[fields(row, 'name title engine online players max_players map mode') for row in summary['servers']],
        warnings=summary.get('warnings', [])[:5],
    )


def data(identifier):
    node = nodes()[identifier]
    # Credential/URL edits invalidate cached data immediately.
    key = (identifier, node['name'], node['url'], node['key'])
    with _lock:
        node_lock = _locks.setdefault(identifier, threading.Lock())
    with node_lock:
        entry = _cache.get(key)
        if entry and time.monotonic() < entry[0]: return entry[1]
        try:
            summary = Client(identifier, actor='public-dashboard').call('GET', 'public/stats')
            result = dict(online=True, node=dict(id=identifier, name=node['name']), **projection(summary))
        except Exception:
            # No raw upstream errors: these can contain private hostnames and filesystem paths.
            result = dict(online=False, node=dict(id=identifier, name=node['name']), error='This node is temporarily unavailable. Please check back shortly.')
        if len(_cache) >= 128: _cache.clear()
        _cache[key] = (time.monotonic() + (60 if result['online'] else 15), result)
        return result
