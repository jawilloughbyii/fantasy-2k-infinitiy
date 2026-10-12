#!/usr/bin/env python3
"""Private, non-sensitive response-shape probes for original-season ESPN player stats."""
import json,os,urllib.error,urllib.parse,urllib.request
from pathlib import Path
D=json.loads((Path(__file__).resolve().parents[1]/"reference/historical_draft_picks.json").read_text())
s2,swid=(os.environ.get("ESPN_S2","").strip(),os.environ.get("ESPN_SWID","").strip())
if not s2 or not swid:raise SystemExit("Missing ESPN credentials")
cookie=f"espn_s2={s2}; SWID={swid}"
for season in D["seasons"][:2]:
 y,lid=season["year"],season["league_id"]
 ids=[p["player_id"] for p in season["picks"][:20]]
 base=f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{y}"
 league=f"{base}/segments/0/leagues/{lid}"
 exact={"players":{"limit":250,"offset":0,"filterIds":{"value":ids}}}
 standard={"players":{"limit":500,"offset":0,"filterSlotIds":{"value":[0,2,4,6,16,17,18]},"sortPercOwned":{"sortPriority":1,"sortAsc":False},"filterStatsForTopScoringPeriodIds":{"value":18,"additionalValue":[f"00{y}"]}}}
 variants=[
 ("standalone_players_wl",f"{base}/players?scoringPeriodId=1&view=players_wl",{"filterIds":{"value":ids}}),
 ("league_kona_exact",league+"?"+urllib.parse.urlencode([("view","kona_player_info"),("scoringPeriodId",1)]),exact),
 ("league_kona_standard",league+"?"+urllib.parse.urlencode([("view","kona_player_info"),("scoringPeriodId",1)]),standard),
 ]
 for label,url,filt in variants:
  req=urllib.request.Request(url,headers={"Cookie":cookie,"Accept":"application/json","X-Fantasy-Filter":json.dumps(filt),"User-Agent":"Fantasy2KInfinity-DraftValue/1.0"})
  try:
   with urllib.request.urlopen(req,timeout=60) as response: data=json.load(response)
   ps=(data if isinstance(data,list) else data.get("players") or [])
   samples=[]
   for row in ps[:4]:
    e=row.get("playerPoolEntry") or row;player=e.get("player") or row.get("player") or e
    st=player.get("stats") or e.get("stats") or []
    samples.append({"id":e.get("id",row.get("id")),"statsCount":len(st),"stats":[{"period":x.get("scoringPeriodId"),"season":x.get("seasonId"),"source":x.get("statSourceId"),"split":x.get("statSplitTypeId"),"total":x.get("appliedTotal")} for x in st[:8]]})
   print(json.dumps({"year":y,"variant":label,"rows":len(ps),"samples":samples}))
  except urllib.error.HTTPError as exc:
   print(json.dumps({"year":y,"variant":label,"httpStatus":exc.code}))
  except (ValueError,urllib.error.URLError,TimeoutError) as exc:
   print(json.dumps({"year":y,"variant":label,"errorType":type(exc).__name__}))
