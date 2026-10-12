#!/usr/bin/env python3
"""Minimal independent source/host checks, reporting only HTTP codes and league IDs."""
import json,os,urllib.error,urllib.request
from pathlib import Path
s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
if not s2 or not swid:raise SystemExit("Missing configured ESPN secrets")
headers={"Cookie":f"espn_s2={s2}; SWID={swid}","Accept":"application/json",
         "User-Agent":"Fantasy2KInfinity-HistoricalHostCheck/1.0"}
root="/apis/v3/games/ffl"
targets=[("control_known_2022","lm-api-reads.fantasy.espn.com",
          "/seasons/2022/segments/0/leagues/1493036707?view=mTeam")]
for year in (2019,2020):
    for shape,path in (
        ("historical",f"/leagueHistory/1435116?seasonId={year}&view=mTeam"),
        ("modern",f"/seasons/{year}/segments/0/leagues/1435116?view=mTeam")):
        targets.append((f"bhm_{year}_{shape}","fantasy.espn.com",path))
records=[]
for label,host,path in targets:
    url=f"https://{host}{root}{path}"
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=35) as response:
            content=json.load(response)
        if isinstance(content,list):content=content[0] if len(content)==1 else {}
        rec={"target":label,"status":200,
             "returned_league_id":content.get("id") if isinstance(content,dict) else None,
             "returned_year":content.get("seasonId") if isinstance(content,dict) else None,
             "team_count":len(content.get("teams") or []) if isinstance(content,dict) else None}
    except urllib.error.HTTPError as e:rec={"target":label,"status":e.code}
    except (urllib.error.URLError,TimeoutError,ValueError) as e:
        rec={"target":label,"status":type(e).__name__}
    records.append(rec)
    print(f"{label}: status={rec['status']} id={rec.get('returned_league_id')}")
out=Path("output/bhm-pre2021-discovery")
out.mkdir(parents=True,exist_ok=True)
(out/"host_control_report.json").write_text(json.dumps(records,indent=2)+"\n")
