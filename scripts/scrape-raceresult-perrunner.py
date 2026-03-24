#!/usr/bin/env python3
"""
Scrape per-runner lap details from raceresult.com using the Details API.

This uses the per-participant detail endpoint that returns every lap's
cumulative and split times. Works across all known raceresult event formats.

API pattern (reverse-engineered via browser network interception):
  1. GET /{eventid}/results/config?lang=en → server, key, lists (with Details IDs)
  2. GET {server}/{eventid}/results/list?key=...&listname={FULL_NAME}&contest=0&r=all
     → participant list with PIDs
  3. GET {server}/{eventid}/{detailsId}/config?key=...&pid=0 → detail list names
  4. GET {server}/{eventid}/{detailsId}/list?key=...&listname={DETAIL_LIST}&contest=0&r=pid&pid={pid}
     → per-runner lap details

Usage:
  python3 scrape-raceresult-perrunner.py EVENT_ID [--dry-run] [--limit N]
  python3 scrape-raceresult-perrunner.py --registry [--dry-run]
"""

import json
import os
import re
import sys
import time
import traceback
import urllib.request
import urllib.parse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
SPLITS_DIR = os.path.join(DATA_DIR, 'splits')
REGISTRY_PATH = os.path.join(DATA_DIR, 'race-registry.json')

DRY_RUN = '--dry-run' in sys.argv
RUNNER_LIMIT = None
CLI_YEAR = None
CLI_LOOP = None
for i, arg in enumerate(sys.argv):
    if arg == '--limit' and i + 1 < len(sys.argv):
        RUNNER_LIMIT = int(sys.argv[i + 1])
    elif arg == '--year' and i + 1 < len(sys.argv):
        CLI_YEAR = int(sys.argv[i + 1])
    elif arg == '--loop' and i + 1 < len(sys.argv):
        CLI_LOOP = float(sys.argv[i + 1])

stats = {'events': 0, 'runners': 0, 'files': 0, 'skipped': 0, 'errors': 0}


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def fetch_json(url, retries=3):
    """Fetch JSON with retries and rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(0.4)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw)
        except Exception as e:
            if attempt == retries - 1:
                log(f'  FETCH ERROR {url}: {e}')
                stats['errors'] += 1
                return None
            time.sleep(2 ** attempt)
    return None


def parse_time_to_seconds(time_str):
    """Parse time strings to seconds. Handles H:MM:SS, D.HH:MM:SS, MM:SS, raw seconds."""
    if not time_str or str(time_str).strip() in ('', '-', '*', 'DNF', 'DNS', 'DSQ'):
        return 0
    s = str(time_str).strip().replace(',', '.')

    # "D.HH:MM:SS" format
    if '.' in s and ':' in s:
        parts = s.split('.')
        if len(parts) == 2 and ':' in parts[1]:
            try:
                days = int(parts[0])
                hms = parts[1].split(':')
                if len(hms) == 3:
                    return days * 86400 + int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])
            except (ValueError, TypeError):
                pass

    parts = s.split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(s)
    except (ValueError, TypeError):
        return 0
    return 0


def slugify(text):
    """Create a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].strip('-')


def flatten_data(data):
    """Recursively flatten nested raceresult data structures to a list of rows.

    RaceResult nesting varies wildly across events:
    - Flat list: [[row], [row], ...]
    - Dict with group keys: {"group1": [[row], ...], "group2": [[row], ...]}
    - Deeply nested: {"rank": {"runner": [[row], ...]}}
    """
    rows = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, list):
                rows.append(item)
            else:
                rows.extend(flatten_data(item))
    elif isinstance(data, dict):
        for v in data.values():
            rows.extend(flatten_data(v))
    return rows


def get_event_config(event_id):
    """Fetch event config: server, key, lists, contests."""
    config = fetch_json(f'https://my.raceresult.com/{event_id}/results/config?lang=en')
    if not config:
        return None
    return config


def find_results_list(config):
    """Find the main results list (Overall Results or similar)."""
    lists = config.get('TabConfig', {}).get('Lists', [])
    # Priority: Overall Results > any Results > first list
    for lst in lists:
        name = lst.get('Name', '').lower()
        if 'overall' in name and 'result' in name:
            return lst
    for lst in lists:
        name = lst.get('Name', '').lower()
        if 'result' in name and 'lap' not in name and 'detail' not in name:
            return lst
    return lists[0] if lists else None


def get_participants(config, event_id, results_list, contest='0'):
    """Fetch participant list from the main results list.

    Returns list of dicts with: pid, name, bib, gender.
    Uses DataFields to find named columns when possible.
    """
    server = config.get('server', 'my.raceresult.com')
    key = config['key']
    full_name = results_list['Name']

    params = urllib.parse.urlencode({
        'key': key,
        'listname': full_name,
        'page': 'results',
        'contest': str(contest),
        'r': 'all',
        'l': '0',
    })
    url = f'https://{server}/{event_id}/results/list?{params}'
    data = fetch_json(url)
    if not data:
        return []

    fields = data.get('DataFields', [])
    raw_data = data.get('data', {})
    rows = flatten_data(raw_data)

    # Find field indices from DataFields
    name_idx = None
    gender_idx = None
    for i, f in enumerate(fields):
        fl = f.lower() if isinstance(f, str) else ''
        if 'displayname' in fl or f == 'DisplayName':
            name_idx = i
        elif 'name' in fl and 'contest' not in fl and name_idx is None:
            name_idx = i
        elif fl in ('gendermf', 'gender', 'sex') or 'gender' in fl:
            gender_idx = i

    participants = []
    seen_pids = set()
    for row in rows:
        if not row or len(row) < 2:
            continue
        try:
            bib = str(row[0]).strip()
            pid = str(row[1]).strip()
            if not pid or pid in seen_pids:
                continue
            seen_pids.add(pid)

            # Get name from known index or search
            name = ''
            if name_idx is not None and name_idx < len(row):
                name = str(row[name_idx]).strip()

            if not name:
                for idx in range(2, min(len(row), 8)):
                    val = str(row[idx]).strip()
                    if not val or len(val) <= 1:
                        continue
                    if re.match(r'^[\d:.\-]+$', val):
                        continue
                    if val.startswith('[img:') or val.startswith('<img') or val.startswith('['):
                        continue
                    if re.match(r'^\d', val):
                        continue
                    name = val
                    break

            if not name:
                name = f'Runner-{pid}'

            gender = None
            if gender_idx is not None and gender_idx < len(row):
                g = str(row[gender_idx]).strip().upper()
                if g in ('M', 'F', 'W'):
                    gender = 'M' if g == 'M' else 'F'

            participants.append({'pid': pid, 'name': name, 'bib': bib, 'gender': gender})
        except (ValueError, IndexError):
            continue

    return participants


def get_detail_config(config, event_id, details_id):
    """Fetch the detail view config to find available detail lists."""
    server = config.get('server', 'my.raceresult.com')
    key = config['key']

    url = f'https://{server}/{event_id}/{details_id}/config?key={key}&pid=0'
    return fetch_json(url)


def find_lap_detail_list(detail_config):
    """Find the lap details list name from detail config.

    Known patterns:
    - "Online|Lap Details" (Desert Solstice)
    - "Result Lists|Lap Details Online" (Self-Transcendence)
    - "Result Lists|Individ Laps" (Sri Chinmoy)
    - "Result Lists|Rundenzeiten" (German events)

    Detail config can have either:
    - "List": "Online|Lap Details" (single string, most common)
    - "TabConfig": {"Lists": [...]} (less common)
    """
    # Most common: single "List" field
    single_list = detail_config.get('List', '')
    if single_list:
        return {'Name': single_list}

    # Fallback: TabConfig.Lists array
    lists = detail_config.get('TabConfig', {}).get('Lists', [])
    for target in ['lap detail', 'individ lap', 'rundenzeiten', 'lap data',
                    'split detail', 'laps', 'runden']:
        for lst in lists:
            if target in lst.get('Name', '').lower():
                return lst
    for lst in lists:
        name = lst.get('Name', '').lower()
        if 'lap' in name or 'split' in name or 'runde' in name:
            return lst
    return None


def get_runner_laps(config, event_id, details_id, detail_list_name, pid):
    """Fetch per-runner lap detail data."""
    server = config.get('server', 'my.raceresult.com')
    key = config['key']

    params = urllib.parse.urlencode({
        'key': key,
        'listname': detail_list_name,
        'page': 'results',
        'contest': '0',
        'r': 'pid',
        'pid': pid,
    })
    url = f'https://{server}/{event_id}/{details_id}/list?{params}'
    return fetch_json(url)


def parse_lap_rows(rows, fields):
    """Parse lap rows into structured lap data.

    Handles known field variations:
    - Read{n}Text / Lap{n}Text (cumulative + split)
    - Split{n} / Lap{n} (cumulative + split)
    - Measurement{n} / Hour{n} (cumulative + running time)
    - Only split time (no cumulative) — derive cumulative
    - Distance field per lap
    """
    # Detect field indices
    cum_idx = None
    split_idx = None
    lap_num_idx = None
    distance_idx = None

    for i, f in enumerate(fields):
        fl = f.lower() if isinstance(f, str) else ''
        # Lap number
        if f == '{n}':
            lap_num_idx = i
        # Cumulative time
        elif 'read' in fl and 'text' in fl:
            cum_idx = i
        elif f in ('[Split{n}]', '[Measurement{n}]'):
            cum_idx = i
        # Split/lap time
        elif 'lap' in fl and 'text' in fl:
            split_idx = i
        elif f in ('[Lap{n}]', '[Hour{n}]'):
            split_idx = i
        # Distance
        elif 'dist' in fl or 'km' in fl.replace('100km', ''):
            distance_idx = i

    if cum_idx is None and split_idx is None:
        # Try generic approach: look for time-like fields
        for i, f in enumerate(fields):
            if i == lap_num_idx:
                continue
            if isinstance(f, str) and ('{n}' in f or 'time' in f.lower()):
                if cum_idx is None:
                    cum_idx = i
                elif split_idx is None:
                    split_idx = i

    if cum_idx is None and split_idx is None:
        return None, f'no time fields found in {fields}'

    laps = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or not row:
            continue

        lap_num = len(laps) + 1
        if lap_num_idx is not None and lap_num_idx < len(row):
            try:
                lap_num = int(row[lap_num_idx])
            except (ValueError, TypeError):
                pass

        cum_time = parse_time_to_seconds(row[cum_idx]) if cum_idx is not None and cum_idx < len(row) else 0
        split_time = parse_time_to_seconds(row[split_idx]) if split_idx is not None and split_idx < len(row) else 0

        if cum_time <= 0 and split_time <= 0:
            continue

        # Derive missing values
        if split_time <= 0 and cum_time > 0 and laps:
            split_time = cum_time - laps[-1]['cum_sec']
        if cum_time <= 0 and split_time > 0:
            cum_time = (laps[-1]['cum_sec'] if laps else 0) + split_time

        if split_time <= 0 or cum_time <= 0:
            continue

        lap = {
            'lap': lap_num,
            'split_sec': round(split_time, 2),
            'cum_sec': round(cum_time, 2),
        }

        # Add distance if available
        if distance_idx is not None and distance_idx < len(row):
            try:
                dist_str = str(row[distance_idx]).replace(',', '.').replace(' km', '').replace(' mi', '')
                dist = float(dist_str)
                if dist > 0:
                    lap['distance_km'] = round(dist, 3)
            except (ValueError, TypeError):
                pass

        laps.append(lap)

    if len(laps) < 3:
        return None, f'only {len(laps)} valid laps'

    # Validate: cumulative should be monotonically increasing
    bad_laps = 0
    for i in range(1, len(laps)):
        if laps[i]['cum_sec'] <= laps[i-1]['cum_sec']:
            bad_laps += 1
    if bad_laps > len(laps) * 0.1:
        return None, f'{bad_laps}/{len(laps)} non-monotonic cumulative times'

    return laps, None


def laps_to_miles(laps, loop_meters):
    """Convert per-lap timing to per-mile splits via interpolation."""
    if not laps or not loop_meters or loop_meters <= 0:
        return None

    loop_miles = loop_meters / 1609.344

    # Build cumulative distance/time points
    cum_points = [(0, 0)]
    for lap in laps:
        dist_mi = lap['lap'] * loop_miles
        cum_points.append((dist_mi, lap['cum_sec']))

    if len(cum_points) < 2:
        return None

    max_miles = int(cum_points[-1][0])
    if max_miles < 5:
        return None

    miles = []
    prev_time = 0
    point_idx = 0

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
            'cum_sec': round(cum_sec, 1),
        })
        prev_time = cum_sec

    return miles if len(miles) >= 5 else None


def classify_distance(text):
    """Classify fixed-time distance from text."""
    text = text.lower()
    patterns = [
        (r'6[- ]?day|6d\b|144[- ]?h', '6d'),
        (r'72[- ]?h', '72h'),
        (r'48[- ]?h', '48h'),
        (r'36[- ]?h', '36h'),
        (r'24[- ]?h|24\s*hour', '24h'),
        (r'12[- ]?h|12\s*hour', '12h'),
        (r'100\s*k|100km', '100k'),
        (r'100\s*mi', '100mi'),
        (r'50\s*k|50km', '50k'),
        (r'6[- ]?h|6\s*hour', '6h'),
    ]
    for pattern, dist_id in patterns:
        if re.search(pattern, text):
            return dist_id
    return None


def process_event(event_id, race_name=None, year=None, loop_meters=None, distance_id=None):
    """Process a single raceresult event using the per-runner Details API."""
    log(f'{"="*60}')
    log(f'Event {event_id}: {race_name or "unknown"} ({year or "?"})')
    log(f'{"="*60}')

    config = get_event_config(event_id)
    if not config:
        log(f'  Failed to get config')
        return 0

    server = config.get('server', 'my.raceresult.com')
    key = config['key']
    contests = config.get('contests', {})
    event_name = config.get('eventname', race_name or f'Event {event_id}')

    if not race_name:
        race_name = event_name
    if CLI_YEAR:
        year = CLI_YEAR
    if not year:
        # Try to extract year from event name or info text
        year_match = re.search(r'\b(20\d{2})\b', event_name)
        if year_match:
            year = int(year_match.group(1))
        else:
            info = config.get('TabConfig', {}).get('InfoText', '')
            year_match = re.search(r'\b(20\d{2})\b', info)
            if year_match:
                year = int(year_match.group(1))
    if CLI_LOOP:
        loop_meters = CLI_LOOP
    if not distance_id:
        contest_text = ' '.join(str(v) for v in contests.values())
        distance_id = classify_distance(event_name + ' ' + contest_text)

    log(f'  Server: {server}')
    log(f'  Contests: {json.dumps(contests)}')

    # Step 1: Find results list
    results_list = find_results_list(config)
    if not results_list:
        log(f'  No results list found')
        return 0

    # Check for Details ID
    details_id = results_list.get('Details')
    if not details_id:
        # Try other lists
        for lst in config.get('TabConfig', {}).get('Lists', []):
            if lst.get('Details'):
                details_id = lst['Details']
                results_list = lst
                break

    if not details_id:
        log(f'  No Details ID found in any list — per-runner data unavailable')
        return 0

    log(f'  Results list: {results_list["Name"]}')
    log(f'  Details ID: {details_id}')

    # Step 2: Get detail config to find lap list name
    detail_config = get_detail_config(config, event_id, details_id)
    if not detail_config:
        log(f'  Failed to get detail config')
        return 0

    lap_list = find_lap_detail_list(detail_config)
    if not lap_list:
        detail_lists = detail_config.get('TabConfig', {}).get('Lists', [])
        log(f'  No lap detail list found. Available: {[l["Name"] for l in detail_lists]}')
        return 0

    detail_list_name = lap_list['Name']
    log(f'  Detail list: {detail_list_name}')

    # Step 3: Get participant list
    # Try contest=0 first (all contests), fall back to per-contest
    participants = get_participants(config, event_id, results_list)
    if not participants and contests:
        log(f'  No participants with contest=0, trying per-contest...')
        all_lists = config.get('TabConfig', {}).get('Lists', [])
        for cid, cname in contests.items():
            # Find a results list for this contest
            contest_list = None
            for lst in all_lists:
                if lst.get('Name', '').lower().startswith('result') and \
                   'overall' in lst.get('Name', '').lower() and \
                   str(lst.get('Contest', '')) == str(cid):
                    contest_list = lst
                    break
            if not contest_list:
                for lst in all_lists:
                    if 'result' in lst.get('Name', '').lower() and \
                       str(lst.get('Contest', '')) == str(cid):
                        contest_list = lst
                        break
            if contest_list:
                contest_participants = get_participants(config, event_id, contest_list, contest=cid)
                # Tag each participant with their contest distance
                contest_dist = classify_distance(cname)
                for p in contest_participants:
                    p['contest_distance_id'] = contest_dist
                    p['contest_name'] = cname
                participants.extend(contest_participants)
                if contest_participants:
                    log(f'    Contest {cid} ({cname}): {len(contest_participants)} participants')

    log(f'  Participants: {len(participants)}')

    if not participants:
        log(f'  No participants found')
        return 0

    if RUNNER_LIMIT:
        participants = participants[:RUNNER_LIMIT]
        log(f'  Limited to {RUNNER_LIMIT} runners')

    # Step 4: Fetch per-runner lap data
    os.makedirs(SPLITS_DIR, exist_ok=True)
    existing_files = set(os.listdir(SPLITS_DIR))
    files_written = 0
    errors_this_event = []

    race_slug = slugify(race_name)

    for idx, p in enumerate(participants):
        pid, name, bib, gender = p['pid'], p['name'], p['bib'], p.get('gender')
        runner_slug = slugify(name)
        if not runner_slug:
            runner_slug = f'pid-{pid}'

        # Check if file already exists
        # Avoid duplicate year in filename if race_slug already contains the year
        year_str = str(year) if year else str(event_id)
        if year and year_str in race_slug:
            filename = f'{race_slug}-{runner_slug}-raceresult.json'
        else:
            filename = f'{race_slug}-{year_str}-{runner_slug}-raceresult.json'
        if filename in existing_files:
            stats['skipped'] += 1
            continue

        # Fetch this runner's lap details
        lap_data = get_runner_laps(config, event_id, details_id, detail_list_name, pid)
        if not lap_data:
            errors_this_event.append(f'{name}: no response')
            continue

        fields = lap_data.get('DataFields', [])
        raw_data = lap_data.get('data', {})
        rows = flatten_data(raw_data)

        if not rows:
            stats['skipped'] += 1
            continue

        # Parse laps
        laps, err = parse_lap_rows(rows, fields)
        if err:
            if len(errors_this_event) < 5:
                errors_this_event.append(f'{name}: {err}')
            stats['skipped'] += 1
            continue

        # Convert to per-mile splits if loop size known
        miles = None
        if loop_meters:
            miles = laps_to_miles(laps, loop_meters)

        # Build split file
        # Use per-participant contest distance if available
        runner_distance_id = p.get('contest_distance_id') or distance_id

        split_data = {
            'runner': name,
            'race': race_name,
            'year': year,
            'distance_id': runner_distance_id,
            'source': f'my.raceresult.com event {event_id}',
        }

        if gender:
            split_data['gender'] = gender

        if miles:
            split_data['data_type'] = 'miles'
            split_data['distance_mi'] = round(len(laps) * loop_meters / 1609.344, 2) if loop_meters else 0
            split_data['duration_sec'] = round(laps[-1]['cum_sec'])
            split_data['loop_meters'] = loop_meters
            split_data['total_laps'] = len(laps)
            split_data['miles'] = miles
        else:
            split_data['data_type'] = 'laps'
            split_data['total_laps'] = len(laps)
            split_data['total_time_sec'] = round(laps[-1]['cum_sec'], 2)
            split_data['laps'] = laps

        filepath = os.path.join(SPLITS_DIR, filename)

        if DRY_RUN:
            dtype = 'miles' if miles else 'laps'
            count = len(miles) if miles else len(laps)
            log(f'  [{idx+1}/{len(participants)}] [DRY] {filename} ({name}, {count} {dtype})')
        else:
            with open(filepath, 'w') as f:
                json.dump(split_data, f, indent=2)
                f.write('\n')
            existing_files.add(filename)

        files_written += 1
        stats['files'] += 1
        stats['runners'] += 1

        # Progress update every 25 runners
        if (idx + 1) % 25 == 0:
            log(f'  Progress: {idx+1}/{len(participants)} runners, {files_written} files')

    log(f'  Done: {files_written} files, {stats["skipped"]} skipped')
    if errors_this_event:
        for err in errors_this_event[:5]:
            log(f'  ERROR: {err}')
        if len(errors_this_event) > 5:
            log(f'  ... and {len(errors_this_event) - 5} more errors')

    stats['events'] += 1
    return files_written


def load_registry():
    """Load race registry and return raceresult events."""
    if not os.path.exists(REGISTRY_PATH):
        log(f'Registry not found: {REGISTRY_PATH}')
        return []

    with open(REGISTRY_PATH) as f:
        reg = json.load(f)

    events = []
    for race_key, race_info in reg['races'].items():
        for src in race_info.get('sources', []):
            if src.get('platform') != 'raceresult':
                continue

            loop_meters = src.get('loop_meters')
            race_name = race_info.get('name', race_key)
            distances = race_info.get('distances', [])
            distance_id = distances[0] if len(distances) == 1 else None

            # Handle single event_id or list
            event_ids = src.get('event_ids', [])
            if not event_ids and src.get('event_id'):
                event_ids = [src['event_id']]

            for eid in event_ids:
                events.append({
                    'event_id': eid,
                    'race_name': race_name,
                    'year': None,
                    'loop_meters': loop_meters,
                    'distance_id': distance_id,
                })

    return events


def main():
    log(f'RaceResult Per-Runner Scraper — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'Dry run: {DRY_RUN}')

    if '--registry' in sys.argv:
        events = load_registry()
        log(f'Registry: {len(events)} events')
        for ev in events:
            try:
                process_event(**ev)
            except Exception as e:
                log(f'FATAL ERROR on event {ev["event_id"]}: {e}')
                traceback.print_exc(file=sys.stdout)
                stats['errors'] += 1
    else:
        args = [a for a in sys.argv[1:] if not a.startswith('--')]
        if not args:
            print('Usage: python3 scrape-raceresult-perrunner.py EVENT_ID [--dry-run] [--limit N]')
            print('       python3 scrape-raceresult-perrunner.py --registry [--dry-run]')
            sys.exit(1)

        event_id = int(args[0])
        process_event(event_id)

    log(f'\n{"="*60}')
    log(f'DONE — {stats["events"]} events, {stats["runners"]} runners, '
        f'{stats["files"]} files, {stats["skipped"]} skipped, {stats["errors"]} errors')


if __name__ == '__main__':
    main()
