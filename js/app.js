// Fixed-Time Running Analysis — Client App
// Loads index.json for discovery, fetches individual split files on demand.

const DATA_BASE = 'data';
const CHART_COLORS = ['#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149', '#79c0ff', '#56d364', '#e3b341'];

let indexData = null;
let selectedIds = new Set();
let loadedSplits = {};
let charts = {};

// === Utilities ===

function fmtPace(sec) {
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtTime(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.round(sec % 60);
  return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

// === Data Loading ===

async function loadIndex() {
  const res = await fetch(DATA_BASE + '/index.json');
  indexData = await res.json();
  renderFilters();
  renderPerformances();
}

async function loadSplits(perfId) {
  if (loadedSplits[perfId]) return loadedSplits[perfId];
  const perf = indexData.performances.find(p => p.id === perfId);
  if (!perf) return null;
  const res = await fetch(DATA_BASE + '/splits/' + perf.splits_file);
  const data = await res.json();
  loadedSplits[perfId] = data;
  return data;
}

// === Filters ===

function renderFilters() {
  const distFilter = document.getElementById('filterDistance');
  const raceFilter = document.getElementById('filterRace');

  // Distances
  const distances = [...new Set(indexData.performances.map(p => p.distance_id))];
  distFilter.innerHTML = '<option value="">All distances</option>' +
    indexData.distances.filter(d => distances.includes(d.id)).map(d =>
      '<option value="' + d.id + '">' + d.name + '</option>'
    ).join('');

  // Races
  const raceIds = [...new Set(indexData.performances.map(p => p.race_id))];
  raceFilter.innerHTML = '<option value="">All races</option>' +
    indexData.races.filter(r => raceIds.includes(r.id)).map(r =>
      '<option value="' + r.id + '">' + r.name + '</option>'
    ).join('');

  distFilter.addEventListener('change', renderPerformances);
  raceFilter.addEventListener('change', renderPerformances);
  document.getElementById('filterRunner').addEventListener('input', renderPerformances);
}

function getFilters() {
  return {
    distance: document.getElementById('filterDistance').value,
    race: document.getElementById('filterRace').value,
    runner: document.getElementById('filterRunner').value.toLowerCase().trim(),
  };
}

// === Performance List ===

function renderPerformances() {
  const filters = getFilters();
  const list = document.getElementById('perfList');

  let perfs = indexData.performances;
  if (filters.distance) perfs = perfs.filter(p => p.distance_id === filters.distance);
  if (filters.race) perfs = perfs.filter(p => p.race_id === filters.race);
  if (filters.runner) perfs = perfs.filter(p => p.runner.toLowerCase().includes(filters.runner));

  // Sort by distance descending, then year
  perfs.sort((a, b) => b.distance_mi - a.distance_mi || b.year - a.year);

  list.innerHTML = perfs.map(p => {
    const race = indexData.races.find(r => r.id === p.race_id);
    const checked = selectedIds.has(p.id) ? ' checked' : '';
    const selected = selectedIds.has(p.id) ? ' selected' : '';
    return '<div class="perf-item' + selected + '" data-id="' + p.id + '">' +
      '<input type="checkbox"' + checked + '>' +
      '<div class="perf-meta">' +
        '<div class="perf-runner">' + p.runner + (p.note ? ' <span class="perf-note">' + p.note + '</span>' : '') + '</div>' +
        '<div class="perf-detail">' + (race ? race.name : p.race_id) + ' ' + p.year + '</div>' +
      '</div>' +
      '<div class="perf-stats">' +
        '<span>' + p.distance_mi + ' mi</span>' +
        '<span>' + p.duration + '</span>' +
        '<span>' + fmtPace(p.pace_sec) + '/mi</span>' +
      '</div>' +
    '</div>';
  }).join('');

  // Click handlers
  list.querySelectorAll('.perf-item').forEach(el => {
    el.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT') return; // let checkbox handle itself
      const cb = this.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      togglePerformance(this.dataset.id, cb.checked);
    });
    el.querySelector('input').addEventListener('change', function() {
      togglePerformance(el.dataset.id, this.checked);
    });
  });

  updateCompareBar();
}

function togglePerformance(id, checked) {
  if (checked) selectedIds.add(id); else selectedIds.delete(id);

  document.querySelectorAll('.perf-item').forEach(el => {
    el.classList.toggle('selected', selectedIds.has(el.dataset.id));
    el.querySelector('input').checked = selectedIds.has(el.dataset.id);
  });

  updateCompareBar();
}

function updateCompareBar() {
  const bar = document.getElementById('compareBar');
  const btn = document.getElementById('compareBtn');
  const count = selectedIds.size;

  if (count > 0) {
    bar.classList.add('visible');
    btn.textContent = 'Compare ' + count + ' performance' + (count > 1 ? 's' : '');
    btn.disabled = count < 2;
  } else {
    bar.classList.remove('visible');
  }
}

// === Comparison View ===

async function runComparison() {
  const chartsSection = document.getElementById('chartsSection');
  chartsSection.innerHTML = '<div class="loading">Loading splits...</div>';
  chartsSection.style.display = 'block';

  // Load all selected splits
  const entries = [];
  for (const id of selectedIds) {
    const perf = indexData.performances.find(p => p.id === id);
    const splits = await loadSplits(id);
    if (splits && perf) entries.push({ perf, splits });
  }

  if (entries.length < 2) {
    chartsSection.innerHTML = '<div class="loading">Need at least 2 performances to compare.</div>';
    return;
  }

  // Sort by year
  entries.sort((a, b) => a.perf.year - b.perf.year);

  const maxMiles = Math.max(...entries.map(e => e.splits.miles.length));
  const minMiles = Math.min(...entries.map(e => e.splits.miles.length));
  const labels = Array.from({ length: maxMiles }, (_, i) => i + 1);
  const longRace = maxMiles > 20;

  chartsSection.innerHTML = '';

  // Summary stats
  const statsHTML = '<div class="stats-row">' + entries.map((e, i) =>
    '<div class="stat" style="border-color:' + CHART_COLORS[i] + '">' +
    '<div class="value" style="color:' + CHART_COLORS[i] + '">' + e.perf.distance_mi + ' mi</div>' +
    '<div class="label">' + e.perf.runner + ' ' + e.perf.year + '</div></div>'
  ).join('') + '</div>';
  chartsSection.insertAdjacentHTML('beforeend', statsHTML);

  // Year toggles
  const toggleId = 'yearToggles';
  const toggleHTML = '<div class="year-toggles" id="' + toggleId + '">' + entries.map((e, i) =>
    '<label><input type="checkbox" checked data-idx="' + i + '"> ' +
    '<span style="color:' + CHART_COLORS[i] + ';font-weight:600">' + e.perf.runner + ' ' + e.perf.year + '</span></label>'
  ).join('') + '</div>';

  // 1. Pace overlay chart
  renderChartCard(chartsSection, 'paceOverlay', 'Mile-by-Mile Pace Comparison',
    'Each performance overlaid. Toggle visibility with checkboxes.', toggleHTML, 400);

  const paceData = {
    labels,
    datasets: entries.map((e, i) => ({
      label: e.perf.runner + ' ' + e.perf.year,
      data: e.splits.miles.map(m => m.moving_sec),
      borderColor: CHART_COLORS[i],
      pointRadius: longRace ? 0 : 4,
      pointHoverRadius: 5,
      borderWidth: 2, tension: 0.2,
    }))
  };

  charts.paceOverlay = new Chart(document.getElementById('paceOverlay'), {
    type: 'line', data: paceData,
    options: chartOptions({
      yReverse: true, yLabel: 'Pace (min/mi)', xLabel: 'Mile', longRace,
      yFmt: fmtPace, tooltipFmt: function(ctx) { return ctx.dataset.label + ': ' + fmtPace(ctx.raw) + '/mi'; }
    })
  });

  // Wire toggles
  document.getElementById(toggleId).querySelectorAll('input').forEach(cb => {
    cb.addEventListener('change', function() {
      const idx = parseInt(this.dataset.idx);
      charts.paceOverlay.data.datasets[idx].hidden = !this.checked;
      if (charts.timeGap) charts.timeGap.data.datasets[idx].hidden = !this.checked;
      charts.paceOverlay.update();
      if (charts.timeGap) charts.timeGap.update();
    });
  });

  // 2. Cumulative time gap
  const baseIdx = entries.reduce((best, e, i) => {
    const avg = e.splits.miles.reduce((s, m) => s + m.moving_sec, 0) / e.splits.miles.length;
    const bestAvg = entries[best].splits.miles.reduce((s, m) => s + m.moving_sec, 0) / entries[best].splits.miles.length;
    return avg < bestAvg ? i : best;
  }, 0);

  const baseCum = [];
  let cs = 0;
  entries[baseIdx].splits.miles.forEach(m => { cs += m.moving_sec; baseCum.push(cs); });

  renderChartCard(chartsSection, 'timeGap', 'Cumulative Time Gap',
    'Seconds ahead (+) or behind (−) the fastest average pace (' + entries[baseIdx].perf.runner + ' ' + entries[baseIdx].perf.year + ').', '', 300);

  const gapData = {
    labels,
    datasets: entries.map((e, i) => {
      const cum = []; let s = 0;
      e.splits.miles.forEach((m, j) => { s += m.moving_sec; cum.push(s - (baseCum[j] || baseCum[baseCum.length - 1])); });
      return {
        label: e.perf.runner + ' ' + e.perf.year + (i === baseIdx ? ' (fastest)' : ''),
        data: cum,
        borderColor: CHART_COLORS[i],
        borderWidth: i === baseIdx ? 3 : 2,
        borderDash: i === baseIdx ? [] : [5, 3],
        pointRadius: longRace ? 0 : 3, pointHoverRadius: 4,
        tension: 0.2, fill: false,
      };
    })
  };

  charts.timeGap = new Chart(document.getElementById('timeGap'), {
    type: 'line', data: gapData,
    options: chartOptions({
      yLabel: 'Gap (seconds)', xLabel: 'Mile', longRace,
      yFmt: v => (v > 0 ? '+' : '') + v + 's',
      tooltipFmt: function(ctx) { return ctx.dataset.label + ': ' + (ctx.raw > 0 ? '+' : '') + ctx.raw.toFixed(0) + 's'; }
    })
  });

  // 3. Heatmap table
  renderHeatmapTable(chartsSection, entries, minMiles);

  // Scroll to charts
  chartsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// === Chart Helpers ===

function chartOptions({ yReverse, yLabel, xLabel, longRace, yFmt, tooltipFmt }) {
  const tickCb = longRace ? { callback: (v, i) => (i + 1) % 10 === 0 ? i + 1 : '' } : {};
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      tooltip: { callbacks: { label: tooltipFmt } },
      legend: { labels: { usePointStyle: true } }
    },
    scales: {
      y: { reverse: !!yReverse, ticks: { callback: yFmt }, title: { display: true, text: yLabel } },
      x: { title: { display: true, text: xLabel }, grid: { display: false }, ticks: tickCb }
    }
  };
}

function renderChartCard(container, canvasId, title, desc, extraHTML, height) {
  container.insertAdjacentHTML('beforeend',
    '<div class="chart-card">' +
    '<h3>' + title + '</h3>' +
    '<div class="desc">' + desc + '</div>' +
    extraHTML +
    '<div style="height:' + height + 'px"><canvas id="' + canvasId + '"></canvas></div>' +
    '</div>'
  );
}

function renderHeatmapTable(container, entries, maxMiles) {
  let html = '<div class="chart-card"><h3>Split Heatmap</h3>' +
    '<div class="desc">Color shows fastest (<span style="color:var(--green)">green</span>) and slowest (<span style="color:var(--red)">red</span>) per mile.</div>' +
    '<div class="table-wrapper"><table><thead><tr><th>Mile</th>';
  entries.forEach((e, i) => html += '<th style="color:' + CHART_COLORS[i] + '">' + e.perf.runner + ' ' + e.perf.year + '</th>');
  html += '<th>Spread</th></tr></thead><tbody>';

  for (let m = 0; m < maxMiles; m++) {
    const vals = entries.map(e => e.splits.miles[m]?.moving_sec).filter(v => v !== undefined);
    if (vals.length === 0) continue;
    const best = Math.min(...vals), worst = Math.max(...vals);
    html += '<tr><td>' + (m + 1) + '</td>';
    entries.forEach(e => {
      const v = e.splits.miles[m]?.moving_sec;
      if (v === undefined) { html += '<td>-</td>'; return; }
      const cls = v === best && vals.length > 1 ? ' class="fastest"' : v === worst && vals.length > 1 ? ' class="slowest"' : '';
      html += '<td' + cls + '>' + fmtPace(v) + '</td>';
    });
    html += '<td style="color:var(--text-muted)">' + (worst - best) + 's</td></tr>';
  }

  html += '</tbody></table></div></div>';
  container.insertAdjacentHTML('beforeend', html);
}

// === Init ===

document.addEventListener('DOMContentLoaded', function() {
  Chart.defaults.color = '#8b949e';
  Chart.defaults.borderColor = 'rgba(139,148,158,0.15)';
  Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif';

  loadIndex();

  document.getElementById('compareBtn').addEventListener('click', runComparison);
});
