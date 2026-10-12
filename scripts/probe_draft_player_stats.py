#!/usr/bin/env python3
"""Read-only probe for original-season weekly scoring on drafted players."""
import json,os,urllib.parse,urllib.request
from pathlib import Path
D=json.loads((Path(__file__).resolve().parents[1]/"reference/historical_draft_picks.json").read_text())
s2,swid=(os.environ.get("ESPN_S2","").strip(),os.environ.get("ESPN_SWID","").strip())
if not s2 or not swid:raise SystemExit("Missing ESPN credentials")
for season in D["seasons"][:2]:
    y,lid=season["year"],season["league_id"]
    ids=[p["player_id"] for p in season["picks"][:20]]
    params=urllib.parse.urlencode([("view","kona_player_info"),("scoringPeriodId",1)])
    url=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{y}/segments/0/leagues/{lid}?{params}"
    f={"players":{"limit":250,"offset":0,"filterIds":{"value":ids},"filterStatsForTopScoringPeriodIds":{"value":1,"additionalValue":[f"00{y}"]}}}
    req=urllib.request.Request(url,headers={"Cookie":f"espn_s2={s2}; SWID={swid}","Accept":"application/json","X-Fantasy-Filter":json.dumps(f),"User-Agent":"Fantasy2KInfinity-DraftValue/1.0"})
    with urllib.request.urlopen(req,timeout=60) as response:data=json.load(response)
    ps=data.get("players") or []
    print(f"{y}: returned {len(ps)} drafted players; requested {len(ids)}")
    for row in ps[:3]:
        e=row.get("playerPoolEntry") or row
        player=e.get("player") or row.get("player") or {}
        st=player.get("stats") or e.get("stats") or []
        safe=[{"period":x.get("scoringPeriodId"),"season":x.get("seasonId"),"source":x.get("statSourceId"),"split":x.get("statSplitTypeId"),"appliedTotal":x.get("appliedTotal")} for x in st[:15]]
        print(json.dumps({"player_id":e.get("id",row.get("id")),"stats_count":len(st),"stats_example":safe}))
