#!/usr/bin/env python3
"""
Enrich lap-only split files with distance_mi and duration_sec.

For files that have data_type='laps' but no distance_mi, this script
infers total distance from race/event metadata and known loop distances.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
SPLITS_DIR = os.path.join(DATA_DIR, 'splits')

DRY_RUN = '--dry-run' in sys.argv

# Known loop distances in miles
BACKYARD_LOOP_MI = 4.167  # 6.706km standard backyard ultra loop

# Map race names to loop distance (miles)
RACE_LOOP_DISTANCES = {
    # Backyard ultras
    'Backyard Ultra': BACKYARD_LOOP_MI,
    'Backyard': BACKYARD_LOOP_MI,
    'MTB Backyard Ultra': BACKYARD_LOOP_MI,
    '{DE:Spiel mir das Lied vom Wald|EN:A Fistful of Trees}': BACKYARD_LOOP_MI,
    # Sri Chinmoy (5km loops)
    '100K Solo': 3.107,  # 5km = 3.107mi
    '50K Solo': 3.107,
}

# Map race name to distance_id
RACE_DISTANCE_IDS = {
    '100K Solo': '100k',
    '50K Solo': '50k',
    '12 Hour Ultra': '12h',
    '6 Hour Ultra': '6h',
    '12h': '12h',
    '6h': '6h',
    '24h': '24h',
}

# Map event IDs to distance_id (for events with generic race names like 'contest-0')
EVENT_DISTANCE_IDS = {
    237157: '12h',   # 12hours TrackRun Greece
    # Note: IKS Ukraine and Bashore use race-name or duration-based inference below
}

# Map source event IDs to loop distances for events not matchable by race name
EVENT_LOOP_DISTANCES = {
    # IKS Ukraine — 1.2km loop = 0.745mi
    338549: 0.745,
    288121: 0.745,
    174509: 0.745,
    # 12hours TrackRun Greece — 400m track = 0.249mi
    237157: 0.249,
    # RODOPI Backyard — standard backyard loop
    339844: BACKYARD_LOOP_MI,
    # Sri Chinmoy Mara-Fun Relays — 3.836km loop (42.195km / 11 laps)
    367396: 2.384,  # 3.836km = 2.384mi
    313522: 2.384,
    265388: 2.384,
    # Bashore Bash — ~5mi loops (8.047km)
    247735: 5.0,
    204651: 5.0,
    170597: 5.0,
}

# Cycling events — skip enrichment (not running)
CYCLING_EVENT_IDS = {277188, 383314, 271196}


def enrich_file(filepath, filename):
    """Enrich a single lap file. Returns (enriched, reason) or (False, None)."""
    with open(filepath) as f:
        data = json.load(f)

    if data.get('data_type') != 'laps':
        return False, None

    # Skip cycling events
    source = data.get('source', '')
    if 'event' in source:
        try:
            event_id = int(source.split('event ')[-1])
            if event_id in CYCLING_EVENT_IDS:
                return False, None
        except ValueError:
            pass

    if data.get('distance_mi') and data.get('duration_sec') and data.get('distance_id'):
        return False, None  # Already enriched

    changed = False
    race = data.get('race', '')
    total_laps = data.get('total_laps', 0)
    total_time = data.get('total_time_sec', 0)

    # Set duration_sec from total_time_sec
    if not data.get('duration_sec') and total_time > 0:
        data['duration_sec'] = total_time
        changed = True

    # Try to determine loop distance
    loop_mi = None

    # Check race name
    if race in RACE_LOOP_DISTANCES:
        loop_mi = RACE_LOOP_DISTANCES[race]

    # Check event ID
    if loop_mi is None and 'event' in source:
        try:
            event_id = int(source.split('event ')[-1])
            if event_id in EVENT_LOOP_DISTANCES:
                loop_mi = EVENT_LOOP_DISTANCES[event_id]
        except ValueError:
            pass

    # Compute total distance
    if loop_mi and total_laps > 0 and not data.get('distance_mi'):
        data['distance_mi'] = round(total_laps * loop_mi, 2)
        data['loop_distance_mi'] = loop_mi
        changed = True

    # Set distance_id for known races
    if race in RACE_DISTANCE_IDS and not data.get('distance_id'):
        data['distance_id'] = RACE_DISTANCE_IDS[race]
        changed = True

    # Set distance_id by event ID
    if not data.get('distance_id') and 'event' in source:
        try:
            event_id = int(source.split('event ')[-1])
            if event_id in EVENT_DISTANCE_IDS:
                data['distance_id'] = EVENT_DISTANCE_IDS[event_id]
                changed = True
        except ValueError:
            pass

    # Infer distance_id from elapsed time for known multi-distance events
    # Only apply to IKS Ukraine events (not backyard ultras or other formats)
    IKS_EVENTS = {338549, 288121, 174509}
    DURATION_THRESHOLDS = [
        (44, '48h', 172800), (20, '24h', 86400), (10, '12h', 43200),
        (5, '6h', 21600), (2.5, '3h', 10800),
    ]
    if not data.get('distance_id') and total_time > 0 and 'event' in source:
        try:
            event_id = int(source.split('event ')[-1])
            if event_id in IKS_EVENTS:
                hours = total_time / 3600
                for threshold, dist_id, official_sec in DURATION_THRESHOLDS:
                    if hours > threshold:
                        data['distance_id'] = dist_id
                        data['duration_sec'] = official_sec
                        changed = True
                        break
        except ValueError:
            pass

    # Compute duration string
    if changed and data.get('duration_sec') and not data.get('duration'):
        sec = data['duration_sec']
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        data['duration'] = f'{h}:{m:02d}:{s:02d}'

    if changed and not DRY_RUN:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            f.write('\n')

    return changed, race


def main():
    enriched = 0
    skipped = 0
    already = 0
    by_race = {}

    for filename in sorted(os.listdir(SPLITS_DIR)):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(SPLITS_DIR, filename)
        was_enriched, race = enrich_file(filepath, filename)

        if was_enriched:
            enriched += 1
            by_race[race] = by_race.get(race, 0) + 1
        elif race is not None:
            already += 1
        else:
            skipped += 1

    prefix = '[DRY] ' if DRY_RUN else ''
    print(f'{prefix}Enriched: {enriched}, Already complete: {already}, Skipped (not laps): {skipped}')
    print(f'\nBy race:')
    for race, count in sorted(by_race.items(), key=lambda x: -x[1]):
        print(f'  {race}: {count}')


if __name__ == '__main__':
    main()
