#!/usr/bin/env python3
"""
Scrape per-lap split data from my.raceresult.com events.

Usage: python3 scrape-raceresult.py [--dry-run] [--event EVENT_ID]

Fetches lap-by-lap timing data and converts to per-mile splits.
Loop size varies by venue — each event config specifies it.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import re
import math
from datetime import datetime

SPLITS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'splits')
INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'index.json')

# Known raceresult.com events with lap data
# Format: (event_id, race_name, year, loop_meters, distance_ids_and_contests)
EVENTS = [
    # 6 Days in the Dome
    (172744, '6 Days in the Dome', 2021, 443.45, [('6d', '1')]),
    (172743, '6 Days in the Dome 24/48h', 2021, 443.45, [('24h', '1'), ('48h', '2')]),
    (134293, '6 Days in the Dome', 2019, 443.45, [('6d', '1')]),
    (134294, '6 Days in the Dome 24/48h', 2019, 443.45, [('24h', '1'), ('48h', '2')]),
    (208449, '6 Days in the Dome', 2022, 443.45, [('6d', '1')]),
    # Desert Solstice
    (228232, 'Desert Solstice', 2022, 400, [('24h', '1')]),
    (188236, 'Desert Solstice', 2021, 400, [('24h', '1')]),
    (163027, 'Desert Solstice', 2020, 400, [('24h', '1')]),
    (144084, 'Desert Solstice', 2019, 400, [('24h', '1')]),
    # Across The Years
    (377012, 'Across The Years', 2025, None, []),  # need to discover contests/loop
    (229460, 'Across The Years', 2022, None, []),
    (188947, 'Across The Years', 2021, None, []),
    (145502, 'Across The Years', 2019, None, []),
]

DRY_RUN = '--dry-run' in sys.argv
SINGLE_EVENT = None
for i, arg in enumerate(sys.argv):
    if arg == '--event' and i + 1 < len(sys.argv):
        SINGLE_EVENT = int(sys.argv[i + 1])

stats = {'events_processed': 0, 'runners_scraped': 0, 'files_written': 0, 'errors': 0}


def fetch_json(url, retries=3):
    """Fetch JSON from URL with retries and rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(0.5)  # rate limit
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            if attempt == retries - 1:
                print(f'  ERROR fetching {url}: {e}')
                stats['errors'] += 1
                return None
            time.sleep(2 ** attempt)
    return None


def get_event_config(event_id):
    """Get event configuration including key, server, and available lists."""
    url = f'https://my.raceresult.com/{event_id}/results/config?lang=en'
    config = fetch_json(url)
    if not config or 'error' in config:
        print(f'  Failed to get config for event {event_id}')
        return None
    return config


def get_list_data(server, event_id, key, listname, contest):
    """Fetch a results list."""
    params = urllib.parse.urlencode({
        'key': key,
        'listname': listname,
        'contest': contest,
        'r': 'all',
        'l': '0'
    })
    url = f'https://{server}/{event_id}/results/list?{params}'
    return fetch_json(url)


def find_split_list(config):
    """Find the best split/lap list from the config."""
    lists = config.get('TabConfig', {}).get('Lists', [])

    # Priority: Lap Details > Split Times MI > Split Times KM
    for target in ['Lap Details', 'Split Times MI', 'Split Times KM',
                    'Lap Data', 'Splits', 'Split Times']:
        for lst in lists:
            if target.lower() in lst['Name'].lower():
                return lst

    # Fallback: any list with "split" or "lap" in the name
    for lst in lists:
        name = lst['Name'].lower()
        if 'split' in name or 'lap' in name:
            return lst

    return None


def find_results_list(config):
    """Find the main results list."""
    lists = config.get('TabConfig', {}).get('Lists', [])
    for lst in lists:
        name = lst['Name'].lower()
        if 'overall' in name and 'result' in name:
            return lst
    for lst in lists:
        if 'result' in lst['Name'].lower():
            return lst
    return lists[0] if lists else None


def parse_time_to_seconds(time_str):
    """Parse various time formats to seconds."""
    if not time_str or time_str == '-' or time_str == '':
        return 0
    time_str = time_str.strip()

    # Handle "D.HH:MM:SS" format (days)
    if '.' in time_str and ':' in time_str:
        parts = time_str.split('.')
        if len(parts) == 2 and ':' in parts[1]:
            days = int(parts[0])
            hms = parts[1].split(':')
            if len(hms) == 3:
                return days * 86400 + int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])

    # Handle "HH:MM:SS" or "H:MM:SS"
    parts = time_str.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])

    try:
        return float(time_str)
    except ValueError:
        return 0


def laps_to_miles(laps_data, loop_meters, runner_name, total_distance_mi=None):
    """Convert per-lap timing data to per-mile splits.

    laps_data: list of [bib, pid, lap_num, cum_time_str, lap_time_str]
    loop_meters: length of one loop in meters
    """
    if not laps_data or not loop_meters:
        return None

    loop_miles = loop_meters / 1609.344
    miles = []
    current_mile = 1

    # Build cumulative distance/time from laps
    # Times may be clock times (e.g. "12:03:40" = noon start) — convert to elapsed
    cum_points = [(0, 0)]  # (distance_mi, time_sec)

    # Detect start time: first lap clock time minus first lap split time
    start_time = 0
    if len(laps_data) >= 1 and len(laps_data[0]) >= 5:
        first_clock = parse_time_to_seconds(laps_data[0][3])
        first_split = parse_time_to_seconds(laps_data[0][4])
        if first_clock > 0 and first_split > 0 and first_clock > first_split:
            start_time = first_clock - first_split

    prev_elapsed = 0
    for lap in laps_data:
        try:
            lap_num = int(lap[2])
            clock_time = parse_time_to_seconds(lap[3])
            if clock_time <= 0:
                continue

            elapsed = clock_time - start_time
            # Handle clock wrapping past midnight/multiple days
            while elapsed < prev_elapsed - 3600:
                elapsed += 86400

            dist_mi = lap_num * loop_miles
            cum_points.append((dist_mi, elapsed))
            prev_elapsed = elapsed
        except (ValueError, IndexError):
            continue

    if len(cum_points) < 2:
        return None

    # Interpolate to per-mile points
    prev_time = 0
    point_idx = 0
    max_miles = int(cum_points[-1][0])

    if total_distance_mi:
        max_miles = min(max_miles, int(total_distance_mi))

    for mile in range(1, max_miles + 1):
        target_dist = float(mile)

        # Find bracketing points
        while point_idx < len(cum_points) - 1 and cum_points[point_idx + 1][0] < target_dist:
            point_idx += 1

        if point_idx >= len(cum_points) - 1:
            break

        # Linear interpolation
        d1, t1 = cum_points[point_idx]
        d2, t2 = cum_points[point_idx + 1]

        if d2 - d1 <= 0:
            continue

        frac = (target_dist - d1) / (d2 - d1)
        cum_sec = t1 + frac * (t2 - t1)
        split_sec = cum_sec - prev_time

        # Sanity check: skip if split is impossibly fast or slow
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


def slugify(text):
    """Create a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def process_event(event_id, race_name, year, loop_meters, distance_configs):
    """Process a single raceresult.com event."""
    print(f'\n{"="*60}')
    print(f'Processing: {race_name} {year} (event {event_id})')
    print(f'{"="*60}')

    config = get_event_config(event_id)
    if not config:
        return

    key = config['key']
    server = config.get('server', 'my.raceresult.com')
    contests = config.get('contests', {})
    event_name = config.get('eventname', race_name)

    # Try to extract loop size from config info text if not provided
    if not loop_meters:
        info = config.get('TabConfig', {}).get('InfoText', '')
        # Look for loop size mentions
        match = re.search(r'(\d+\.?\d*)\s*(?:meter|metre|m)\b', info, re.I)
        if match:
            loop_meters = float(match.group(1))
            print(f'  Detected loop size: {loop_meters}m')
        else:
            print(f'  WARNING: No loop size found, skipping')
            return

    loop_miles = loop_meters / 1609.344
    print(f'  Loop: {loop_meters}m = {loop_miles:.4f} miles')
    print(f'  Server: {server}')
    print(f'  Contests: {contests}')

    # Find lap details list
    lists = config.get('TabConfig', {}).get('Lists', [])
    print(f'  Available lists: {[l["Name"] for l in lists]}')

    lap_list = find_split_list(config)
    results_list = find_results_list(config)

    if not lap_list:
        print(f'  No lap/split list found, skipping')
        return

    print(f'  Using list: {lap_list["Name"]}')

    # Process each contest (distance category)
    for contest_id, contest_name in contests.items():
        print(f'\n  Contest {contest_id}: {contest_name}')

        # Get lap data
        data = get_list_data(server, event_id, key, lap_list['Name'], contest_id)
        if not data or 'error' in data:
            print(f'    Failed to get lap data: {data.get("error") if data else "no response"}')
            continue

        laps_by_runner = data.get('data', {})
        if isinstance(laps_by_runner, list):
            # Some events return a flat list — group by runner
            print(f'    Got {len(laps_by_runner)} lap entries (flat list)')
            # Group by first element (bib/pid)
            grouped = {}
            for entry in laps_by_runner:
                key_val = entry[0] if entry else 'unknown'
                if key_val not in grouped:
                    grouped[key_val] = []
                grouped[key_val].append(entry)
            laps_by_runner = grouped

        print(f'    Got {len(laps_by_runner)} runners with lap data')

        # Also get results list for metadata (distance, time, etc.)
        results_data = None
        if results_list:
            results_data = get_list_data(server, event_id, key, results_list['Name'], contest_id)

        for runner_key, laps in laps_by_runner.items():
            if not laps or len(laps) < 10:
                continue

            # Parse runner info from key format: "#1_153///Herve Leconte///1175 Laps"
            runner_name = 'Unknown'
            total_laps = len(laps)

            if isinstance(runner_key, str) and '///' in runner_key:
                parts = runner_key.split('///')
                if len(parts) >= 2:
                    runner_name = parts[1].strip()
                if len(parts) >= 3:
                    lap_match = re.search(r'(\d+)', parts[2])
                    if lap_match:
                        total_laps = int(lap_match.group(1))

            total_distance_mi = total_laps * loop_miles
            total_time_sec = 0

            if laps:
                last_lap = laps[-1]
                total_time_sec = parse_time_to_seconds(last_lap[3]) if len(last_lap) > 3 else 0

            # Convert laps to per-mile splits
            miles = laps_to_miles(laps, loop_meters, runner_name, total_distance_mi)

            if not miles:
                continue

            # Determine duration based on contest name
            duration_sec = total_time_sec
            distance_mi = total_distance_mi

            # Build filename
            race_slug = slugify(race_name)
            runner_slug = slugify(runner_name)
            filename = f'{race_slug}-{year}-{runner_slug}-raceresult.json'
            filepath = os.path.join(SPLITS_DIR, filename)

            # Build split data
            split_data = {
                'runner': runner_name,
                'race': event_name,
                'year': year,
                'distance_mi': round(distance_mi, 2),
                'duration_sec': round(duration_sec),
                'duration': f'{int(duration_sec // 3600)}:{int((duration_sec % 3600) // 60):02d}:{int(duration_sec % 60):02d}',
                'data_type': 'miles',
                'source': f'my.raceresult.com event {event_id}',
                'loop_meters': loop_meters,
                'total_laps': total_laps,
                'miles': miles,
            }

            if DRY_RUN:
                print(f'    [DRY RUN] Would write: {filename} ({runner_name}, {len(miles)} miles, {distance_mi:.1f}mi)')
            else:
                with open(filepath, 'w') as f:
                    json.dump(split_data, f, indent=2)
                    f.write('\n')
                print(f'    Wrote: {filename} ({runner_name}, {len(miles)} miles, {distance_mi:.1f}mi)')
                stats['files_written'] += 1

            stats['runners_scraped'] += 1

    stats['events_processed'] += 1


def main():
    print(f'RaceResult.com Scraper — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'Dry run: {DRY_RUN}')
    print(f'Target: {SINGLE_EVENT or "all events"}')
    print(f'Output: {SPLITS_DIR}')

    events = EVENTS
    if SINGLE_EVENT:
        events = [e for e in events if e[0] == SINGLE_EVENT]
        if not events:
            print(f'Event {SINGLE_EVENT} not found in event list')
            return

    for event_id, race_name, year, loop_meters, distance_configs in events:
        try:
            process_event(event_id, race_name, year, loop_meters, distance_configs)
        except Exception as e:
            print(f'ERROR processing event {event_id}: {e}')
            import traceback
            traceback.print_exc()
            stats['errors'] += 1

    print(f'\n{"="*60}')
    print(f'DONE — {stats["events_processed"]} events, {stats["runners_scraped"]} runners, '
          f'{stats["files_written"]} files written, {stats["errors"]} errors')


if __name__ == '__main__':
    main()
