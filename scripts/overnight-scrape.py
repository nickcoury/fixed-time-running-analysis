#!/usr/bin/env python3
"""
Overnight scraper for fixed-time running analysis data.

Scrapes raceresult.com events for:
1. Per-lap timing data (converts to per-mile splits)
2. Checkpoint/split data (saves as checkpoints)
3. Scans event ID ranges for undiscovered events with lap data

Usage: python3 overnight-scrape.py [--dry-run] [--phase PHASE]
  Phases: checkpoints, scan, integrate, all (default: all)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
SPLITS_DIR = os.path.join(DATA_DIR, 'splits')
INDEX_PATH = os.path.join(DATA_DIR, 'index.json')

DRY_RUN = '--dry-run' in sys.argv
PHASE = 'all'
for i, arg in enumerate(sys.argv):
    if arg == '--phase' and i + 1 < len(sys.argv):
        PHASE = sys.argv[i + 1]

stats = {
    'events_checked': 0, 'events_with_data': 0,
    'runners_scraped': 0, 'files_written': 0,
    'files_skipped': 0, 'errors': 0,
    'new_lap_events': [],
}


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            time.sleep(0.4)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2 ** attempt)
    return None


def parse_time_to_seconds(time_str):
    if not time_str or time_str in ('-', '', '*'):
        return 0
    time_str = time_str.strip().replace(',', '.')

    # "D.HH:MM:SS" format
    if '.' in time_str and ':' in time_str:
        dot_parts = time_str.split('.')
        if len(dot_parts) >= 2 and ':' in dot_parts[-1]:
            # Could be "1.23:45:06" or "23:45:06.7"
            if len(dot_parts[0].split(':')) == 1 and int(dot_parts[0]) < 30:
                days = int(dot_parts[0])
                hms = dot_parts[1].split(':')
                if len(hms) == 3:
                    return days * 86400 + int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])

    # "HH:MM:SS" or "H:MM:SS"
    parts = time_str.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])

    try:
        return float(time_str)
    except ValueError:
        return 0


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


# ============================================================
# Phase 1: Scrape checkpoint data from known events
# ============================================================

# Events with checkpoint split data (not per-lap)
CHECKPOINT_EVENTS = [
    # Dome 2019 — 50mi interval checkpoints
    {
        'event_id': 134293,
        'race_name': '6 Days in the Dome',
        'year': 2019,
        'listname': 'Result Lists|Split Times MI',
        'contest': '1',
        'distance_id': '6d',
        'duration_sec': 518400,
        'fields_map': {
            # field_name: (distance_mi, label)
            '50MI': (50, '50mi'),
            '100MI': (100, '100mi'),
            '150MI': (150, '150mi'),
            '200MI': (200, '200mi'),
            '250MI': (250, '250mi'),
            '300MI': (300, '300mi'),
            '350MI': (350, '350mi'),
            '400MI': (400, '400mi'),
            '450MI': (450, '450mi'),
            '500MI': (500, '500mi'),
            '550MI': (550, '550mi'),
        },
    },
    # Snowdrop 55-Hour Ultra
    {
        'event_id': 376902,
        'race_name': 'Snowdrop 55-Hour Ultra',
        'year': 2025,
        'listname': 'Result Lists|Split Times Individual',
        'contest': '1',
        'distance_id': '48h',  # closest standard distance
        'duration_sec': 198000,  # 55 hours
        'fields_map': {
            'MarSplit': (26.2, 'Marathon'),
            '50KSplit': (31.07, '50K'),
            '50Mile': (50, '50mi'),
            '100KSplit': (62.14, '100K'),
            '100MileSplit': (100, '100mi'),
            '200KSplit': (124.27, '200K'),
            '150MSplit': (150, '150mi'),
            '200MSplit': (200, '200mi'),
        },
    },
    {
        'event_id': 321270,
        'race_name': 'Snowdrop 55-Hour Ultra',
        'year': 2024,
        'listname': 'Result Lists|Split Times Individual',
        'contest': '1',
        'distance_id': '48h',
        'duration_sec': 198000,
        'fields_map': {
            'MarSplit': (26.2, 'Marathon'),
            '50KSplit': (31.07, '50K'),
            '50Mile': (50, '50mi'),
            '100KSplit': (62.14, '100K'),
            '100MileSplit': (100, '100mi'),
            '200KSplit': (124.27, '200K'),
            '150MSplit': (150, '150mi'),
            '200MSplit': (200, '200mi'),
        },
    },
    {
        'event_id': 272977,
        'race_name': 'Snowdrop 55-Hour Ultra',
        'year': 2023,
        'listname': 'Result Lists|Split Times Individual',
        'contest': '1',
        'distance_id': '48h',
        'duration_sec': 198000,
        'fields_map': {
            'MarSplit': (26.2, 'Marathon'),
            '50KSplit': (31.07, '50K'),
            '50Mile': (50, '50mi'),
            '100KSplit': (62.14, '100K'),
            '100MileSplit': (100, '100mi'),
            '200KSplit': (124.27, '200K'),
            '150MSplit': (150, '150mi'),
            '200MSplit': (200, '200mi'),
        },
    },
    {
        'event_id': 229458,
        'race_name': 'Snowdrop 55-Hour Ultra',
        'year': 2022,
        'listname': 'Result Lists|Split Times Individual',
        'contest': '1',
        'distance_id': '48h',
        'duration_sec': 198000,
        'fields_map': {
            'MarSplit': (26.2, 'Marathon'),
            '50KSplit': (31.07, '50K'),
            '50Mile': (50, '50mi'),
            '100KSplit': (62.14, '100K'),
            '100MileSplit': (100, '100mi'),
            '200KSplit': (124.27, '200K'),
            '150MSplit': (150, '150mi'),
            '200MSplit': (200, '200mi'),
        },
    },
]


def scrape_checkpoint_events():
    log('=== Phase 1: Scraping checkpoint data ===')

    for evt in CHECKPOINT_EVENTS:
        eid = evt['event_id']
        log(f'Processing {evt["race_name"]} {evt["year"]} (event {eid})')

        config = fetch_json(f'https://my.raceresult.com/{eid}/results/config?lang=en')
        if not config:
            log(f'  Failed to get config')
            stats['errors'] += 1
            continue

        key = config['key']
        server = config.get('server', 'my.raceresult.com')

        params = urllib.parse.urlencode({
            'key': key, 'listname': evt['listname'],
            'contest': evt['contest'], 'r': 'all', 'l': '0'
        })
        url = f'https://{server}/{eid}/results/list?{params}'
        data = fetch_json(url)

        if not data:
            log(f'  Failed to get list data')
            stats['errors'] += 1
            continue

        fields = data.get('DataFields', [])
        entries = data.get('data', [])
        if isinstance(entries, dict):
            entries = list(entries.values())
            if entries and isinstance(entries[0], list) and entries[0] and isinstance(entries[0][0], list):
                # Nested dict → flatten
                flat = []
                for v in entries:
                    flat.extend(v)
                entries = flat

        log(f'  Got {len(entries)} runners, fields: {fields[:8]}...')

        # Map field indices
        field_idx = {f: i for i, f in enumerate(fields)}

        name_idx = field_idx.get('DisplayName', field_idx.get('NAME', 2))
        gender_idx = field_idx.get('GenderMF', field_idx.get('GENDER', None))
        age_idx = field_idx.get('AGE', None)

        runners_written = 0
        for entry in entries:
            if not isinstance(entry, list) or len(entry) < 5:
                continue

            runner_name = entry[name_idx] if name_idx < len(entry) else 'Unknown'
            if not runner_name or runner_name == 'Unknown':
                continue

            gender = entry[gender_idx] if gender_idx is not None and gender_idx < len(entry) else None

            # Build checkpoints
            checkpoints = []
            max_dist_mi = 0
            last_time_sec = 0

            for field_name, (dist_mi, label) in evt['fields_map'].items():
                idx = field_idx.get(field_name)
                if idx is None or idx >= len(entry):
                    continue
                time_str = entry[idx]
                time_sec = parse_time_to_seconds(time_str)
                if time_sec <= 0:
                    continue

                # Sanity: checkpoint time should be increasing
                if time_sec <= last_time_sec:
                    continue

                checkpoints.append({
                    'label': label,
                    'elapsed_sec': round(time_sec),
                    'distance_mi': dist_mi,
                })
                if dist_mi > max_dist_mi:
                    max_dist_mi = dist_mi
                    last_time_sec = time_sec

            if len(checkpoints) < 2:
                continue

            # Use last checkpoint as total distance/time
            total_distance_mi = checkpoints[-1]['distance_mi']
            total_time_sec = checkpoints[-1]['elapsed_sec']

            # Sanity: skip very short efforts
            if total_distance_mi < 30:
                continue

            race_slug = slugify(evt['race_name'])
            runner_slug = slugify(runner_name)
            filename = f'{race_slug}-{evt["year"]}-{runner_slug}-raceresult.json'
            filepath = os.path.join(SPLITS_DIR, filename)

            # Skip if file already exists
            if os.path.exists(filepath):
                stats['files_skipped'] += 1
                continue

            duration_str = f'{int(total_time_sec // 3600)}:{int((total_time_sec % 3600) // 60):02d}:{int(total_time_sec % 60):02d}'

            split_data = {
                'runner': runner_name,
                'gender': gender[0].upper() if gender else None,
                'race': evt['race_name'],
                'year': evt['year'],
                'distance_mi': round(total_distance_mi, 2),
                'duration_sec': round(total_time_sec),
                'duration': duration_str,
                'data_type': 'checkpoints',
                'source': f'my.raceresult.com event {eid}',
                'distance_id': evt['distance_id'],
                'checkpoints': checkpoints,
            }
            # Remove None values
            split_data = {k: v for k, v in split_data.items() if v is not None}

            if DRY_RUN:
                log(f'    [DRY] {filename} ({runner_name}, {len(checkpoints)} checkpoints, {total_distance_mi:.1f}mi)')
            else:
                with open(filepath, 'w') as f:
                    json.dump(split_data, f, indent=2)
                    f.write('\n')
                runners_written += 1
                stats['files_written'] += 1

            stats['runners_scraped'] += 1

        log(f'  Wrote {runners_written} files')
        stats['events_with_data'] += 1
        stats['events_checked'] += 1


# ============================================================
# Phase 2: Scan for undiscovered events with lap/split data
# ============================================================

def scan_for_events():
    log('=== Phase 2: Scanning for events with lap data ===')

    # Get all MCM Timing events
    log('Fetching MCM Timing event list...')
    mcm_data = fetch_json('https://my.raceresult.com/RREvents/list?group=4286&lang=en')
    if not mcm_data:
        log('  Failed to fetch MCM events')
        return

    # Filter for ultra/timed events
    ultra_keywords = ['24', '48', '12 hour', '6 hour', 'dome', 'solstice', 'ultra',
                      'across the years', 'backyard', 'endurance', 'track']
    candidates = []
    for event in mcm_data:
        eid = event[0]
        name = event[2]
        date = event[3]
        year = int(date[:4]) if date else 0
        if year < 2017:
            continue
        name_lower = name.lower()
        if any(k in name_lower for k in ultra_keywords):
            candidates.append((eid, name, year))

    # Also add known non-MCM events
    non_mcm = [
        (328902, 'Sri Chinmoy Auckland 2025', 2025),
        (273112, 'Sri Chinmoy Auckland 2024', 2024),
        (175381, 'Sri Chinmoy Auckland 2022', 2022),
        (311660, 'Sri Chinmoy Basel 2025', 2025),
        (263242, 'Sri Chinmoy Basel 2024', 2024),
        (272718, 'Sri Chinmoy Belgrade 2024', 2024),
        (175623, 'Sri Chinmoy Belgrade 2021', 2021),
        (359724, 'Self-Transcendence 24h London 2025', 2025),
        (335400, 'World TT Championship 2025', 2025),
        (282273, 'World TT Championship 2024', 2024),
        (335579, 'World TT Championship 6h 2025', 2025),
        (284825, 'World TT Championship 6h 2024', 2024),
        (347684, 'Sri Chinmoy Skopje 2026', 2026),
        (365566, 'Sri Chinmoy Auckland 2026', 2026),
    ]
    candidates.extend(non_mcm)

    log(f'Checking {len(candidates)} candidate events for lap data...')

    # Already known events — skip them
    known_events = set(e['event_id'] for e in CHECKPOINT_EVENTS)
    known_events.update([172744])  # Dome 2021 already scraped

    checked = 0
    for eid, name, year in candidates:
        if eid in known_events:
            continue

        checked += 1
        stats['events_checked'] += 1

        if checked % 50 == 0:
            log(f'  Checked {checked} events so far, found {len(stats["new_lap_events"])} with data')

        try:
            config = fetch_json(f'https://my.raceresult.com/{eid}/results/config?lang=en')
            if not config:
                continue

            key = config['key']
            server = config.get('server', 'my.raceresult.com')
            contests = config.get('contests', {})
            lists = config.get('TabConfig', {}).get('Lists', [])

            # Look specifically for "Lap Details" (per-lap data)
            lap_detail_lists = [l for l in lists if 'lap detail' in l['Name'].lower()]

            # Also check "Lap Result List", "Split Times Individual", "Lap Information"
            all_lap_lists = [l for l in lists if any(k in l['Name'].lower()
                            for k in ['lap detail', 'lap result', 'split times individual',
                                      'lap information', 'lap data', 'lap statistics'])]

            if not all_lap_lists:
                continue

            # Try to fetch data from the first matching list
            first_contest = list(contests.keys())[0] if contests else '1'
            for ll in all_lap_lists:
                params = urllib.parse.urlencode({
                    'key': key, 'listname': ll['Name'],
                    'contest': first_contest, 'r': 'all', 'l': '0'
                })
                url = f'https://{server}/{eid}/results/list?{params}'
                data = fetch_json(url)
                if not data:
                    continue

                d = data.get('data', {})
                count = len(d) if isinstance(d, (dict, list)) else 0
                fields = data.get('DataFields', [])

                if count > 0:
                    has_lap_cols = any('lap' in f.lower() for f in fields) if fields else False
                    event_info = {
                        'event_id': eid,
                        'name': name,
                        'year': year,
                        'list': ll['Name'],
                        'count': count,
                        'fields': fields[:10],
                        'contests': contests,
                        'has_lap_columns': has_lap_cols,
                    }
                    stats['new_lap_events'].append(event_info)
                    log(f'  FOUND: {eid} {name} — {ll["Name"]} ({count} entries)')
                    break

        except Exception:
            stats['errors'] += 1

    log(f'Scan complete. Found {len(stats["new_lap_events"])} events with lap/split data')


# ============================================================
# Phase 3: Integrate new data into index.json
# ============================================================

def integrate_into_index():
    log('=== Phase 3: Integrating new data into index.json ===')

    if DRY_RUN:
        log('  Skipping integration in dry-run mode')
        return

    with open(INDEX_PATH) as f:
        index = json.load(f)

    existing_files = set(p['splits_file'] for p in index['performances'])
    existing_races = {r['id']: r for r in index['races']}
    existing_distances = {d['id'] for d in index['distances']}

    # Scan splits directory for new raceresult files
    new_files = []
    for fname in sorted(os.listdir(SPLITS_DIR)):
        if not fname.endswith('-raceresult.json'):
            continue
        if fname in existing_files:
            continue
        new_files.append(fname)

    if not new_files:
        log('  No new raceresult files to integrate')
        return

    log(f'  Found {len(new_files)} new split files to integrate')

    added = 0
    for fname in new_files:
        filepath = os.path.join(SPLITS_DIR, fname)
        try:
            with open(filepath) as f:
                data = json.load(f)
        except Exception:
            continue

        runner = data.get('runner', 'Unknown')
        race_name = data.get('race', 'Unknown')
        year = data.get('year', 0)
        distance_mi = data.get('distance_mi', 0)
        duration_sec = data.get('duration_sec', 0)
        distance_id = data.get('distance_id', '')
        gender = data.get('gender', 'M')

        if not distance_mi or not duration_sec:
            continue

        # Determine distance_id if not set
        if not distance_id:
            if duration_sec <= 21600 + 1800:  # ~6h
                distance_id = '6h'
            elif duration_sec <= 43200 + 1800:  # ~12h
                distance_id = '12h'
            elif duration_sec <= 86400 + 1800:  # ~24h
                distance_id = '24h'
            elif duration_sec <= 172800 + 3600:  # ~48h
                distance_id = '48h'
            elif duration_sec <= 259200 + 3600:  # ~72h
                distance_id = '72h'
            elif duration_sec <= 518400 + 7200:  # ~6d
                distance_id = '6d'
            else:
                distance_id = '6d'

        # Ensure distance exists
        if distance_id not in existing_distances:
            # Add it
            dist_labels = {
                '6h': '6 Hours', '12h': '12 Hours', '24h': '24 Hours',
                '48h': '48 Hours', '72h': '72 Hours', '6d': '6 Days',
                '10d': '10 Days', '100mi': '100 Miles', '100k': '100 Kilometers',
            }
            index['distances'].append({
                'id': distance_id,
                'label': dist_labels.get(distance_id, distance_id),
                'type': 'timed' if 'h' in distance_id or 'd' in distance_id else 'distance',
            })
            existing_distances.add(distance_id)

        # Create or find race
        race_slug = slugify(race_name)
        race_id = race_slug
        if race_id not in existing_races:
            race_entry = {
                'id': race_id,
                'name': race_name,
                'location': 'USA',
            }
            index['races'].append(race_entry)
            existing_races[race_id] = race_entry

        # Build performance ID
        runner_slug = slugify(runner)
        perf_id = f'{race_slug}-{year}-{runner_slug}'

        # Check for duplicate
        if any(p['id'] == perf_id for p in index['performances']):
            continue

        pace_sec = round(duration_sec / distance_mi, 2) if distance_mi > 0 else 0

        duration_str = data.get('duration', '')
        if not duration_str:
            h = int(duration_sec // 3600)
            m = int((duration_sec % 3600) // 60)
            s = int(duration_sec % 60)
            duration_str = f'{h}:{m:02d}:{s:02d}'

        perf = {
            'id': perf_id,
            'runner': runner,
            'race_id': race_id,
            'year': year,
            'distance_id': distance_id,
            'distance_mi': round(distance_mi, 2),
            'duration': duration_str,
            'pace_sec': pace_sec,
            'splits_file': fname,
        }
        if gender:
            perf['gender'] = gender
        if data.get('nationality'):
            perf['nationality'] = data['nationality']

        index['performances'].append(perf)
        added += 1

    if added > 0:
        with open(INDEX_PATH, 'w') as f:
            json.dump(index, f, indent=2)
            f.write('\n')
        log(f'  Added {added} performances to index.json')
    else:
        log('  No new performances to add')


# ============================================================
# Main
# ============================================================

def main():
    log(f'Overnight Scraper — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'Dry run: {DRY_RUN}')
    log(f'Phase: {PHASE}')
    log(f'Output: {SPLITS_DIR}')

    os.makedirs(SPLITS_DIR, exist_ok=True)

    if PHASE in ('all', 'checkpoints'):
        scrape_checkpoint_events()

    if PHASE in ('all', 'scan'):
        scan_for_events()

    if PHASE in ('all', 'integrate'):
        integrate_into_index()

    log(f'\n{"="*60}')
    log(f'RESULTS:')
    log(f'  Events checked: {stats["events_checked"]}')
    log(f'  Events with data: {stats["events_with_data"]}')
    log(f'  Runners scraped: {stats["runners_scraped"]}')
    log(f'  Files written: {stats["files_written"]}')
    log(f'  Files skipped (existing): {stats["files_skipped"]}')
    log(f'  Errors: {stats["errors"]}')

    if stats['new_lap_events']:
        log(f'\nNew events with lap/split data:')
        for evt in stats['new_lap_events']:
            log(f'  {evt["event_id"]}: {evt["name"]} — {evt["list"]} ({evt["count"]} entries)')
            log(f'    Fields: {evt["fields"][:8]}')
            log(f'    Contests: {evt["contests"]}')


if __name__ == '__main__':
    main()
