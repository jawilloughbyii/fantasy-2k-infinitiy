#!/usr/bin/env python3
"""Private ESPN league ingestion; never logs or publishes authentication cookies.

Stage one: read-only historical backfill and strict reconciliation. The workflow
uploads its output as a PRIVATE Actions artifact, not into GitHub Pages.
"""
import argparse
import datetime as dt
import json
import math
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from statistics import fmean, pstdev, median

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEAM_COUNT = 10
LEAGUE_ID = 418244680
YEAR = 2026


def normalize(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch_espn():
    s2, swid = os.environ.get("ESPN_S2", "").strip(), os.environ.get("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise ValueError("Missing ESPN_S2 or ESPN_SWID GitHub Actions secrets")
    # Cookie is only transmitted to ESPN; never print or persist it.
    params = urllib.parse.urlencode([
        ("view", "mTeam"), ("view", "mMatchup"), ("view", "mMatchupScore"),
        ("view", "mSettings"), ("view", "mStatus"), ("view", "mStandings")
    ])
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
           f"seasons/{YEAR}/segments/0/leagues/{LEAGUE_ID}?{params}")
    request = urllib.request.Request(url, headers={
        "Cookie": f"espn_s2={s2}; SWID={swid}",
        "Accept": "application/json", "User-Agent": "Fantasy2KInfinity/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as res:
            if res.status != 200:
                raise RuntimeError(f"ESPN HTTP {res.status}")
            return json.load(res)
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"ESPN HTTP {ex.code}; check session cookies or endpoint") from None
    except urllib.error.URLError as ex:
        raise RuntimeError("Unable to reach ESPN; retry the workflow") from None


def extract(source):
    if int(source.get('id', -1)) != LEAGUE_ID:
        raise ValueError('League ID mismatch: refusing to process response')
    teams = source.get('teams') or []
    if len(teams) != TEAM_COUNT:
        raise ValueError(f'Expected {TEAM_COUNT} teams, ESPN returned {len(teams)}')
    clean_teams = []
    for t in teams:
        name = (t.get('name') or ' '.join(str(t.get(k) or '') for k in ('location','nickname'))).strip()
        clean_teams.append({'espn_id': int(t['id']), 'name': name})
    if len({t['espn_id'] for t in clean_teams}) != TEAM_COUNT:
        raise ValueError('Duplicate team IDs')
    known_ids = {t['espn_id'] for t in clean_teams}
    raw = source.get('schedule')
    if raw is None:
        raise ValueError('ESPN response does not contain schedule; inspect requested views')
    matches = []
    for item in raw:
        week = int(item.get('matchupPeriodId') or 0)
        if week <= 0: continue
        sides = []
        for side in ('home', 'away'):
            dat = item.get(side) or {}
            if dat.get('teamId') is None: continue
            team = int(dat['teamId'])
            if team not in known_ids:
                raise ValueError('Schedule references unknown team')
            points = dat.get('totalPoints')
            points = None if points is None else round(float(points), 2)
            sides.append({'team_id':team, 'points':points, 'side':side})
        if len(sides) != 2: continue
        if sides[0]['team_id'] == sides[1]['team_id']:
            raise ValueError('Team scheduled against itself')
        matches.append({'week': week, 'matchup_id': str(item.get('id', '')),
                        'home_id': next(s['team_id'] for s in sides if s['side']=='home'),
                        'away_id': next(s['team_id'] for s in sides if s['side']=='away'),
                        'home_points': next(s['points'] for s in sides if s['side']=='home'),
                        'away_points': next(s['points'] for s in sides if s['side']=='away'),
                        'winner': item.get('winner')})
    return clean_teams, matches


def validate(teams, matches, baseline):
    errors, warnings = [], []
    by_name = {normalize(t['name']):t for t in teams}
    mapping = {}
    for old in baseline['teams']:
        candidate = by_name.get(normalize(old['team_name']))
        if candidate:
            mapping[old['team_id']] = candidate['espn_id']
        else:
            errors.append(f"No matching ESPN team name for baseline: {old['team_name']!r}")
    if len(set(mapping.values())) != len(mapping):
        errors.append('Multiple baseline teams mapped to the same ESPN team')

    by_week = defaultdict(list)
    for match in matches:
        by_week[match['week']].append(match)
    baseline_weeks = sorted({x['week'] for x in baseline['scores']})
    results = []
    for week in baseline_weeks:
        games = by_week.get(week, [])
        if len(games) != TEAM_COUNT//2:
            errors.append(f'Week {week}: expected 5 matchups; ESPN returned {len(games)}')
            continue
        allids = [v for m in games for v in (m['home_id'], m['away_id'])]
        if len(set(allids)) != TEAM_COUNT:
            errors.append(f'Week {week}: duplicate or missing teams')
        indexed = {}
        for game in games:
            for side in ('home','away'):
                team = game[f'{side}_id']
                indexed[team] = (game[f'{side}_points'], game[f'{"away" if side == "home" else "home"}_id'])
        for row in (x for x in baseline['scores'] if x['week']==week):
            eid = mapping.get(row['team_id'])
            opp = mapping.get(row['opponent_id'])
            if eid is None or opp is None: continue
            if eid not in indexed:
                errors.append(f'W{week} {row["team_id"]}: no ESPN score')
                continue
            actual, actual_opp = indexed[eid]
            if actual_opp != opp:
                errors.append(f'W{week} {row["team_id"]}: opponent mismatch')
            if actual is None:
                errors.append(f'W{week} {row["team_id"]}: no ESPN point total')
            elif abs(actual-row['points']) > .011:
                errors.append(f'W{week} {row["team_id"]}: expected {row["points"]:.2f}, ESPN {actual:.2f}')
            else:
                results.append({'week':week,'team_id':row['team_id'],'match':True})
    return {'passed':not errors, 'errors':errors,'warnings':warnings,
            'verified_team_scores':len(results), 'target_team_scores':len(baseline['scores']),
            'weeks':baseline_weeks, 'team_id_mapping':mapping}


def compute_preview(teams,matches,full_weeks):
    """Preview only. Does not publish a new dashboard or imply pregame projections."""
    names = {t['espn_id']:t['name'] for t in teams}
    per_team=defaultdict(list)
    per_week=defaultdict(dict)
    for m in matches:
        if m['week'] not in full_weeks: continue
        for side in ('home','away'):
            pts = m[f'{side}_points']
            if pts is None: continue
            tid = m[f'{side}_id']
            per_team[tid].append({'week':m['week'],'points':pts})
            per_week[m['week']][tid]=pts
    valid_weeks = sorted(w for w,v in per_week.items() if len(v)==TEAM_COUNT)
    if not valid_weeks: return {'latest_valid_week':None,'teams':[]}
    league_avg=fmean(p for w in valid_weeks for p in per_week[w].values())
    entries=[]
    for tid, name in sorted(names.items(),key=lambda a:a[1]):
        pts=[per_week[w][tid] for w in valid_weeks]
        avg=fmean(pts)
        cv=pstdev(pts)/avg if avg>0 else 0
        # Preserve established priority ordering and thresholds.
        if cv>=.235 and max(pts)>=1.10*league_avg: dna='High ceiling, low floor'
        elif cv>=.235: dna='Boom-or-bust'
        elif cv<=.135 and avg>=1.04*league_avg: dna='Reliable contender'
        elif cv<=.135: dna='Steady scorer'
        elif avg>=1.08*league_avg: dna='High-upside contender'
        elif avg<=.92*league_avg: dna='Inconsistent underdog'
        else: dna='Balanced, with swings'
        n=len(pts)
        recent_avg = fmean(pts[-3:]) if n>=3 else None
        # Current weeks 1-5: two recent vs first two; >=6 compare 3+3.
        if n>=6: old,new=fmean(pts[-6:-3]),fmean(pts[-3:]); threshold=.12*avg
        elif n>=4: old,new=fmean(pts[:2]),fmean(pts[-2:]); threshold=.12*avg
        else: old=new=None; threshold=.12*avg
        form=('Not enough weeks' if new is None else
              'Heating up' if new-old >=threshold else
              'Cooling off' if old-new>=threshold else 'Mostly flat')
        entries.append({'team_id':tid,'name':name,'average_pf':round(avg,2),
                        'floor':min(pts),'ceiling':max(pts),'cv_pct':round(cv*100,2),
                        'dna':dna,'form':form,'last_3_avg_pf':round(recent_avg,2) if recent_avg else None,
                        'identity_confidence':'provisional' if n<=5 else 'emerging' if n<=9 else 'established'})
    return {'latest_valid_week':max(valid_weeks),'league_average_pf':round(league_avg,2),
            'weekly_average_pf':[{ 'week':w,'points':round(fmean(per_week[w].values()),2)} for w in valid_weeks],
            'teams':entries,'status':'preview_not_published'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',help='ESPN-like JSON test fixture; no secrets needed')
    parser.add_argument('--output-dir',default=str(ROOT/'output'))
    args=parser.parse_args()
    output=pathlib.Path(args.output_dir); output.mkdir(parents=True,exist_ok=True)
    source=json.load(open(args.fixture,encoding='utf-8')) if args.fixture else fetch_espn()
    teams,matches=extract(source)
    baseline=json.load(open(ROOT/'reference'/'validated_weeks_1_4.json',encoding='utf-8'))
    result=validate(teams,matches,baseline)
    # No owners, cookies, rosters, or private ESPN fields saved.
    report={'season':YEAR,'league_id':LEAGUE_ID,'generated_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
            'validation':result,'safe_teams':teams,'matchups':matches,
            'current_matchup_period':(source.get('status') or {}).get('currentMatchupPeriod')}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"Matched {result['verified_team_scores']}/{result['target_team_scores']} baseline team-week scores")
    if not result['passed']:
        print('VALIDATION FAILED; no site content has been changed.')
        for error in result['errors'][:25]: print(' - '+error)
        return 1
    # Preview only from fully scored weeks; no unfinalized week enters published metrics.
    completed=[]
    by_week=defaultdict(list)
    for match in matches: by_week[match['week']].append(match)
    for week,ms in by_week.items():
        if len(ms)==5 and all(m['home_points'] is not None and m['away_points'] is not None for m in ms):
            # Do NOT assume partial live points indicate final: only baseline-validated
            # weeks are allowed into this stage-one preview.
            if week in result['weeks']: completed.append(week)
    preview=compute_preview(teams,matches,sorted(completed))
    (output/'team_dna_preview.json').write_text(json.dumps(preview,indent=2)+'\n')
    print('VALIDATION PASSED. Team DNA preview written. Public dashboard unchanged.')
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except (ValueError,RuntimeError,KeyError,TypeError) as e:
        print('SAFE ERROR: '+str(e), file=sys.stderr)
        sys.exit(1)
