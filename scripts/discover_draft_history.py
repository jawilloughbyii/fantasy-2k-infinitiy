#!/usr/bin/env python3
"""Private 2021–2026 ESPN draft coverage probe. No writes to public dashboard."""
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

LEAGUES = {2021:1493036707, 2022:1493036707, 2023:418244680,
           2024:418244680, 2025:418244680, 2026:418244680}
OUT = Path("output/draft-coverage")
FIELDS = ("playerId", "teamId", "overallPickNumber", "roundId", "roundPickNumber",
          "bidAmount", "keeper", "autoDraftTypeId")


def get(year, league, cookie):
    query=urllib.parse.urlencode([("view","mDraftDetail"),("view","mSettings")])
    url=(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
         f"seasons/{year}/segments/0/leagues/{league}?{query}")
    req=urllib.request.Request(url, headers={
        "Cookie":cookie,"Accept":"application/json","User-Agent":"Fantasy2KInfinity-DraftResearch/1.0"
    })
    with urllib.request.urlopen(req, timeout=45) as f:
        payload=json.load(f)
    if isinstance(payload,list):
        if len(payload)!=1:raise ValueError(f"{year}: unexpected API array response")
        payload=payload[0]
    if int(payload.get("id",-1))!=league:
        raise ValueError(f"{year}: incorrect league ID")
    return payload


def process(year, league, payload):
    details=payload.get("draftDetail") or {}
    picks=details.get("picks")
    if picks is None:
        picks=[]
    if not isinstance(picks,list):
        raise ValueError(f"{year}: draft picks not an array")
    drafted=details.get("drafted")
    sanitized=[]
    for pick in picks:
        entry={key:pick.get(key) for key in FIELDS}
        if not all(isinstance(entry[key],int) for key in ("playerId","teamId","roundId")):
            raise ValueError(f"{year}: invalid draft pick identifiers")
        if not isinstance(entry["overallPickNumber"],int):
            raise ValueError(f"{year}: no overall pick number")
        sanitized.append(entry)
    numbers=[p["overallPickNumber"] for p in sanitized]
    if len(set(numbers))!=len(numbers):
        raise ValueError(f"{year}: duplicate overall pick numbers")
    rounds=sorted({int(p["roundId"]) for p in sanitized})
    team_ids=sorted({int(p["teamId"]) for p in sanitized})
    settings=payload.get("settings") or {}
    draft_settings=settings.get("draftSettings") or {}
    meta={
      "year":year,"source_league_id":league,"drafted":drafted,
      "in_progress":details.get("inProgress"),"complete_date":details.get("completeDate"),
      "draft_type":draft_settings.get("type"),
      "expected_team_count":10,
      "pick_count":len(sanitized),
      "round_count":len(rounds),"rounds":rounds,
      "drafting_team_count":len(team_ids),
      "team_ids":team_ids,
      "has_unique_overall_picks":True,
      "missing_player_ids":sum(not p.get("playerId") for p in sanitized),
      "status":"retrieved" if sanitized else "no_picks_returned",
    }
    private={"metadata":meta,"picks":sorted(sanitized,key=lambda p:p["overallPickNumber"]),
             "scope":"private research; no owner IDs or cookies; draft player names not yet resolved"}
    return meta,private


def main():
    s2,swid=os.environ.get("ESPN_S2","").strip(),os.environ.get("ESPN_SWID","").strip()
    if not s2 or not swid:raise RuntimeError("Missing GitHub Actions ESPN credentials")
    OUT.mkdir(parents=True,exist_ok=True)
    summary=[]
    for year,league in LEAGUES.items():
        try:
            meta,data=process(year,league,get(year,league,
                                  f"espn_s2={s2}; SWID={swid}"))
            (OUT/f"draft_{year}.json").write_text(json.dumps(data,indent=2)+"\n")
        except urllib.error.HTTPError as e:
            meta={"year":year,"source_league_id":league,"status":f"http_{e.code}",
                  "pick_count":None}
        except (urllib.error.URLError,TimeoutError,ValueError) as e:
            meta={"year":year,"source_league_id":league,
                  "status":"error_"+type(e).__name__, "pick_count":None}
        summary.append(meta)
        print(f"{year}: {meta['status']}; picks={meta.get('pick_count')}; "
              f"rounds={meta.get('round_count')}; teams={meta.get('drafting_team_count')}")
    (OUT/"coverage_report.json").write_text(json.dumps({
        "scope":"private only, not published",
        "seasons":summary},indent=2)+"\n")
    print("Draft research complete. No public history or dashboard changed.")


if __name__=="__main__":
    main()
