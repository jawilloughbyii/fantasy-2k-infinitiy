#!/usr/bin/env python3
"""Opt-in, historical franchise keys. Does not alter the published 2026 pipeline."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'reference' / 'franchise_continuity.json'
TEAM_REFERENCE = ROOT / 'reference' / 'team_id_map.json'
EXPECTED_ESPN_IDS = {str(i) for i in range(1, 11)}


def load_mapping(path=REFERENCE):
    manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    validate_mapping(manifest)
    return manifest


def validate_mapping(manifest):
    if manifest.get('league_id') != 418244680:
        raise ValueError('League ID mismatch in franchise continuity reference')
    seasons = manifest.get('season_to_franchise')
    if not isinstance(seasons, dict) or not seasons:
        raise ValueError('Missing explicit season mappings')
    year_values = sorted(int(year) for year in seasons)
    if {str(year) for year in year_values} != set(seasons):
        raise ValueError('Season keys must be canonical year strings')
    for year, mapping in seasons.items():
        if not isinstance(mapping, dict) or set(mapping) != EXPECTED_ESPN_IDS:
            raise ValueError(f'{year}: expected precisely ESPN team IDs 1–10')
        if any(not isinstance(fid, str) or not fid.strip() for fid in mapping.values()):
            raise ValueError(f'{year}: every franchise ID must be non-empty')
        if len(set(mapping.values())) != 10:
            raise ValueError(f'{year}: a franchise cannot occupy two ESPN slots in one season')
    source_leagues = manifest.get('league_ids_by_season')
    if not isinstance(source_leagues, dict) or set(source_leagues) != set(seasons):
        raise ValueError('Each mapped season must declare its ESPN league ID')
    if any(not isinstance(source_leagues[y], int) or source_leagues[y] <= 0 for y in seasons):
        raise ValueError('Invalid season ESPN league ID')
    transitions = manifest.get('documented_transitions')
    if not isinstance(transitions, list):
        raise ValueError('Missing explicit transition list')
    declared = set()
    for t in transitions:
        tid = str(t['espn_team_id'])
        previous, following = str(t['prior_season']), str(t['first_new_season'])
        if tid not in EXPECTED_ESPN_IDS or int(following) != int(previous) + 1:
            raise ValueError('Invalid franchise transition boundary')
        if previous not in seasons or following not in seasons:
            raise ValueError('Transition references an unmapped season')
        if seasons[previous][tid] != t['prior_franchise_id'] or seasons[following][tid] != t['new_franchise_id']:
            raise ValueError('Transition disagrees with explicit franchise mapping')
        if t['prior_franchise_id'] == t['new_franchise_id']:
            raise ValueError('Declared transition has no franchise change')
        declared.add((previous, following, tid))
    if len(declared) != len(transitions):
        raise ValueError('Duplicate franchise transition')
    for before, after in zip(year_values, year_values[1:]):
        if after != before + 1:
            continue  # Disjoint seasons are not evidence of continuity.
        if source_leagues[str(before)] != source_leagues[str(after)]:
            continue  # ESPN slots are not comparable across different league IDs.
        for tid in EXPECTED_ESPN_IDS:
            if seasons[str(before)][tid] != seasons[str(after)][tid] and (str(before), str(after), tid) not in declared:
                raise ValueError(f'Undocumented franchise change: {before}/{after}, ESPN ID {tid}')
    # Owner identity across old/new league IDs is explicitly validated, never inferred from slots.
    owner_old = seasons['2022']
    owner_new = seasons['2023']
    if source_leagues['2022'] == source_leagues['2023'] or not (source_leagues['2021']==source_leagues['2022']==1493036707):
        raise ValueError('Archived league source identity mismatch')
    if owner_old['1'] != seasons['2024']['6'] or owner_old['2'] != owner_new['6']:
        raise ValueError('Departed and returning franchise continuity must remain distinct')
    if owner_old['5'] != owner_new['3'] or owner_old['6'] != owner_new['4']:
        raise ValueError('Confirmed Quattro Padres / Golden Ponies franchise linkage changed')
    if owner_new['5'] in set(owner_old.values()):
        raise ValueError('2023 entrant must begin as a new franchise')
    # User-confirmed historical exception: never silently undo this split.
    for year in ('2023', '2024', '2025', '2026'):
        if year not in seasons:
            raise ValueError(f'Missing confirmed historical season {year}')
    previous_id = seasons['2023']['6']
    current_id = seasons['2024']['6']
    if previous_id == current_id or not (current_id == seasons['2025']['6'] == seasons['2026']['6']):
        raise ValueError('Confirmed ESPN ID 6 ownership break must remain 2023/2024')
    if ('2023', '2024', '6') not in declared:
        raise ValueError('Missing documented 2023/2024 ESPN ID 6 transition')
    # Existing 2026 reference uses dashboard IDs, not ESPN IDs. Check coverage, not equality.
    team_reference = json.loads(TEAM_REFERENCE.read_text(encoding='utf-8'))
    if team_reference['league_id'] != manifest['league_id'] or team_reference['season'] != 2026:
        raise ValueError('2026 team reference mismatch')
    if {str(x) for x in team_reference['baseline_to_espn'].values()} != set(seasons['2026']):
        raise ValueError('2026 ESPN IDs not covered by verified dashboard mapping')
    for forbidden in ('owner_id', 'owner_name', 'manager_id', 'manager_name', 'espn_s2', 'espn_swid'):
        if forbidden in json.dumps(manifest).lower():
            raise ValueError('Sensitive identity or credential field is not allowed')
    return True


def franchise_for(season, espn_team_id, manifest, league_id=None):
    """Strict resolver: unmapped years or IDs require explicit human validation."""
    validate_mapping(manifest)
    expected_league = manifest['league_ids_by_season'].get(str(season))
    if league_id is not None and expected_league != league_id:
        raise ValueError(f'ESPN league ID does not match season {season}')
    try:
        return manifest['season_to_franchise'][str(season)][str(espn_team_id)]
    except KeyError:
        raise ValueError(f'Unverified franchise key: season={season}, ESPN team ID={espn_team_id}') from None
