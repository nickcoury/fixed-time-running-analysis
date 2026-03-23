#!/usr/bin/env python3
"""
Scrape per-lap timing data from raceresult.com events.

Handles the row-per-lap format where each runner has multiple rows:
  [BIB, ID, lap_number, cumulative_time, split_time, ...]

Stores raw lap data at native fidelity — no per-mile extrapolation.

Usage:
  python3 scrape-raceresult-laps.py EVENT_ID [--dry-run] [--contest CONTEST_ID]
  python3 scrape-raceresult-laps.py --batch  # Process all pending events from registry
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
SPLITS_DIR = os.path.join(DATA_DIR, 'splits')
REGISTRY_PATH = os.path.join(DATA_DIR, 'race-registry.json')

DRY_RUN = '--dry-run' in sys.argv


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


def fetch_json(url, retries=2):
    for attempt in range(retries):
        try:
            time.sleep(0.3)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(1)
    return None


def parse_time_to_seconds(time_str):
    """Parse various time formats to seconds."""
    if not time_str or str(time_str).strip() in ('', '-', '*', 'DNF', 'DNS', 'DSQ'):
        return 0
    s = str(time_str).strip().replace(',', '.')

    # "H:MM:SS.xx" or "M:SS.xx" or "MM:SS.xx"
    parts = s.split(':')
    try:
        if len(parts) == 3:
            h, m, sec = parts
            return int(h) * 3600 + int(m) * 60 + float(sec)
        elif len(parts) == 2:
            m, sec = parts
            return int(m) * 60 + float(sec)
        elif len(parts) == 1:
            return float(s)
    except (ValueError, TypeError):
        return 0
    return 0


def get_event_config(event_id):
    """Fetch event configuration from raceresult."""
    config = fetch_json(f'https://my.raceresult.com/{event_id}/results/config?lang=en')
    if not config:
        return None
    return {
        'key': config.get('key', ''),
        'server': config.get('server', 'my.raceresult.com'),
        'contests': config.get('contests', {}),
        'lists': config.get('TabConfig', {}).get('Lists', []),
    }


def find_lap_detail_lists(config):
    """Find lists that contain per-lap detail data (row-per-lap format)."""
    results = []
    seen = set()
    for l in config['lists']:
        name = l.get('Name', '')
        contest = l.get('Contest', '0')
        key = (name, contest)
        if key in seen:
            continue
        seen.add(key)
        name_lower = name.lower()
        # "Lap Details" lists have row-per-lap format
        # "Lap Result List" is typically columnar summary — skip
        if 'lap detail' in name_lower or 'rundenzeiten' in name_lower:
            results.append({'name': name, 'contest': contest})
    return results


def find_overall_results_list(config):
    """Find the overall results list to get total distance per runner."""
    for l in config['lists']:
        name = l.get('Name', '').lower()
        if 'overall' in name or 'ergebnis' in name or 'classement' in name:
            return l.get('Name'), l.get('Contest', '0')
    return None, None


def fetch_lap_data(config, list_name, contest_id, event_id):
    """Fetch the lap detail data from a specific list."""
    params = urllib.parse.urlencode({
        'key': config['key'],
        'listname': list_name,
        'contest': contest_id,
        'r': 'all',
        'l': '0',
    })
    url = f'https://{config["server"]}/{event_id}/results/list?{params}'
    return fetch_json(url)


def detect_row_per_lap_format(fields):
    """Check if the data uses row-per-lap format (template fields like {n})."""
    for f in fields:
        if '{n}' in f or 'Start_Lap' in f:
            return True
    return False


def find_time_field_indices(fields):
    """Find cumulative and split time field indices in row-per-lap data.

    Known field patterns:
    - IKS/Greece: [Start_Lap.Read{n}Text] (cum), [Start_Lap.Lap{n}Text] (split)
    - Sri Chinmoy: [Split{n}] (cum), [Lap{n}] (split)
    - RODOPI: [Measurement{n}] (cum), [Hour{n}] (running time), [RestTime{n}] (rest)
    - NZ Backyard: [Hour{n}] (running time), [RestTime{n}] (rest) — no cumulative

    Returns (cum_idx, split_idx, rest_idx). rest_idx is set for backyard events
    where cumulative must be computed from running + rest times.
    """
    cum_idx = None
    split_idx = None
    rest_idx = None
    for i, f in enumerate(fields):
        fl = f.lower()
        # Cumulative time patterns
        if 'read' in fl and 'text' in fl:
            cum_idx = i
        elif f == '[Start_Lap.Read{n}Text]':
            cum_idx = i
        elif f == '[Split{n}]':
            cum_idx = i
        elif f == '[Measurement{n}]':
            cum_idx = i
        # Split/lap time patterns
        elif 'lap' in fl and 'text' in fl:
            split_idx = i
        elif f == '[Start_Lap.Lap{n}Text]':
            split_idx = i
        elif f == '[Lap{n}]':
            split_idx = i
        elif f == '[Hour{n}]':
            split_idx = i
        # Rest time (backyard ultras)
        elif f == '[RestTime{n}]':
            rest_idx = i
    return cum_idx, split_idx, rest_idx


def parse_runner_key(key):
    """Parse runner info from the data dict key.
    Format: '#rank_BIB///Name///N Laps' or '#rank_Gender///Name///...'
    """
    # Remove leading #
    key = key.lstrip('#')
    parts = key.split('///')
    if len(parts) >= 2:
        name = parts[1].strip()
        # Extract lap count from last part if present
        lap_count = None
        if len(parts) >= 3:
            m = re.search(r'(\d+)\s*Lap', parts[2])
            if m:
                lap_count = int(m.group(1))
        return name, lap_count
    return key, None


def validate_laps(laps, race_duration_sec=None):
    """Sanity check raw lap data. Returns (valid, issues)."""
    issues = []

    if len(laps) < 2:
        issues.append('fewer than 2 laps')
        return False, issues

    # Check cumulative times are monotonically increasing
    for i in range(1, len(laps)):
        if laps[i]['cum_sec'] <= laps[i-1]['cum_sec']:
            issues.append(f'non-monotonic cumulative time at lap {laps[i]["lap"]}: '
                         f'{laps[i]["cum_sec"]:.1f} <= {laps[i-1]["cum_sec"]:.1f}')

    # Check split times are positive
    for lap in laps:
        if lap['split_sec'] <= 0:
            issues.append(f'non-positive split at lap {lap["lap"]}: {lap["split_sec"]:.1f}s')

    # Verify split = diff of cumulative (within 1s tolerance)
    for i in range(1, len(laps)):
        expected_split = laps[i]['cum_sec'] - laps[i-1]['cum_sec']
        actual_split = laps[i]['split_sec']
        if abs(expected_split - actual_split) > 1.0:
            issues.append(f'split/cumulative mismatch at lap {laps[i]["lap"]}: '
                         f'split={actual_split:.1f}s, expected={expected_split:.1f}s')

    # Check total time is reasonable
    total_time = laps[-1]['cum_sec']
    if total_time < 60:
        issues.append(f'total time too short: {total_time:.0f}s')
    if race_duration_sec and total_time > race_duration_sec * 1.05:
        issues.append(f'total time {total_time:.0f}s exceeds race duration {race_duration_sec}s')

    # Check for unreasonably fast or slow laps
    splits = [lap['split_sec'] for lap in laps]
    median_split = sorted(splits)[len(splits) // 2]
    for lap in laps:
        if lap['split_sec'] < median_split * 0.2 and lap['split_sec'] < 30:
            issues.append(f'suspiciously fast lap {lap["lap"]}: {lap["split_sec"]:.1f}s '
                         f'(median: {median_split:.1f}s)')
        if lap['split_sec'] > median_split * 20:
            issues.append(f'suspiciously slow lap {lap["lap"]}: {lap["split_sec"]:.1f}s '
                         f'(median: {median_split:.1f}s)')

    has_critical = any('non-monotonic' in i or 'non-positive' in i or 'too short' in i
                       for i in issues)
    return not has_critical, issues


def get_duration_seconds(distance_id):
    """Convert distance_id to race duration in seconds."""
    durations = {
        '6h': 21600, '12h': 43200, '24h': 86400, '48h': 172800,
        '72h': 259200, '6d': 518400, '36h': 129600, '55h': 198000,
    }
    return durations.get(distance_id)


def classify_distance(name, contests):
    """Try to classify the event's fixed-time distance from name and contest info."""
    text = (name + ' ' + ' '.join(str(v) for v in contests.values())).lower()

    patterns = [
        (r'6[- ]?day|6d\b|144[- ]?h', '6d'),
        (r'72[- ]?h', '72h'),
        (r'55[- ]?h', '55h'),
        (r'48[- ]?h', '48h'),
        (r'36[- ]?h', '36h'),
        (r'24[- ]?h|24\s*hour', '24h'),
        (r'12[- ]?h|12\s*hour', '12h'),
        (r'6[- ]?h|6\s*hour', '6h'),
    ]
    for pattern, dist_id in patterns:
        if re.search(pattern, text):
            return dist_id
    return None


def slugify(text):
    """Convert text to filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].strip('-')


def scrape_event(event_id, contest_filter=None):
    """Scrape per-lap data from a raceresult event."""
    log(f'Fetching config for event {event_id}...')
    config = get_event_config(event_id)
    if not config:
        log(f'  Failed to fetch config')
        return 0, {}

    contests = config['contests']
    log(f'  Contests: {json.dumps(contests)}')

    lap_lists = find_lap_detail_lists(config)
    if not lap_lists:
        log(f'  No lap detail lists found')
        return 0, {}

    log(f'  Lap detail lists: {[l["name"] for l in lap_lists]}')

    os.makedirs(SPLITS_DIR, exist_ok=True)
    existing_files = set(os.listdir(SPLITS_DIR))
    total_written = 0
    event_meta = {}

    for lap_list in lap_lists:
        list_name = lap_list['name']
        list_contest = lap_list['contest']

        # If contest filter specified, only process matching contests
        if contest_filter and str(list_contest) != str(contest_filter):
            continue

        contest_name = contests.get(str(list_contest), f'contest-{list_contest}')
        distance_id = classify_distance(contest_name, {})
        if not distance_id:
            distance_id = classify_distance('', contests)

        log(f'  Fetching {list_name} (contest {list_contest}: {contest_name})...')
        data = fetch_lap_data(config, list_name, list_contest, event_id)
        if not data:
            log(f'    Failed to fetch')
            continue

        fields = data.get('DataFields', [])
        entries = data.get('data', {})

        if not detect_row_per_lap_format(fields):
            log(f'    Not row-per-lap format, skipping (fields: {fields})')
            continue

        cum_idx, split_idx, rest_idx = find_time_field_indices(fields)
        # Need at least split (running time) or cumulative
        if cum_idx is None and split_idx is None:
            log(f'    Cannot find time fields in: {fields}')
            continue

        # Find lap number field
        lap_num_idx = None
        for i, f in enumerate(fields):
            if f == '{n}':
                lap_num_idx = i
                break

        field_desc = []
        if cum_idx is not None:
            field_desc.append(f'cum={fields[cum_idx]}')
        if split_idx is not None:
            field_desc.append(f'split={fields[split_idx]}')
        if rest_idx is not None:
            field_desc.append(f'rest={fields[rest_idx]}')
        log(f'    {len(entries)} entries, fields: {", ".join(field_desc)}')

        duration_sec = get_duration_seconds(distance_id) if distance_id else None
        runners_written = 0
        runners_skipped = 0
        validation_issues = []

        # Flatten nested format: data -> rank_key -> runner_key -> rows
        flat_entries = {}
        for key, val in entries.items():
            if isinstance(val, dict):
                # Nested: val is {runner_key: rows}
                for runner_key, rows in val.items():
                    if isinstance(rows, list):
                        flat_entries[runner_key] = rows
            elif isinstance(val, list):
                flat_entries[key] = val

        for runner_key, rows in flat_entries.items():
            if not isinstance(rows, list) or not rows:
                continue

            runner_name, expected_laps = parse_runner_key(runner_key)
            if not runner_name:
                continue

            # Parse laps
            laps = []
            for row in rows:
                if not isinstance(row, (list, tuple)):
                    continue

                lap_num = None
                if lap_num_idx is not None and lap_num_idx < len(row):
                    try:
                        lap_num = int(row[lap_num_idx])
                    except (ValueError, TypeError):
                        pass
                if lap_num is None:
                    lap_num = len(laps) + 1

                cum_time = parse_time_to_seconds(row[cum_idx]) if cum_idx is not None and cum_idx < len(row) else 0
                split_time = parse_time_to_seconds(row[split_idx]) if split_idx is not None and split_idx < len(row) else 0
                rest_time = parse_time_to_seconds(row[rest_idx]) if rest_idx is not None and rest_idx < len(row) else 0

                if cum_time <= 0 and split_time <= 0:
                    continue

                # Backyard format: running time + rest = elapsed per lap
                # Use elapsed (running + rest) as the split, compute cumulative
                if rest_idx is not None and cum_idx is None and split_time > 0:
                    elapsed = split_time + rest_time
                    cum_time = (laps[-1]['cum_sec'] if laps else 0) + elapsed
                    split_time = elapsed

                # If we only have cumulative, derive split
                if split_time <= 0 and cum_time > 0 and laps:
                    split_time = cum_time - laps[-1]['cum_sec']

                # If we only have split, derive cumulative
                if cum_time <= 0 and split_time > 0:
                    cum_time = (laps[-1]['cum_sec'] if laps else 0) + split_time

                laps.append({
                    'lap': lap_num,
                    'split_sec': round(split_time, 2),
                    'cum_sec': round(cum_time, 2),
                })

            if len(laps) < 3:
                runners_skipped += 1
                continue

            # Validate
            valid, issues = validate_laps(laps, duration_sec)
            if not valid:
                runners_skipped += 1
                validation_issues.append(f'{runner_name}: {"; ".join(issues)}')
                continue

            if issues:
                # Non-critical issues — log but still save
                validation_issues.append(f'{runner_name} (saved with warnings): {"; ".join(issues)}')

            # Try to get gender from data
            gender = None
            # Check if gender info is in the key
            if '_Female' in runner_key or '_female' in runner_key:
                gender = 'F'
            elif '_Male' in runner_key or '_male' in runner_key:
                gender = 'M'
            # Check fields for gender
            for i, f in enumerate(fields):
                if f.lower() in ('gendermf', 'gender', 'sex') and i < len(rows[0]):
                    g = str(rows[0][i]).strip().upper()
                    if g in ('M', 'F', 'W'):
                        gender = 'M' if g == 'M' else 'F'

            # Build filename
            race_slug = slugify(contest_name if contest_name != f'contest-{list_contest}' else str(event_id))
            runner_slug = slugify(runner_name)
            filename = f'{race_slug}-laps-{runner_slug}-raceresult.json'
            filepath = os.path.join(SPLITS_DIR, filename)

            if filename in existing_files:
                runners_skipped += 1
                continue

            # Build split data
            split_data = {
                'runner': runner_name,
                'race': contest_name,
                'year': None,  # Will be filled from registry
                'distance_id': distance_id,
                'data_type': 'laps',
                'source': f'my.raceresult.com event {event_id}',
                'total_laps': len(laps),
                'total_time_sec': round(laps[-1]['cum_sec'], 2),
                'laps': laps,
            }
            if gender:
                split_data['gender'] = gender

            if DRY_RUN:
                log(f'    [DRY] {filename} ({runner_name}, {len(laps)} laps, '
                    f'{laps[-1]["cum_sec"]/3600:.1f}h)')
            else:
                with open(filepath, 'w') as f:
                    json.dump(split_data, f, indent=2)
                    f.write('\n')
                existing_files.add(filename)

            runners_written += 1
            total_written += 1

        log(f'    Written: {runners_written}, Skipped: {runners_skipped}')
        if validation_issues:
            for issue in validation_issues[:5]:
                log(f'    ISSUE: {issue}')
            if len(validation_issues) > 5:
                log(f'    ... and {len(validation_issues) - 5} more issues')

    return total_written, event_meta


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    contest_filter = None
    if '--contest' in sys.argv:
        idx = sys.argv.index('--contest')
        if idx + 1 < len(sys.argv):
            contest_filter = sys.argv[idx + 1]

    if not args:
        print('Usage: python3 scrape-raceresult-laps.py EVENT_ID [--dry-run] [--contest ID]')
        print('       python3 scrape-raceresult-laps.py --batch')
        sys.exit(1)

    event_id = args[0]
    written, meta = scrape_event(event_id, contest_filter)
    log(f'Done. {written} files written.')


if __name__ == '__main__':
    main()
