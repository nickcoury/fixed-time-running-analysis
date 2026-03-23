#!/usr/bin/env node
/**
 * Full audit + rebuild of index.json from all split files on disk.
 *
 * 1. Scans all split files in data/splits/
 * 2. Validates each has actual split data (miles[] or checkpoints[])
 * 3. Applies 70% WR threshold (gender-specific)
 * 4. Generates proper id, duration, pace_sec for each entry
 * 5. Builds clean index.json
 * 6. Reports what was removed and why
 */

const fs = require('fs');
const path = require('path');

const SPLITS_DIR = path.join(__dirname, '..', 'data', 'splits');
const INDEX_PATH = path.join(__dirname, '..', 'data', 'index.json');

// World Records for threshold calculation
// Timed events: distance in miles. Distance events: time in seconds.
const WR = {
  '24h':  { M: 198.55, F: 173.12 },
  '48h':  { M: 294.21, F: 271.12 },
  '6d':   { M: 644.05, F: 603.0 },
  '12h':  { M: 104.88, F: 93.00 },
  '72h':  { M: 301.09, F: 250.0 },
  '6h':   { M: 60.0,   F: 52.0 },
  '10d':  { M: 900.0,  F: 750.0 },
  '100mi': { M_sec: 38499, F_sec: 44374 }, // Sorokin 10:41:39, Paulson 12:19:34
  '100k':  { M_sec: 21902, F_sec: 25263 }, // Sorokin 6:05:02, Herron 7:01:03ish
};

const THRESHOLD = 0.70;

function slugify(str) {
  return str.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[łŁ]/g, 'l').replace(/[đĐ]/g, 'd').replace(/[øØ]/g, 'o')
    .replace(/\s*\(.*?\)\s*/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function secToHMS(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.round(sec % 60);
  return h + ':' + (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
}

function inferDistanceId(data, filename) {
  if (data.distance_id) return data.distance_id;
  const dur = data.duration_sec;
  if (dur === 86400) return '24h';
  if (dur === 172800) return '48h';
  if (dur === 259200) return '72h';
  if (dur === 518400) return '6d';
  if (dur === 43200) return '12h';
  if (dur === 21600) return '6h';
  if (dur === 864000) return '10d';
  // Check filename
  if (filename.includes('-100mi-') || filename.includes('-100mi.')) return '100mi';
  if (filename.includes('-100k-') || filename.includes('-100k.')) return '100k';
  if (data.distance_mi === 100) return '100mi';
  return null;
}

function passesThreshold(distId, gender, data) {
  const g = gender || 'M';

  if (distId === '100mi') {
    const maxTime = (WR['100mi'][g + '_sec'] || WR['100mi'].M_sec) / THRESHOLD;
    return data.duration_sec <= maxTime;
  }

  if (distId === '100k') {
    const maxTime = (WR['100k'][g + '_sec'] || WR['100k'].M_sec) / THRESHOLD;
    return data.duration_sec <= maxTime;
  }

  if (WR[distId]) {
    const wrDist = WR[distId][g] || WR[distId].M;
    const threshold = wrDist * THRESHOLD;
    return data.distance_mi >= threshold;
  }

  return true; // Unknown distance, keep
}

// Fix files where distance_mi stores lap count instead of miles
function fixDistanceMi(data) {
  if (data.distance_km && data.distance_mi) {
    const expected = data.distance_km * 0.621371;
    const ratio = data.distance_mi / expected;
    if (ratio > 2) {
      // distance_mi is actually lap count — fix it
      data.distance_mi = Math.round(expected * 100) / 100;
    }
  }
  // Also fix checkpoints missing distance_mi
  if (data.checkpoints) {
    for (const cp of data.checkpoints) {
      if (cp.distance_km && !cp.distance_mi) {
        cp.distance_mi = Math.round(cp.distance_km * 0.621371 * 100) / 100;
      }
    }
  }
}

function inferRaceId(data, filename) {
  // Try to build race_id from race name
  if (data.race) return slugify(data.race);
  // From filename: strip year and runner parts
  const parts = filename.replace('.json', '').split('-');
  // Heuristic: race name is before the year
  const yearIdx = parts.findIndex(p => /^\d{4}$/.test(p));
  if (yearIdx > 0) return parts.slice(0, yearIdx).join('-');
  return slugify(filename.replace('.json', ''));
}

// Load existing index for race definitions and notes
const existingIdx = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));
const existingPerfMap = {};
for (const p of existingIdx.performances) {
  existingPerfMap[p.splits_file] = p;
}

// Scan all files
const files = fs.readdirSync(SPLITS_DIR).filter(f => f.endsWith('.json'));
console.log('Total split files on disk:', files.length);

const stats = {
  noSplits: 0,
  zeroDuration: 0,
  noDistanceId: 0,
  belowThreshold: 0,
  badData: 0,
  kept: 0,
};

const performances = [];
const raceMap = {}; // race_id -> race info
const distanceIds = new Set();
const usedIds = new Set();

for (const filename of files) {
  const filepath = path.join(SPLITS_DIR, filename);
  let data;
  try {
    data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
  } catch (e) {
    stats.badData++;
    continue;
  }

  // Fix lap count bug in distance_mi and missing checkpoint distance_mi
  const origMi = data.distance_mi;
  const origCps = data.checkpoints ? data.checkpoints.map(c => c.distance_mi) : [];
  fixDistanceMi(data);
  // Write back if fixed
  if (data.distance_mi !== origMi || (data.checkpoints && data.checkpoints.some((c, i) => c.distance_mi !== origCps[i]))) {
    fs.writeFileSync(filepath, JSON.stringify(data, null, 2));
    stats.filesFixed = (stats.filesFixed || 0) + 1;
  }

  // Must have actual splits
  const hasMiles = data.miles && data.miles.length > 0;
  const hasCheckpoints = data.checkpoints && data.checkpoints.length > 0;
  if (!hasMiles && !hasCheckpoints) {
    stats.noSplits++;
    continue;
  }

  // Must have duration
  const durSec = data.duration_sec || 0;
  if (durSec === 0) {
    stats.zeroDuration++;
    continue;
  }

  // Must have distance
  if (!data.distance_mi || data.distance_mi <= 0) {
    stats.badData++;
    continue;
  }

  // Determine distance_id
  const distId = inferDistanceId(data, filename);
  if (!distId) {
    stats.noDistanceId++;
    continue;
  }

  // Apply threshold
  const gender = data.gender || 'M';
  if (!passesThreshold(distId, gender, data)) {
    stats.belowThreshold++;
    continue;
  }

  // Build performance entry
  const existing = existingPerfMap[filename];
  const raceId = (existing && existing.race_id) || inferRaceId(data, filename);

  let id = slugify(raceId + '-' + data.year + '-' + (data.runner || ''));
  // Deduplicate
  if (usedIds.has(id)) {
    id = id + '-' + distId;
  }
  if (usedIds.has(id)) {
    id = id + '-' + Math.random().toString(36).slice(2, 6);
  }
  usedIds.add(id);

  const perf = {
    id: id,
    runner: data.runner || 'Unknown',
    race_id: raceId,
    year: data.year,
    distance_id: distId,
    distance_mi: data.distance_mi,
    duration: secToHMS(durSec),
    pace_sec: Math.round(durSec / data.distance_mi * 100) / 100,
    splits_file: filename,
    gender: gender,
  };

  // Carry over notes from existing
  if (existing && existing.note) perf.note = existing.note;
  if (data.nationality) perf.nationality = data.nationality;

  performances.push(perf);
  distanceIds.add(distId);

  // Build race entry
  if (!raceMap[raceId]) {
    raceMap[raceId] = {
      id: raceId,
      name: data.race || raceId,
      location: data.location || '',
      distances: [distId],
    };
    if (data.track_m) raceMap[raceId].track_m = data.track_m;
  } else {
    if (!raceMap[raceId].distances.includes(distId)) {
      raceMap[raceId].distances.push(distId);
    }
  }

  stats.kept++;
}

// Sort performances: by distance_id, then distance_mi desc, then year desc
const distOrder = ['6d', '10d', '72h', '48h', '24h', '12h', '6h', '100mi', '100k'];
performances.sort((a, b) => {
  const da = distOrder.indexOf(a.distance_id);
  const db = distOrder.indexOf(b.distance_id);
  if (da !== db) return da - db;
  return b.distance_mi - a.distance_mi || b.year - a.year;
});

// Build distances array
const distDefs = {
  '24h': { id: '24h', name: '24 Hour', unit: 'hours' },
  '48h': { id: '48h', name: '48 Hour', unit: 'hours' },
  '6d':  { id: '6d', name: '6 Day', unit: 'days' },
  '12h': { id: '12h', name: '12 Hour', unit: 'hours' },
  '72h': { id: '72h', name: '72 Hour', unit: 'hours' },
  '6h':  { id: '6h', name: '6 Hour', unit: 'hours' },
  '10d': { id: '10d', name: '10 Day', unit: 'days' },
  '100mi': { id: '100mi', name: '100 Miles', unit: 'miles' },
  '100k':  { id: '100k', name: '100 Kilometers', unit: 'kilometers' },
};
const distances = [...distanceIds].map(id => distDefs[id] || { id, name: id, unit: 'unknown' });

// Deduplicate: same runner + year + distance_id with distance_mi within 5%
const groups = {};
for (const p of performances) {
  const key = p.runner.toLowerCase().trim() + '|' + p.year + '|' + (p.distance_id || '');
  if (!groups[key]) groups[key] = [];
  groups[key].push(p);
}
const toRemove = new Set();
for (const perfs of Object.values(groups)) {
  if (perfs.length <= 1) continue;
  const used = new Set();
  for (let i = 0; i < perfs.length; i++) {
    if (used.has(i)) continue;
    const cluster = [perfs[i]];
    used.add(i);
    for (let j = i + 1; j < perfs.length; j++) {
      if (used.has(j)) continue;
      const a = perfs[i].distance_mi || 0;
      const b = perfs[j].distance_mi || 0;
      if (a && b && Math.abs(a - b) / Math.max(a, b) < 0.05) {
        cluster.push(perfs[j]);
        used.add(j);
      }
    }
    if (cluster.length > 1) {
      cluster.sort((a, b) => (b.distance_mi || 0) - (a.distance_mi || 0) || b.id.length - a.id.length);
      for (let k = 1; k < cluster.length; k++) toRemove.add(cluster[k].id);
    }
  }
}
const dedupedPerformances = performances.filter(p => !toRemove.has(p.id));
stats.duplicates = toRemove.size;

// Rebuild races from deduped performances
const usedRaceIds = new Set(dedupedPerformances.map(p => p.race_id).filter(Boolean));
const dedupedRaces = Object.values(raceMap).filter(r => usedRaceIds.has(r.id));

// Build new index
const newIndex = {
  distances: distances,
  races: dedupedRaces,
  performances: dedupedPerformances,
};

// Write
fs.writeFileSync(INDEX_PATH, JSON.stringify(newIndex, null, 2));

console.log('\n=== AUDIT RESULTS ===');
console.log('Scanned:', files.length, 'files');
console.log('Removed - no splits:', stats.noSplits);
console.log('Removed - zero duration:', stats.zeroDuration);
console.log('Removed - no distance_id:', stats.noDistanceId);
console.log('Removed - below 70% WR:', stats.belowThreshold);
console.log('Removed - bad data:', stats.badData);
console.log('Removed - duplicates:', stats.duplicates);
console.log('Split files fixed on disk:', stats.filesFixed || 0);
console.log('KEPT:', dedupedPerformances.length);
console.log();
console.log('By distance:');
const byDist = {};
for (const p of dedupedPerformances) {
  byDist[p.distance_id] = (byDist[p.distance_id] || 0) + 1;
}
for (const [d, c] of Object.entries(byDist).sort((a, b) => b[1] - a[1])) {
  console.log('  ' + d + ': ' + c);
}
console.log();
console.log('Races:', dedupedRaces.length);
console.log('Index written to', INDEX_PATH);
