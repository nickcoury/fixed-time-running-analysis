// Fixed-Time Running Analysis — Client App
// Loads index.json for discovery, fetches individual split files on demand.

const DATA_BASE = 'data';
const CHART_COLORS = ['#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149', '#79c0ff', '#56d364', '#e3b341'];

let indexData = null;
let loadedSplits = {};
let charts = {};

// State per mode
const projState = { selectedIds: new Set() };
const compareState = { selectedIds: new Set() };

// === Utilities ===

function fmtPace(sec) {
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtTime(sec) {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = Math.round(sec % 60);
  return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

function fmtHours(sec) {
  const h = sec / 3600;
  return h.toFixed(1) + 'h';
}

// === Data Loading ===

async function loadIndex() {
  const res = await fetch(DATA_BASE + '/index.json');
  indexData = await res.json();
  initProjectionMode();
  initCompareMode();
}

async function loadSplits(perfId) {
  if (loadedSplits[perfId]) return loadedSplits[perfId];
  const perf = indexData.performances.find(function(p) { return p.id === perfId; });
  if (!perf) return null;
  const res = await fetch(DATA_BASE + '/splits/' + perf.splits_file);
  const data = await res.json();
  loadedSplits[perfId] = data;
  return data;
}

// Normalize split data into array of {time_sec, distance_mi} pairs
// Works with both per-mile data (miles[]) and checkpoint data (checkpoints[])
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
      if (time && dist) {
        pairs.push({ time_sec: time, distance_mi: dist, label: cp.label });
      }
    });
    // Sort by time
    pairs.sort(function(a, b) { return a.time_sec - b.time_sec; });
  }

  return pairs;
}

// Check if splits have per-mile granularity
function hasMileData(splits) {
  return splits.miles && splits.miles.length > 0;
}

// === Mode Switching ===

function switchMode(mode) {
  document.querySelectorAll('.mode-tab').forEach(function(t) {
    t.classList.toggle('active', t.dataset.mode === mode);
  });
  document.getElementById('projectionMode').style.display = mode === 'projection' ? '' : 'none';
  document.getElementById('projCompareBar').style.display = mode === 'projection' ? '' : 'none';
  document.getElementById('compareMode').style.display = mode === 'compare' ? '' : 'none';
  document.getElementById('compareBar').style.display = mode === 'compare' ? '' : 'none';
}

// =============================================
// PROJECTION MODE — Even Split Deviation Chart
// =============================================

function initProjectionMode() {
  const baselineSelect = document.getElementById('baselineSelect');

  // Populate baseline dropdown with all performances
  baselineSelect.innerHTML = indexData.performances.map(function(p) {
    var race = indexData.races.find(function(r) { return r.id === p.race_id; });
    var raceName = race ? race.name : p.race_id;
    return '<option value="' + p.id + '">' + p.runner + ' — ' + raceName + ' ' + p.year +
      ' (' + p.distance_mi + ' mi, ' + p.duration + ')' +
      (p.note ? ' [' + p.note + ']' : '') + '</option>';
  }).join('');

  baselineSelect.addEventListener('change', renderProjectionPerfs);
  renderProjectionPerfs();
}

function renderProjectionPerfs() {
  var list = document.getElementById('projPerfList');
  var perfs = indexData.performances;

  // Sort by distance desc, then year
  perfs.sort(function(a, b) { return b.distance_mi - a.distance_mi || b.year - a.year; });

  list.innerHTML = perfs.map(function(p) {
    var race = indexData.races.find(function(r) { return r.id === p.race_id; });
    var checked = projState.selectedIds.has(p.id) ? ' checked' : '';
    var selected = projState.selectedIds.has(p.id) ? ' selected' : '';
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

  list.querySelectorAll('.perf-item').forEach(function(el) {
    el.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT') return;
      var cb = this.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      toggleProjectionPerf(this.dataset.id, cb.checked);
    });
    el.querySelector('input').addEventListener('change', function() {
      toggleProjectionPerf(el.dataset.id, this.checked);
    });
  });

  updateProjectionBar();
}

function toggleProjectionPerf(id, checked) {
  if (checked) projState.selectedIds.add(id); else projState.selectedIds.delete(id);

  document.querySelectorAll('#projPerfList .perf-item').forEach(function(el) {
    el.classList.toggle('selected', projState.selectedIds.has(el.dataset.id));
    el.querySelector('input').checked = projState.selectedIds.has(el.dataset.id);
  });

  updateProjectionBar();
}

function updateProjectionBar() {
  var bar = document.getElementById('projCompareBar');
  var btn = document.getElementById('projCompareBtn');
  var count = projState.selectedIds.size;

  if (count > 0) {
    bar.classList.add('visible');
    btn.textContent = 'Show Projection (' + count + ')';
    btn.disabled = false;
  } else {
    bar.classList.remove('visible');
  }
}

async function runProjection() {
  var chartsSection = document.getElementById('projChartsSection');
  chartsSection.innerHTML = '<div class="loading">Loading splits...</div>';
  chartsSection.style.display = 'block';

  // Load baseline
  var baselineId = document.getElementById('baselineSelect').value;
  var baselinePerf = indexData.performances.find(function(p) { return p.id === baselineId; });
  var baselineSplits = await loadSplits(baselineId);

  if (!baselinePerf || !baselineSplits) {
    chartsSection.innerHTML = '<div class="loading">Could not load baseline performance.</div>';
    return;
  }

  // Calculate baseline even pace: total_time / total_distance = sec per mile
  var baselinePairs = getTimeDistancePairs(baselineSplits);
  var lastPair = baselinePairs[baselinePairs.length - 1];
  var baselineTotalTime = lastPair.time_sec;
  var baselineTotalMiles = lastPair.distance_mi;
  var evenPaceSecPerMile = baselineTotalTime / baselineTotalMiles;

  // Load all selected performances
  var entries = [];
  for (var id of projState.selectedIds) {
    var perf = indexData.performances.find(function(p) { return p.id === id; });
    var splits = await loadSplits(id);
    if (splits && perf) entries.push({ perf: perf, splits: splits });
  }

  if (entries.length === 0) {
    chartsSection.innerHTML = '<div class="loading">Select at least one performance.</div>';
    return;
  }

  entries.sort(function(a, b) { return a.perf.year - b.perf.year; });
  chartsSection.innerHTML = '';

  // The projection chart:
  // X axis = elapsed time (hours)
  // Y axis = miles ahead/behind even pace
  // At each mile M with cumulative time T:
  //   even_pace_distance_at_T = T / evenPaceSecPerMile
  //   deviation = M - even_pace_distance_at_T (positive = ahead)
  //
  // The baseline performance itself will oscillate around 0 if it had uneven pacing,
  // ending exactly at 0 (by definition — same total distance and time).

  // Build datasets
  var datasets = entries.map(function(e, i) {
    var pairs = getTimeDistancePairs(e.splits);
    var isCheckpoint = !hasMileData(e.splits);
    var points = [];

    pairs.forEach(function(p) {
      var elapsedHours = p.time_sec / 3600;
      var expectedMilesAtThisTime = p.time_sec / evenPaceSecPerMile;
      var deviation = p.distance_mi - expectedMilesAtThisTime;
      points.push({ x: elapsedHours, y: deviation });
    });

    return {
      label: e.perf.runner + ' ' + e.perf.year + ' (' + e.perf.distance_mi + ' mi)',
      data: points,
      borderColor: CHART_COLORS[i % CHART_COLORS.length],
      pointRadius: isCheckpoint ? 5 : 0,
      pointHoverRadius: isCheckpoint ? 7 : 5,
      borderWidth: 2,
      tension: 0.2,
      fill: false,
      showLine: true,
    };
  });

  // Add the even pace reference line (y=0)
  var maxTime = Math.max.apply(null, entries.map(function(e) {
    var pairs = getTimeDistancePairs(e.splits);
    return pairs[pairs.length - 1].time_sec;
  }));
  datasets.unshift({
    label: 'Even Pace (' + fmtPace(Math.round(evenPaceSecPerMile)) + '/mi for ' + baselinePerf.distance_mi + ' mi)',
    data: [{ x: 0, y: 0 }, { x: maxTime / 3600, y: 0 }],
    borderColor: '#ffffff44',
    borderWidth: 2,
    borderDash: [8, 4],
    pointRadius: 0,
    fill: false,
  });

  // Year toggles
  var toggleHTML = '<div class="year-toggles" id="projToggles">';
  entries.forEach(function(e, i) {
    toggleHTML += '<label><input type="checkbox" checked data-idx="' + (i + 1) + '"> ' +
      '<span style="color:' + CHART_COLORS[i % CHART_COLORS.length] + ';font-weight:600">' +
      e.perf.runner + ' ' + e.perf.year + '</span></label>';
  });
  toggleHTML += '</div>';

  // Baseline info
  var baselineRace = indexData.races.find(function(r) { return r.id === baselinePerf.race_id; });
  var baselineDesc = baselinePerf.runner + ' — ' + (baselineRace ? baselineRace.name : '') + ' ' + baselinePerf.year +
    ' (' + baselinePerf.distance_mi + ' mi in ' + baselinePerf.duration + ')';

  chartsSection.insertAdjacentHTML('beforeend',
    '<div class="chart-card">' +
    '<h3>Pacing Projection vs Even Splits</h3>' +
    '<div class="desc">Baseline: <strong>' + baselineDesc + '</strong> — even pace would be ' +
    fmtPace(Math.round(evenPaceSecPerMile)) + '/mi. Above the line = ahead of that schedule, below = behind.</div>' +
    toggleHTML +
    '<div style="height:500px"><canvas id="projChart"></canvas></div>' +
    '</div>'
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
            title: function(items) {
              if (!items.length) return '';
              return fmtHours(items[0].raw.x * 3600);
            },
            label: function(ctx) {
              if (ctx.datasetIndex === 0) return 'Even pace baseline';
              var v = ctx.raw.y;
              var sign = v >= 0 ? '+' : '';
              var miAt = ctx.raw.x * 3600 / evenPaceSecPerMile + v;
              return ctx.dataset.label + ': ' + sign + v.toFixed(2) + ' mi (' + miAt.toFixed(1) + ' mi covered)';
            }
          }
        },
        legend: { labels: { usePointStyle: true } }
      },
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 'Elapsed Time (hours)' },
          ticks: { callback: function(v) { return v + 'h'; } },
          grid: { color: 'rgba(139,148,158,0.08)' }
        },
        y: {
          title: { display: true, text: 'Miles Ahead / Behind Even Pace' },
          ticks: {
            callback: function(v) { return (v >= 0 ? '+' : '') + v.toFixed(1); }
          },
          grid: { color: function(ctx) { return ctx.tick.value === 0 ? '#ffffff33' : 'rgba(139,148,158,0.08)'; } }
        }
      }
    }
  });

  // Wire toggles
  document.getElementById('projToggles').querySelectorAll('input').forEach(function(cb) {
    cb.addEventListener('change', function() {
      var idx = parseInt(this.dataset.idx);
      charts.projection.data.datasets[idx].hidden = !this.checked;
      charts.projection.update();
    });
  });

  chartsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// =============================================
// COMPARE MODE — Side-by-Side Comparison
// =============================================

function initCompareMode() {
  var distFilter = document.getElementById('filterDistance');
  var raceFilter = document.getElementById('filterRace');

  var distances = [];
  indexData.performances.forEach(function(p) {
    if (distances.indexOf(p.distance_id) === -1) distances.push(p.distance_id);
  });
  distFilter.innerHTML = '<option value="">All distances</option>' +
    indexData.distances.filter(function(d) { return distances.indexOf(d.id) >= 0; }).map(function(d) {
      return '<option value="' + d.id + '">' + d.name + '</option>';
    }).join('');

  var raceIds = [];
  indexData.performances.forEach(function(p) {
    if (raceIds.indexOf(p.race_id) === -1) raceIds.push(p.race_id);
  });
  raceFilter.innerHTML = '<option value="">All races</option>' +
    indexData.races.filter(function(r) { return raceIds.indexOf(r.id) >= 0; }).map(function(r) {
      return '<option value="' + r.id + '">' + r.name + '</option>';
    }).join('');

  distFilter.addEventListener('change', renderComparePerfs);
  raceFilter.addEventListener('change', renderComparePerfs);
  document.getElementById('filterRunner').addEventListener('input', renderComparePerfs);
  renderComparePerfs();
}

function renderComparePerfs() {
  var distVal = document.getElementById('filterDistance').value;
  var raceVal = document.getElementById('filterRace').value;
  var runnerVal = document.getElementById('filterRunner').value.toLowerCase().trim();
  var list = document.getElementById('perfList');

  var perfs = indexData.performances.slice();
  if (distVal) perfs = perfs.filter(function(p) { return p.distance_id === distVal; });
  if (raceVal) perfs = perfs.filter(function(p) { return p.race_id === raceVal; });
  if (runnerVal) perfs = perfs.filter(function(p) { return p.runner.toLowerCase().indexOf(runnerVal) >= 0; });

  perfs.sort(function(a, b) { return b.distance_mi - a.distance_mi || b.year - a.year; });

  list.innerHTML = perfs.map(function(p) {
    var race = indexData.races.find(function(r) { return r.id === p.race_id; });
    var checked = compareState.selectedIds.has(p.id) ? ' checked' : '';
    var selected = compareState.selectedIds.has(p.id) ? ' selected' : '';
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

  list.querySelectorAll('.perf-item').forEach(function(el) {
    el.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT') return;
      var cb = this.querySelector('input[type="checkbox"]');
      cb.checked = !cb.checked;
      toggleComparePerf(this.dataset.id, cb.checked);
    });
    el.querySelector('input').addEventListener('change', function() {
      toggleComparePerf(el.dataset.id, this.checked);
    });
  });

  updateCompareBar();
}

function toggleComparePerf(id, checked) {
  if (checked) compareState.selectedIds.add(id); else compareState.selectedIds.delete(id);

  document.querySelectorAll('#perfList .perf-item').forEach(function(el) {
    el.classList.toggle('selected', compareState.selectedIds.has(el.dataset.id));
    el.querySelector('input').checked = compareState.selectedIds.has(el.dataset.id);
  });

  updateCompareBar();
}

function updateCompareBar() {
  var bar = document.getElementById('compareBar');
  var btn = document.getElementById('compareBtn');
  var count = compareState.selectedIds.size;

  if (count > 0) {
    bar.classList.add('visible');
    btn.textContent = 'Compare ' + count + ' performance' + (count > 1 ? 's' : '');
    btn.disabled = count < 2;
  } else {
    bar.classList.remove('visible');
  }
}

async function runComparison() {
  var chartsSection = document.getElementById('chartsSection');
  chartsSection.innerHTML = '<div class="loading">Loading splits...</div>';
  chartsSection.style.display = 'block';

  var entries = [];
  for (var id of compareState.selectedIds) {
    var perf = indexData.performances.find(function(p) { return p.id === id; });
    var splits = await loadSplits(id);
    if (splits && perf) entries.push({ perf: perf, splits: splits });
  }

  if (entries.length < 2) {
    chartsSection.innerHTML = '<div class="loading">Need at least 2 performances to compare.</div>';
    return;
  }

  entries.sort(function(a, b) { return a.perf.year - b.perf.year; });

  // Split entries into those with per-mile data vs checkpoint-only
  var mileEntries = entries.filter(function(e) { return hasMileData(e.splits); });
  var checkpointEntries = entries.filter(function(e) { return !hasMileData(e.splits); });

  chartsSection.innerHTML = '';

  // Toggle HTML
  var toggleHTML = '<div class="year-toggles" id="cmpToggles">';
  entries.forEach(function(e, i) {
    toggleHTML += '<label><input type="checkbox" checked data-idx="' + i + '"> ' +
      '<span style="color:' + CHART_COLORS[i % CHART_COLORS.length] + ';font-weight:600">' +
      e.perf.runner + ' ' + e.perf.year + '</span></label>';
  });
  toggleHTML += '</div>';

  if (mileEntries.length >= 2) {
    // Per-mile charts: pace overlay, time gap, heatmap
    var maxMiles = Math.max.apply(null, mileEntries.map(function(e) { return e.splits.miles.length; }));
    var minMiles = Math.min.apply(null, mileEntries.map(function(e) { return e.splits.miles.length; }));
    var labels = Array.from({ length: maxMiles }, function(_, i) { return i + 1; });
    var longRace = maxMiles > 20;

    // 1. Pace overlay
    renderChartCard(chartsSection, 'cmpPaceOverlay', 'Mile-by-Mile Pace Comparison',
      'Each performance overlaid. Toggle visibility with checkboxes.' +
      (checkpointEntries.length ? ' (' + checkpointEntries.length + ' checkpoint-only performances not shown.)' : ''),
      toggleHTML, 400);

    var paceChart = new Chart(document.getElementById('cmpPaceOverlay'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: mileEntries.map(function(e, i) {
          return {
            label: e.perf.runner + ' ' + e.perf.year,
            data: e.splits.miles.map(function(m) { return m.moving_sec; }),
            borderColor: CHART_COLORS[entries.indexOf(e) % CHART_COLORS.length],
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

    // Wire toggles
    document.getElementById('cmpToggles').querySelectorAll('input').forEach(function(cb) {
      cb.addEventListener('change', function() {
        var idx = parseInt(this.dataset.idx);
        if (mileEntries.indexOf(entries[idx]) >= 0) {
          var mileIdx = mileEntries.indexOf(entries[idx]);
          paceChart.data.datasets[mileIdx].hidden = !this.checked;
          paceChart.update();
        }
      });
    });

    // 2. Time gap
    var baseIdx = mileEntries.reduce(function(best, e, i) {
      var avg = e.splits.miles.reduce(function(s, m) { return s + m.moving_sec; }, 0) / e.splits.miles.length;
      var bestAvg = mileEntries[best].splits.miles.reduce(function(s, m) { return s + m.moving_sec; }, 0) / mileEntries[best].splits.miles.length;
      return avg < bestAvg ? i : best;
    }, 0);

    var baseCum = [];
    var cs = 0;
    mileEntries[baseIdx].splits.miles.forEach(function(m) { cs += m.moving_sec; baseCum.push(cs); });

    renderChartCard(chartsSection, 'cmpTimeGap', 'Cumulative Time Gap',
      'Seconds ahead (+) or behind (−) ' + mileEntries[baseIdx].perf.runner + ' ' + mileEntries[baseIdx].perf.year + '.', '', 300);

    new Chart(document.getElementById('cmpTimeGap'), {
      type: 'line',
      data: {
        labels: labels,
        datasets: mileEntries.map(function(e, i) {
          var cum = []; var s = 0;
          e.splits.miles.forEach(function(m, j) { s += m.moving_sec; cum.push(s - (baseCum[j] || baseCum[baseCum.length - 1])); });
          return {
            label: e.perf.runner + ' ' + e.perf.year + (i === baseIdx ? ' (fastest)' : ''),
            data: cum,
            borderColor: CHART_COLORS[entries.indexOf(e) % CHART_COLORS.length],
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

    // 3. Heatmap
    renderHeatmapTable(chartsSection, mileEntries, minMiles);
  } else if (mileEntries.length < 2 && entries.length >= 2) {
    chartsSection.innerHTML += '<div class="chart-card"><h3>Compare Mode</h3>' +
      '<div class="desc">Per-mile comparison requires at least 2 performances with mile-level split data. ' +
      'Checkpoint-only performances can be compared using Pacing Projection mode.</div></div>';
  }

  chartsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

function renderChartCard(container, canvasId, title, desc, extraHTML, height) {
  container.insertAdjacentHTML('beforeend',
    '<div class="chart-card">' +
    '<h3>' + title + '</h3>' +
    '<div class="desc">' + desc + '</div>' +
    (extraHTML || '') +
    '<div style="height:' + height + 'px"><canvas id="' + canvasId + '"></canvas></div>' +
    '</div>'
  );
}

function renderHeatmapTable(container, entries, maxMiles) {
  var html = '<div class="chart-card"><h3>Split Heatmap</h3>' +
    '<div class="desc">Color shows fastest (<span style="color:var(--green)">green</span>) and slowest (<span style="color:var(--red)">red</span>) per mile.</div>' +
    '<div class="table-wrapper"><table><thead><tr><th>Mile</th>';
  entries.forEach(function(e, i) {
    html += '<th style="color:' + CHART_COLORS[i % CHART_COLORS.length] + '">' + e.perf.runner + ' ' + e.perf.year + '</th>';
  });
  html += '<th>Spread</th></tr></thead><tbody>';

  for (var m = 0; m < maxMiles; m++) {
    var vals = entries.map(function(e) { return e.splits.miles[m] ? e.splits.miles[m].moving_sec : undefined; }).filter(function(v) { return v !== undefined; });
    if (vals.length === 0) continue;
    var best = Math.min.apply(null, vals), worst = Math.max.apply(null, vals);
    html += '<tr><td>' + (m + 1) + '</td>';
    entries.forEach(function(e) {
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

// === Init ===

document.addEventListener('DOMContentLoaded', function() {
  Chart.defaults.color = '#8b949e';
  Chart.defaults.borderColor = 'rgba(139,148,158,0.15)';
  Chart.defaults.font.family = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif';

  loadIndex();

  // Mode switching
  document.querySelectorAll('.mode-tab').forEach(function(tab) {
    tab.addEventListener('click', function() { switchMode(this.dataset.mode); });
  });

  // Projection mode
  document.getElementById('projCompareBtn').addEventListener('click', runProjection);

  // Compare mode
  document.getElementById('compareBtn').addEventListener('click', runComparison);
});
