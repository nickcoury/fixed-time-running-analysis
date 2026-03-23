#!/usr/bin/env python3
"""
Convert Aravaipa overall results to split-compatible files.

Creates checkpoint-style split files with a single finish point,
allowing these performances to appear in the index and browse table
even without per-lap data. The chart will show a single point at
(finish_distance, race_duration).
"""

import json
import os
import re
import sys

RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'aravaipa-results')
SPLITS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'splits')

DISTANCE_DURATIONS = {
    '6h': 21600, '12h': 43200, '24h': 86400,
    '48h': 172800, '72h': 259200, '6d': 518400,
}

DRY_RUN = '--dry-run' in sys.argv
stats = {'converted': 0, 'skipped_existing': 0, 'skipped_short': 0, 'skipped_no_dist': 0}


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def convert_result(filepath):
    with open(filepath) as f:
        data = json.load(f)

    distance_cat = data.get('distance_cat')
    if distance_cat not in DISTANCE_DURATIONS:
        stats['skipped_no_dist'] += 1
        return

    distance_mi = data.get('distance_mi', 0)
    duration_sec = DISTANCE_DURATIONS[distance_cat]

    # Skip very short performances
    if distance_mi < 10:
        stats['skipped_short'] += 1
        return

    # Build output filename
    race_slug = slugify(data.get('race', 'unknown'))
    runner_slug = slugify(data.get('runner', 'unknown'))
    year = data.get('year', 0)
    filename = f'{race_slug}-{year}-{runner_slug}-aravaipa.json'
    outpath = os.path.join(SPLITS_DIR, filename)

    if os.path.exists(outpath):
        stats['skipped_existing'] += 1
        return

    # Duration string
    h = int(duration_sec // 3600)
    m = int((duration_sec % 3600) // 60)
    s = int(duration_sec % 60)
    duration_str = f'{h}:{m:02d}:{s:02d}'

    # Create split file with single checkpoint at finish
    split_data = {
        'runner': data['runner'],
        'race': data['race'],
        'year': year,
        'distance_mi': distance_mi,
        'distance_id': distance_cat,
        'duration_sec': duration_sec,
        'duration': duration_str,
        'data_type': 'checkpoints',
        'source': data.get('source', 'live.aravaiparunning.com'),
        'gender': data.get('gender', ''),
        'checkpoints': [
            {
                'name': 'Finish',
                'distance_mi': distance_mi,
                'time_sec': duration_sec,
            }
        ],
    }

    if not DRY_RUN:
        with open(outpath, 'w') as f:
            json.dump(split_data, f, indent=2)
            f.write('\n')

    stats['converted'] += 1


def main():
    if not os.path.isdir(RESULTS_DIR):
        print(f'No results directory: {RESULTS_DIR}')
        return

    files = sorted(f for f in os.listdir(RESULTS_DIR) if f.endswith('.json'))
    print(f'Processing {len(files)} Aravaipa result files...')

    for f in files:
        convert_result(os.path.join(RESULTS_DIR, f))

    print(f'Converted: {stats["converted"]}, Skipped existing: {stats["skipped_existing"]}, '
          f'Skipped short: {stats["skipped_short"]}, Skipped no distance: {stats["skipped_no_dist"]}')


if __name__ == '__main__':
    main()
