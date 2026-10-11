#!/usr/bin/env python3
"""Attach strictly validated (read-only) Starter-Worthy Rate metrics to an approved JSON copy."""
import argparse
import json
from pathlib import Path

POSSIBLE=json.loads((Path(__file__).resolve().parents[1]/'reference'/'metric_definitions.json').read_text(encoding='utf8'))['lineup']['weightedPossible']


def attach(data,rosters):
    # The approved public baseline intentionally omits private ESPN league/season identifiers.
    if (data.get('title')!='Fantasy 2K Infinity' or
        data.get('source')!='ESPN authenticated, baseline reconciled' or
        rosters.get('leagueId')!=418244680 or rosters.get('season')!=2026 or
        data.get('completedThrough')!=rosters.get('completedThrough')):
        raise ValueError('Roster analysis does not match approved league/season/week')
    weeks=rosters.get('weeks') or []
    if [x['week'] for x in weeks]!=list(range(1,data['completedThrough']+1)):raise ValueError('Roster analysis is missing approved completed weeks')
    known={t['id'] for t in data['teams']}
    for w in weeks:
        items=w['teams']
        if len(items)!=10 or {x['teamId'] for x in items}!=known:raise ValueError('Roster analysis does not contain exactly ten approved teams')
        for x in items:
            if not (0<=x['weightedHits']<=x['weightedMax']<=POSSIBLE and x['weightedPossible']==POSSIBLE):raise ValueError('Invalid weighted lineup scores')
            if abs(100*x['weightedHits']/POSSIBLE-x['swrPct'])>.02:raise ValueError('Invalid SWR percent')
            if abs(x['weightedMax']-x['weightedHits']-x['missedWeighted']-x['reassignmentWeighted'])>.001:raise ValueError('Invalid opportunity decomposition')
            if not 0<=x['qualifiedStarters']<=9:raise ValueError('Invalid starter counts')
    # No raw authenticated ESPN responses or account information are included.
    payload={'status':'validated-final-rosters','throughWeek':data['completedThrough'],'generatedAt':rosters['generatedAt'],
             'weights':rosters['weights'],'weeks':weeks}
    import copy
    output=copy.deepcopy(data);output['rosterAnalysis']=payload
    return output


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--league-data',required=True);ap.add_argument('--roster-data',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    data=json.loads(Path(a.league_data).read_text());rosters=json.loads(Path(a.roster_data).read_text());out=attach(data,rosters)
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(f'Validated roster analysis attached through W{out["completedThrough"]}; public website unchanged.')
if __name__=='__main__':main()