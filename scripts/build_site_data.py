#!/usr/bin/env python3
"""Build public, anonymous league.json from a validated ESPN report.

No ESPN authentication values are accepted or written here. Requires a previously
validated score baseline and ESPN current matchup period to add post-baseline weeks.
Fails closed on incomplete/ambiguous score data; produces no partial site update.
"""
import argparse
import copy
import datetime as dt
import json
import math
import pathlib
import random
import re
import statistics as stats
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load(path):
    with open(path, encoding='utf-8') as f: return json.load(f)

def embed(html):
    text=pathlib.Path(html).read_text(encoding='utf-8')
    m=re.search(r'<script id="fantasydata" type="application/json">(.*?)</script>',text,re.S)
    if not m: raise ValueError('index.html is missing the original validated fallback')
    return json.loads(m.group(1))

METRICS=load(ROOT/'reference/metric_definitions.json')

def mean(x): return sum(x)/len(x)
def normalize(s): return re.sub('[^a-z0-9]','',s.lower())
def rounding(x): return round(x+0.,8)

def classification(scores, league_mean):
    """Use the identical four quadrants as the frontend map and shared definitions."""
    average=mean(scores)
    sd=stats.pstdev(scores) if len(scores)>1 else 0
    cv=sd/average if average>0 else 0
    high=cv>METRICS['scoring']['quadrantCvBoundary']
    right=average>=league_mean
    return METRICS['scoring']['quadrants'][(1 if right else 0)+(0 if high else 2)]


def simulate(teams, n=20000):
    """Historical weekly score-preserving random valid perfect matchings."""
    rnd=random.Random(20261009); weeks=len(teams[0]['weeks']); by_id={t['id']:t for t in teams}; ids=list(by_id)
    old_divs=sorted({t['division'] for t in teams}); groups={d:[t for t in teams if t['division']==d] for d in old_divs}
    count_wins={id:[0]*(weeks+1) for id in ids}
    rank_counts={id:[0]*len(groups[by_id[id]['division']]) for id in ids}; rank_sum={id:0 for id in ids}; win_sum={id:0 for id in ids}
    total=weeks*n
    for _ in range(n):
        wins={id:0 for id in ids}
        for w in range(weeks):
            shuffled=ids[:];rnd.shuffle(shuffled)
            for i in range(0,len(ids),2):
                a,b=shuffled[i:i+2];ap=by_id[a]['weeks'][w]['pf'];bp=by_id[b]['weeks'][w]['pf']
                if ap>bp: wins[a]+=1
                elif bp>ap:wins[b]+=1
                else:wins[a]+=.5;wins[b]+=.5
        for t in teams:
            id=t['id'];wa=wins[id];win_sum[id]+=wa
            ix=min(weeks,int(wa));count_wins[id][ix]+=1
        for group in groups.values():
            for t in group:
                id=t['id'];place=1+sum(wins[o['id']]>wins[id] for o in group)
                rank_counts[id][place-1]+=1;rank_sum[id]+=place
    for t in teams:
        id=t['id'];t['simWinMean']=round(win_sum[id]/n,3);t['simRankMean']=round(rank_sum[id]/n,3)
        t['rankDist']=[round(100*x/n,3) for x in rank_counts[id]]
        t['winDist']=[round(100*x/n,3) for x in count_wins[id]]
        t['simTop2Pct']=round(100*(rank_counts[id][0]+rank_counts[id][1])/n,1)
    return n

def build(report,base):
    valid=report.get('validation') or {}
    if not valid.get('passed') or valid.get('verified_team_scores')!=40 or valid.get('target_team_scores')!=40:
        raise ValueError('Backfill must pass exact 40/40 baseline validation before publishing')
    if report.get('season')!=2026 or report.get('league_id')!=418244680:
        raise ValueError('Wrong ESPN league or season')
    mapping={int(k):int(v) for k,v in valid['team_id_mapping'].items()}
    if set(mapping)!={t['id'] for t in base['teams']} or len(set(mapping.values()))!=10:raise ValueError('Incomplete team ID mapping')
    reverse={v:k for k,v in mapping.items()}
    names={t['espn_id']:t['name'] for t in report['safe_teams']}
    for t in base['teams']:
        if normalize(names[mapping[t['id']]])!=normalize(t['name']):raise ValueError('Team name mismatch: '+t['name'])
    by_week=defaultdict(list)
    for m in report['matchups']:by_week[int(m['week'])].append(m)
    baseline_max=max(valid['weeks'])
    if sorted(valid['weeks'])!=list(range(1,baseline_max+1)):raise ValueError('Non-contiguous validated weeks')
    current=report.get('current_matchup_period')
    # If ESPN status is absent (as in the original backfill), validated weeks only.
    if current is None: latest=baseline_max
    else:
        current=int(current)
        if current<baseline_max+1: latest=baseline_max
        else: latest=max(baseline_max,current-1)
    if latest>18:raise ValueError('Implausible current matchup period; inspect API')
    for w in range(1,latest+1):
        ms=by_week.get(w,[])
        if len(ms)!=5:raise ValueError(f'Week {w}: expected five matchups, found {len(ms)}')
        ids=[x for m in ms for x in (m['home_id'],m['away_id'])]
        if sorted(ids)!=sorted(mapping.values()):raise ValueError(f'Week {w}: missing/duplicate ESPN IDs')
        for m in ms:
            p,q=m['home_points'],m['away_points']
            if p is None or q is None or not all(math.isfinite(float(v)) and float(v)>=0 for v in (p,q)):
                raise ValueError(f'Week {w}: missing or invalid score')
            if w>baseline_max and m.get('winner') not in ('HOME','AWAY'):
                raise ValueError(f'Week {w}: game is not confirmed finalized')
            predicted='HOME' if p>q else 'AWAY' if q>p else 'TIE'
            if m.get('winner') not in (None,predicted):raise ValueError(f'Week {w}: inconsistent winner')
    result=copy.deepcopy(base)
    result.pop('week5',None)  # old in-progress screenshot must not persist
    result.pop('rosterAnalysis',None)  # historical roster analysis requires a separate completed-week validation
    result['completedThrough']=latest
    result['source']='ESPN authenticated, baseline reconciled'
    result['generated']=report.get('generated_at_utc') or dt.datetime.now(dt.timezone.utc).isoformat()
    result['projectionCoverage']={'kind':'historical ESPN screenshot displayed values','throughWeek':baseline_max,'notice':'Historical displayed values are not verified pregame and must not be used in headline comparisons.'}
    for t in result['teams']:
        t['weeks']=[]
        for legacy in ('rankLuckPct','winLuckPct','luckpp'):t.pop(legacy,None)
    indexed={t['id']:t for t in result['teams']}; week_points={}
    base_week={(t['id'],w['week']):w for t in base['teams'] for w in t['weeks']}
    for w in range(1,latest+1):
        week_points[w]={};pairs=[]
        for m in by_week[w]:
            h,a=(reverse[m[k]] for k in ('home_id','away_id'))
            hp,ap=float(m['home_points']),float(m['away_points'])
            pairs.append((h,a,hp,ap));week_points[w][h]=hp;week_points[w][a]=ap
        for h,a,hp,ap in pairs:
            for id,opp,pf,pa in ((h,a,hp,ap),(a,h,ap,hp)):
                raw=base_week.get((id,w))
                if w<=baseline_max and (raw is None or abs(raw['pf']-pf)>.011 or raw['opp']!=opp):
                    raise ValueError(f'W{w} score or opponent differs from screenshot baseline')
                proj=raw.get('proj') if w<=baseline_max and raw else None
                indexed[id]['weeks'].append({'week':w,'pf':round(pf,2),'pa':round(pa,2),'opp':opp,'proj':proj,
                    'win':1 if pf>pa else 0,'xw':None,'weekLuck':None,'delta':round(pf-proj,2) if proj is not None else None,'rank':None})
        sorted_week=sorted(week_points[w].values(),reverse=True)
        for t in result['teams']:
            row=t['weeks'][-1];pf=row['pf'];beats=sum(pf>p for id,p in week_points[w].items() if id!=t['id']);ties=sum(pf==p for id,p in week_points[w].items() if id!=t['id']);xw=(beats+METRICS['luck']['tieCredit']*ties)/(len(result['teams'])-1)
            row['xw']=rounding(xw);row['weekLuck']=rounding(row['win']-xw);row['rank']=1+sum(p>pf for p in week_points[w].values())
    for t in result['teams']:
        rows=t['weeks'];wins=sum(x['win'] for x in rows); losses=len(rows)-wins
        t['wins']=wins;t['losses']=losses;t['pf']=round(sum(x['pf'] for x in rows),2);t['pa']=round(sum(x['pa'] for x in rows),2);t['pd']=round(t['pf']-t['pa'],2)
        t['xw']=rounding(sum(x['xw'] for x in rows));t['luck']=rounding(wins-t['xw']);t['winsAllPlay']=sum(9*x['xw'] for x in rows)
        projrows=[x for x in rows if x['proj'] is not None];t['projWeeks']=len(projrows)
        t['proj']=round(sum(x['proj'] for x in projrows),2);t['projdelta']=round(sum(x['pf']-x['proj'] for x in projrows),2)
        t['projPct']=round(100*t['projdelta']/t['proj'],3) if t['proj'] else None
    for t in result['teams']:
        peers=[z for z in result['teams'] if z['division']==t['division']]
        t['divrank']=1+sum(z['wins']>t['wins'] for z in peers)
    # Preserve exact historical simulation at four validated weeks; future periods get reproducible reruns.
    if latest>baseline_max:result['simulationRuns']=simulate(result['teams'])
    else:result['simulationRuns']=base.get('simulationRuns',100000)
    week_avg=[mean(list(week_points[w].values())) for w in range(1,latest+1)]
    league_avg=mean(week_avg)
    result['weeklyLeagueAverage']=[round(v,2) for v in week_avg]
    result['leagueAveragePf']=round(league_avg,2)
    result['leagueMedianPf']=round(stats.median([p for x in week_points.values() for p in x.values()]),2)
    result['dnaHistory']=[]
    for w in range(1,latest+1):
        avg=mean(week_avg[:w]);entry={'throughWeek':w,'status':'observed','teams':[]}
        for t in result['teams']:
            scores=[r['pf'] for r in t['weeks'][:w]]
            entry['teams'].append({'id':t['id'],'category':classification(scores,avg) if w>=METRICS['scoring']['minimumWeeks'] else 'Not enough weeks','averagePf':round(mean(scores),2),
             'cvPct':round((stats.pstdev(scores)/mean(scores))*100,2) if mean(scores)>0 else 0.0})
        result['dnaHistory'].append(entry)
    result['recentDna']=[]
    if latest>=METRICS['recentDna']['minimumWeeks']:
        recent_window=METRICS['recentDna']['window'];recent_week_avg=mean(week_avg[-recent_window:]);earliest_recent=latest-recent_window+1
        for t in result['teams']:
            scores=[r['pf'] for r in t['weeks'][-recent_window:]]
            result['recentDna'].append({'id':t['id'],'weeks':[earliest_recent,latest],
             'category':classification(scores,recent_week_avg),'cvPct':round(100*stats.pstdev(scores)/mean(scores),2) if mean(scores)>0 else 0.0})
    result['methodNotes']=["Private ESPN backfill reconciled against 40 known scores and opponents for Weeks 1–4.",
     "Only completed periods before ESPN's current matchup period enter scoring calculations.",
     "Original Weeks 1–4 displayed projection values are not verified pregame snapshots. Missing future projections remain blank.",
     "Manager names and ESPN authentication credentials are never published. Validated finalized roster metrics are published separately."]
    if len(result['teams'])!=10 or any(len(t['weeks'])!=latest for t in result['teams']):raise ValueError('Output completeness check failed')
    assert round(sum(t['pf'] for t in result['teams']),2)==round(sum(t['pa'] for t in result['teams']),2)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--baseline-html',default=str(ROOT/'index.html'));p.add_argument('--output',default=str(ROOT/'output/league.json'));args=p.parse_args()
    result=build(load(args.report),embed(args.baseline_html));out=pathlib.Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');tmp.replace(out)
    print(f"Validated public data ready: {result['completedThrough']} completed weeks, 10 anonymized teams, {result['simulationRuns']:,} retrospective simulations; projections through W{result['projectionCoverage']['throughWeek']} only.")
if __name__=='__main__':
    try:main()
    except (ValueError,TypeError,KeyError,ZeroDivisionError,AssertionError) as e:
        raise SystemExit('SAFE DATA BUILD FAILURE: '+str(e))
