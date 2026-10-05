'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const number = value => Number(value || 0).toLocaleString();
  const decimal = value => value == null ? '—' : Number(value).toFixed(2);
  const percent = value => value == null ? '—' : `${value}%`;
  const signed = value => `${value > 0 ? '+' : ''}${number(value)}`;
  const duration = seconds => {
    const minutes = Math.floor(Number(seconds || 0) / 60);
    return minutes >= 60 ? `${number(Math.floor(minutes / 60))}h ${minutes % 60}m` : `${minutes}m`;
  };
  let summary = null, playerPage = 0, casinoPage = 0, loading = false, requestVersion = 0;
  const pageSize = 20;
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  function cell(row, value, className) { const node = element('td', value, className); row.append(node); return node; }
  function playerCell(row, player) {
    const node = cell(row, player.name);
    node.append(element('small', player.identity === 'account' ? 'ACCOUNT' : 'NICKNAME', 'identity-tag'));
  }
  function pageRows(kind, records, render) {
    let page = kind === 'player' ? playerPage : casinoPage;
    page = Math.max(0, Math.min(page, Math.ceil(records.length / pageSize) - 1));
    if (kind === 'player') playerPage = page; else casinoPage = page;
    const body = $(`${kind}-rows`); body.replaceChildren();
    records.slice(page * pageSize, (page + 1) * pageSize).forEach((player, index) => {
      const rank = page * pageSize + index + 1, row = element('tr');
      cell(row, String(rank).padStart(2, '0'), rank <= 3 ? 'rank-top' : '');
      playerCell(row, player); render(row, player); body.append(row);
    });
    if (!records.length) {
      const row = element('tr'), td = cell(row, 'No recorded players match this view.', 'empty-state');
      td.colSpan = 6; td.style.textAlign = 'center'; body.append(row);
    }
    $(`${kind}-count`).textContent = records.length ? `${number(page * pageSize + 1)}–${number(Math.min((page + 1) * pageSize, records.length))} of ${number(records.length)} players` : '0 players';
    $(`${kind}-prev`).disabled = page === 0;
    $(`${kind}-next`).disabled = (page + 1) * pageSize >= records.length;
  }
  function renderPlayers() {
    if (!summary) return;
    const query = $('player-search').value.toLowerCase(), sort = $('player-sort').value;
    const records = summary.gameplay.players.filter(row => row.name.toLowerCase().includes(query) && (sort !== 'kd' || row.deaths >= 10))
      .slice().sort((a, b) => (b[sort] || 0) - (a[sort] || 0) || b.kills - a.kills || a.name.localeCompare(b.name));
    pageRows('player', records, (row, player) => {
      cell(row, number(player.kills)); cell(row, number(player.deaths)); cell(row, decimal(player.kd)); cell(row, duration(player.playtime_seconds));
    });
  }
  function renderCasinoPlayers() {
    if (!summary) return;
    const query = $('casino-search').value.toLowerCase();
    const rows = summary.casino.players.filter(row => row.name.toLowerCase().includes(query));
    pageRows('casino', rows, (row, player) => {
      cell(row, number(player.results)); cell(row, number(player.wins)); cell(row, percent(player.win_rate));
      cell(row, signed(player.net_credits), player.net_credits > 0 ? 'positive' : player.net_credits < 0 ? 'negative' : 'neutral');
    });
  }
  function highlights(players) {
    const target = $('highlights'); target.replaceChildren();
    const pick = (key, filter = () => true) => players.filter(filter).slice().sort((a, b) => (b[key] || 0) - (a[key] || 0))[0];
    for (const [label, player, value] of [
      ['MOST KILLS', pick('kills'), row => `${number(row.kills)} recorded kills`],
      ['MOST TIME PLAYED', pick('playtime_seconds'), row => duration(row.playtime_seconds)],
      ['HIGHEST K/D · 10+ DEATHS', pick('kd', row => row.deaths >= 10), row => `${decimal(row.kd)} kill/death ratio`]
    ]) {
      const card = element('article', null, 'highlight');
      card.append(element('span', label, 'highlight-label'), element('strong', player?.name || 'No records yet', 'highlight-name'), element('small', player ? value(player) : 'Waiting for recorded gameplay'));
      target.append(card);
    }
  }
  function renderCasino(casino) {
    $('casino-empty').hidden = casino.available && casino.totals.results > 0;
    $('casino-content').hidden = !casino.available || casino.totals.results === 0;
    $('casino-coverage').textContent = casino.limited ? 'LATEST RECORDED WINDOW' : 'RECORDED RESULTS';
    $('casino-results').textContent = number(casino.totals.results);
    $('casino-wagered').textContent = number(casino.totals.credits_wagered);
    $('casino-won').textContent = number(casino.totals.credits_won);
    $('casino-rate').textContent = percent(casino.totals.win_rate);
    const chart = $('activity-chart'); chart.replaceChildren();
    const max = Math.max(1, ...casino.daily.map(row => row.results));
    for (const day of casino.daily) {
      const bar = element('div', null, `chart-bar${day.results ? '' : ' zero'}`);
      bar.style.height = `${day.results ? Math.max(4, 100 * day.results / max) : 2}%`;
      bar.title = `${day.date}: ${number(day.results)} player results`;
      chart.append(bar);
    }
    chart.setAttribute('aria-label', `Casino activity over the last 30 days: ${number(casino.daily.reduce((sum, day) => sum + day.results, 0))} recorded player results.`);
    $('chart-start').textContent = casino.daily[0]?.date || '';
    const games = $('game-breakdown'); games.replaceChildren();
    for (const game of casino.games.slice().sort((a, b) => b.results - a.results)) {
      const row = element('div', null, 'game-row'), label = element('div');
      label.append(element('span', game.name), element('small', `${number(game.wins)} wins · ${number(game.prizes)} prizes`));
      row.append(label, element('strong', number(game.results))); games.append(row);
    }
    const recent = $('recent-results'); recent.replaceChildren();
    for (const event of casino.recent) {
      const row = element('div', null, 'recent-item'), player = element('div'), outcome = element('div');
      player.append(element('strong', event.player), element('small', `${event.game} · ${new Date(event.time * 1000).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})}`));
      outcome.append(element('strong', signed(event.net_credits), event.net_credits > 0 ? 'positive' : event.net_credits < 0 ? 'negative' : 'neutral'), element('small', `${event.result} · ${number(event.stake)} staked`));
      row.append(player, outcome); recent.append(row);
    }
    $('casino-note').textContent = 'Credits are in-game currency. This page shows settled results, not account balances. Pushes, refunds and prize-wheel awards are excluded from win rate.'
      + (casino.limited ? ' Large logs are limited to the latest 50,000 records within 16 MiB; totals and charts cover that recorded window.' : '')
      + (casino.players_limited ? ' The casino leaderboard shows the top 1,000 players by net credits.' : '')
      + (casino.skipped_records ? ` ${number(casino.skipped_records)} invalid records were skipped.` : '');
    renderCasinoPlayers();
  }
  function renderServers(servers) {
    const target = $('server-cards'); target.replaceChildren();
    $('server-count').textContent = `${servers.filter(row => row.online).length} ONLINE / ${servers.length} PUBLIC`;
    for (const server of servers.slice().sort((a, b) => Number(b.online) - Number(a.online) || b.players - a.players || a.title.localeCompare(b.title))) {
      const card = element('article', null, 'server-card'), top = element('div', null, 'server-top'), detail = element('div', null, 'server-detail');
      top.append(element('span', server.online ? 'Online' : 'Not responding', `server-status${server.online ? '' : ' offline'}`), element('span', ({'caded.i386':'CADEd','openjkded.i386':'OpenJK','OpenJKDed':'OpenJK','mbiided.i386':'MBII'})[server.engine] || server.engine, 'engine-tag'));
      detail.append(element('span', server.map || 'Map unavailable'), element('strong', server.online ? `${server.players} / ${server.max_players || '—'} players` : '—'));
      const occupancy = element('div', null, 'occupancy'), fill = element('span');
      fill.style.width = `${server.max_players ? Math.min(100, 100 * server.players / server.max_players) : 0}%`; occupancy.append(fill);
      card.append(top, element('h3', server.title), detail, occupancy); target.append(card);
    }
    if (!servers.length) target.append(element('p', 'No public instances are configured on this node.', 'empty-state'));
  }
  async function load() {
    const version = ++requestVersion;
    loading = true; $('refresh').disabled = true;
    const node = $('node-picker').value || document.body.dataset.node;
    try {
      const response = await fetch(`/public/data?node=${encodeURIComponent(node)}`, {headers:{Accept:'application/json'}});
      const data = await response.json();
      if (version !== requestVersion) return;
      if (!response.ok || !data.online) throw new Error(data.error || 'Statistics are temporarily unavailable.');
      summary = data;
      const totals = data.gameplay.totals;
      $('total-players').textContent = number(totals.players);
      $('total-hours').textContent = Number(totals.playtime_seconds / 3600).toLocaleString([], {maximumFractionDigits:1});
      $('total-kills').textContent = number(totals.kills);
      $('total-kd').textContent = decimal(totals.kd);
      highlights(data.gameplay.players); renderPlayers(); renderCasino(data.casino); renderServers(data.servers);
      $('updated').textContent = `Updated ${new Date(data.generated_at * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
      const warnings = [...(data.warnings || [])];
      if (!data.gameplay.available) warnings.push('No CADED gameplay counters are available on this node yet.');
      if (data.gameplay.skipped_records) warnings.push(`${number(data.gameplay.skipped_records)} invalid gameplay records were skipped.`);
      $('notice').textContent = warnings.join(' '); $('notice').hidden = !warnings.length;
      $('loading').hidden = true; $('content').hidden = false;
    } catch (error) {
      if (version !== requestVersion) return;
      $('loading').hidden = true; $('notice').hidden = false;
      $('notice').textContent = error.message;
      $('updated').textContent = summary ? 'Showing the last successful update' : 'Waiting for this node';
    } finally {
      if (version === requestVersion) { loading = false; $('refresh').disabled = false; }
    }
  }
  $('player-search').addEventListener('input', () => { playerPage = 0; renderPlayers(); });
  $('player-sort').addEventListener('change', () => { playerPage = 0; renderPlayers(); });
  $('casino-search').addEventListener('input', () => { casinoPage = 0; renderCasinoPlayers(); });
  for (const kind of ['player', 'casino']) for (const direction of ['prev', 'next']) {
    $(`${kind}-${direction}`).addEventListener('click', () => {
      const offset = direction === 'next' ? 1 : -1;
      if (kind === 'player') { playerPage += offset; renderPlayers(); } else { casinoPage += offset; renderCasinoPlayers(); }
    });
  }
  $('refresh').addEventListener('click', load);
  $('node-picker').addEventListener('change', () => {
    playerPage = 0; casinoPage = 0; summary = null; $('content').hidden = true; $('loading').hidden = false;
    $('notice').hidden = true; document.body.dataset.node = $('node-picker').value;
    const url = new URL(location.href); url.searchParams.set('node', $('node-picker').value); history.replaceState(null, '', url);
    load();
  });
  load();
  setInterval(() => { if (!document.hidden && !loading) load(); }, 60000);
})();
