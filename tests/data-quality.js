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
const THRESHOLD = 0.70;

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

test('every split file has actual split data (miles[] or checkpoints[])', () => {
  const errors = [];
  for (const p of idx.performances) {
    const filepath = path.join(SPLITS_DIR, p.splits_file);
    if (!fs.existsSync(filepath)) continue;
    const data = JSON.parse(fs.readFileSync(filepath, 'utf8'));
    const hasMiles = data.miles && data.miles.length > 0;
    const hasCheckpoints = data.checkpoints && data.checkpoints.length > 0;
    if (!hasMiles && !hasCheckpoints) {
      errors.push(`no splits: ${p.splits_file} (${p.runner})`);
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

test('all timed-event performances meet 70% WR threshold', () => {
  const errors = [];
  for (const p of idx.performances) {
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
