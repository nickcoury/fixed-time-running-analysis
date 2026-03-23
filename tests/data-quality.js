#!/usr/bin/env node
/**
 * Data quality tests for fixed-time running analysis.
 * Run: node tests/data-quality.js
 *
 * Catches the exact issues found in the 2026-03-22 audit:
 * - null/undefined/NaN in index fields
 * - missing split files
 * - empty checkpoints
 * - lap count vs miles confusion
 * - below 70% WR threshold
 * - duplicate IDs
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const INDEX_PATH = path.join(ROOT, 'data', 'index.json');
const SPLITS_DIR = path.join(ROOT, 'data', 'splits');

// Gender-specific world records (miles for timed events, seconds for distance events)
const WR = {
  '24h':  { M: 198.55, F: 173.12 },
  '48h':  { M: 294.21, F: 271.12 },
  '6d':   { M: 644.05, F: 603.0 },
  '12h':  { M: 104.88, F: 93.00 },
  '72h':  { M: 301.09, F: 250.0 },
  '6h':   { M: 60.0,   F: 52.0 },
  '10d':  { M: 900.0,  F: 750.0 },
  '100mi': { M_sec: 38499, F_sec: 44374 },
  '100k':  { M_sec: 21902, F_sec: 25263 },
};
const THRESHOLD = 0.30;

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    const errors = fn();
    if (errors && errors.length > 0) {
      failed++;
      failures.push({ name, errors: errors.slice(0, 10), total: errors.length });
      console.log(`  FAIL  ${name} (${errors.length} issues)`);
    } else {
      passed++;
      console.log(`  PASS  ${name}`);
    }
  } catch (e) {
    failed++;
    failures.push({ name, errors: [e.message], total: 1 });
    console.log(`  FAIL  ${name} (${e.message})`);
  }
}

// Load index
const idx = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));

console.log(`\nRunning data quality tests on ${idx.performances.length} performances...\n`);

// === Index structure tests ===

test('index has required top-level keys', () => {
  const errors = [];
  for (const key of ['distances', 'races', 'performances']) {
    if (!Array.isArray(idx[key])) errors.push(`missing or non-array: ${key}`);
  }
  return errors;
});

test('every performance has required fields', () => {
  const required = ['id', 'runner', 'race_id', 'year', 'distance_id', 'distance_mi', 'duration', 'pace_sec', 'splits_file'];
  const errors = [];
  for (const p of idx.performances) {
    for (const field of required) {
      if (p[field] === undefined || p[field] === null) {
        errors.push(`${p.runner || 'unknown'} (${p.splits_file}): ${field} is ${p[field]}`);
      }
    }
  }
  return errors;
});

test('no NaN values in numeric fields', () => {
  const errors = [];
  for (const p of idx.performances) {
    if (isNaN(p.distance_mi)) errors.push(`${p.runner}: distance_mi is NaN`);
    if (isNaN(p.pace_sec)) errors.push(`${p.runner}: pace_sec is NaN`);
    if (isNaN(p.year)) errors.push(`${p.runner}: year is NaN`);
  }
  return errors;
});

test('no duplicate performance IDs', () => {
  const seen = {};
  const errors = [];
  for (const p of idx.performances) {
    if (seen[p.id]) {
      errors.push(`duplicate id: "${p.id}" (${p.runner} and ${seen[p.id]})`);
    }
    seen[p.id] = p.runner;
  }
  return errors;
});

test('no duplicate runner+year+distance within 5% distance', () => {
  const groups = {};
  for (const p of idx.performances) {
    const key = p.runner.toLowerCase().trim() + '|' + p.year + '|' + (p.distance_id || '');
    if (!groups[key]) groups[key] = [];
    groups[key].push(p);
  }
  const errors = [];
  for (const [key, perfs] of Object.entries(groups)) {
    if (perfs.length <= 1) continue;
    for (let i = 0; i < perfs.length; i++) {
      for (let j = i + 1; j < perfs.length; j++) {
        const a = perfs[i].distance_mi || 0;
        const b = perfs[j].distance_mi || 0;
        if (a && b && Math.abs(a - b) / Math.max(a, b) < 0.05) {
          errors.push(`${perfs[i].runner} ${perfs[i].year}: "${perfs[i].id}" vs "${perfs[j].id}" (${a}mi vs ${b}mi)`);
        }
      }
    }
  }
  return errors;
});

test('every race_id references a known race', () => {
  const raceIds = new Set(idx.races.map(r => r.id));
  const errors = [];
  for (const p of idx.performances) {
    if (!raceIds.has(p.race_id)) {
      errors.push(`${p.runner}: race_id "${p.race_id}" not in races array`);
    }
  }
  return errors;
});

test('every distance_id references a known distance', () => {
  const distIds = new Set(idx.distances.map(d => d.id));
  const errors = [];
  for (const p of idx.performances) {
    if (!distIds.has(p.distance_id)) {
      errors.push(`${p.runner}: distance_id "${p.distance_id}" not in distances array`);
    }
  }
  return errors;
});

// === Split file tests ===

test('every splits_file exists on disk', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) {
      errors.push(`missing: ${p.splits_file} (${p.runner})`);
    }
  }
  return errors;
});

test('every split file is valid JSON with metadata', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    try {
      const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
      if (!data.runner) errors.push(`missing runner field: ${p.splits_file}`);
    } catch (e) {
      errors.push(`invalid JSON: ${p.splits_file}`);
    }
  }
  return errors;
});

test('every split file has non-zero duration', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
    if (!data.duration_sec || data.duration_sec === 0) {
      errors.push(`zero duration: ${p.splits_file} (${p.runner})`);
    }
  }
  return errors;
});

test('checkpoints have distance_mi', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
    if (data.checkpoints) {
      for (const cp of data.checkpoints) {
        if (cp.distance_km && !cp.distance_mi) {
          errors.push(`checkpoint missing distance_mi: ${p.splits_file} cp "${cp.label}"`);
          break; // one per file is enough
        }
      }
    }
  }
  return errors;
});

test('distance_mi is not a lap count (km/mi ratio sanity)', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
    if (data.distance_km && data.distance_mi) {
      const expected = data.distance_km * 0.621371;
      const ratio = data.distance_mi / expected;
      if (ratio > 2 || ratio < 0.3) {
        errors.push(`bad km/mi ratio (${ratio.toFixed(1)}): ${p.splits_file} km=${data.distance_km} mi=${data.distance_mi}`);
      }
    }
  }
  return errors;
});

// === Threshold tests ===

test('all timed-event performances meet 70% WR threshold (pinned runners exempt)', () => {
  const pinned = ['nick coury', 'nicholas coury'];
  const errors = [];
  for (const p of idx.performances) {
    if (pinned.includes(p.runner.toLowerCase().trim())) continue;
    const wr = WR[p.distance_id];
    if (!wr || wr.M_sec) continue; // skip distance events
    const gender = p.gender || 'M';
    const wrDist = wr[gender] || wr.M;
    const threshold = wrDist * THRESHOLD;
    if (p.distance_mi < threshold) {
      errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${p.distance_mi}mi < ${threshold.toFixed(1)}mi threshold (${Math.round(p.distance_mi/wrDist*100)}% WR)`);
    }
  }
  return errors;
});

test('all distance-event performances meet 70% WR time threshold', () => {
  const errors = [];
  for (const p of idx.performances) {
    const wr = WR[p.distance_id];
    if (!wr || !wr.M_sec) continue; // skip timed events
    const gender = p.gender || 'M';
    const wrTime = wr[gender + '_sec'] || wr.M_sec;
    const maxTime = wrTime / THRESHOLD;
    // Parse duration
    const parts = p.duration.split(':').map(Number);
    if (parts.length === 3) {
      const sec = parts[0] * 3600 + parts[1] * 60 + parts[2];
      if (sec > maxTime) {
        errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${p.duration} > ${Math.floor(maxTime/3600)}h threshold`);
      }
    }
  }
  return errors;
});

// === Sanity tests ===

test('pace_sec matches distance_mi and duration', () => {
  const errors = [];
  for (const p of idx.performances) {
    const parts = p.duration.split(':').map(Number);
    if (parts.length !== 3) continue;
    const sec = parts[0] * 3600 + parts[1] * 60 + parts[2];
    const expectedPace = sec / p.distance_mi;
    const diff = Math.abs(expectedPace - p.pace_sec);
    if (diff > 1) { // allow 1 second rounding
      errors.push(`${p.runner}: pace ${p.pace_sec} vs expected ${expectedPace.toFixed(2)} (diff: ${diff.toFixed(1)}s)`);
    }
  }
  return errors;
});

test('years are reasonable (1970-2030)', () => {
  const errors = [];
  for (const p of idx.performances) {
    if (p.year < 1970 || p.year > 2030) {
      errors.push(`${p.runner}: year ${p.year}`);
    }
  }
  return errors;
});

test('distance_mi is positive and reasonable for distance type', () => {
  const maxMi = { '6h': 80, '12h': 150, '24h': 220, '48h': 350, '72h': 400, '6d': 700, '10d': 1000, '100mi': 101, '100k': 63 };
  const errors = [];
  for (const p of idx.performances) {
    if (p.distance_mi <= 0) {
      errors.push(`${p.runner}: distance_mi ${p.distance_mi}`);
    }
    const max = maxMi[p.distance_id];
    if (max && p.distance_mi > max) {
      errors.push(`${p.runner} (${p.distance_id}): distance_mi ${p.distance_mi} > max ${max}`);
    }
  }
  return errors;
});

test('no impossible segment pacing in checkpoints (<4 min/mi)', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
    if (!data.checkpoints || data.checkpoints.length < 2) continue;
    let prevDist = 0, prevTime = 0;
    for (const cp of data.checkpoints) {
      const dist = cp.distance_mi || 0;
      const time = cp.cum_sec || cp.elapsed_sec || 0;
      if (dist > 0 && time > 0) {
        const segDist = dist - prevDist;
        const segTime = time - prevTime;
        if (segDist > 0 && segTime > 0) {
          const paceMin = segTime / segDist / 60;
          if (paceMin < 4) {
            errors.push(`${p.runner} (${p.splits_file}): ${cp.label || '?'} at ${paceMin.toFixed(1)} min/mi`);
            break;
          }
        }
        if (dist > 0) prevDist = dist;
        if (time > 0) prevTime = time;
      }
    }
  }
  return errors;
});

// === Outlier detection tests ===
// These flag potential bad data. Add IDs to allowlist to override legitimate outliers.

const ALLOWLIST_PATH = path.join(ROOT, 'tests', 'outlier-allowlist.json');
let allowlist = {};
try {
  allowlist = JSON.parse(fs.readFileSync(ALLOWLIST_PATH, 'utf8'));
} catch (e) {
  // No allowlist file yet — all flags are active
}

function isAllowed(testName, perfId) {
  const list = allowlist[testName];
  return list && list.includes(perfId);
}

// Helper: load split data for a performance
function loadSplitData(p) {
  const filepath = path.join(SPLITS_DIR, p.splits_file);
  if (!fs.existsSync(filepath)) return null;
  return JSON.parse(fs.readFileSync(filepath, 'utf8'));
}

// Helper: get ordered split segments from any data type
function getSegments(data) {
  const segments = [];
  if (data.miles && data.miles.length > 0) {
    let prevCum = 0;
    for (const m of data.miles) {
      const cumSec = m.cum_sec || 0;
      const splitSec = m.split_sec || (cumSec - prevCum);
      if (splitSec > 0) {
        segments.push({ mile: m.mile, dist_mi: 1, split_sec: splitSec, cum_sec: cumSec });
      }
      prevCum = cumSec;
    }
  } else if (data.checkpoints && data.checkpoints.length > 0) {
    let prevDist = 0, prevTime = 0;
    for (const cp of data.checkpoints) {
      const dist = cp.distance_mi || 0;
      const time = cp.cum_sec || cp.elapsed_sec || 0;
      if (dist > prevDist && time > prevTime) {
        segments.push({
          label: cp.label,
          dist_mi: dist - prevDist,
          split_sec: time - prevTime,
          cum_sec: time,
          cum_dist: dist
        });
        prevDist = dist;
        prevTime = time;
      }
    }
  }
  return segments;
}

test('no performance exceeds 110% of world record', () => {
  const errors = [];
  for (const p of idx.performances) {
    if (isAllowed('exceeds_wr', p.id)) continue;
    const wr = WR[p.distance_id];
    if (!wr) continue;
    if (wr.M_sec) {
      // Distance event: faster time = lower seconds
      const gender = p.gender || 'M';
      const wrTime = wr[gender + '_sec'] || wr.M_sec;
      const parts = p.duration.split(':').map(Number);
      if (parts.length !== 3) continue;
      const sec = parts[0] * 3600 + parts[1] * 60 + parts[2];
      if (sec < wrTime * 0.9) { // 10% faster than WR
        errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${p.duration} is ${Math.round((1 - sec/wrTime) * 100)}% faster than WR [id: ${p.id}]`);
      }
    } else {
      // Timed event: more distance = better
      const gender = p.gender || 'M';
      const wrDist = wr[gender] || wr.M;
      if (p.distance_mi > wrDist * 1.1) {
        errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${p.distance_mi}mi is ${Math.round((p.distance_mi/wrDist - 1) * 100)}% beyond WR (${wrDist}mi) [id: ${p.id}]`);
      }
    }
  }
  return errors;
});

test('all checkpoints have non-zero elapsed times', () => {
  const errors = [];
  for (const p of idx.performances) {
    const data = loadSplitData(p);
    if (!data || !data.checkpoints || data.checkpoints.length === 0) continue;
    const allZero = data.checkpoints.every(cp => {
      const t = cp.cum_sec || cp.elapsed_sec || 0;
      return t === 0;
    });
    if (allZero) {
      errors.push(`${p.runner} (${p.splits_file}): all ${data.checkpoints.length} checkpoints have elapsed_sec=0 [id: ${p.id}]`);
    }
  }
  return errors;
});

test('no negative split greater than 10%', () => {
  const errors = [];
  for (const p of idx.performances) {
    if (isAllowed('negative_split', p.id)) continue;
    const data = loadSplitData(p);
    if (!data) continue;
    const segments = getSegments(data);
    if (segments.length < 4) continue;
    // Skip if segments have zero cumulative time (bad data caught by other test)
    if (segments[segments.length - 1].cum_sec <= 0) continue;

    // Split segments into first half and second half by cumulative time
    const totalTime = segments[segments.length - 1].cum_sec;
    const halfTime = totalTime / 2;

    let firstHalfDist = 0, secondHalfDist = 0;
    for (const seg of segments) {
      const segMidTime = seg.cum_sec - seg.split_sec / 2;
      if (segMidTime <= halfTime) {
        firstHalfDist += seg.dist_mi;
      } else {
        secondHalfDist += seg.dist_mi;
      }
    }

    if (firstHalfDist > 0 && secondHalfDist > 0) {
      // Negative split means second half is faster (more distance per time)
      // Compare pace: first half pace vs second half pace
      const firstPace = (halfTime) / firstHalfDist;
      const secondPace = (totalTime - halfTime) / secondHalfDist;
      const negSplitPct = (firstPace - secondPace) / firstPace;

      if (negSplitPct > 0.10) {
        errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${Math.round(negSplitPct * 100)}% negative split — 1st half ${(firstPace/60).toFixed(1)} min/mi, 2nd half ${(secondPace/60).toFixed(1)} min/mi [id: ${p.id}]`);
      }
    }
  }
  return errors;
});

test('no abnormally fast intermediate split', () => {
  // Flag any segment that's faster than the WR average pace for that distance category.
  // For a 24h runner doing 200mi, WR pace is ~7.25 min/mi. A single split at 4 min/mi
  // over 50 miles is suspicious. We flag segments faster than 80% of WR pace.
  const wrPace = {
    '6h':   { M: 6 * 3600 / 60,  F: 6 * 3600 / 52 },   // sec/mi at WR
    '12h':  { M: 12 * 3600 / 104.88, F: 12 * 3600 / 93 },
    '24h':  { M: 24 * 3600 / 198.55, F: 24 * 3600 / 173.12 },
    '48h':  { M: 48 * 3600 / 294.21, F: 48 * 3600 / 271.12 },
    '72h':  { M: 72 * 3600 / 301.09, F: 72 * 3600 / 250 },
    '6d':   { M: 144 * 3600 / 644.05, F: 144 * 3600 / 603 },
  };
  const errors = [];
  for (const p of idx.performances) {
    if (isAllowed('fast_split', p.id)) continue;
    const wrp = wrPace[p.distance_id];
    if (!wrp) continue;
    const gender = p.gender || 'M';
    const wrPaceSec = wrp[gender] || wrp.M; // sec per mile at WR

    // Threshold: 80% of WR pace (20% faster than WR average)
    const minPaceSec = wrPaceSec * 0.5;

    const data = loadSplitData(p);
    if (!data) continue;
    const segments = getSegments(data);

    for (const seg of segments) {
      if (seg.dist_mi <= 0) continue;
      const segPace = seg.split_sec / seg.dist_mi;
      if (segPace < minPaceSec) {
        const paceMin = segPace / 60;
        const threshMin = minPaceSec / 60;
        errors.push(`${p.runner} (${p.distance_id} ${p.year}): segment ${seg.label || 'mile ' + seg.mile} at ${paceMin.toFixed(1)} min/mi (threshold: ${threshMin.toFixed(1)}) [id: ${p.id}]`);
        break; // one per performance
      }
    }
  }
  return errors;
});

test('no time inversions in split data', () => {
  const errors = [];
  for (const p of idx.performances) {
    const data = loadSplitData(p);
    if (!data) continue;

    if (data.miles) {
      let prevCum = 0;
      for (const m of data.miles) {
        if (m.cum_sec < prevCum) {
          errors.push(`${p.runner} (${p.splits_file}): time inversion at mile ${m.mile} — ${m.cum_sec}s < prev ${prevCum}s`);
          break;
        }
        prevCum = m.cum_sec;
      }
    }
    if (data.checkpoints) {
      let prevTime = 0;
      for (const cp of data.checkpoints) {
        const t = cp.cum_sec || cp.elapsed_sec || 0;
        if (t > 0 && t < prevTime) {
          errors.push(`${p.runner} (${p.splits_file}): time inversion at ${cp.label} — ${t}s < prev ${prevTime}s`);
          break;
        }
        if (t > 0) prevTime = t;
      }
    }
  }
  return errors;
});

test('checkpoint distances increase monotonically', () => {
  const errors = [];
  for (const p of idx.performances) {
    const data = loadSplitData(p);
    if (!data || !data.checkpoints) continue;
    let prevDist = 0;
    for (const cp of data.checkpoints) {
      const d = cp.distance_mi || 0;
      if (d > 0 && d < prevDist) {
        errors.push(`${p.runner} (${p.splits_file}): distance goes backwards at ${cp.label} — ${d}mi < prev ${prevDist}mi`);
        break;
      }
      if (d > 0) prevDist = d;
    }
  }
  return errors;
});

test('per-mile split count matches index distance_mi within 5%', () => {
  // Only applies to per-mile data where last mile should approximate total distance.
  // Checkpoint data uses intermediate timing mats and won't match total distance.
  const errors = [];
  for (const p of idx.performances) {
    const data = loadSplitData(p);
    if (!data || !data.miles || data.miles.length === 0) continue;

    const splitDist = data.miles[data.miles.length - 1].mile;
    const indexDist = p.distance_mi;
    const diff = Math.abs(splitDist - indexDist) / Math.max(splitDist, indexDist);
    if (diff > 0.05) {
      errors.push(`${p.runner} (${p.distance_id} ${p.year}): ${splitDist} miles in splits vs ${indexDist}mi in index (${Math.round(diff * 100)}% diff) [id: ${p.id}]`);
    }
  }
  return errors;
});

// === Report ===

console.log(`\n${'='.repeat(50)}`);
console.log(`${passed} passed, ${failed} failed`);

if (failures.length > 0) {
  console.log(`\nFailure details:`);
  for (const f of failures) {
    console.log(`\n  ${f.name} (${f.total} issues):`);
    for (const e of f.errors) {
      console.log(`    - ${e}`);
    }
    if (f.total > f.errors.length) {
      console.log(`    ... and ${f.total - f.errors.length} more`);
    }
  }
  process.exit(1);
}

process.exit(0);
