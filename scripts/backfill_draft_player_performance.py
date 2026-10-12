#!/usr/bin/env python3
"""Read-only original-season ESPN player scoring: ALL eligible players, weeks 1–14.
Output private, minimized per-player performance, no owner names/credentials/rosters."""
import json,os,urllib.parse,urllib.request,urllib.error,math,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"reference/historical_draft_picks.json").read_text())
H=json.loads((ROOT/"reference/historical_regular_season_scores.json").read_text())
OUT=ROOT/"output/draft-performance"
PAGE=500
SLOT_TO_POS={1:"QB",2:"RB",3:"WR",4:"TE",5:"K",7:"P",16:"D/ST"}
SLOTS=[0,2,4,6,16,17,18]
def scored_week(stats,y,week):
    exact=[];untagged=[]
    for st in stats:
        if st.get("scoringPeriodId")!=week:continue
        if st.get("seasonId") not in (None,y):continue
        if st.get("statSourceId",st.get("statTypeId"))!=0:continue
        if st.get("statSplitTypeId") not in (None,1):continue
        pt=st.get("appliedTotal")
        if pt is None:continue
        if not isinstance(pt,(int,float)) or not math.isfinite(pt):raise ValueError("Nonfinite points")
        (exact if st.get("seasonId") is not None else untagged).append(float(pt))
    hits=exact or untagged
    if hits and max(hits)-min(hits)>.011:raise ValueError(f"{y} week {week}: conflicting actuals")
    return round(hits[0],2) if hits else 0.0

def fetch(url,cookie,filter):
    req=urllib.request.Request(url,headers={
        "Cookie":cookie,"Accept":"application/json",
        "X-Fantasy-Filter":json.dumps(filter,separators=(",",":")),
        "User-Agent":"Fantasy2KInfinity-DraftPerformance/1.0"})
    with urllib.request.urlopen(req,timeout=65) as response:return json.load(response)

def season_data(season,cookie):
    y,lid=season["year"],season["league_id"]
    q=urllib.parse.urlencode([("view","kona_player_info"),("scoringPeriodId",1)])
    url=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{y}/segments/0/leagues/{lid}?{q}"
    universe={}
    for offset in range(0,6000,PAGE):
        f={"players":{"limit":PAGE,"offset":offset,
             "filterSlotIds":{"value":SLOTS},
             "sortPercOwned":{"sortPriority":1,"sortAsc":False},
             "filterStatsForTopScoringPeriodIds":{"value":18,"additionalValue":[f"00{y}"]}}}
        data=fetch(url,cookie,f)
        if data.get("id")!=lid:raise ValueError(f"{y}: league mismatch")
        rows=data.get("players")
        if not isinstance(rows,list) or (offset==0 and not rows):raise ValueError(f"{y}: empty/incomplete player pool")
        for row in rows:
            e=row.get("playerPoolEntry") or row
            player=e.get("player") or row.get("player") or {}
            pid=e.get("id",row.get("id"))
            position=SLOT_TO_POS.get(player.get("defaultPositionId"))
            if not isinstance(pid,int) or position is None:continue
            if pid in universe:raise ValueError(f"{y}: paginated player pool repeats ID {pid}")
            stats=player.get("stats") or e.get("stats") or []
            weekly=[scored_week(stats,y,w) for w in range(1,15)]
            universe[pid]={"player_id":pid,"position":position,"weekly":weekly,
                           "regular_pf":round(sum(weekly),2),
                           "weeks_with_stats":sum(any(st.get("scoringPeriodId")==w and
                              st.get("seasonId") in (None,y) and st.get("statSourceId",st.get("statTypeId"))==0
                              and st.get("statSplitTypeId") in (None,1) and st.get("appliedTotal") is not None
                              for st in stats) for w in range(1,15))}
        print(f"{y}: player pool page offset={offset} records={len(rows)}")
        if len(rows)<PAGE:break
    else:raise ValueError(f"{y}: player pagination exceeded bounded limit")
    missing={p["player_id"] for p in season["picks"]}-set(universe)
    counts=collections.Counter(p["position"] for p in universe.values())
    # Sampling a pool that misses ANY drafted player is unsafe for draft grades.
    if missing:raise ValueError(f"{y}: {len(missing)} drafted player IDs missing in full pool; no publication")
    for pos,required in {"QB":30,"RB":60,"WR":60,"TE":30,"K":10,"D/ST":10}.items():
        if counts[pos]<required:raise ValueError(f"{y}: insufficient {pos} pool ({counts[pos]})")
    if y<2023 and counts["P"]<10:raise ValueError(f"{y}: expected archived punters")
    if not all(len(x["weekly"])==14 for x in universe.values()):raise ValueError("Weekly coverage error")
    season_counts={"year":y,"league_id":lid,"all_players":len(universe),
                   "drafted_player_count":len(season["picks"]),"missing_drafted_ids":0,
                   "positions":dict(sorted(counts.items()))}
    return {"metadata":season_counts,"players":sorted(universe.values(),key=lambda x:x["player_id"])}

def main():
    s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("Missing ESPN secrets")
    cookie=f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True,exist_ok=True)
    out=[]
    for season in D["seasons"][:5]:
        y=season["year"]
        obj=season_data(season,cookie)
        (OUT/f"player_performance_{y}.json").write_text(json.dumps(obj,separators=(",",":"))+"\n")
        out.append(obj["metadata"])
        print(f"{y}: PASS {obj['metadata']['all_players']} player records, ALL "
              f"{obj['metadata']['drafted_player_count']} draft picks matched")
    (OUT/"coverage_report.json").write_text(json.dumps({"status":"verified_source_coverage_not_graded",
        "scoring_periods":list(range(1,15)),"seasons":out},indent=2)+"\n")
    print("Original-year weekly performance extracted privately. No grades or dashboard changed.")

if __name__=="__main__":
    try:main()
    except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
        raise SystemExit("SAFE ERROR: "+ (f"HTTP {e.code}" if isinstance(e,urllib.error.HTTPError) else str(e)))
