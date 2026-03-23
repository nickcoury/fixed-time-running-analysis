#!/usr/bin/env python3
"""
Scrape timed race results from live.aravaiparunning.com.

Aravaipa Running uses a live tracking platform that serves participant data
via REST API. Per-lap crossing data is only available for currently-live events;
historical events only have overall results (total laps, start/finish times).

This script:
1. Discovers all timed events across all event IDs
2. Extracts participant results with total distance/time
3. For currently-live timed events, attempts to capture per-lap crossing data
4. Outputs split files where crossing data is available

Usage: python3 scrape-aravaipa.py [--dry-run] [--event EVENT_ID] [--crossings-only]
"""

import json
import os
import sys
import time
import urllib.request
import re
import math
from datetime import datetime, timezone

SPLITS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'splits')
INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'index.json')
RESULTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'aravaipa-results')

API_BASE = 'https://live.aravaiparunning.com/api/v1'
HEADERS = {'x-live-ver': '200', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}

# Relevant timed distances for fixed-time analysis (exclude bike rides, school events, relays)
RELEVANT_RACE_NAMES = {
    '24h', '24hrs', '24 hour', '24 Hour', 'USATF 24HR', '24-Hour Day 1', '24-Hour Day 2',
    '24 Hour - FRI', '24 Hour',
    '48h', '48hrs', '48 hour', '48 Hour',
    '72h', '72hrs', '72 hour', '72 Hours', '72 Hour',
    '12h', '12hrs', '12 hour', '12 Hour', '12HR', '12hr Solo', '12 Hour - FRI',
    '6h', '6hrs', '6 hour', '6 Hour', '6HR', '6hr Solo', '6 Hour Solo',
    '6 Day', '6d',
    'Last Person Standing',
}

# Skip these patterns (relays, bikes, school, duos)
SKIP_PATTERNS = [
    'relay', 'duo', 'trio', 'team', 'bike', 'grade', 'kindergarten',
    'single speed', 'per relay', 'person relay',
]

DRY_RUN = '--dry-run' in sys.argv
CROSSINGS_ONLY = '--crossings-only' in sys.argv
SINGLE_EVENT = None
for i, arg in enumerate(sys.argv):
    if arg == '--event' and i + 1 < len(sys.argv):
        SINGLE_EVENT = int(sys.argv[i + 1])

stats = {'events': 0, 'races': 0, 'participants': 0, 'with_crossings': 0, 'files_written': 0, 'errors': 0}


def fetch_json(url, retries=3):
    """Fetch JSON from URL with retries and rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(0.3)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode('utf-8')
                if not data:
                    return None
                return json.loads(data)
        except Exception as e:
            if attempt == retries - 1:
                print(f'  ERROR fetching {url}: {e}')
                stats['errors'] += 1
                return None
            time.sleep(2 ** attempt)
    return None


def is_relevant_race(race):
    """Check if a race is relevant for fixed-time analysis."""
    if not race.get('isTimed'):
        return False
    name = race.get('name', '')
    name_lower = name.lower()
    # Skip relays, bikes, school events
    for pattern in SKIP_PATTERNS:
        if pattern in name_lower:
            return False
    return True


def classify_distance(race_name):
    """Classify race name into a standard distance category."""
    name = race_name.lower().strip()
    if '6 day' in name or '6d' in name:
        return '6d'
    if '72' in name:
        return '72h'
    if '48' in name:
        return '48h'
    if '24' in name:
        return '24h'
    if '12' in name:
        return '12h'
    if '6' in name:
        return '6h'
    if 'last person standing' in name:
        return 'lps'
    return None


def get_duration_seconds(distance_category):
    """Get expected duration in seconds for a distance category."""
    durations = {
        '6h': 21600,
        '12h': 43200,
        '24h': 86400,
        '48h': 172800,
        '72h': 259200,
        '6d': 518400,
    }
    return durations.get(distance_category, 0)


def slugify(text):
    """Create a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def get_crossings(event_id, participant_ids, max_pages=100):
    """Try to get crossing data for specific participants.

    The crossings endpoint returns the 50 most recent crossings globally.
    We paginate back to find crossings for our participants.
    Note: This only works for currently-live or very recent events.
    """
    all_crossings = {}
    target_pids = set(participant_ids)

    url = f'{API_BASE}/race_events/{event_id}/crossings'
    data = fetch_json(url)

    if not data or not isinstance(data, list):
        return all_crossings

    # Check if any crossings match our participants
    for crossing in data:
        pid = crossing.get('participantId')
        if pid in target_pids and crossing.get('validCrossing'):
            if pid not in all_crossings:
                all_crossings[pid] = []
            all_crossings[pid].append(crossing)

    return all_crossings


def crossings_to_miles(crossings, loop_meters, start_time_str):
    """Convert validated crossings to per-mile splits."""
    if not crossings or not loop_meters:
        return None

    loop_miles = loop_meters / 1609.344

    # Parse start time
    start_dt = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))

    # Sort crossings by timestamp
    sorted_crossings = sorted(crossings, key=lambda c: c['timestamp'])

    # Build cumulative distance/time points
    cum_points = [(0, 0)]
    lap_num = 0

    for crossing in sorted_crossings:
        if not crossing.get('validCrossing'):
            continue
        lap_num += 1
        ts = datetime.fromisoformat(crossing['timestamp'].replace('Z', '+00:00'))
        elapsed_sec = (ts - start_dt).total_seconds()
        dist_mi = lap_num * loop_miles
        cum_points.append((dist_mi, elapsed_sec))

    if len(cum_points) < 10:
        return None

    # Interpolate to per-mile points
    miles = []
    prev_time = 0
    point_idx = 0
    max_miles = int(cum_points[-1][0])

    for mile in range(1, max_miles + 1):
        target_dist = float(mile)

        while point_idx < len(cum_points) - 1 and cum_points[point_idx + 1][0] < target_dist:
            point_idx += 1

        if point_idx >= len(cum_points) - 1:
            break

        d1, t1 = cum_points[point_idx]
        d2, t2 = cum_points[point_idx + 1]

        if d2 - d1 <= 0:
            continue

        frac = (target_dist - d1) / (d2 - d1)
        cum_sec = t1 + frac * (t2 - t1)
        split_sec = cum_sec - prev_time

        if split_sec < 120 or split_sec > 7200:
            continue

        miles.append({
            'mile': mile,
            'split_sec': round(split_sec, 1),
            'moving_sec': round(split_sec, 1),
            'cum_sec': round(cum_sec, 1)
        })
        prev_time = cum_sec

    return miles if len(miles) >= 5 else None


def process_event(event_id):
    """Process a single Aravaipa event."""
    data = fetch_json(f'{API_BASE}/race_events/{event_id}')
    if not data or 'name' not in data:
        return

    event_name = data['name']
    slug = data.get('slug', '')

    # Extract year from slug
    year_match = re.search(r'-(\d{4})$', slug)
    year = int(year_match.group(1)) if year_match else None

    races = data.get('races', [])
    relevant_races = [r for r in races if is_relevant_race(r)]

    if not relevant_races:
        return

    participants = data.get('participants', [])

    print(f'\n{"="*60}')
    print(f'Event {event_id}: {event_name} ({slug})')
    print(f'{"="*60}')
    stats['events'] += 1

    for race in relevant_races:
        race_name = race['name']
        race_id = race['id']
        distance_cat = classify_distance(race_name)
        loop_meters = race.get('distance', 0)
        is_loop = race.get('isLoop', False)
        start_time = race.get('startTime', '')
        cutoff = race.get('cutoff', '')

        if not distance_cat or distance_cat == 'lps':
            continue

        # Get splits info for loop size
        splits = race.get('splits', [])
        finish_split = next((s for s in splits if s.get('name') == 'Finish'), None)
        if finish_split and finish_split.get('distance'):
            loop_meters = finish_split['distance']

        if not loop_meters or loop_meters < 100:
            print(f'  {race_name}: skipping, no valid loop distance (got {loop_meters})')
            continue

        loop_miles = loop_meters / 1609.344
        duration_sec = get_duration_seconds(distance_cat)

        # Get participants for this race
        race_participants = [p for p in participants if p.get('raceId') == race_id]
        active = [p for p in race_participants if p.get('lapCount', 0) > 0]

        print(f'  {race_name} ({distance_cat}): {loop_meters}m loop, {len(active)}/{len(race_participants)} active participants')
        stats['races'] += 1

        if CROSSINGS_ONLY:
            # Only try to get crossing data, skip overall results
            pids = [p['id'] for p in active]
            crossings = get_crossings(event_id, pids)
            if crossings:
                print(f'    Found crossings for {len(crossings)} participants!')
                for pid, cx in crossings.items():
                    participant = next((p for p in active if p['id'] == pid), None)
                    if not participant:
                        continue
                    runner_name = f"{participant['firstName']} {participant['lastName']}"
                    miles = crossings_to_miles(cx, loop_meters, participant.get('st', start_time))
                    if miles:
                        write_split_file(event_name, year, race_name, distance_cat,
                                        runner_name, participant, loop_meters, miles, duration_sec)
            else:
                print(f'    No crossing data available (event not live)')
            continue

        # Process each participant
        for p in sorted(active, key=lambda x: x.get('lapCount', 0), reverse=True):
            runner_name = f"{p['firstName']} {p['lastName']}"
            lap_count = p.get('lapCount', 0)
            total_distance_mi = round(lap_count * loop_miles, 2)

            # Calculate elapsed time
            st = p.get('st')
            last_seen = p.get('lastSeenAt')

            if st and last_seen:
                try:
                    start_dt = datetime.fromisoformat(st.replace('Z', '+00:00'))
                    last_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                    elapsed_sec = (last_dt - start_dt).total_seconds()
                except:
                    elapsed_sec = duration_sec
            else:
                elapsed_sec = duration_sec

            # Use race duration as the actual duration (timed event)
            actual_duration = duration_sec if duration_sec > 0 else elapsed_sec

            stats['participants'] += 1

            # Build result entry (no per-lap splits available)
            result = {
                'runner': runner_name,
                'race': event_name,
                'year': year,
                'distance_mi': total_distance_mi,
                'distance_cat': distance_cat,
                'duration_sec': actual_duration,
                'lap_count': lap_count,
                'loop_meters': loop_meters,
                'gender': p.get('gender', ''),
                'age': p.get('age', 0),
                'country': p.get('country', ''),
                'overall_place': p.get('overallPlace'),
                'gender_place': p.get('genderPlace'),
                'bib': p.get('bib', ''),
                'source': f'live.aravaiparunning.com event {event_id}',
                'has_splits': False,
            }

            if not DRY_RUN:
                # Save to results directory (not splits — no per-lap data)
                os.makedirs(RESULTS_DIR, exist_ok=True)
                race_slug = slugify(event_name)
                runner_slug = slugify(runner_name)
                filename = f'{race_slug}-{year}-{distance_cat}-{runner_slug}.json'
                filepath = os.path.join(RESULTS_DIR, filename)
                with open(filepath, 'w') as f:
                    json.dump(result, f, indent=2)
                    f.write('\n')
                stats['files_written'] += 1

            if total_distance_mi >= 20:  # Only print notable results
                hours = actual_duration / 3600
                print(f'    {runner_name}: {total_distance_mi:.1f}mi in {hours:.0f}h ({lap_count} laps)')


def write_split_file(event_name, year, race_name, distance_cat, runner_name,
                     participant, loop_meters, miles, duration_sec):
    """Write a split file for a participant with per-lap data."""
    race_slug = slugify(event_name)
    runner_slug = slugify(runner_name)
    filename = f'{race_slug}-{year}-{runner_slug}-aravaipa.json'
    filepath = os.path.join(SPLITS_DIR, filename)

    lap_count = participant.get('lapCount', len(miles))
    total_distance_mi = round(lap_count * (loop_meters / 1609.344), 2)

    split_data = {
        'runner': runner_name,
        'race': f'{event_name} {race_name}',
        'year': year,
        'distance_mi': total_distance_mi,
        'duration_sec': duration_sec,
        'duration': f'{int(duration_sec // 3600)}:{int((duration_sec % 3600) // 60):02d}:{int(duration_sec % 60):02d}',
        'data_type': 'miles',
        'source': f'live.aravaiparunning.com',
        'loop_meters': loop_meters,
        'total_laps': lap_count,
        'miles': miles,
    }

    if DRY_RUN:
        print(f'    [DRY RUN] Would write: {filename} ({runner_name}, {len(miles)} miles)')
    else:
        with open(filepath, 'w') as f:
            json.dump(split_data, f, indent=2)
            f.write('\n')
        print(f'    Wrote split file: {filename} ({runner_name}, {len(miles)} miles)')
        stats['files_written'] += 1
        stats['with_crossings'] += 1


def discover_timed_events():
    """Scan all event IDs to find timed running events."""
    print('Discovering timed events across all event IDs...')
    timed_events = []

    # Scan IDs 1 through 500 (known range)
    max_consecutive_404 = 20
    consecutive_404 = 0

    for event_id in range(1, 550):
        if SINGLE_EVENT and event_id != SINGLE_EVENT:
            continue

        data = fetch_json(f'{API_BASE}/race_events/{event_id}')
        if not data or 'name' not in data:
            consecutive_404 += 1
            if consecutive_404 > max_consecutive_404 and event_id > 490:
                break
            continue

        consecutive_404 = 0
        races = data.get('races', [])
        relevant = [r for r in races if is_relevant_race(r)]

        if relevant:
            timed_events.append(event_id)
            event_name = data['name']
            slug = data.get('slug', '')
            race_names = [r['name'] for r in relevant]
            print(f'  Found: {event_id} - {event_name} ({slug}) — {race_names}')

    print(f'\nFound {len(timed_events)} timed running events')
    return timed_events


def main():
    print(f'Aravaipa Running Scraper — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Dry run: {DRY_RUN}')
    print(f'Crossings only: {CROSSINGS_ONLY}')
    print(f'Target: {SINGLE_EVENT or "all events"}')

    if SINGLE_EVENT:
        events = [SINGLE_EVENT]
    else:
        events = discover_timed_events()

    for event_id in events:
        try:
            process_event(event_id)
        except Exception as e:
            print(f'ERROR processing event {event_id}: {e}')
            import traceback
            traceback.print_exc()
            stats['errors'] += 1

    print(f'\n{"="*60}')
    print(f'DONE — {stats["events"]} events, {stats["races"]} races, '
          f'{stats["participants"]} participants, {stats["with_crossings"]} with crossings, '
          f'{stats["files_written"]} files written, {stats["errors"]} errors')

    if not CROSSINGS_ONLY and stats['participants'] > 0:
        print(f'\nNote: Per-lap crossing data is only available for currently-live events.')
        print(f'Results saved to {RESULTS_DIR} (overall results, no per-mile splits).')
        print(f'To capture per-lap data during a live event, run with --crossings-only during the race.')


if __name__ == '__main__':
    main()
