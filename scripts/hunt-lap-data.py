#!/usr/bin/env python3
"""
8-hour hunt for fixed-time races with per-lap split data on raceresult.com.

Strategy:
1. Search RREvents API with multiple keywords to find all fixed-time events
2. Check each event for lists with per-lap data ("Lap Details", "Lap Result", etc.)
3. Scrape per-lap data and convert to per-mile splits
4. Also collect checkpoint data as secondary goal
5. Integrate everything into index.json

Usage: python3 hunt-lap-data.py [--dry-run] [--max-hours 8]
"""

import json
import os
import signal
import sys
import time
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta


class FetchTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise FetchTimeout("Request timed out")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
SPLITS_DIR = os.path.join(DATA_DIR, 'splits')
INDEX_PATH = os.path.join(DATA_DIR, 'index.json')
PROGRESS_PATH = os.path.join(DATA_DIR, 'hunt-progress.json')

DRY_RUN = '--dry-run' in sys.argv
MAX_HOURS = 8
for i, arg in enumerate(sys.argv):
    if arg == '--max-hours' and i + 1 < len(sys.argv):
        MAX_HOURS = float(sys.argv[i + 1])

START_TIME = datetime.now()
DEADLINE = START_TIME + timedelta(hours=MAX_HOURS)

stats = {
    'events_discovered': 0,
    'events_checked': 0,
    'events_with_laps': 0,
    'events_with_checkpoints': 0,
    'runners_scraped': 0,
    'lap_files_written': 0,
    'checkpoint_files_written': 0,
    'files_skipped': 0,
    'errors': 0,
    'found_events': [],
}

# Keywords to search for fixed-time events
SEARCH_KEYWORDS = [
    '24 hour', '24-hour', '24h',
    '48 hour', '48-hour', '48h',
    '12 hour', '12-hour', '12h',
    '6 hour', '6-hour', '6h',
    '72 hour',
    '6 day', '6-day',
    'stunden',       # German: hours
    'heures',        # French: hours
    'horas',         # Spanish/Portuguese: hours
    'stundenrennen', # German: hour race
    'stundenlauf',   # German: hour run
    'sri chinmoy',
    'self-transcendence',
    'track ultra',
    'backyard ultra',
    'timed ultra',
    'fixed time',
    'dome ultra',
    'solstice',
    'across the years',
    'fat ox',
    'snowdrop',
    'jackpot ultra',
    'biggest little',
    'beyond limits',
    'endurance run',
    'laufchallenge',
    'ultralauf',
    'dauerlauf',
    'hourly',
    'centurion 24',
    'tooting bec 24',
    'soochow 24',
    'taipei 24',
    'commonwealth 24',
    'coast to kosciuszko',
    'surgeres',
    'ultrapark',
]

# Timer groups known to time fixed-time events
TIMER_GROUPS = [
    4286,    # MCM Timing (Desert Solstice, Snowdrop, Dome)
    # Will discover more through search
]

# Lists that indicate per-lap data
LAP_LIST_KEYWORDS = [
    'lap detail', 'lap data', 'lap result', 'lap information',
    'lap statistics', 'lap time', 'einzelrunde', 'rundenzeiten',
    'rundendaten', 'tours', 'giri', 'vueltas',
]

# Lists that indicate checkpoint/split data
CHECKPOINT_LIST_KEYWORDS = [
    'split time', 'zwischenzeit', 'checkpoint', 'intermediate',
    'passage', 'durchgang',
]

# Distance milestone fields commonly found in checkpoint data
CHECKPOINT_FIELD_PATTERNS = {
    'marathon': (26.2, 'Marathon'),
    'marsplit': (26.2, 'Marathon'),
    '50k': (31.07, '50K'),
    '50ksplit': (31.07, '50K'),
    '50mile': (50, '50 Mile'),
    '50mi': (50, '50 Mile'),
    '100k': (62.14, '100K'),
    '100ksplit': (62.14, '100K'),
    '100mile': (100, '100 Mile'),
    '100mi': (100, '100 Mile'),
    '100msplit': (100, '100 Mile'),
    '100milsplit': (100, '100 Mile'),
    '200k': (124.27, '200K'),
    '200ksplit': (124.27, '200K'),
    '150m': (150, '150 Mile'),
    '150mi': (150, '150 Mile'),
    '150msplit': (150, '150 Mile'),
    '200m': (200, '200 Mile'),
    '200mi': (200, '200 Mile'),
    '200msplit': (200, '200 Mile'),
    '250mi': (250, '250 Mile'),
    '300mi': (300, '300 Mile'),
    '350mi': (350, '350 Mile'),
    '400mi': (400, '400 Mile'),
    '450mi': (450, '450 Mile'),
    '500mi': (500, '500 Mile'),
    '550mi': (550, '550 Mile'),
}

# Time-based checkpoint fields
TIME_CHECKPOINT_PATTERNS = {
    '6h': (6, '6h'),
    '12h': (12, '12h'),
    '24h': (24, '24h'),
    '48h': (48, '48h'),
    '72h': (72, '72h'),
}


LOG_FILE = None

def log(msg):
    elapsed = datetime.now() - START_TIME
    hours = elapsed.total_seconds() / 3600
    line = f'[{datetime.now().strftime("%H:%M:%S")} +{hours:.1f}h] {msg}'
    print(line, flush=True)
    # Also write directly to log file to bypass buffering
    if LOG_FILE:
        LOG_FILE.write(line + '\n')
        LOG_FILE.flush()


def time_remaining():
    return (DEADLINE - datetime.now()).total_seconds()


def fetch_json(url, retries=2):
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    for attempt in range(retries):
        try:
            time.sleep(0.2)
            signal.alarm(15)  # Hard 15s timeout per attempt
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            signal.alarm(0)
            return data
        except (FetchTimeout, Exception):
            signal.alarm(0)
            if attempt == retries - 1:
                signal.signal(signal.SIGALRM, old_handler)
                return None
            time.sleep(1)
    signal.signal(signal.SIGALRM, old_handler)
    return None


def parse_time_to_seconds(time_str):
    if not time_str or time_str in ('-', '', '*', 'DNF', 'DNS', 'DSQ'):
        return 0
    time_str = str(time_str).strip().replace(',', '.')

    # "D.HH:MM:SS" format
    if '.' in time_str and ':' in time_str:
        dot_parts = time_str.split('.')
        if len(dot_parts) >= 2 and ':' in dot_parts[-1]:
            if len(dot_parts[0].split(':')) == 1:
                try:
                    days = int(dot_parts[0])
                    if days < 30:
                        rest = '.'.join(dot_parts[1:])
                        hms = rest.split(':')
                        if len(hms) == 3:
                            return days * 86400 + int(hms[0]) * 3600 + int(hms[1]) * 60 + float(hms[2])
                except ValueError:
                    pass

    # "HH:MM:SS" or "H:MM:SS"
    parts = time_str.split(':')
    if len(parts) == 3:
        try:
            h, m = int(parts[0]), int(parts[1])
            s = float(parts[2].split('.')[0]) if '.' in parts[2] else float(parts[2])
            return h * 3600 + m * 60 + s
        except ValueError:
            return 0
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + float(parts[1])
        except ValueError:
            return 0

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


def classify_event_duration(name, contests):
    """Try to determine if this is a 6h, 12h, 24h, 48h, 72h, or 6d event."""
    name_lower = name.lower()
    for pattern, dur_id in [
        ('6 day', '6d'), ('6-day', '6d'), ('6d ', '6d'), ('six day', '6d'),
        ('72 hour', '72h'), ('72-hour', '72h'), ('72h', '72h'),
        ('48 hour', '48h'), ('48-hour', '48h'), ('48h', '48h'),
        ('24 hour', '24h'), ('24-hour', '24h'), ('24h', '24h'), ('24 stunden', '24h'),
        ('12 hour', '12h'), ('12-hour', '12h'), ('12h', '12h'), ('12 stunden', '12h'),
        ('6 hour', '6h'), ('6-hour', '6h'), ('6h', '6h'), ('6 stunden', '6h'),
    ]:
        if pattern in name_lower:
            return dur_id

    # Check contest names
    for cid, cname in contests.items():
        cname_lower = str(cname).lower() if cname else ''
        for pattern, dur_id in [
            ('6 day', '6d'), ('24 hour', '24h'), ('48 hour', '48h'),
            ('12 hour', '12h'), ('6 hour', '6h'), ('72 hour', '72h'),
            ('24h', '24h'), ('48h', '48h'), ('12h', '12h'), ('6h', '6h'),
        ]:
            if pattern in cname_lower:
                return dur_id

    return None


def get_duration_seconds(distance_id):
    durations = {
        '6h': 21600, '12h': 43200, '24h': 86400,
        '48h': 172800, '72h': 259200, '6d': 518400,
    }
    return durations.get(distance_id, 0)


def save_progress():
    """Save progress for resume capability."""
    progress = {
        'timestamp': datetime.now().isoformat(),
        'stats': stats,
        'checked_events': list(checked_events),
    }
    try:
        with open(PROGRESS_PATH, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception:
        pass


def load_progress():
    """Load previous progress if resuming."""
    try:
        with open(PROGRESS_PATH) as f:
            return json.load(f)
    except Exception:
        return None


# Track which events we've already checked
checked_events = set()
existing_split_files = set()


def discover_events():
    """Phase 1: Discover all fixed-time events on raceresult.com."""
    log('=== Phase 1: Discovering fixed-time events ===')
    all_events = {}  # event_id -> (name, date)

    for keyword in SEARCH_KEYWORDS:
        if time_remaining() < 60:
            log('Time limit approaching, stopping discovery')
            break

        encoded = urllib.parse.quote(keyword)
        url = f'https://my.raceresult.com/RREvents/list?filter={encoded}&searchMode=2&lang=en'
        data = fetch_json(url)

        if not data:
            continue

        new_count = 0
        # API returns [{"Events": [[id,...], ...]}, ...] or [[id,...], ...]
        events_list = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'Events' in item:
                    events_list.extend(item['Events'])
                elif isinstance(item, list):
                    events_list.append(item)
        elif isinstance(data, dict):
            events_list = data.get('Events', data.get('events', []))

        for event in events_list:
            try:
                eid = event[0]
                name = event[2] if len(event) > 2 else ''
                date = event[3] if len(event) > 3 else ''
            except (KeyError, IndexError, TypeError):
                continue
            if eid not in all_events:
                year = int(date[:4]) if date and len(date) >= 4 else 0

                # Skip very old events (unlikely to have data)
                if year > 0 and year < 2015:
                    continue
                # Skip future events
                if year > 2026:
                    continue

                all_events[eid] = (name, date, year)
                new_count += 1

        if new_count > 0:
            log(f'  "{keyword}": {len(events_list)} results, {new_count} new (total: {len(all_events)})')

    # Also add timer group events
    for group_id in TIMER_GROUPS:
        url = f'https://my.raceresult.com/RREvents/list?group={group_id}&lang=en'
        data = fetch_json(url)
        if data:
            events_list = []
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'Events' in item:
                        events_list.extend(item['Events'])
                    elif isinstance(item, list):
                        events_list.append(item)
            elif isinstance(data, dict):
                events_list = data.get('Events', data.get('events', []))
            for event in events_list:
                try:
                    eid = event[0]
                    name = event[2] if len(event) > 2 else ''
                except (KeyError, IndexError, TypeError):
                    continue
                if eid not in all_events:
                    try:
                        date = event[3] if len(event) > 3 else ''
                    except (KeyError, IndexError, TypeError):
                        date = ''
                    year = int(date[:4]) if date and len(date) >= 4 else 0
                    if 2015 <= year <= 2026:
                        all_events[eid] = (name, date, year)

    stats['events_discovered'] = len(all_events)
    log(f'Discovered {len(all_events)} unique events to check')
    return all_events


def check_event_for_lap_data(eid, name, year):
    """Check a single event for per-lap or checkpoint data."""
    if eid in checked_events:
        return None

    checked_events.add(eid)
    stats['events_checked'] += 1

    if stats['events_checked'] % 10 == 1 or stats['events_checked'] <= 5:
        log(f'  [{stats["events_checked"]}/{len(checked_events)}] Checking {eid}: {name} ({year})')

    config = fetch_json(f'https://my.raceresult.com/{eid}/results/config?lang=en')
    if not config:
        return None

    key = config.get('key')
    server = config.get('server', 'my.raceresult.com')
    contests = config.get('contests', {})
    tab_config = config.get('TabConfig', {})
    lists = tab_config.get('Lists', [])

    if not lists:
        return None

    list_names = [l.get('Name', '') for l in lists]

    # Check for per-lap lists
    lap_lists = []
    checkpoint_lists = []
    promising_lists = []

    for l in lists:
        lname = l.get('Name', '').lower()
        if any(kw in lname for kw in LAP_LIST_KEYWORDS):
            lap_lists.append(l)
        elif any(kw in lname for kw in CHECKPOINT_LIST_KEYWORDS):
            checkpoint_lists.append(l)
        elif any(pk in lname for pk in ['result', 'split', 'ergebnis', 'classement',
                                         'ranking', 'individual', 'detail']):
            promising_lists.append(l)

    # Quick exit: no interesting lists at all
    if not lap_lists and not checkpoint_lists and not promising_lists:
        return None

    result = {
        'event_id': eid,
        'name': name,
        'year': year,
        'key': key,
        'server': server,
        'contests': contests,
        'all_lists': list_names,
        'lap_lists': [l['Name'] for l in lap_lists],
        'checkpoint_lists': [l['Name'] for l in checkpoint_lists],
        'has_laps': False,
        'has_checkpoints': False,
    }

    # Try lap lists first (highest value)
    for ll in lap_lists:
        for contest_id in list(contests.keys())[:3]:  # First 3 contests max
            params = urllib.parse.urlencode({
                'key': key, 'listname': ll['Name'],
                'contest': contest_id, 'r': 'all', 'l': '0'
            })
            url = f'https://{server}/{eid}/results/list?{params}'
            data = fetch_json(url)
            if not data:
                continue

            entries = data.get('data', {})
            fields = data.get('DataFields', [])
            count = 0
            if isinstance(entries, dict):
                count = sum(len(v) if isinstance(v, list) else 1 for v in entries.values())
            elif isinstance(entries, list):
                count = len(entries)

            if count > 0:
                result['has_laps'] = True
                result['lap_data'] = {
                    'list_name': ll['Name'],
                    'contest': contest_id,
                    'count': count,
                    'fields': fields[:15],
                }
                log(f'  *** LAP DATA: {eid} {name} — {ll["Name"]} ({count} entries)')
                stats['events_with_laps'] += 1
                return result

    # Try checkpoint lists
    for cl in checkpoint_lists:
        for contest_id in list(contests.keys())[:3]:  # First 3 contests max
            params = urllib.parse.urlencode({
                'key': key, 'listname': cl['Name'],
                'contest': contest_id, 'r': 'all', 'l': '0'
            })
            url = f'https://{server}/{eid}/results/list?{params}'
            data = fetch_json(url)
            if not data:
                continue

            entries = data.get('data', {})
            fields = data.get('DataFields', [])
            count = 0
            if isinstance(entries, dict):
                count = sum(len(v) if isinstance(v, list) else 1 for v in entries.values())
            elif isinstance(entries, list):
                count = len(entries)

            if count > 0:
                # Check if fields contain recognizable checkpoint names
                fields_lower = [f.lower() for f in fields]
                has_distance_fields = any(
                    any(pat in fl for pat in CHECKPOINT_FIELD_PATTERNS)
                    for fl in fields_lower
                )
                has_time_fields = any(
                    any(pat in fl for pat in TIME_CHECKPOINT_PATTERNS)
                    for fl in fields_lower
                )

                if has_distance_fields or has_time_fields:
                    result['has_checkpoints'] = True
                    result['checkpoint_data'] = {
                        'list_name': cl['Name'],
                        'contest': contest_id,
                        'count': count,
                        'fields': fields[:15],
                    }
                    log(f'  + CHECKPOINT: {eid} {name} — {cl["Name"]} ({count} entries, fields: {fields[:8]})')
                    stats['events_with_checkpoints'] += 1
                    return result

    # Quick scan: check remaining lists for promising field names
    # Only fetch data from lists with names suggesting results/splits
    promising_keywords = ['result', 'split', 'ergebnis', 'classement',
                          'ranking', 'individual', 'detail']
    for l in lists:
        lname = l.get('Name', '')
        lname_lower = lname.lower()
        if any(kw in lname_lower for kw in LAP_LIST_KEYWORDS + CHECKPOINT_LIST_KEYWORDS):
            continue
        if not any(pk in lname_lower for pk in promising_keywords):
            continue

        for contest_id in list(contests.keys())[:1]:  # Only first contest
            params = urllib.parse.urlencode({
                'key': key, 'listname': lname,
                'contest': contest_id, 'r': 'all', 'l': '0'
            })
            url = f'https://{server}/{eid}/results/list?{params}'
            data = fetch_json(url)
            if not data:
                continue

            fields = data.get('DataFields', [])
            fields_lower = [f.lower() for f in fields]

            # Check for checkpoint-like fields
            has_distance_fields = any(
                any(pat in fl for pat in CHECKPOINT_FIELD_PATTERNS)
                for fl in fields_lower
            )
            if has_distance_fields:
                entries = data.get('data', {})
                count = 0
                if isinstance(entries, dict):
                    count = sum(len(v) if isinstance(v, list) else 1 for v in entries.values())
                elif isinstance(entries, list):
                    count = len(entries)

                if count > 0:
                    result['has_checkpoints'] = True
                    result['checkpoint_data'] = {
                        'list_name': lname,
                        'contest': contest_id,
                        'count': count,
                        'fields': fields[:15],
                    }
                    log(f'  + CHECKPOINT (discovered): {eid} {name} — {lname} ({count} entries)')
                    stats['events_with_checkpoints'] += 1
                    return result
            break  # Only check first promising list

    return None


def scrape_lap_data(event_info):
    """Scrape per-lap data from an event and convert to per-mile splits."""
    eid = event_info['event_id']
    name = event_info['name']
    year = event_info['year']
    lap_info = event_info.get('lap_data', {})
    key = event_info['key']
    server = event_info['server']
    contests = event_info['contests']

    list_name = lap_info['list_name']
    contest_id = lap_info.get('contest', list(contests.keys())[0])

    distance_id = classify_event_duration(name, contests)
    if not distance_id:
        log(f'  Cannot determine duration for {name}, skipping')
        return 0

    duration_sec = get_duration_seconds(distance_id)

    params = urllib.parse.urlencode({
        'key': key, 'listname': list_name,
        'contest': contest_id, 'r': 'all', 'l': '0'
    })
    url = f'https://{server}/{eid}/results/list?{params}'
    data = fetch_json(url)

    if not data:
        return 0

    fields = data.get('DataFields', [])
    entries = data.get('data', {})

    # Flatten entries
    flat_entries = []
    if isinstance(entries, dict):
        for v in entries.values():
            if isinstance(v, list):
                if v and isinstance(v[0], list):
                    flat_entries.extend(v)
                else:
                    flat_entries.append(v)
            else:
                flat_entries.append(v)
    elif isinstance(entries, list):
        flat_entries = entries

    field_idx = {f: i for i, f in enumerate(fields)}

    # Find name field
    name_idx = None
    for candidate in ['DisplayName', 'NAME', 'Name', 'FULLNAME']:
        if candidate in field_idx:
            name_idx = field_idx[candidate]
            break
    if name_idx is None:
        name_idx = min(2, len(fields) - 1)

    # Find gender field
    gender_idx = field_idx.get('GenderMF', field_idx.get('GENDER', field_idx.get('Sex', None)))

    # Find lap time fields (numbered fields like "Lap 1", "Lap 2", etc.)
    lap_fields = []
    for i, f in enumerate(fields):
        f_lower = f.lower()
        if re.match(r'^(lap|runde|round|tour)\s*\d+', f_lower):
            lap_fields.append((i, f))
        elif re.match(r'^#\d+$', f):
            lap_fields.append((i, f))
        elif re.match(r'^\d+$', f_lower) and int(f) <= 1000:
            lap_fields.append((i, f))

    if not lap_fields:
        # Try clock time pattern — all time-like fields after name
        for i, f in enumerate(fields):
            if i <= (name_idx or 2):
                continue
            # Check if field contains time-like data by examining first entry
            if flat_entries:
                sample = flat_entries[0]
                if i < len(sample):
                    val = str(sample[i])
                    if ':' in val and len(val) >= 5:
                        lap_fields.append((i, f))
        if len(lap_fields) < 5:
            lap_fields = []

    if not lap_fields:
        log(f'  No lap fields found in {name} ({list_name})')
        return 0

    log(f'  Found {len(lap_fields)} lap fields in {name}')

    # We need to know the loop distance to convert laps to miles
    # Try to infer from event data or use common values
    # Common loop distances: 400m, 443m (Dome), 500m, 1000m, 1609m (1mi)
    # We'll try to detect from the data

    files_written = 0
    for entry in flat_entries:
        if not isinstance(entry, (list, tuple)) or len(entry) < 5:
            continue

        runner_name = entry[name_idx] if name_idx < len(entry) else None
        if not runner_name or not isinstance(runner_name, str):
            continue
        runner_name = runner_name.strip()
        if not runner_name:
            continue

        gender = None
        if gender_idx is not None and gender_idx < len(entry):
            g = str(entry[gender_idx]).strip().upper()
            if g in ('M', 'F', 'W'):
                gender = 'M' if g == 'M' else 'F'

        # Extract lap times
        lap_times = []
        for lap_idx, lap_name in lap_fields:
            if lap_idx >= len(entry):
                break
            val = entry[lap_idx]
            t = parse_time_to_seconds(val)
            if t > 0:
                lap_times.append(t)
            elif lap_times:
                # Gap in data — stop here
                break

        if len(lap_times) < 5:
            continue

        # Determine if times are cumulative or split times
        is_cumulative = True
        for i in range(1, min(10, len(lap_times))):
            if lap_times[i] < lap_times[i-1]:
                is_cumulative = False
                break

        if is_cumulative:
            # Convert cumulative to split times
            split_times = [lap_times[0]]
            for i in range(1, len(lap_times)):
                split_times.append(lap_times[i] - lap_times[i-1])
            cum_times = lap_times
        else:
            split_times = lap_times
            cum_times = []
            running = 0
            for t in split_times:
                running += t
                cum_times.append(running)

        # Estimate loop distance from total laps and expected distance
        # For a 24h at ~150mi with 400m loop: ~600 laps
        # For a 24h at ~150mi with 1mi loop: ~150 laps
        total_time = cum_times[-1]
        num_laps = len(cum_times)

        # Skip if total time is unreasonable
        if total_time < 3600 or total_time > duration_sec * 1.1:
            continue

        # Try common loop distances and see which gives reasonable total distance
        loop_candidates_m = [400, 443, 443.5, 500, 804.672, 1000, 1609.344]
        best_loop = None
        best_distance_mi = 0

        for loop_m in loop_candidates_m:
            total_mi = num_laps * loop_m / 1609.344
            # Check if total distance is reasonable for the duration
            if distance_id == '24h' and 30 < total_mi < 220:
                if best_loop is None or abs(total_mi - 120) < abs(best_distance_mi - 120):
                    best_loop = loop_m
                    best_distance_mi = total_mi
            elif distance_id == '48h' and 50 < total_mi < 350:
                if best_loop is None:
                    best_loop = loop_m
                    best_distance_mi = total_mi
            elif distance_id == '12h' and 20 < total_mi < 150:
                if best_loop is None:
                    best_loop = loop_m
                    best_distance_mi = total_mi
            elif distance_id == '6h' and 10 < total_mi < 80:
                if best_loop is None:
                    best_loop = loop_m
                    best_distance_mi = total_mi
            elif distance_id == '6d' and 100 < total_mi < 700:
                if best_loop is None:
                    best_loop = loop_m
                    best_distance_mi = total_mi
            elif distance_id == '72h' and 80 < total_mi < 400:
                if best_loop is None:
                    best_loop = loop_m
                    best_distance_mi = total_mi

        if not best_loop:
            continue

        loop_mi = best_loop / 1609.344
        total_mi = num_laps * loop_mi

        # Build per-mile splits by interpolating from per-lap data
        miles = []
        cum_lap_time = 0
        cum_lap_dist = 0
        prev_mile_time = 0

        for mile_num in range(1, int(total_mi) + 1):
            target_dist = mile_num

            # Find which lap this mile falls in
            while cum_lap_dist + loop_mi < target_dist and len(split_times) > int(cum_lap_dist / loop_mi):
                lap_idx = int(cum_lap_dist / loop_mi)
                if lap_idx >= len(split_times):
                    break
                cum_lap_time += split_times[lap_idx]
                cum_lap_dist += loop_mi

            # Interpolate within the current lap
            if cum_lap_dist / loop_mi >= len(split_times):
                break

            current_lap_idx = int(cum_lap_dist / loop_mi)
            if current_lap_idx >= len(split_times):
                break

            remaining_in_lap = target_dist - cum_lap_dist
            fraction = remaining_in_lap / loop_mi if loop_mi > 0 else 0
            interpolated_time = cum_lap_time + fraction * split_times[current_lap_idx]

            split_sec = interpolated_time - prev_mile_time

            if split_sec < 120 or split_sec > 7200:
                continue

            miles.append({
                'mile': mile_num,
                'split_sec': round(split_sec, 1),
                'moving_sec': round(split_sec, 1),
                'cum_sec': round(interpolated_time, 1),
            })
            prev_mile_time = interpolated_time

        if len(miles) < 5:
            continue

        # Write split file
        race_slug = slugify(name)
        runner_slug = slugify(runner_name)
        filename = f'{race_slug}-{year}-{runner_slug}-raceresult.json'
        filepath = os.path.join(SPLITS_DIR, filename)

        if filename in existing_split_files or os.path.exists(filepath):
            stats['files_skipped'] += 1
            continue

        duration_str = f'{int(total_time // 3600)}:{int((total_time % 3600) // 60):02d}:{int(total_time % 60):02d}'

        split_data = {
            'runner': runner_name,
            'race': name,
            'year': year,
            'distance_mi': round(total_mi, 2),
            'duration_sec': round(total_time),
            'duration': duration_str,
            'data_type': 'miles',
            'source': f'my.raceresult.com event {eid}',
            'distance_id': distance_id,
            'loop_meters': best_loop,
            'total_laps': num_laps,
            'miles': miles,
        }
        if gender:
            split_data['gender'] = gender

        if DRY_RUN:
            log(f'    [DRY] {filename} ({runner_name}, {len(miles)} miles, {total_mi:.1f}mi)')
        else:
            with open(filepath, 'w') as f:
                json.dump(split_data, f, indent=2)
                f.write('\n')
            existing_split_files.add(filename)

        files_written += 1
        stats['lap_files_written'] += 1
        stats['runners_scraped'] += 1

    return files_written


def scrape_checkpoint_data(event_info):
    """Scrape checkpoint/split data from an event."""
    eid = event_info['event_id']
    name = event_info['name']
    year = event_info['year']
    cp_info = event_info.get('checkpoint_data', {})
    key = event_info['key']
    server = event_info['server']
    contests = event_info['contests']

    list_name = cp_info['list_name']
    contest_id = cp_info.get('contest', list(contests.keys())[0])

    distance_id = classify_event_duration(name, contests)
    if not distance_id:
        return 0

    duration_sec = get_duration_seconds(distance_id)

    params = urllib.parse.urlencode({
        'key': key, 'listname': list_name,
        'contest': contest_id, 'r': 'all', 'l': '0'
    })
    url = f'https://{server}/{eid}/results/list?{params}'
    data = fetch_json(url)

    if not data:
        return 0

    fields = data.get('DataFields', [])
    entries = data.get('data', {})

    # Flatten entries
    flat_entries = []
    if isinstance(entries, dict):
        for v in entries.values():
            if isinstance(v, list):
                if v and isinstance(v[0], list):
                    flat_entries.extend(v)
                else:
                    flat_entries.append(v)
    elif isinstance(entries, list):
        flat_entries = entries

    field_idx = {f: i for i, f in enumerate(fields)}

    # Find name field
    name_idx = None
    for candidate in ['DisplayName', 'NAME', 'Name', 'FULLNAME']:
        if candidate in field_idx:
            name_idx = field_idx[candidate]
            break
    if name_idx is None:
        name_idx = min(2, len(fields) - 1)

    gender_idx = field_idx.get('GenderMF', field_idx.get('GENDER', field_idx.get('Sex', None)))

    # Map fields to checkpoint definitions
    checkpoint_defs = []
    for i, f in enumerate(fields):
        f_lower = f.lower().replace(' ', '').replace('_', '')
        for pattern, (dist_mi, label) in CHECKPOINT_FIELD_PATTERNS.items():
            if pattern in f_lower:
                checkpoint_defs.append((i, dist_mi, label, f))
                break

    if len(checkpoint_defs) < 2:
        return 0

    # Sort by distance
    checkpoint_defs.sort(key=lambda x: x[1])

    files_written = 0
    for entry in flat_entries:
        if not isinstance(entry, (list, tuple)) or len(entry) < 5:
            continue

        runner_name = entry[name_idx] if name_idx < len(entry) else None
        if not runner_name or not isinstance(runner_name, str):
            continue
        runner_name = runner_name.strip()
        if not runner_name:
            continue

        gender = None
        if gender_idx is not None and gender_idx < len(entry):
            g = str(entry[gender_idx]).strip().upper()
            if g in ('M', 'F', 'W'):
                gender = 'M' if g == 'M' else 'F'

        checkpoints = []
        last_time = 0
        for cp_field_idx, dist_mi, label, field_name in checkpoint_defs:
            if cp_field_idx >= len(entry):
                continue
            val = entry[cp_field_idx]
            t = parse_time_to_seconds(val)
            if t <= 0 or t <= last_time:
                continue
            checkpoints.append({
                'label': label,
                'elapsed_sec': round(t),
                'distance_mi': dist_mi,
            })
            last_time = t

        if len(checkpoints) < 2:
            continue

        total_mi = checkpoints[-1]['distance_mi']
        total_time = checkpoints[-1]['elapsed_sec']

        if total_mi < 20:
            continue

        race_slug = slugify(name)
        runner_slug = slugify(runner_name)
        filename = f'{race_slug}-{year}-{runner_slug}-raceresult.json'
        filepath = os.path.join(SPLITS_DIR, filename)

        if filename in existing_split_files or os.path.exists(filepath):
            stats['files_skipped'] += 1
            continue

        duration_str = f'{int(total_time // 3600)}:{int((total_time % 3600) // 60):02d}:{int(total_time % 60):02d}'

        split_data = {
            'runner': runner_name,
            'race': name,
            'year': year,
            'distance_mi': round(total_mi, 2),
            'duration_sec': round(total_time),
            'duration': duration_str,
            'data_type': 'checkpoints',
            'source': f'my.raceresult.com event {eid}',
            'distance_id': distance_id,
            'checkpoints': checkpoints,
        }
        if gender:
            split_data['gender'] = gender

        if DRY_RUN:
            log(f'    [DRY] {filename} ({runner_name}, {len(checkpoints)} checkpoints, {total_mi:.1f}mi)')
        else:
            with open(filepath, 'w') as f:
                json.dump(split_data, f, indent=2)
                f.write('\n')
            existing_split_files.add(filename)

        files_written += 1
        stats['checkpoint_files_written'] += 1
        stats['runners_scraped'] += 1

    return files_written


def integrate_into_index():
    """Integrate all new raceresult split files into index.json."""
    log('=== Phase 3: Integrating into index.json ===')

    if DRY_RUN:
        log('  Skipping in dry-run mode')
        return

    with open(INDEX_PATH) as f:
        index = json.load(f)

    existing_files = set(p['splits_file'] for p in index['performances'])
    existing_races = {r['id']: r for r in index['races']}
    existing_distances = {d['id'] for d in index['distances']}

    new_files = []
    for fname in sorted(os.listdir(SPLITS_DIR)):
        if not fname.endswith('-raceresult.json'):
            continue
        if fname in existing_files:
            continue
        new_files.append(fname)

    if not new_files:
        log('  No new files to integrate')
        return

    log(f'  Found {len(new_files)} new split files')

    dist_labels = {
        '6h': '6 Hours', '12h': '12 Hours', '24h': '24 Hours',
        '48h': '48 Hours', '72h': '72 Hours', '6d': '6 Days',
        '10d': '10 Days', '100mi': '100 Miles', '100k': '100 Kilometers',
    }

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
        gender = data.get('gender')

        if not distance_mi or not duration_sec or not distance_id:
            continue

        if distance_id not in existing_distances:
            index['distances'].append({
                'id': distance_id,
                'label': dist_labels.get(distance_id, distance_id),
                'type': 'timed' if 'h' in distance_id or 'd' in distance_id else 'distance',
            })
            existing_distances.add(distance_id)

        race_slug = slugify(race_name)
        if race_slug not in existing_races:
            race_entry = {'id': race_slug, 'name': race_name, 'location': 'Unknown'}
            index['races'].append(race_entry)
            existing_races[race_slug] = race_entry

        runner_slug = slugify(runner)
        perf_id = f'{race_slug}-{year}-{runner_slug}'
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
            'race_id': race_slug,
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
        log(f'  Added {added} performances to index.json (total: {len(index["performances"])})')


def main():
    global existing_split_files, LOG_FILE

    # Open direct log file (bypasses nohup buffering)
    LOG_FILE = open(os.path.join(DATA_DIR, 'hunt-log.txt'), 'a')

    log(f'=== 8-Hour Lap Data Hunt ===')
    log(f'Start: {START_TIME.strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'Deadline: {DEADLINE.strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'Dry run: {DRY_RUN}')

    os.makedirs(SPLITS_DIR, exist_ok=True)

    # Load existing files to avoid duplicates
    existing_split_files = set(os.listdir(SPLITS_DIR))
    log(f'Existing split files: {len(existing_split_files)}')

    # Load previous progress
    prev = load_progress()
    if prev:
        checked_events.update(prev.get('checked_events', []))
        log(f'Resuming: {len(checked_events)} events previously checked')

    # Phase 1: Discover events
    all_events = discover_events()

    # Phase 2: Check each event for lap/checkpoint data and scrape
    log(f'\n=== Phase 2: Checking {len(all_events)} events for lap data ===')

    # Sort by year (newest first) — more likely to have data
    sorted_events = sorted(all_events.items(), key=lambda x: x[1][2], reverse=True)

    events_with_data = []
    batch_count = 0

    for eid, (name, date, year) in sorted_events:
        if time_remaining() < 120:  # 2 min buffer for integration
            log('Time limit approaching, stopping scan')
            break

        if eid in checked_events:
            continue

        try:
            result = check_event_for_lap_data(eid, name, year)
        except Exception as e:
            log(f'  ERROR checking {eid} ({name}): {e}')
            result = None
        if result:
            events_with_data.append(result)
            stats['found_events'].append({
                'event_id': eid, 'name': name, 'year': year,
                'has_laps': result.get('has_laps', False),
                'has_checkpoints': result.get('has_checkpoints', False),
            })

            # Immediately scrape if has data
            try:
                if result.get('has_laps') and result.get('lap_data'):
                    written = scrape_lap_data(result)
                    log(f'    Scraped {written} per-mile split files')
                elif result.get('has_checkpoints') and result.get('checkpoint_data'):
                    written = scrape_checkpoint_data(result)
                    log(f'    Scraped {written} checkpoint files')
            except Exception as e:
                log(f'    ERROR scraping {eid}: {e}')

        batch_count += 1
        if batch_count % 100 == 0:
            log(f'  Progress: {stats["events_checked"]} checked, {stats["events_with_laps"]} with laps, '
                f'{stats["events_with_checkpoints"]} with checkpoints, '
                f'{stats["lap_files_written"]} lap files, {stats["checkpoint_files_written"]} cp files')
            save_progress()

    # Phase 3: Integrate
    if stats['lap_files_written'] + stats['checkpoint_files_written'] > 0:
        integrate_into_index()

    # Final report
    elapsed = datetime.now() - START_TIME
    log(f'\n{"="*60}')
    log(f'HUNT COMPLETE — {elapsed}')
    log(f'  Events discovered: {stats["events_discovered"]}')
    log(f'  Events checked: {stats["events_checked"]}')
    log(f'  Events with per-lap data: {stats["events_with_laps"]}')
    log(f'  Events with checkpoint data: {stats["events_with_checkpoints"]}')
    log(f'  Per-mile split files written: {stats["lap_files_written"]}')
    log(f'  Checkpoint files written: {stats["checkpoint_files_written"]}')
    log(f'  Files skipped (existing): {stats["files_skipped"]}')
    log(f'  Runners scraped: {stats["runners_scraped"]}')
    log(f'  Errors: {stats["errors"]}')

    if stats['found_events']:
        log(f'\nEvents with data found:')
        for evt in stats['found_events']:
            dtype = 'LAPS' if evt['has_laps'] else 'CHECKPOINTS'
            log(f'  [{dtype}] {evt["event_id"]}: {evt["name"]} ({evt["year"]})')

    save_progress()


if __name__ == '__main__':
    main()
