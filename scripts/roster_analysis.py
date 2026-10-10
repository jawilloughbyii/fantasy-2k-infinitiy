#!/usr/bin/env python3
"""Finalized weekly ESPN fantasy lineups, starter-worthiness and *legal* bench opportunities.

No ESPN authentication values, owner names, or pre-lock movements are persisted.
Read-only by design: this does not write to the public site.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

LEAGUE_ID, YEAR = 418244680, 2026
SLOTS = {'QB':0, 'RB':2, 'WR':4, 'TE':6, 'FLEX':23, 'K':17, 'DST':16}
SLOT_TO_POSITION = {v:k for k,v in SLOTS.items()}
POSITION_ID = {1:'QB', 2:'RB', 3:'WR', 4:'TE', 5:'K', 16:'DST'}
REQUIRED = {'QB':1,'RB':2,'WR':2,'TE':1,'FLEX':1,'K':1,'DST':1}
BASE = {'QB':10,'RB':20,'WR':20,'TE':10,'K':10,'DST':10}
WEIGHT = {'QB':2,'RB':2,'WR':2,'TE':2,'FLEX':2,'K':1,'DST':1} # integer half-units; total 16
BENCH, IR = 20, 21
PAGE_SIZE, MAX_POOL = 500, 5000
BASE_URL=f'https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}/segments/0/leagues/{LEAGUE_ID}'


def score_stat(p,week):
    """Find *weekly actual* league-scored points; never use season totals or projections.
    None means ESPN omitted a weekly stat (a player with no appearance scores 0).
    """
    data=p.get('playerPoolEntry') or p
    player=data.get('player') or p.get('player') or {}
    stats=player.get('stats') or data.get('stats') or []
    matched=[]
    for s in stats:
        if int(s.get('scoringPeriodId',-1))!=week:continue
        if int(s.get('statSourceId',s.get('statTypeId',-1)))!=0:continue
        split=s.get('statSplitTypeId')
        if split is not None and int(split)!=1:continue
        if s.get('appliedTotal') is not None:
            matched.append(float(s['appliedTotal']))
    if len(matched)>1 and max(matched)-min(matched)>.011:raise ValueError(f'Ambiguous actual weekly stats, week {week}')
    if matched:
        value=matched[0]
        if not math.isfinite(value):raise ValueError('Non-finite player points')
        return round(value,2)
    return None


def clean_player(row,week,require_score=False):
    pool=row.get('playerPoolEntry') or row
    player=pool.get('player') or row.get('player') or {}
    pid=pool.get('id',row.get('playerId',row.get('id')))
    pos=POSITION_ID.get(int(player.get('defaultPositionId',-1)))
    if pos not in BASE: return None
    if pid is None:raise ValueError('Player is missing ESPN ID')
    pts=score_stat(row,week)
    if pts is None and require_score:raise ValueError('Missing actual weekly player scoring')
    if pts is None:pts=0.0  # no week stat / bye / did not play; not season totals
    return {'id':int(pid),'name':str(player.get('fullName') or f'Player {pid}')[:90],
            'pos':pos,'points':pts}


def _get_json(params,filters=None):
    s2,swid=os.getenv('ESPN_S2','').strip(),os.getenv('ESPN_SWID','').strip()
    if not s2 or not swid:raise ValueError('Missing ESPN secrets; configure ESPN_S2 and ESPN_SWID')
    url=BASE_URL+'?'+urllib.parse.urlencode(params,doseq=True)
    headers={'Cookie':f'espn_s2={s2}; SWID={swid}','Accept':'application/json','User-Agent':'Fantasy2KInfinity/roster-analysis'}
    if filters:headers['X-Fantasy-Filter']=json.dumps(filters,separators=(',',':'))
    req=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)
    except urllib.error.HTTPError as e:
        view=','.join(str(v) for k,v in params if k=='view')
        week=next((v for k,v in params if k=='scoringPeriodId'),'unspecified')
        stage='weekly player pool' if 'kona_player_info' in view else 'historical box score'
        raise ValueError(f'ESPN HTTP {e.code} retrieving {stage} (week {week}, view {view}); URL, cookies and response body omitted') from None
    except urllib.error.URLError:raise ValueError('ESPN unreachable during roster retrieval') from None


def fetch_week(week):
    filters={'schedule':{'filterMatchupPeriodIds':{'value':[week]}}}
    data=_get_json([('view','mBoxscore'),('view','mScoreboard'),('view','mMatchupScore'),('scoringPeriodId',week)],filters)
    if int(data.get('id',-1))!=LEAGUE_ID:raise ValueError('Wrong ESPN league in historical boxscore')
    if not data.get('schedule'):raise ValueError(f'Week {week}: no ESPN boxscore schedule')
    # The complete eligible player pool must include rostered AND unrostered NFL players.
    # No current-team status filter: historical waiver movement must not affect ranking.
    pool=[];seen=set()
    for offset in range(0,MAX_POOL,PAGE_SIZE):
        filt={'players':{'limit':PAGE_SIZE,'offset':offset,'filterSlotIds':{'value':[0,2,4,6,16,17]}}}
        blob=_get_json([('view','kona_player_info'),('scoringPeriodId',week)],filt)
        batch=blob.get('players')
        if not isinstance(batch,list) or (offset==0 and not batch):raise ValueError(f'Week {week}: missing complete ESPN player pool')
        identifiers=[int((p.get('playerPoolEntry') or p).get('id',p.get('id',-1))) for p in batch]
        if any(pid in seen for pid in identifiers):raise ValueError('ESPN pool pagination repeats player IDs; rankings unsafe')
        seen.update(identifiers);pool.extend(batch)
        if len(batch)<PAGE_SIZE:break
    else:raise ValueError('Player pool hit pagination safety limit; increase MAX_POOL')
    return data,pool


def extract_week(data,pool,week,expected_ids,league_week):
    games=[m for m in data.get('schedule',[]) if int(m.get('matchupPeriodId',week))==week]
    if len(games)!=5:raise ValueError(f'Week {week}: expected five boxscore matchups, got {len(games)}')
    observed={};all_rostered=set()
    for g in games:
        for side in ('home','away'):
            s=g.get(side) or {};tid=int(s.get('teamId',-1))
            if tid in observed:raise ValueError(f'Week {week}: duplicate team {tid}')
            entries=(s.get('rosterForCurrentScoringPeriod') or {}).get('entries')
            if not isinstance(entries,list):raise ValueError(f'Week {week}: historical boxscore lacks locked lineup for team {tid}')
            roster=[];slots=defaultdict(int);ids=set()
            for e in entries:
                slot=int(e.get('lineupSlotId',-1))
                if slot not in (*SLOTS.values(),BENCH,IR):raise ValueError(f'Week {week}: unexpected lineup slot {slot}')
                p=clean_player(e,week)
                if p is None:raise ValueError('Unexpected position in roster; check league lineup configuration')
                if p['id'] in ids:raise ValueError('Duplicate player on the same roster')
                ids.add(p['id']);all_rostered.add(p['id']);p['slot']=slot
                roster.append(p)
                if slot in SLOT_TO_POSITION:
                    slotname=SLOT_TO_POSITION[slot];slots[slotname]+=1
                    if slotname!='FLEX' and slotname!=p['pos']:raise ValueError('Ineligible starter in boxscore')
                    if slotname=='FLEX' and p['pos'] not in ('RB','WR','TE'):raise ValueError('Ineligible FLEX in boxscore')
            if dict(slots)!=REQUIRED:raise ValueError(f'Week {week}: team {tid} starter slots {dict(slots)} differ from expected {REQUIRED}')
            if len(roster)<9:raise ValueError('Incomplete historical roster')
            # Guard against returned current roster masquerading as historical.
            starter_sum=round(sum(p['points'] for p in roster if p['slot'] in SLOT_TO_POSITION),2)
            espn_score=s.get('totalPoints')
            if espn_score is None or abs(starter_sum-float(espn_score))>.15:
                raise ValueError(f'Week {week}: historical lineup score mismatch for team {tid}; '
                                 'do not substitute Tuesday current roster')
            canonical=expected_ids.get(tid)
            if canonical is None:raise ValueError('Historical boxscore contains unmapped ESPN team')
            expected=league_week.get(canonical)
            if expected is None or abs(starter_sum-expected)>.15:raise ValueError('Historical roster scoring disagrees with approved weekly team PF')
            observed[tid]=roster
    if set(observed)!=set(expected_ids):raise ValueError('Historical boxscore missing one or more teams')
    universe={}
    for raw in pool:
        p=clean_player(raw,week)
        if p is None:continue
        if p['id'] in universe:raise ValueError('Duplicate player in ranking pool')
        universe[p['id']]=p
    if not all_rostered.issubset(universe):
        raise ValueError(f'Full player pool missing {len(all_rostered-set(universe))} rostered players; cannot trust positional ranks')
    for roster in observed.values():
        for p in roster:
            other=universe[p['id']]
            if abs(p['points']-other['points'])>.011:
                raise ValueError(f'Week {week}: boxscore/pool point discrepancy for player {p["id"]}')
    counts={pos:sum(p['pos']==pos for p in universe.values()) for pos in BASE}
    minima={'QB':32,'RB':40,'WR':50,'TE':28,'K':25,'DST':28}
    if any(counts[k]<v for k,v in minima.items()):raise ValueError(f'ESPN player pool too small to rank NFL players: {counts}')
    return observed,universe


def qualified_sets(universe):
    """Tie-inclusive positional cutoffs, then ten additional FLEX players after excluding base qualified RB/WR/TE."""
    qualified={};cutoffs={}
    for pos,n in BASE.items():
        ranked=sorted((p for p in universe.values() if p['pos']==pos),key=lambda p:(-p['points'],p['id']))
        if len(ranked)<n:raise ValueError(f'Incomplete {pos} position rankings')
        threshold=ranked[n-1]['points']
        if threshold<=0:raise ValueError(f'Non-positive {pos} starter cutoff: incomplete weekly ranking universe')
        qualified[pos]={p['id'] for p in ranked if p['points']>=threshold}
        cutoffs[pos]=round(threshold,2)
    remaining=sorted((p for p in universe.values() if p['pos'] in ('RB','WR','TE')
                     and p['id'] not in qualified[p['pos']]),key=lambda p:(-p['points'],p['id']))
    if len(remaining)<10 or remaining[9]['points']<=0:raise ValueError('Incomplete FLEX scoring pool')
    flex_threshold=remaining[9]['points']
    qualified['FLEX']={p['id'] for p in remaining if p['points']>=flex_threshold}
    cutoffs['FLEX']=round(flex_threshold,2)
    return qualified,cutoffs


def qualifies(p,slot,sets):
    if slot=='FLEX':return p['pos'] in ('RB','WR','TE') and p['id'] in (sets[p['pos']]|sets['FLEX'])
    return p['pos']==slot and p['id'] in sets[slot]


def max_qualified_lineup(roster,sets):
    """Nine-slot exact matching. Counts only incremental *eligible* worthy hits; no duplicate player.
    Return optimal weighted half-units (16 max) and player IDs chosen per slot.
    """
    slots=['QB','RB','RB','WR','WR','TE','FLEX','K','DST']
    available=sorted((p for p in roster if p['slot']!=IR), key=lambda p:(p['slot']==BENCH,p['id'])) # starter-first, IR ineligible
    options=[[p for p in available if qualifies(p,slot,sets)] for slot in slots]
    best=(-1,());used=set()
    def rec(i,points,choices):
        nonlocal best
        if i==len(slots):
            if points>best[0]:best=(points,tuple(choices))
            return
        if points+sum(WEIGHT[s] for s in slots[i:])<best[0]:return
        rec(i+1,points,choices+[None])
        for p in options[i]:
            if p['id'] in used:continue
            used.add(p['id']);rec(i+1,points+WEIGHT[slots[i]],choices+[p['id']]);used.remove(p['id'])
    rec(0,0,[])
    return best[0],dict(zip((f'{slot}{sum(1 for s in slots[:i] if s==slot)+1}' for i,slot in enumerate(slots)),best[1]))


def analyze_week(observed,universe,week,espn_to_canonical):
    sets,cutoffs=qualified_sets(universe)
    output=[]
    for espn_id,roster in observed.items():
        active=[p for p in roster if p['slot'] in SLOT_TO_POSITION]
        by_position={p['id']:SLOT_TO_POSITION[p['slot']] for p in active}
        hits=[p for p in active if qualifies(p,by_position[p['id']],sets)]
        current=sum(WEIGHT[by_position[p['id']]] for p in hits)
        starter_best,_=max_qualified_lineup(active,sets)
        best,allocation=max_qualified_lineup(roster,sets)
        if best<starter_best or starter_best<current:raise AssertionError('Qualified lineup optimization is inconsistent')
        bench_qualified=[p for p in roster if p['slot']==BENCH and (p['id'] in sets[p['pos']] or (p['pos'] in ('RB','WR','TE') and p['id'] in sets['FLEX']))]
        chosen_bench=[p for p in bench_qualified if p['id'] in set(v for v in allocation.values() if v is not None)] if best>starter_best else []
        output.append({'teamId':espn_to_canonical[espn_id],'week':week,'weightedHits':current/2,'weightedMax':best/2,
            'weightedPossible':8,'swrPct':round(100*current/16,2),'qualifiedStarters':len(hits),'totalStarters':9,
            'missedWeighted':(best-starter_best)/2,'reassignmentWeighted':(starter_best-current)/2,
            'totalOpportunityWeighted':(best-current)/2,'benchQualifiedCount':len(bench_qualified),
            'potentiallyUsefulBenchCount':len(chosen_bench),
            'slots':[{'slot':by_position[p['id']],'player':p['name'],'position':p['pos'],'points':p['points'],
                      'worthy':qualifies(p,by_position[p['id']],sets)} for p in active],
            'benchOpportunities':[{'player':p['name'],'position':p['pos'],'points':p['points']} for p in chosen_bench]})
    return {'week':week,'cutoffs':cutoffs,'teams':sorted(output,key=lambda x:x['teamId'])}


def build(league,mapping,weeks,fixture_dir=None):
    if league.get('title')!='Fantasy 2K Infinity' or league.get('source')!='ESPN authenticated, baseline reconciled':raise ValueError('Wrong approved league dataset source')
    if int(mapping.get('league_id',-1))!=LEAGUE_ID or int(mapping.get('season',-1))!=YEAR:raise ValueError('Wrong team-ID map')
    ids={int(eid):int(cid) for cid,eid in mapping['baseline_to_espn'].items()}
    if len(ids)!=10 or {t['id'] for t in league['teams']}!=set(ids.values()):raise ValueError('Unverified team ID mapping')
    complete=int(league['completedThrough'])
    if complete<1:raise ValueError('Approved league has no completed weeks')
    by_id={int(t['id']):t for t in league['teams']}
    if len(by_id)!=10:raise ValueError('Duplicate approved team IDs')
    for tid,t in by_id.items():
        rows=t.get('weeks')
        if not isinstance(rows,list) or len(rows)!=complete:raise ValueError(f'Approved team {tid} does not have exactly {complete} completed weeks')
        if any(int(row.get('week',-1))!=i for i,row in enumerate(rows,1)):raise ValueError(f'Approved team {tid} has inconsistent week ordering')
        if abs(sum(float(row['pf']) for row in rows)-float(t['pf']))>.02:raise ValueError(f'Approved team {tid} weekly PF does not reconcile')
        for row in rows:
            opp=int(row['opp'])
            if opp==tid or opp not in by_id:raise ValueError('Invalid approved opponent ID')
            other=by_id[opp]['weeks'][int(row['week'])-1]
            if int(other['opp'])!=tid or abs(float(other['pf'])-float(row['pa']))>.02 or abs(float(other['pa'])-float(row['pf']))>.02:
                raise ValueError('Approved league matchups are not reciprocal')
    if any(w<1 or w>complete for w in weeks):raise ValueError('Only approved completed fantasy weeks can be analyzed')
    result={'leagueId':LEAGUE_ID,'season':YEAR,'completedThrough':complete,
            'generatedAt':datetime.now(timezone.utc).isoformat(),'method':'finalized historical boxscore + complete ESPN weekly player pool',
            'weights':{'skill':1,'K':0.5,'DST':0.5},'weeks':[]}
    for week in weeks:
        league_week={t['id']:t['weeks'][week-1]['pf'] for t in league['teams']}
        if fixture_dir:
            d=json.loads((Path(fixture_dir)/f'week_{week}_boxscore.json').read_text())
            pool=json.loads((Path(fixture_dir)/f'week_{week}_player_pool.json').read_text())['players']
        else:d,pool=fetch_week(week)
        rosters,universe=extract_week(d,pool,week,ids,league_week)
        result['weeks'].append(analyze_week(rosters,universe,week,ids))
        print(f'W{week}: validated 10 finalized lineups, {len(universe)} ranking candidates; '
              f'qualified starters + bench opportunities calculated (no owner data).')
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--league-data',required=True);ap.add_argument('--mapping',default='reference/team_id_map.json')
    ap.add_argument('--week',type=int,action='append',help='Approved completed week to fetch; defaults to all completed weeks')
    ap.add_argument('--fixture-dir',help='Offline synthetic test data only');ap.add_argument('--output',required=True);a=ap.parse_args()
    league=json.loads(Path(a.league_data).read_text());mapping=json.loads(Path(a.mapping).read_text())
    weeks=sorted(set(a.week or range(1,int(league['completedThrough'])+1)))
    result=build(league,mapping,weeks,a.fixture_dir)
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(f'Roster analysis ready for review: {len(weeks)} weeks; no public site was changed.')

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,IndexError) as exc:
        print(f'ROSTER VALIDATION FAILED: {exc}');raise SystemExit(1)