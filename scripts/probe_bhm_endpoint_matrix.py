#!/usr/bin/env python3
"""Private narrow ESPN historical endpoint shape probe; no response bodies published."""
import json,os,urllib.parse,urllib.request,urllib.error
from pathlib import Path
ID=1435116
s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
if not s2 or not swid:raise SystemExit("Missing configured ESPN credentials")
base="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
results=[]
for year in range(2015,2022):
 for endpoint in ("leagueHistory","modern"):
  root=(f"{base}/leagueHistory/{ID}?seasonId={year}" if endpoint=="leagueHistory"
        else f"{base}/seasons/{year}/segments/0/leagues/{ID}")
  for view in ("", "mTeam", "mSettings", "mMatchupScore"):
   url=root+("&" if "?" in root else "?")+"view="+view if view else root
   req=urllib.request.Request(url,headers={"Cookie":f"espn_s2={s2}; SWID={swid}",
       "Accept":"application/json","User-Agent":"Fantasy2KInfinity-ArchivedLeagueProbe/1.0"})
   try:
    with urllib.request.urlopen(req,timeout=30) as response:
     data=json.load(response)
    if isinstance(data,list):data=data[0] if len(data)==1 else {}
    result={"year":year,"endpoint":endpoint,"view":view or "none","http":200,
            "returned_league_id":data.get("id") if isinstance(data,dict) else None,
            "returned_season":data.get("seasonId") if isinstance(data,dict) else None,
            "team_count":len(data.get("teams") or []) if isinstance(data,dict) else None,
            "keys":sorted(data.keys()) if isinstance(data,dict) else []}
   except urllib.error.HTTPError as e:
    result={"year":year,"endpoint":endpoint,"view":view or "none","http":e.code}
   except (urllib.error.URLError,TimeoutError,ValueError) as e:
    result={"year":year,"endpoint":endpoint,"view":view or "none","error":type(e).__name__}
   results.append(result)
   print(f"{year} {endpoint} {view or 'no-view'}: {result.get('http',result.get('error'))}; teams={result.get('team_count','?')}")
out=Path("output/bhm-pre2021-discovery")
out.mkdir(parents=True,exist_ok=True)
(out/"endpoint_matrix.json").write_text(json.dumps(results,indent=2)+"\n")
print("No public data or manager information changed.")
