#!/usr/bin/env python3
"""Generate an HTML file with the SAME approved dataset as data/league.json.
Read-only preview until a human commits BOTH HTML and JSON together.
"""
import argparse
import json
import pathlib
import re

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFINITIONS=ROOT/'reference'/'metric_definitions.json'
IDENTITIES=ROOT/'reference'/'franchise_continuity.json'
TEAM_IDS=ROOT/'reference'/'team_id_map.json'
CHAMPIONS=ROOT/'reference'/'championship_history.json'
HISTORICAL_SCORES=ROOT/'reference'/'historical_regular_season_scores.json'
HISTORICAL_DRAFTS=ROOT/'reference'/'historical_draft_picks.json'
LEGACY_DRAFTS=ROOT/'reference'/'historical_legacy_draft_picks_2014_2017.json'
HISTORICAL_DRAFT_GRADES=ROOT/'reference'/'historical_draft_grades.json'
PLAYOFF_BRACKETS=ROOT/'reference'/'historical_playoff_brackets.json'
METRIC_PATTERN=re.compile(r'(<script id="metricdefs" type="application/json">)(.*?)(</script>)',re.S)
CHAMP_PATTERN=re.compile(r'(<script id="championships" type="application/json">)(.*?)(</script>)',re.S)
HIST_PATTERN=re.compile(r'(<script id="historicalscores" type="application/json">)(.*?)(</script>)',re.S)
DRAFT_PATTERN=re.compile(r'(<script id="historicaldrafts" type="application/json">)(.*?)(</script>)',re.S)
LEGACY_DRAFT_PATTERN=re.compile(r'(<script id="legacydrafts" type="application/json">)(.*?)(</script>)',re.S)
GRADE_PATTERN=re.compile(DRAFT_PATTERN.pattern.replace('historicaldrafts','historicaldraftgrades'),re.S)
PLAYOFF_PATTERN=re.compile(r'(<script id="historicalplayoffs" type="application/json">)(.*?)(</script>)',re.S)

PATTERN=re.compile(r'(<script id="fantasydata" type="application/json">)(.*?)(</script>)',re.S)

def safe_json(data):
    return json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')

def championship_metadata():
    """Public, owner-free identity lookup, sourced from verified references."""
    identity=json.loads(IDENTITIES.read_text(encoding='utf8'))
    team_ids=json.loads(TEAM_IDS.read_text(encoding='utf8'))
    history=json.loads(CHAMPIONS.read_text(encoding='utf8'))
    if not (identity['league_id']==team_ids['league_id']==history['league_id']):
        raise ValueError('Championship and franchise league IDs disagree')
    years=set()
    for winner in history['champions']:
        year,tid=winner['season'],str(winner['espn_team_id'])
        if winner['status']!='confirmed' or year in years:
            raise ValueError('Unverified or duplicate championship season')
        years.add(year)
        mapped=identity['season_to_franchise'].get(str(year),{}).get(tid)
        if not mapped or mapped!=winner['franchise_id']:
            raise ValueError('Championship identity is not verified for its season')
    historical=json.loads(HISTORICAL_SCORES.read_text(encoding='utf8'))
    archived={s['year']:s for s in historical['seasons']}
    old_winners=history.get('legacy_champions',[])
    if [r['season'] for r in old_winners]!=[2014,2016,2017]:
        raise ValueError('Missing or extra source-verified legacy title years')
    for old in old_winners:
        season=archived.get(old['season'])
        final=season.get('postseason') if season else None
        if not (season and season['league_id']==791996 and
                old['source_league_id']==791996 and old['status']=='confirmed_legacy_season' and
                old.get('franchise_id') is None and
                final and final['status']=='validated_bracket_path' and final['bracket_validated'] is True and
                old['espn_team_id']==final['winner_espn_team_id'] and
                old['team_name_at_win']==final['winner_team_name'] and
                next((t['name'] for t in season['teams'] if t['espn_team_id']==old['espn_team_id']),None)==old['team_name_at_win']):
            raise ValueError('Unreconciled legacy trophy data')
        if str(old['season']) in identity['season_to_franchise']:
            raise ValueError('Old-era franchise attribution is not authorized')
    if archived[2015]['postseason']['bracket_validated'] is not False or 2015 in {r['season'] for r in old_winners}:
        raise ValueError('Disputed 2015 final must not award a trophy')
    if team_ids['season'] not in (2026,):
        raise ValueError('Unverified live dashboard season mapping')
    result={
        'league_id':history['league_id'],
        'season_to_franchise':identity['season_to_franchise'],
        'dashboard_to_espn':team_ids['baseline_to_espn'],
        'champions':history['champions'],
        'legacy_champions':old_winners
    }
    for forbidden in ('owner_name','manager_name','espn_s2','espn_swid'):
        if forbidden in json.dumps(result).lower():
            raise ValueError('Sensitive information in championship metadata')
    return result

def identity_leagues():
    return json.loads(IDENTITIES.read_text(encoding='utf8'))['league_ids_by_season']

def sync(html,data):
    if data.get('completedThrough',0)<4 or len(data.get('teams',[]))!=10:raise ValueError('Incomplete approved dataset')
    match=PATTERN.search(html)
    if not match:raise ValueError('Missing embedded snapshot in HTML')
    old=json.loads(match.group(2))
    if int(data['completedThrough'])<int(old['completedThrough']):raise ValueError('Refusing backward fallback snapshot')
    for word in ('espn_s2','espn_swid','owner_name','manager_name','session_cookie'):
        if word in json.dumps(data).lower():raise ValueError('Potential sensitive field found in public data')
    updated=html[:match.start(2)]+safe_json(data)+html[match.end(2):]
    metrics=json.loads(DEFINITIONS.read_text(encoding='utf8'))
    m=METRIC_PATTERN.search(updated)
    if not m:raise ValueError('Missing shared metric definitions in HTML')
    updated=updated[:m.start(2)]+safe_json(metrics)+updated[m.end(2):]
    champ=CHAMP_PATTERN.search(updated)
    if not champ:raise ValueError('Missing championship metadata block in HTML')
    updated=updated[:champ.start(2)]+safe_json(championship_metadata())+updated[champ.end(2):]
    historical=HIST_PATTERN.search(updated)
    if not historical:raise ValueError('Missing historical scoring data block in HTML')
    source=json.loads(HISTORICAL_SCORES.read_text(encoding='utf8'))
    if source.get('league_id')!=data.get('leagueId',418244680):
        raise ValueError('Historical scoring league mismatch')
    updated=updated[:historical.start(2)]+safe_json(source)+updated[historical.end(2):]
    playoff=PLAYOFF_PATTERN.search(updated)
    if not playoff:raise ValueError('Missing historical playoff data block in HTML')
    brackets=json.loads(PLAYOFF_BRACKETS.read_text(encoding='utf8'))
    if not set(brackets['seasons']).issubset({str(s['year']) for s in source['seasons']}):
        raise ValueError('Approved playoff seasons have no matching scoring season')
    if {s['year'] for s in source['seasons'] if s.get('league_id')==791996}!={2014,2015,2016,2017}:
        raise ValueError('Legacy ESPN source coverage is incomplete')
    champions=json.loads(CHAMPIONS.read_text(encoding='utf8'))['champions']
    if {int(x['season']) for x in champions}!={int(y) for y in brackets['seasons']}:
        raise ValueError('Championship history coverage differs from verified playoff brackets')
    updated=updated[:playoff.start(2)]+safe_json(brackets)+updated[playoff.end(2):]
    draft=DRAFT_PATTERN.search(updated)
    if not draft:raise ValueError('Missing embedded historical draft snapshot')
    drafts=json.loads(HISTORICAL_DRAFTS.read_text(encoding='utf8'))
    if drafts.get('status')!='verified_picks_not_performance_grades' or drafts.get('coverage',{}).get('pick_count')!=980:
        raise ValueError('Unvalidated historic draft data')
    if {str(s['year']):s['league_id'] for s in drafts['seasons']}!=identity_leagues():
        raise ValueError('Draft season ESPN league IDs do not match owner mapping')
    updated=updated[:draft.start(2)]+safe_json(drafts)+updated[draft.end(2):]
    legacy_match=LEGACY_DRAFT_PATTERN.search(updated)
    if not legacy_match:raise ValueError('Missing legacy draft snapshot')
    legacy=json.loads(LEGACY_DRAFTS.read_text(encoding='utf8'))
    if legacy.get('status')!='verified_raw_picks_player_enrichment_pending' or legacy.get('coverage',{}).get('pick_count')!=680:
        raise ValueError('Legacy 2014-17 drafts are incomplete')
    if [s['year'] for s in legacy['seasons']]!=[2014,2015,2016,2017] or any(s['league_id']!=791996 for s in legacy['seasons']):
        raise ValueError('Legacy draft identity mismatch')
    updated=updated[:legacy_match.start(2)]+safe_json(legacy)+updated[legacy_match.end(2):]
    grade_match=GRADE_PATTERN.search(updated)
    if not grade_match:raise ValueError('Missing historical draft grade block')
    grade_data=json.loads(HISTORICAL_DRAFT_GRADES.read_text(encoding='utf8'))
    if grade_data.get('status')!='retrospective_verified_model_v1':
        raise ValueError('Unverified draft grading data')
    if [s['year'] for s in grade_data['seasons']]!=[s['year'] for s in drafts['seasons'][:5]]:
        raise ValueError('Draft grade year mismatch')
    if grade_data.get('coverage',{}).get('pick_count')!=820:
        raise ValueError('Incomplete draft grade coverage')
    return updated[:grade_match.start(2)]+safe_json(grade_data)+updated[grade_match.end(2):]

def main():
    a=argparse.ArgumentParser();a.add_argument('--html',default='index.html');a.add_argument('--data',required=True);a.add_argument('--output',required=True);args=a.parse_args()
    original=pathlib.Path(args.html).read_text(encoding='utf8');data=json.loads(pathlib.Path(args.data).read_text(encoding='utf8'))
    updated=sync(original,data);out=pathlib.Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(updated,encoding='utf8')
    print(f'Prepared matching HTML fallback at Week {data["completedThrough"]}; live website untouched.')
if __name__=='__main__':main()