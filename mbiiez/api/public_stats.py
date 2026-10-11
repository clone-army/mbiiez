"""Read-only public projection. Never read accounts, ban files or private chat."""
from concurrent.futures import ThreadPoolExecutor
from collections import deque
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
from mbiiez import settings
from .paths import names, config_path
from .sync import engine_file

MAX_LOG_BYTES = 16 * 1024 * 1024
MAX_LOG_LINES = 50000
GAMES = {'blackjack': 'Blackjack', 'pazaak': 'Pazaak', 'chance': 'Chance',
         'bet': 'Duel betting', 'raffle': 'Raffle', 'spin': 'Prize wheel'}
RESULTS = {'win', 'loss', 'push', 'refund', 'prize', 'none'}
_lock = threading.Lock()
_cache = {}


def clean(value, limit=80):
    value = str(value or '')
    value = re.sub(r'\^[0-9]', '', value)
    return ''.join(c for c in value if c.isprintable())[:limit]


def counter(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2147483647:
        raise ValueError('Invalid counter')
    return value


def ratio(kills, deaths):
    # Undefined for zero deaths; the presentation uses an em dash rather than infinity.
    return round(kills / deaths, 2) if deaths else None


def gameplay():
    players = []
    totals = dict(players=0, kills=0, deaths=0, suicides=0, playtime_seconds=0)
    invalid = 0
    with engine_file('stats', writable=False) as (_, content, path):
        present = path.exists()
    for line in content.splitlines()[:4096]:
        if not line or line.startswith('#'): continue
        try:
            identity, *values = line.split('|')
            if len(values) != 4 or not identity: raise ValueError()
            kills, deaths, suicides, seconds = [counter(int(v)) for v in values]
        except (ValueError, TypeError):
            invalid += 1
            continue
        account = identity.startswith('h:')
        display = identity[2:] if identity.startswith(('h:', 'n:')) else identity
        row = dict(name=clean(display) or 'Unnamed player', identity='account' if account else 'nickname',
                   kills=kills, deaths=deaths, suicides=suicides, playtime_seconds=seconds,
                   kd=ratio(kills, deaths))
        players.append(row)
        for field in ('kills', 'deaths', 'suicides', 'playtime_seconds'): totals[field] += row[field]
    totals['players'] = len(players)
    totals['kd'] = ratio(totals['kills'], totals['deaths'])
    players.sort(key=lambda row: (-row['kills'], -row['playtime_seconds'], row['name'].lower()))
    return dict(available=present, totals=totals, players=players, skipped_records=invalid)


def blank_casino():
    return dict(results=0, wins=0, losses=0, pushes=0, refunds=0, prizes=0,
                credits_wagered=0, credits_won=0, credits_lost=0, net_credits=0)


def casino():
    # Snapshot a bounded tail without locking the append-only engine log. Only complete
    # newline-terminated records are included; concurrent writes appear on the next refresh.
    path = Path(settings.locations.mbii_path) / 'game_results.log'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return dict(available=False, limited=False, totals=blank_casino(), players=[], games=[], daily=[], recent=[])
    with os.fdopen(fd, 'rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        start = max(0, size - MAX_LOG_BYTES)
        stream.seek(start)
        raw = stream.read(min(size, MAX_LOG_BYTES))
    if start:
        raw = raw.partition(b'\n')[2]
    lines = raw.split(b'\n')[:-1]
    limited = bool(start or len(lines) > MAX_LOG_LINES)
    lines = lines[-MAX_LOG_LINES:]
    totals, people, games, daily, recent = blank_casino(), {}, {}, {}, deque(maxlen=20)
    skipped, first, last = 0, None, None
    now = time.time()
    for line in lines:
        try:
            row = json.loads(line.decode('utf-8', errors='replace'))
            game, result = row['game'], row['result']
            if game not in GAMES or result not in RESULTS: raise ValueError()
            stamp, stake = counter(row['t']), counter(row['stake'])
            net = row['net']
            if isinstance(net, bool) or not isinstance(net, int) or not -2147483647 <= net <= 2147483647: raise ValueError()
            if stamp > now + 300: raise ValueError()
            account = clean(row.get('account'), 23)
            name = clean(row.get('name')) or account or 'Unnamed player'
            key = ('account', account.lower()) if account else ('nickname', name.lower())
        except (ValueError, TypeError, KeyError, AttributeError):
            skipped += 1
            continue
        first = min(first or stamp, stamp); last = max(last or stamp, stamp)
        player = people.setdefault(key, dict(name=name, identity=key[0], **blank_casino()))
        player['name'] = name
        group = games.setdefault(game, dict(id=game, name=GAMES[game], **blank_casino()))
        day = datetime.fromtimestamp(stamp, timezone.utc).strftime('%Y-%m-%d')
        bucket = daily.setdefault(day, dict(date=day, **blank_casino()))
        for aggregate in (totals, player, group, bucket):
            aggregate['results'] += 1
            field = {'win':'wins', 'loss':'losses', 'push':'pushes', 'refund':'refunds', 'prize':'prizes'}.get(result)
            if field: aggregate[field] += 1
            if result != 'refund': aggregate['credits_wagered'] += stake
            aggregate['credits_won'] += max(0, net)
            aggregate['credits_lost'] += max(0, -net)
            aggregate['net_credits'] += net
        recent.append(dict(time=stamp, player=name, game=GAMES[game], result=result, stake=stake, net_credits=net))
    for item in [totals, *people.values(), *games.values()]:
        settled = item['wins'] + item['losses']
        item['win_rate'] = round(100 * item['wins'] / settled, 1) if settled else None
    today = datetime.now(timezone.utc).date()
    trend = [daily.get(str(today - timedelta(days=offset)), dict(date=str(today - timedelta(days=offset)), **blank_casino())) for offset in range(29, -1, -1)]
    ranking = sorted(people.values(), key=lambda item: (-item['net_credits'], -item['wins'], item['name'].lower()))
    return dict(available=True, limited=limited, totals=totals, players=ranking[:1000],
                players_limited=len(ranking) > 1000, games=list(games.values()), daily=trend,
                recent=sorted(recent, key=lambda item: item['time'], reverse=True)[:20],
                skipped_records=skipped, first_record=first, last_record=last)


def server_info(name):
    with open(config_path(name)) as stream:
        document = json.load(stream)
        if document.get('security', {}).get('server_password') or document.get('server', {}).get('public_stats') is False:
            return None
        config = document.get('server', {})
    result = dict(name=name, title=clean(config.get('host_name', name)), engine=clean(config.get('engine', '')),
                  online=False, players=0, max_players=0, map='', mode='')
    try:
        port = int(config.get('port', 0))
        if not 1 <= port <= 65535: return result
        result['port'] = port  # as the master server list shows it: for players' connect command
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(.6)
            sock.connect(('127.0.0.1', port))
            sock.send(b'\xff\xff\xff\xffgetinfo mbiiez-public\n')
            reply = sock.recv(8192)
        if not reply.startswith(b'\xff\xff\xff\xffinfoResponse\n'): return result
        parts = reply.split(b'\n', 1)[1].decode('utf-8', errors='replace').strip().split('\\')
        info = dict(zip(parts[1::2], parts[2::2]))
        result.update(online=True, players=min(256, max(0, int(info.get('clients', 0)))),
                      max_players=min(256, max(0, int(info.get('sv_maxclients', 0)))),
                      map=clean(info.get('mapname')), mode=clean(info.get('gametype')))
    except (OSError, ValueError):
        pass
    return result


def build():
    warnings = []
    try: stats = gameplay()
    except (OSError, ValueError):
        stats = dict(available=False, totals=dict(players=0, kills=0, deaths=0, suicides=0, playtime_seconds=0, kd=None), players=[])
        warnings.append('Gameplay statistics are temporarily unavailable.')
    try: gambling = casino()
    except (OSError, ValueError):
        gambling = dict(available=False, limited=False, totals=blank_casino(), players=[], games=[], daily=[], recent=[])
        warnings.append('Casino statistics are temporarily unavailable.')
    def safe_server(name):
        try: return server_info(name)
        except (OSError, ValueError): return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        servers = [row for row in pool.map(safe_server, names()) if row]
    return dict(generated_at=int(time.time()), gameplay=stats, casino=gambling, servers=servers, warnings=warnings)


def snapshot():
    # One computation per worker per minute; public traffic cannot repeatedly poll game data.
    key = (str(settings.locations.mbii_path), str(settings.locations.config_path))
    with _lock:
        entry = _cache.get(key)
        if entry and time.monotonic() < entry[0]: return entry[1]
        data = build()
        _cache.clear()
        _cache[key] = (time.monotonic() + 60, data)
        return data
