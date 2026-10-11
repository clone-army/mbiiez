'use strict';
// Clone Army public hub: live servers, the service record, the cantina.
(() => {
  const $ = (id) => document.getElementById(id);
  const num = (v) => Number(v || 0).toLocaleString();
  const PAGE = 25;
  const state = { data: null, sort: 'kills', page: 0, casinoPage: 0, node: document.body.dataset.node, busy: false, ask: 0 };

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  // --- Words ------------------------------------------------------------------

  // Maps as players say them: mb2_cmp_narshaddaa -> Nar Shaddaa.
  const MAP_NAMES = {
    deathstar: 'Death Star', jeditemple: 'Jedi Temple', tradefed: 'Trade Federation Ship', narshaddaa: 'Nar Shaddaa',
    duel_training: 'Duel Training', cantina: 'Mos Eisley Cantina', kamino: 'Kamino', geonosis: 'Geonosis', theed: 'Theed',
    hoth: 'Hoth', endor: 'Endor', bespin: 'Bespin', tatooine: 'Tatooine', utapau: 'Utapau', mustafar: 'Mustafar',
    coruscant: 'Coruscant', dotf: 'Duel of the Fates', commtower: 'Comm Tower', lunarbase: 'Lunar Base',
  };
  function mapName(map) {
    if (!map) return 'Map unknown';
    const key = map.toLowerCase().replace(/^(mb2_|um_|mb_|ffa_|siege_)/, '').replace(/^(cmp_|dc_)/, '');
    if (MAP_NAMES[key]) return MAP_NAMES[key];
    return key.split(/[_-]+/).filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
  }
  // "CloneArmy|NA|FA Night" -> FA Night (the clan and region are the page's).
  function serverName(title) {
    const parts = String(title || '').split('|').map((p) => p.replace(/\^\d/g, '').trim()).filter(Boolean);
    const rest = parts.filter((p) => !/^(na|eu|au|sa|as|us|uk)$/i.test(p) && !/^clone ?army$/i.test(p));
    return rest.join(' ') || parts.join(' ') || 'Server';
  }
  function hours(sec) {
    const h = Number(sec || 0) / 3600;
    return h >= 10 ? num(Math.round(h)) + ' h' : h >= 1 ? h.toFixed(1) + ' h' : Math.round(h * 60) + ' min';
  }
  function plural(n, one, many) { return num(n) + ' ' + (Number(n) === 1 ? one : many); }

  // Ranks by time served, marked as the Republic marked clone officers' armour.
  const RANKS = [
    [150, 'Commander', 'r-commander'], [75, 'Captain', 'r-captain'], [30, 'Lieutenant', 'r-lieutenant'],
    [10, 'Sergeant', 'r-sergeant'], [2, 'Trooper', 'r-trooper'], [0, 'Cadet', 'r-cadet'],
  ];
  const rankOf = (sec) => RANKS.find(([h]) => sec / 3600 >= h);
  function insignia(sec) {
    const [, name, cls] = rankOf(sec || 0);
    const i = el('i', 'insignia ' + cls);
    i.title = name;
    i.setAttribute('aria-label', name);
    return i;
  }

  // A name, in the colours its ^ codes give it.
  function nameNode(name, cls) {
    const n = el('span', cls);
    const parts = String(name || '').split(/(\^[0-9])/);
    let colour = null;
    for (const part of parts) {
      const m = /^\^([0-9])$/.exec(part);
      if (m) { colour = m[1]; continue; }
      if (!part) continue;
      n.append(colour ? el('span', 'q' + colour, part) : document.createTextNode(part));
    }
    if (!n.textContent) n.textContent = 'Unnamed';
    return n;
  }
  const plainName = (name) => String(name || '').replace(/\^[0-9]/g, '');

  // --- Servers ------------------------------------------------------------------

  const shot = (map) => (map ? '/public/levelshot/' + encodeURIComponent(map) : '');
  function connectFor(server) {
    if (!server.port) return null;
    const host = state.data && state.data.node && state.data.node.local ? location.hostname : null;
    return host ? host + ':' + server.port : null;
  }
  function copyButton(server, big) {
    const addr = connectFor(server);
    const b = el('button', 'btn' + (big ? ' btn-go' : ' btn-card'));
    b.type = 'button';
    if (!addr) {
      b.disabled = !server.port;
      b.append(el('span', null, server.port ? 'Port ' + server.port : 'Not reachable'));
      b.title = 'Find CloneArmy in the in-game server browser';
      return b;
    }
    const label = el('span', null, 'Copy connect command');
    b.append(label, el('code', null, 'connect ' + addr));
    b.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText('/connect ' + addr);
        label.textContent = 'Copied';
        b.classList.add('done');
        setTimeout(() => { label.textContent = 'Copy connect command'; b.classList.remove('done'); }, 2200);
      } catch (e) {
        label.textContent = '/connect ' + addr;
      }
    });
    return b;
  }

  function renderHero(servers) {
    const hero = $('hero');
    const up = servers.filter((s) => s.online);
    const playing = up.reduce((n, s) => n + s.players, 0);
    const best = up.slice().sort((a, b) => b.players - a.players)[0];
    hero.classList.toggle('live', playing > 0);
    const kicker = $('hero-kicker').lastChild;
    const region = (state.data.node && state.data.node.name) || 'this region';
    if (best && best.players > 0) {
      kicker.textContent = 'Live now in ' + region;
      $('hero-title').textContent = plural(best.players, 'trooper is', 'troopers are') + ' fighting on ' + mapName(best.map);
      const others = playing - best.players;
      $('hero-sub').textContent = 'On ' + serverName(best.title) + (others > 0 ? ', with ' + plural(others, 'more', 'more') + ' on our other servers.' : '.') +
        ' ' + plural(up.length, 'server is', 'servers are') + ' up. Jump in.';
    } else if (best) {
      kicker.textContent = 'All quiet in ' + region;
      $('hero-title').textContent = plural(up.length, 'server is', 'servers are') + ' standing by';
      $('hero-sub').textContent = 'Nobody is playing right now. Be the first in, and the rest will follow.';
    } else {
      kicker.textContent = region;
      $('hero-title').textContent = 'The servers are down';
      $('hero-sub').textContent = 'None of our servers in ' + region + ' are answering. They usually come back within a few minutes.';
    }
    const actions = $('hero-actions');
    actions.replaceChildren();
    if (best) actions.append(copyButton(best, true));
    const all = el('a', 'btn', 'See every server');
    all.href = '#servers';
    actions.append(all);
    // The art: the busiest map (loaded before it fades in).
    const art = $('hero-art');
    const want = best ? shot(best.map) : '';
    if (art.dataset.src !== want) {
      art.dataset.src = want;
      art.classList.remove('ready');
      if (want) {
        const img = new Image();
        img.onload = () => { if (art.dataset.src === want) { art.style.backgroundImage = 'url("' + want + '")'; art.classList.add('ready'); } };
        img.src = want;
      }
    }
    const roster = $('hero-roster');
    roster.replaceChildren();
    if (best && best.max_players) {
      for (let i = 0; i < Math.min(32, best.max_players); i++) roster.append(el('i', i < best.players ? 'in' : ''));
    }
  }

  function renderServers(servers) {
    const grid = $('server-grid');
    grid.replaceChildren();
    const up = servers.filter((s) => s.online);
    $('server-summary').textContent = servers.length
      ? up.length + ' of ' + plural(servers.length, 'server', 'servers') + ' up, ' + plural(up.reduce((n, s) => n + s.players, 0), 'player', 'players') + ' on'
      : '';
    const sorted = servers.slice().sort((a, b) => Number(b.online) - Number(a.online) || b.players - a.players || serverName(a.title).localeCompare(serverName(b.title)));
    for (const s of sorted) {
      const card = el('article', 'server' + (s.online ? '' : ' down') + (s.players && s.max_players && s.players >= s.max_players * 0.75 ? ' full-up' : ''));
      const art = el('div', 'server-art');
      if (s.map) art.style.backgroundImage = 'url("' + shot(s.map) + '")';
      art.append(el('span', 'server-state ' + (!s.online ? '' : s.players ? 'live' : 'ready'), !s.online ? 'Not answering' : s.players ? 'In battle' : 'Waiting for players'));
      const body = el('div', 'server-body');
      body.append(el('h3', 'server-name', serverName(s.title)), el('p', 'server-map', s.online ? mapName(s.map) : 'Last seen offline'));
      const slots = el('div', 'slots'), bar = el('div', 'slot-bar'), fill = el('span');
      fill.style.width = (s.max_players ? Math.min(100, (100 * s.players) / s.max_players) : 0) + '%';
      bar.append(fill);
      slots.append(bar, el('span', 'slot-count', s.online ? s.players + ' / ' + (s.max_players || '?') : '-'));
      body.append(slots);
      if (s.online) body.append(copyButton(s, false));
      card.append(art, body);
      grid.append(card);
    }
    if (!servers.length) grid.append(el('p', 'empty', 'No public servers are listed for this region yet.'));
  }

  // --- Service record -----------------------------------------------------------

  const SORTS = {
    kills: { label: 'kills', value: (p) => num(p.kills), key: (p) => p.kills, ok: () => true },
    kd: { label: 'K/D', value: (p) => (p.kd == null ? '-' : Number(p.kd).toFixed(2)), key: (p) => p.kd || 0, ok: (p) => p.deaths >= 10 },
    playtime_seconds: { label: 'served', value: (p) => hours(p.playtime_seconds), key: (p) => p.playtime_seconds, ok: () => true },
  };

  function ranked() {
    const sort = SORTS[state.sort];
    return state.data.gameplay.players.filter(sort.ok).slice()
      .sort((a, b) => sort.key(b) - sort.key(a) || b.kills - a.kills || plainName(a.name).localeCompare(plainName(b.name)))
      .map((p, i) => Object.assign({ pos: i + 1 }, p));
  }

  function renderRecord() {
    const g = state.data.gameplay, t = g.totals;
    const sum = $('record-summary');
    sum.replaceChildren();
    if (!g.available || !t.players) {
      sum.textContent = 'No battles recorded yet. Play a round and your record starts here.';
    } else {
      const b = (v) => el('b', null, v);
      sum.append(b(num(t.players)), ' troopers have served ', b(num(Math.round(t.playtime_seconds / 3600))), ' hours and made ', b(num(t.kills)), ' kills.');
    }
    renderBoard();
  }

  function renderBoard() {
    const all = ranked();
    const q = $('player-search').value.trim().toLowerCase();
    const rows = q ? all.filter((p) => plainName(p.name).toLowerCase().includes(q)) : all;
    const sort = SORTS[state.sort];
    // The top three, unless searching.
    const podium = $('podium');
    podium.replaceChildren();
    podium.hidden = !!q || all.length < 3;
    if (!podium.hidden) {
      all.slice(0, 3).forEach((p) => {
        const li = el('li');
        const [, rank] = rankOf(p.playtime_seconds || 0);
        const line = el('div', 'rank-line');
        line.append(insignia(p.playtime_seconds), rank);
        const stat = el('div', 'stat', sort.value(p));
        stat.append(el('small', null, sort.label));
        li.append(el('span', 'place', String(p.pos)), line, nameNode(p.name, 'who'), stat);
        podium.append(li);
      });
    }
    const pages = Math.max(1, Math.ceil(rows.length / PAGE));
    state.page = Math.max(0, Math.min(state.page, pages - 1));
    const body = $('player-rows');
    body.replaceChildren();
    for (const p of rows.slice(state.page * PAGE, (state.page + 1) * PAGE)) {
      const tr = el('tr');
      const who = el('div', 'trooper');
      who.append(insignia(p.playtime_seconds), nameNode(p.name, 'trooper-name'));
      if (p.identity === 'account') who.append(el('span', 'account', 'account'));
      const td = (v, cls) => { const c = el('td', cls, v); tr.append(c); return c; };
      td(String(p.pos), 'c-pos');
      const whoCell = el('td');
      whoCell.append(who);
      tr.append(whoCell);
      td(num(p.kills), 'c-num');
      td(num(p.deaths), 'c-num');
      td(p.kd == null ? '-' : Number(p.kd).toFixed(2), 'c-num ' + (p.kd >= 1 ? 'kd-hi' : 'kd-lo'));
      td(hours(p.playtime_seconds), 'c-num');
      body.append(tr);
    }
    if (!rows.length) {
      const tr = el('tr'), c = el('td', 'empty', q ? 'No trooper called "' + q + '" on this board.' : 'Nobody qualifies yet.');
      c.colSpan = 6;
      tr.append(c);
      body.append(tr);
    }
    $('player-count').textContent = rows.length ? (state.page * PAGE + 1) + '-' + Math.min(rows.length, (state.page + 1) * PAGE) + ' of ' + num(rows.length) : '';
    $('player-prev').disabled = state.page === 0;
    $('player-next').disabled = state.page >= pages - 1;
  }

  // --- Cantina ------------------------------------------------------------------

  function renderCantina() {
    const c = state.data.casino, t = c.totals;
    const has = c.available && t.results > 0;
    $('cantina-more').hidden = !has;
    $('cantina-summary').textContent = !has ? 'No games settled at the cantina yet. Sabacc, pazaak and the prize wheel are on the Social server.'
      : plural(t.results, 'game', 'games') + ' settled, ' + num(t.credits_wagered) + ' credits wagered' + (t.win_rate != null ? ', ' + t.win_rate + '% won' : '');
    if (!has) return;
    const chart = $('activity-chart');
    chart.replaceChildren();
    const max = Math.max(1, ...c.daily.map((d) => d.results));
    for (const d of c.daily) {
      const bar = el('span', d.results ? '' : 'zero');
      bar.style.height = (d.results ? Math.max(4, (100 * d.results) / max) : 2) + '%';
      bar.title = d.date + ': ' + plural(d.results, 'game', 'games');
      chart.append(bar);
    }
    chart.setAttribute('aria-label', 'Games settled each day over the last 30 days');
    $('chart-start').textContent = c.daily[0] ? c.daily[0].date : '';
    const games = $('game-rows');
    games.replaceChildren();
    for (const g of c.games.slice().sort((a, b) => b.results - a.results)) {
      const row = el('div', 'game'), left = el('div');
      left.append(el('span', null, g.name), el('small', null, plural(g.wins, 'win', 'wins') + ', ' + plural(g.prizes, 'prize', 'prizes')));
      row.append(left, el('b', null, num(g.results)));
      games.append(row);
    }
    renderCasinoBoard();
    const recent = $('recent');
    recent.replaceChildren();
    for (const r of c.recent) {
      const li = el('li'), a = el('div'), b = el('div');
      a.append(nameNode(r.player), el('small', null, r.game + ', ' + new Date(r.time * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })));
      b.append(el('span', r.net_credits > 0 ? 'up' : r.net_credits < 0 ? 'down-c' : 'flat', (r.net_credits > 0 ? '+' : '') + num(r.net_credits)), el('small', null, r.result));
      li.append(a, b);
      recent.append(li);
    }
    $('casino-note').textContent = 'Credits are in-game currency. These are settled results, not balances; pushes, refunds and prize-wheel spins don\'t count towards win rate.' +
      (c.limited ? ' Large logs are cut to their latest 50,000 results.' : '');
  }

  function renderCasinoBoard() {
    const q = $('casino-search').value.trim().toLowerCase();
    const rows = state.data.casino.players.filter((p) => plainName(p.name).toLowerCase().includes(q));
    const pages = Math.max(1, Math.ceil(rows.length / PAGE));
    state.casinoPage = Math.max(0, Math.min(state.casinoPage, pages - 1));
    const body = $('casino-rows');
    body.replaceChildren();
    rows.slice(state.casinoPage * PAGE, (state.casinoPage + 1) * PAGE).forEach((p, i) => {
      const tr = el('tr');
      const name = el('td');
      name.append(nameNode(p.name, 'trooper-name'));
      tr.append(el('td', 'c-pos', String(state.casinoPage * PAGE + i + 1)), name, el('td', 'c-num', num(p.results)), el('td', 'c-num', num(p.wins)),
        el('td', 'c-num', p.win_rate == null ? '-' : p.win_rate + '%'),
        el('td', 'c-num ' + (p.net_credits > 0 ? 'up' : p.net_credits < 0 ? 'down-c' : 'flat'), (p.net_credits > 0 ? '+' : '') + num(p.net_credits)));
      body.append(tr);
    });
    $('casino-count').textContent = rows.length ? plural(rows.length, 'player', 'players') : 'No players match';
    $('casino-prev').disabled = state.casinoPage === 0;
    $('casino-next').disabled = state.casinoPage >= pages - 1;
  }

  // --- Loading ------------------------------------------------------------------

  async function load() {
    const ask = ++state.ask;
    state.busy = true;
    try {
      const r = await fetch('/public/data?node=' + encodeURIComponent(state.node), { headers: { Accept: 'application/json' } });
      const data = await r.json();
      if (ask !== state.ask) return;
      if (!r.ok || !data.online) throw new Error(data.error || 'Live data for this region is unavailable. Try again in a minute.');
      state.data = data;
      renderHero(data.servers);
      renderServers(data.servers);
      renderRecord();
      renderCantina();
      const notes = (data.warnings || []).slice();
      $('notice').textContent = notes.join(' ');
      $('notice').hidden = !notes.length;
      $('updated').textContent = 'Updated ' + new Date(data.generated_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
      if (ask !== state.ask) return;
      $('notice').textContent = e.message;
      $('notice').hidden = false;
      if (!state.data) {
        $('hero-title').textContent = 'Live data is unavailable';
        $('hero-sub').textContent = 'This region isn\'t answering right now. The page retries every minute.';
      }
    } finally {
      if (ask === state.ask) state.busy = false;
    }
  }

  document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => {
    state.sort = tab.dataset.sort;
    state.page = 0;
    document.querySelectorAll('.tab').forEach((t) => { t.classList.toggle('on', t === tab); t.setAttribute('aria-selected', String(t === tab)); });
    if (state.data) renderBoard();
  }));
  $('player-search').addEventListener('input', () => { state.page = 0; if (state.data) renderBoard(); });
  $('player-prev').addEventListener('click', () => { state.page--; renderBoard(); });
  $('player-next').addEventListener('click', () => { state.page++; renderBoard(); });
  $('casino-search').addEventListener('input', () => { state.casinoPage = 0; if (state.data) renderCasinoBoard(); });
  $('casino-prev').addEventListener('click', () => { state.casinoPage--; renderCasinoBoard(); });
  $('casino-next').addEventListener('click', () => { state.casinoPage++; renderCasinoBoard(); });
  document.querySelectorAll('.region').forEach((b) => b.addEventListener('click', () => {
    if (b.dataset.node === state.node) return;
    state.node = b.dataset.node;
    document.querySelectorAll('.region').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
    const url = new URL(location.href);
    url.searchParams.set('node', state.node);
    history.replaceState(null, '', url);
    state.data = null;
    state.page = state.casinoPage = 0;
    $('hero-title').textContent = 'Finding where the fighting is…';
    $('hero-sub').textContent = '';
    load();
  }));
  load();
  setInterval(() => { if (!document.hidden && !state.busy) load(); }, 60000);
})();
