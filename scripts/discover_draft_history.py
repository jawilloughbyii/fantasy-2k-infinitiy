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



def enrich(year, league, cookie, data):
    ids={int(p["playerId"]) for p in data["picks"]}
    # Use year-specific ESPN player records, not 2026 rosters (retired players may disappear).
    url=(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
         f"seasons/{year}/players?scoringPeriodId=0&view=players_wl")
    filt={"filterIds":{"value":sorted(ids)}}
    req=urllib.request.Request(url, headers={
        "Cookie":cookie,"Accept":"application/json",
        "X-Fantasy-Filter":json.dumps(filt),
        "User-Agent":"Fantasy2KInfinity-DraftResearch/1.0"})
    with urllib.request.urlopen(req, timeout=65) as response:
        source=json.load(response)
    if not isinstance(source,list):
        raise ValueError(f"{year}: year-specific player endpoint has unexpected shape")
    candidates={}
    for entry in source:
        record=entry.get("player") or entry
        pid=record.get("id",entry.get("id"))
        if type(pid) is int and pid in ids and isinstance(record.get("fullName"),str) and record["fullName"].strip():
            candidates[pid]={"name":record["fullName"].strip(),"position_id":record.get("defaultPositionId")}
    missing=ids-set(candidates)
    # Retired and legacy special-teams players: look for them by ID in the same
    # historical league context, never invent or substitute modern player names.
    if missing:
        query=urllib.parse.urlencode([("view","kona_player_info")])
        lurl=(f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
              f"seasons/{year}/segments/0/leagues/{league}?{query}")
        req=urllib.request.Request(lurl,headers={
            "Cookie":cookie,"Accept":"application/json",
            "X-Fantasy-Filter":json.dumps({"players":{"filterIds":{"value":sorted(missing)}}}),
            "User-Agent":"Fantasy2KInfinity-DraftResearch/1.0"})
        with urllib.request.urlopen(req,timeout=65) as response:pool=json.load(response)
        for entry in pool.get("players") or []:
            record=(entry.get("playerPoolEntry") or entry).get("player") or entry.get("player") or {}
            pid=record.get("id", (entry.get("playerPoolEntry") or entry).get("id",entry.get("id")))
            if type(pid) is int and pid in missing and isinstance(record.get("fullName"),str) and record["fullName"].strip():
                candidates[pid]={"name":record["fullName"].strip(),"position_id":record.get("defaultPositionId")}
    for pick in data["picks"]:
        meta=candidates.get(pick["playerId"])
        pick["playerName"]=meta["name"] if meta else None
        pick["positionId"]=meta["position_id"] if meta else None
    unresolved=sorted(ids-set(candidates))
    data["metadata"]["resolved_player_names"]=len(data["picks"])-sum(p["playerName"] is None for p in data["picks"])
    data["metadata"]["unresolved_player_ids"]=unresolved
    data["metadata"]["name_source"]="ESPN season-specific players_wl with ESPN same-season league fallback"
    return data


def main():
    s2,swid=os.environ.get("ESPN_S2","").strip(),os.environ.get("ESPN_SWID","").strip()
    if not s2 or not swid:raise RuntimeError("Missing GitHub Actions ESPN credentials")
    OUT.mkdir(parents=True,exist_ok=True)
    summary=[]
    for year,league in LEAGUES.items():
        try:
            cookie=f"espn_s2={s2}; SWID={swid}"
            meta,data=process(year,league,get(year,league,cookie))
            data=enrich(year,league,cookie,data)
            meta=data["metadata"]
            (OUT/f"draft_{year}.json").write_text(json.dumps(data,indent=2)+"\n")
        except urllib.error.HTTPError as e:
            meta={"year":year,"source_league_id":league,"status":f"http_{e.code}",
                  "pick_count":None}
        except (urllib.error.URLError,TimeoutError,ValueError) as e:
            meta={"year":year,"source_league_id":league,
                  "status":"error_"+type(e).__name__, "pick_count":None}
        summary.append(meta)
        print(f"{year}: {meta['status']}; picks={meta.get('pick_count')}; "
              f"rounds={meta.get('round_count')}; teams={meta.get('drafting_team_count')}; "
              f"names={meta.get('resolved_player_names')}; unresolved={len(meta.get('unresolved_player_ids',[]))}")
    (OUT/"coverage_report.json").write_text(json.dumps({
        "scope":"private only, not published",
        "seasons":summary},indent=2)+"\n")
    print("Draft research complete. No public history or dashboard changed.")


if __name__=="__main__":
    main()
