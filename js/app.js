// Fixed-Time Running Analysis — Unified UI
// Browse → Select → Visualize

const DATA_BASE = 'data';
const CHART_COLORS = ['#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149', '#79c0ff', '#56d364', '#e3b341'];

let indexData = null;
let loadedSplits = {};
let charts = {};

// State
const selected = new Set(); // performance IDs
let currentView = 'browse'; // 'browse' | 'cart'
let currentViz = 'projection';
let filteredPerfs = [];

// === Utilities ===

function fmtPace(sec) {
  if (!sec || isNaN(sec)) return '-';
  var m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtTime(sec) {
  var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.round(sec % 60);
  return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtHours(sec) {
  return (sec / 3600).toFixed(1) + 'h';
}

function getRaceName(p) {
  var race = indexData.races.find(function(r) { return r.id === p.race_id; });
  return race ? race.name : p.race_id;
}

// === Data Loading ===

async function loadIndex() {
  var res = await fetch(DATA_BASE + '/index.json');
  indexData = await res.json();
  initUI();
}

async function loadSplits(perfId) {
  if (loadedSplits[perfId]) return loadedSplits[perfId];
  var perf = indexData.performances.find(function(p) { return p.id === perfId; });
  if (!perf) return null;
  var res = await fetch(DATA_BASE + '/splits/' + perf.splits_file);
  var data = await res.json();
  loadedSplits[perfId] = data;
  return data;
}

function getTimeDistancePairs(splits) {
  var pairs = [{ time_sec: 0, distance_mi: 0 }];
  if (splits.miles && splits.miles.length > 0) {
    splits.miles.forEach(function(m) {
      pairs.push({ time_sec: m.cum_sec, distance_mi: m.mile });
    });
  } else if (splits.checkpoints && splits.checkpoints.length > 0) {
    splits.checkpoints.forEach(function(cp) {
      var time = cp.cum_sec || cp.elapsed_sec;
      var dist = cp.distance_mi;
      if (time && dist) pairs.push({ time_sec: time, distance_mi: dist, label: cp.label });
    });
    pairs.sort(function(a, b) { return a.time_sec - b.time_sec; });
  }
  return pairs;
}

function hasMileData(splits) {
  return splits.miles && splits.miles.length > 0;
}

// === Initialization ===

function initUI() {
  populateFilters();
  buildQuickPicks();
  applyFilters();
  wireEvents();
}

function populateFilters() {
  var distFilter = document.getElementById('filterDistance');
  var raceFilter = document.getElementById('filterRace');
  var countryFilter = document.getElementById('filterCountry');

  // Distances
  var distIds = [];
  indexData.performances.forEach(function(p) {
    if (distIds.indexOf(p.distance_id) === -1) distIds.push(p.distance_id);
  });
  distFilter.innerHTML = '<option value="">All distances</option>' +
    indexData.distances.filter(function(d) { return distIds.indexOf(d.id) >= 0; }).map(function(d) {
      return '<option value="' + d.id + '">' + d.name + '</option>';
    }).join('');

  // Races — sorted alphabetically
  var raceIds = [];
  indexData.performances.forEach(function(p) {
    if (raceIds.indexOf(p.race_id) === -1) raceIds.push(p.race_id);
  });
  var races = indexData.races.filter(function(r) { return raceIds.indexOf(r.id) >= 0; });
  races.sort(function(a, b) { return a.name.localeCompare(b.name); });
  raceFilter.innerHTML = '<option value="">All races</option>' +
    races.map(function(r) {
      return '<option value="' + r.id + '">' + r.name + '</option>';
    }).join('');

  // Countries
  var countries = [];
  indexData.performances.forEach(function(p) {
    if (p.nationality && countries.indexOf(p.nationality) === -1) countries.push(p.nationality);
  });
  countries.sort();
  countryFilter.innerHTML = '<option value="">All countries</option>' +
    countries.map(function(c) { return '<option value="' + c + '">' + c + '</option>'; }).join('');
}

function buildQuickPicks() {
  var container = document.getElementById('quickPicks');

  // Dynamic quick picks based on current distance filter
  var picks = [
    { label: 'Top 5 All-Time', fn: function() { return getTopN(5); } },
    { label: 'Top 10 All-Time', fn: function() { return getTopN(10); } },
    { label: 'Top 5 Women', fn: function() { return getTopN(5, 'F'); } },
    { label: 'Top 5 Men', fn: function() { return getTopN(5, 'M'); } },
    { label: 'World Records', fn: function() { return getNotedPerfs('World Record'); } },
    { label: 'Championship Races', fn: function() { return getChampionshipPerfs(); } },
  ];

  picks.forEach(function(pick) {
    var btn = document.createElement('button');
    btn.className = 'quick-pick-btn';
    btn.textContent = pick.label;
    btn.addEventListener('click', function() {
      var ids = pick.fn();
      ids.forEach(function(id) { selected.add(id); });
      updateAll();
    });
    container.appendChild(btn);
  });
}

function getTopN(n, gender) {
  var perfs = getFilteredByDistance();
  if (gender) perfs = perfs.filter(function(p) { return p.gender === gender; });
  perfs.sort(function(a, b) { return b.distance_mi - a.distance_mi; });
  return perfs.slice(0, n).map(function(p) { return p.id; });
}

function getFilteredByDistance() {
  var dist = document.getElementById('filterDistance').value;
  var perfs = indexData.performances;
  if (dist) perfs = perfs.filter(function(p) { return p.distance_id === dist; });
  return perfs;
}

function getNotedPerfs(noteSubstr) {
  var perfs = getFilteredByDistance();
  return perfs.filter(function(p) {
    return p.note && p.note.toLowerCase().indexOf(noteSubstr.toLowerCase()) >= 0;
  }).map(function(p) { return p.id; });
}

function getChampionshipPerfs() {
  var perfs = getFilteredByDistance();
  return perfs.filter(function(p) {
    var race = getRaceName(p).toLowerCase();
    return race.indexOf('iau') >= 0 || race.indexOf('championship') >= 0 ||
           race.indexOf('world') >= 0 || race.indexOf('european') >= 0;
  }).slice(0, 10).map(function(p) { return p.id; });
}

// === Filtering ===

function applyFilters() {
  var dist = document.getElementById('filterDistance').value;
  var race = document.getElementById('filterRace').value;
  var country = document.getElementById('filterCountry').value;
  var gender = document.getElementById('filterGender').value;
  var search = document.getElementById('searchInput').value.toLowerCase().trim();

  // Cascade: update race/country dropdowns based on distance filter
  updateCascadingFilters(dist);

  // If selected race is no longer valid for this distance, reset it
  if (race && dist) {
    var raceValid = indexData.performances.some(function(p) { return p.race_id === race && p.distance_id === dist; });
    if (!raceValid) {
      document.getElementById('filterRace').value = '';
      race = '';
    }
  }

  filteredPerfs = indexData.performances.slice();

  if (dist) filteredPerfs = filteredPerfs.filter(function(p) { return p.distance_id === dist; });
  if (race) filteredPerfs = filteredPerfs.filter(function(p) { return p.race_id === race; });
  if (country) filteredPerfs = filteredPerfs.filter(function(p) { return p.nationality === country; });
  if (gender) filteredPerfs = filteredPerfs.filter(function(p) { return p.gender === gender; });
  if (search) {
    filteredPerfs = filteredPerfs.filter(function(p) {
      return p.runner.toLowerCase().indexOf(search) >= 0 ||
             getRaceName(p).toLowerCase().indexOf(search) >= 0 ||
             (p.nationality && p.nationality.toLowerCase().indexOf(search) >= 0) ||
             String(p.year).indexOf(search) >= 0;
    });
  }

  // Sort by distance desc (best performances first)
  filteredPerfs.sort(function(a, b) { return b.distance_mi - a.distance_mi || b.year - a.year; });

  renderBrowseList();
}

function updateCascadingFilters(dist) {
  var raceFilter = document.getElementById('filterRace');
  var countryFilter = document.getElementById('filterCountry');
  var currentRace = raceFilter.value;
  var currentCountry = countryFilter.value;

  var perfs = indexData.performances;
  if (dist) perfs = perfs.filter(function(p) { return p.distance_id === dist; });

  // Update races
  var raceIds = [];
  perfs.forEach(function(p) { if (raceIds.indexOf(p.race_id) === -1) raceIds.push(p.race_id); });
  var races = indexData.races.filter(function(r) { return raceIds.indexOf(r.id) >= 0; });
  races.sort(function(a, b) { return a.name.localeCompare(b.name); });
  raceFilter.innerHTML = '<option value="">All races</option>' +
    races.map(function(r) { return '<option value="' + r.id + '"' + (r.id === currentRace ? ' selected' : '') + '>' + r.name + '</option>'; }).join('');

  // Update countries
  var countries = [];
  perfs.forEach(function(p) { if (p.nationality && countries.indexOf(p.nationality) === -1) countries.push(p.nationality); });
  countries.sort();
  countryFilter.innerHTML = '<option value="">All countries</option>' +
    countries.map(function(c) { return '<option value="' + c + '"' + (c === currentCountry ? ' selected' : '') + '>' + c + '</option>'; }).join('');
}

// === Rendering ===

function renderBrowseList() {
  var list = document.getElementById('perfList');
  var header = document.getElementById('resultsHeader');

  header.innerHTML = '<span class="results-count">' + filteredPerfs.length + ' performances</span>';

  if (filteredPerfs.length === 0) {
    list.innerHTML = '<div class="no-data-msg">No performances match your filters.</div>';
    return;
  }

  // Show max 100, with message if truncated
  var shown = filteredPerfs.slice(0, 100);

  list.innerHTML = shown.map(function(p) {
    var isSelected = selected.has(p.id);
    return '<div class="perf-item' + (isSelected ? ' selected' : '') + '" data-id="' + p.id + '">' +
      '<input type="checkbox"' + (isSelected ? ' checked' : '') + '>' +
      '<div class="perf-meta">' +
        '<div class="perf-runner">' +
          (p.nationality ? '<span class="perf-flag">' + p.nationality + '</span> ' : '') +
          p.runner +
          (p.note ? ' <span class="perf-note">' + p.note + '</span>' : '') +
        '</div>' +
        '<div class="perf-detail">' + getRaceName(p) + ' ' + p.year + '</div>' +
      '</div>' +
      '<div class="perf-stats">' +
        '<span>' + p.distance_mi + ' mi</span>' +
        '<span>' + p.duration + '</span>' +
        '<span>' + fmtPace(p.pace_sec) + '/mi</span>' +
      '</div>' +
      '<button class="perf-add">' + (isSelected ? '✓' : '+') + '</button>' +
    '</div>';
  }).join('');

  if (filteredPerfs.length > 100) {
    list.innerHTML += '<div class="no-data-msg">Showing 100 of ' + filteredPerfs.length + '. Use filters to narrow down.</div>';
  }

  // Wire click handlers
  list.querySelectorAll('.perf-item').forEach(function(el) {
    el.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT') return;
      togglePerf(this.dataset.id);
    });
    el.querySelector('input').addEventListener('change', function() {
      togglePerf(el.dataset.id);
    });
  });
}

function renderCartList() {
  var list = document.getElementById('cartList');
  var empty = document.getElementById('cartEmpty');
  var actions = document.getElementById('cartActions');

  if (selected.size === 0) {
    empty.style.display = '';
    list.innerHTML = '';
    actions.style.display = 'none';
    return;
  }

  empty.style.display = 'none';
  actions.style.display = '';

  var selectedPerfs = [];
  selected.forEach(function(id) {
    var p = indexData.performances.find(function(x) { return x.id === id; });
    if (p) selectedPerfs.push(p);
  });

  list.innerHTML = selectedPerfs.map(function(p, i) {
    return '<div class="cart-item">' +
      '<span style="color:' + CHART_COLORS[i % CHART_COLORS.length] + ';font-weight:700;width:20px;text-align:center">' + (i + 1) + '</span>' +
      '<div class="perf-meta">' +
        '<div class="perf-runner">' +
          (p.nationality ? '<span class="perf-flag">' + p.nationality + '</span> ' : '') +
          p.runner +
          (p.note ? ' <span class="perf-note">' + p.note + '</span>' : '') +
        '</div>' +
        '<div class="perf-detail">' + getRaceName(p) + ' ' + p.year + ' — ' + p.distance_mi + ' mi, ' + p.duration + '</div>' +
      '</div>' +
      '<button class="cart-remove" data-id="' + p.id + '">&times;</button>' +
    '</div>';
  }).join('');

  list.querySelectorAll('.cart-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      selected.delete(this.dataset.id);
      updateAll();
    });
  });
}

function updateAll() {
  // Update pill count
  document.getElementById('pillCount').textContent = selected.size;

  // Re-render current view
  if (currentView === 'browse') {
    renderBrowseList();
  } else {
    renderCartList();
  }

  // Update viz area
  if (selected.size > 0) {
    document.getElementById('vizArea').style.display = '';
    renderViz();
  } else {
    document.getElementById('vizArea').style.display = 'none';
  }
}

function togglePerf(id) {
  if (selected.has(id)) {
    selected.delete(id);
  } else {
    selected.add(id);
  }
  updateAll();
}

function switchView(view) {
  currentView = view;
  document.getElementById('pillBrowse').classList.toggle('active', view === 'browse');
  document.getElementById('pillSelected').classList.toggle('active', view === 'cart');
  document.getElementById('browseView').style.display = view === 'browse' ? '' : 'none';
  document.getElementById('filterBar').style.display = view === 'browse' ? '' : 'none';
  document.getElementById('cartView').style.display = view === 'cart' ? '' : 'none';

  if (view === 'cart') renderCartList();
  if (view === 'browse') renderBrowseList();
}

// === Visualization ===

async function renderViz() {
  var content = document.getElementById('vizContent');
  var controls = document.getElementById('vizControls');

  // Destroy existing charts
  Object.values(charts).forEach(function(c) { if (c && c.destroy) c.destroy(); });
  charts = {};

  if (selected.size === 0) {
    content.innerHTML = '<div class="no-data-msg">Select performances to visualize.</div>';
    return;
  }

  content.innerHTML = '<div class="loading">Loading splits...</div>';

  // Load all selected
  var entries = [];
  for (var id of selected) {
    var perf = indexData.performances.find(function(p) { return p.id === id; });
    var splits = await loadSplits(id);
    if (splits && perf) entries.push({ perf: perf, splits: splits });
  }

  if (entries.length === 0) {
    content.innerHTML = '<div class="no-data-msg">Could not load split data.</div>';
    return;
  }

  entries.sort(function(a, b) { return b.perf.distance_mi - a.perf.distance_mi; });

  // Update tab disabled states
  var mileEntries = entries.filter(function(e) { return hasMileData(e.splits); });
  document.querySelectorAll('.viz-tab').forEach(function(tab) {
    var viz = tab.dataset.viz;
    var needsMile = viz === 'pace' || viz === 'gap' || viz === 'heatmap';
    tab.classList.toggle('disabled', needsMile && mileEntries.length < 2);
  });

  // Build toggles
  var toggleHTML = '<div class="year-toggles" id="vizToggles">';
  entries.forEach(function(e, i) {
    toggleHTML += '<label><input type="checkbox" checked data-idx="' + i + '"> ' +
      '<span style="color:' + CHART_COLORS[i % CHART_COLORS.length] + ';font-weight:600">' +
      e.perf.runner + ' ' + e.perf.year + '</span></label>';
  });
  toggleHTML += '</div>';

  content.innerHTML = '';

  switch (currentViz) {
    case 'projection':
      renderProjection(content, entries, toggleHTML, controls);
      break;
    case 'pace':
      if (mileEntries.length < 2) {
        content.innerHTML = '<div class="no-data-msg">Pace overlay requires 2+ performances with per-mile splits.</div>';
      } else {
        renderPaceOverlay(content, entries, mileEntries, toggleHTML);
      }
      controls.innerHTML = '';
      break;
    case 'gap':
      if (mileEntries.length < 2) {
        content.innerHTML = '<div class="no-data-msg">Time gap requires 2+ performances with per-mile splits.</div>';
      } else {
        renderTimeGap(content, entries, mileEntries);
      }
      controls.innerHTML = '';
      break;
    case 'heatmap':
      if (mileEntries.length < 2) {
        content.innerHTML = '<div class="no-data-msg">Heatmap requires 2+ performances with per-mile splits.</div>';
      } else {
        renderHeatmap(content, mileEntries);
      }
      controls.innerHTML = '';
      break;
  }
}

function renderProjection(container, entries, toggleHTML, controls) {
  // Baseline selector in controls
  controls.innerHTML = '<div class="filter-group">' +
    '<label class="filter-label">Baseline (even pace reference)</label>' +
    '<select id="baselineSelect" style="background:var(--bg-card);color:var(--text-primary);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-size:14px;">' +
    entries.map(function(e) {
      return '<option value="' + e.perf.id + '">' + e.perf.runner + ' — ' + getRaceName(e.perf) + ' ' + e.perf.year +
        ' (' + e.perf.distance_mi + ' mi)</option>';
    }).join('') +
    '</select></div>';

  document.getElementById('baselineSelect').addEventListener('change', function() { renderViz(); });

  var baselineId = document.getElementById('baselineSelect').value;
  var baselineEntry = entries.find(function(e) { return e.perf.id === baselineId; }) || entries[0];

  var baselinePairs = getTimeDistancePairs(baselineEntry.splits);
  var lastPair = baselinePairs[baselinePairs.length - 1];
  var evenPace = lastPair.time_sec / lastPair.distance_mi;

  var datasets = entries.map(function(e, i) {
    var pairs = getTimeDistancePairs(e.splits);
    var isCheckpoint = !hasMileData(e.splits);
    return {
      label: e.perf.runner + ' ' + e.perf.year + ' (' + e.perf.distance_mi + ' mi)',
      data: pairs.map(function(p) {
        return { x: p.time_sec / 3600, y: p.distance_mi - (p.time_sec / evenPace) };
      }),
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      pointRadius: isCheckpoint ? 5 : 0,
      pointHoverRadius: isCheckpoint ? 7 : 5,
      borderWidth: 2, tension: 0.2, fill: false, showLine: true,
    };
  });

  // Even pace reference line
  var maxTime = Math.max.apply(null, entries.map(function(e) {
    var p = getTimeDistancePairs(e.splits);
    return p[p.length - 1].time_sec;
  }));
  datasets.unshift({
    label: 'Even Pace (' + fmtPace(Math.round(evenPace)) + '/mi)',
    data: [{ x: 0, y: 0 }, { x: maxTime / 3600, y: 0 }],
    borderColor: '#ffffff44', borderWidth: 2, borderDash: [8, 4],
    pointRadius: 0, fill: false,
  });

  container.insertAdjacentHTML('beforeend',
    '<div class="chart-card"><h3>Pacing Projection vs Even Splits</h3>' +
    '<div class="desc">Baseline: <strong>' + baselineEntry.perf.runner + ' ' + baselineEntry.perf.year +
    '</strong> — even pace ' + fmtPace(Math.round(evenPace)) + '/mi. Above = ahead of schedule.</div>' +
    toggleHTML +
    '<div style="height:500px"><canvas id="projChart"></canvas></div></div>'
  );

  charts.projection = new Chart(document.getElementById('projChart'), {
    type: 'line',
    data: { datasets: datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'nearest', intersect: false },
      plugins: {
        tooltip: {
          callbacks: {
            title: function(items) { return items.length ? fmtHours(items[0].raw.x * 3600) : ''; },
            label: function(ctx) {
              if (ctx.datasetIndex === 0) return 'Even pace baseline';
              var v = ctx.raw.y;
              return ctx.dataset.label + ': ' + (v >= 0 ? '+' : '') + v.toFixed(2) + ' mi';
            }
          }
        },
        legend: { labels: { usePointStyle: true } }
      },
      scales: {
        x: { type: 'linear', title: { display: true, text: 'Elapsed Time (hours)' },
             ticks: { callback: function(v) { return v + 'h'; } },
             grid: { color: 'rgba(139,148,158,0.08)' } },
        y: { title: { display: true, text: 'Miles Ahead / Behind Even Pace' },
             ticks: { callback: function(v) { return (v >= 0 ? '+' : '') + v.toFixed(1); } },
             grid: { color: function(ctx) { return ctx.tick.value === 0 ? '#ffffff33' : 'rgba(139,148,158,0.08)'; } } }
      }
    }
  });

  wireToggles('vizToggles', charts.projection);
}

function renderPaceOverlay(container, allEntries, mileEntries, toggleHTML) {
  var maxMiles = Math.max.apply(null, mileEntries.map(function(e) { return e.splits.miles.length; }));
  var labels = Array.from({ length: maxMiles }, function(_, i) { return i + 1; });
  var longRace = maxMiles > 20;

  container.insertAdjacentHTML('beforeend',
    '<div class="chart-card"><h3>Mile-by-Mile Pace Comparison</h3>' +
    '<div class="desc">Each runner\'s pace per mile overlaid.' +
    (allEntries.length > mileEntries.length ? ' (' + (allEntries.length - mileEntries.length) + ' checkpoint-only not shown.)' : '') +
    '</div>' + toggleHTML +
    '<div style="height:400px"><canvas id="paceChart"></canvas></div></div>'
  );

  charts.pace = new Chart(document.getElementById('paceChart'), {
    type: 'line',
    data: {
      labels: labels,
      datasets: mileEntries.map(function(e, i) {
        var idx = allEntries.indexOf(e);
        return {
          label: e.perf.runner + ' ' + e.perf.year,
          data: e.splits.miles.map(function(m) { return m.moving_sec; }),
          borderColor: CHART_COLORS[idx % CHART_COLORS.length],
          pointRadius: longRace ? 0 : 4, pointHoverRadius: 5,
          borderWidth: 2, tension: 0.2,
        };
      })
    },
    options: chartOptions({
      yReverse: true, yLabel: 'Pace (min/mi)', xLabel: 'Mile', longRace: longRace,
      yFmt: fmtPace, tooltipFmt: function(ctx) { return ctx.dataset.label + ': ' + fmtPace(ctx.raw) + '/mi'; }
    })
  });

  wireToggles('vizToggles', charts.pace, function(globalIdx) {
    return mileEntries.indexOf(allEntries[globalIdx]);
  });
}

function renderTimeGap(container, allEntries, mileEntries) {
  var maxMiles = Math.max.apply(null, mileEntries.map(function(e) { return e.splits.miles.length; }));
  var labels = Array.from({ length: maxMiles }, function(_, i) { return i + 1; });
  var longRace = maxMiles > 20;

  var baseIdx = mileEntries.reduce(function(best, e, i) {
    var avg = e.splits.miles.reduce(function(s, m) { return s + m.moving_sec; }, 0) / e.splits.miles.length;
    var bestAvg = mileEntries[best].splits.miles.reduce(function(s, m) { return s + m.moving_sec; }, 0) / mileEntries[best].splits.miles.length;
    return avg < bestAvg ? i : best;
  }, 0);

  var baseCum = [];
  var cs = 0;
  mileEntries[baseIdx].splits.miles.forEach(function(m) { cs += m.moving_sec; baseCum.push(cs); });

  container.insertAdjacentHTML('beforeend',
    '<div class="chart-card"><h3>Cumulative Time Gap</h3>' +
    '<div class="desc">Seconds ahead (+) or behind (−) ' + mileEntries[baseIdx].perf.runner + ' ' + mileEntries[baseIdx].perf.year + '.</div>' +
    '<div style="height:300px"><canvas id="gapChart"></canvas></div></div>'
  );

  charts.gap = new Chart(document.getElementById('gapChart'), {
    type: 'line',
    data: {
      labels: labels,
      datasets: mileEntries.map(function(e, i) {
        var cum = []; var s = 0;
        e.splits.miles.forEach(function(m, j) {
          s += m.moving_sec;
          cum.push(s - (baseCum[j] || baseCum[baseCum.length - 1]));
        });
        var idx = allEntries.indexOf(e);
        return {
          label: e.perf.runner + ' ' + e.perf.year + (i === baseIdx ? ' (fastest)' : ''),
          data: cum,
          borderColor: CHART_COLORS[idx % CHART_COLORS.length],
          borderWidth: i === baseIdx ? 3 : 2,
          borderDash: i === baseIdx ? [] : [5, 3],
          pointRadius: longRace ? 0 : 3, pointHoverRadius: 4,
          tension: 0.2, fill: false,
        };
      })
    },
    options: chartOptions({
      yLabel: 'Gap (seconds)', xLabel: 'Mile', longRace: longRace,
      yFmt: function(v) { return (v > 0 ? '+' : '') + v + 's'; },
      tooltipFmt: function(ctx) { return ctx.dataset.label + ': ' + (ctx.raw > 0 ? '+' : '') + ctx.raw.toFixed(0) + 's'; }
    })
  });
}

function renderHeatmap(container, mileEntries) {
  var minMiles = Math.min.apply(null, mileEntries.map(function(e) { return e.splits.miles.length; }));

  var html = '<div class="chart-card"><h3>Split Heatmap</h3>' +
    '<div class="desc">Color shows fastest (<span style="color:var(--green)">green</span>) and slowest (<span style="color:var(--red)">red</span>) per mile.</div>' +
    '<div class="table-wrapper"><table><thead><tr><th>Mile</th>';

  mileEntries.forEach(function(e, i) {
    html += '<th style="color:' + CHART_COLORS[i % CHART_COLORS.length] + '">' + e.perf.runner + ' ' + e.perf.year + '</th>';
  });
  html += '<th>Spread</th></tr></thead><tbody>';

  for (var m = 0; m < minMiles; m++) {
    var vals = mileEntries.map(function(e) {
      return e.splits.miles[m] ? e.splits.miles[m].moving_sec : undefined;
    }).filter(function(v) { return v !== undefined; });
    if (vals.length === 0) continue;
    var best = Math.min.apply(null, vals), worst = Math.max.apply(null, vals);
    html += '<tr><td>' + (m + 1) + '</td>';
    mileEntries.forEach(function(e) {
      var v = e.splits.miles[m] ? e.splits.miles[m].moving_sec : undefined;
      if (v === undefined) { html += '<td>-</td>'; return; }
      var cls = v === best && vals.length > 1 ? ' class="fastest"' : v === worst && vals.length > 1 ? ' class="slowest"' : '';
      html += '<td' + cls + '>' + fmtPace(v) + '</td>';
    });
    html += '<td style="color:var(--text-muted)">' + (worst - best) + 's</td></tr>';
  }

  html += '</tbody></table></div></div>';
  container.insertAdjacentHTML('beforeend', html);
}

// === Shared Helpers ===

function chartOptions(opts) {
  var tickCb = opts.longRace ? { callback: function(v, i) { return (i + 1) % 10 === 0 ? i + 1 : ''; } } : {};
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      tooltip: { callbacks: { label: opts.tooltipFmt } },
      legend: { labels: { usePointStyle: true } }
    },
    scales: {
      y: { reverse: !!opts.yReverse, ticks: { callback: opts.yFmt }, title: { display: true, text: opts.yLabel } },
      x: { title: { display: true, text: opts.xLabel }, grid: { display: false }, ticks: tickCb }
    }
  };
}

function wireToggles(toggleContainerId, chart, indexMapper) {
  var container = document.getElementById(toggleContainerId);
  if (!container) return;
  container.querySelectorAll('input').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var idx = parseInt(this.dataset.idx);
      var chartIdx = indexMapper ? indexMapper(idx) : idx;
      // +1 for projection (reference line at 0), no offset for others
      var offset = chart === charts.projection ? 1 : 0;
      if (chartIdx >= 0 && chart.data.datasets[chartIdx + offset]) {
        chart.data.datasets[chartIdx + offset].hidden = !this.checked;
        chart.update();
      }
    });
  });
}

// === Event Wiring ===

function wireEvents() {
  // Pill toggle
  document.getElementById('pillBrowse').addEventListener('click', function() { switchView('browse'); });
  document.getElementById('pillSelected').addEventListener('click', function() { switchView('cart'); });

  // Filters
  ['filterDistance', 'filterRace', 'filterCountry', 'filterGender'].forEach(function(id) {
    document.getElementById(id).addEventListener('change', applyFilters);
  });
  document.getElementById('searchInput').addEventListener('input', applyFilters);

  // Clear all
  document.getElementById('clearAll').addEventListener('click', function() {
    selected.clear();
    updateAll();
  });

  // Viz tabs
  document.querySelectorAll('.viz-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      if (this.classList.contains('disabled')) return;
      currentViz = this.dataset.viz;
      document.querySelectorAll('.viz-tab').forEach(function(t) {
        t.classList.toggle('active', t.dataset.viz === currentViz);
      });
      renderViz();
    });
  });
}

// === Init ===

document.addEventListener('DOMContentLoaded', function() {
  Chart.defaults.color = '#8b949e';
  Chart.defaults.borderColor = 'rgba(139,148,158,0.15)';
  Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif';
  loadIndex();
});
