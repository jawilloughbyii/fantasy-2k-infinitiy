#!/usr/bin/env python3
"""Read-only ESPN 2014-17 historical scoring, standings & season-specific draft metadata probe.
No owner/member details, credentials, or raw ESPN payloads are saved or logged.
"""
import json,os,urllib.request,urllib.parse,urllib.error, pathlib, collections,math
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path("output/legacy-2014-17-verification")
DRAFT=json.loads((ROOT/"reference/historical_legacy_draft_picks_2014_2017.json").read_text())
SCORES=json.loads((ROOT/"reference/historical_regular_season_scores.json").read_text())
LEAGUE=791996
BASE="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
POSITION={1:"QB",2:"RB",3:"WR",4:"TE",5:"K",16:"D/ST",17:"P"}
def call(url,cookie,filter_obj=None):
    h={"Cookie":cookie,"Accept":"application/json","User-Agent":"Fantasy2K-Audit/1.0"}
    if filter_obj is not None:h["X-Fantasy-Filter"]=json.dumps(filter_obj,separators=(",",":"))
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=35) as response:
            return json.load(response),{"status":"ok"}
    except urllib.error.HTTPError as e:return None,{"status":"http_error","code":e.code}
    except (urllib.error.URLError,TimeoutError,ValueError) as e:return None,{"status":"request_error","type":type(e).__name__}
def history(year,view,cookie,fil=None):
    u=f"{BASE}/leagueHistory/{LEAGUE}?"+urllib.parse.urlencode([("seasonId",year),("view",view)])
    obj,status=call(u,cookie,fil)
    if isinstance(obj,list):obj=obj[0] if len(obj)==1 else None
    if obj is None or not isinstance(obj,dict):return None,status
    if obj.get("id")!=LEAGUE or obj.get("seasonId",year)!=year:return None,{"status":"identity_mismatch"}
    return obj,status
def safe_info(q):
    if not isinstance(q,dict):return None
    p=q.get("player") if isinstance(q.get("player"),dict) else q
    id=p.get("id",q.get("id"))
    if type(id) is not int:return None
    name=p.get("fullName") or p.get("name")
    position=p.get("defaultPositionId")
    if not isinstance(name,str) or not name.strip() or type(position) is not int:return None
    return {"player_id":id,"name":name.strip(),"position_id":position,"position":POSITION.get(position),"pro_team_id":p.get("proTeamId")}
def find_players(response):
    if isinstance(response,list):items=response
    elif isinstance(response,dict):items=response.get("players") or []
    else:items=[]
    found={}
    for entry in items:
        info=safe_info(entry)
        if info is not None:found[info["player_id"]]=info
    return found,len(items)
def official(t):
    ov=(t.get("record") or {}).get("overall") or {}
    keys=("wins","losses","ties","pointsFor","pointsAgainst","percentage","rank","gamesBack")
    return {k:ov[k] for k in keys if isinstance(ov.get(k),(int,float)) and not isinstance(ov[k],bool)}
def scoring(src):
    s=(src.get("settings") or {}).get("scoringSettings") or {}
    roster=(src.get("settings") or {}).get("rosterSettings") or {}
    raw=s.get("scoringItems") or []
    items=[]
    for row in raw:
        if not isinstance(row,dict):continue
        item={}
        for k in ("statId","points","isReverseItem","pointsOverrides","scoringType","statSourceId"):
            if k in row and (isinstance(row[k],(int,float,bool)) or (k=="pointsOverrides" and isinstance(row[k],(dict,list)))):
                item[k]=row[k]
        items.append(item)
    items.sort(key=lambda x:x.get("statId",-1))
    return {"scoring_type":s.get("scoringType"),"item_count":len(raw),
            "items":items,"lineup_slot_counts":roster.get("lineupSlotCounts"),
            "roster_settings_keys":sorted(k for k in roster if k not in ("owners","members"))}
def get_pool(year,cookie,ids,variant):
    filt=({"players":{"filterIds":{"value":ids}}}
          if variant in ("history_kona","history_card","league_default") else {"filterIds":{"value":ids}})
    if variant=="history_kona":return history(year,"kona_player_info",cookie,filt)
    if variant=="history_card":return history(year,"kona_playercard",cookie,filt)
    if variant=="league_default":
        url=f"{BASE}/seasons/{year}/segments/0/leaguedefaults/1?view=kona_player_info"
    else:url=f"{BASE}/seasons/{year}/players?view=players_wl"
    return call(url,cookie,filt)
def main():
    s2=os.getenv("ESPN_S2","").strip();swid=os.getenv("ESPN_SWID","").strip()
    if not (s2 and swid):raise SystemExit("SAFE ERROR: missing existing Actions credentials")
    cookie=f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True,exist_ok=True)
    allresult={"source_league_id":LEAGUE,"status":"PRIVATE_RESEARCH_NOT_APPROVED","seasons":[]}
    for year in range(2014,2018):
        src,diag=history(year,"mSettings",cookie)
        if not src:raise ValueError(f"{year} mSettings inaccessible: {diag}")
        rules=scoring(src)
        tm,td=history(year,"mTeam",cookie)
        if not tm:raise ValueError(f"{year} mTeam inaccessible: {td}")
        teams=tm.get("teams") or []
        if len(teams)!=10:raise ValueError(f"{year} lacks ten original teams")
        saved=next(s for s in SCORES["seasons"] if s["year"]==year)
        ar={r["espn_team_id"]:r for r in json.loads((ROOT/f"research/espn-791996-2014-2017/season_{year}.json").read_text())["standings"]["rows"]}
        standings=[]
        for t in teams:
            tid=t.get("id")
            if tid not in ar:raise ValueError("missing team")
            standings.append({"team_id":tid,"team_name":next(z["name"] for z in saved["teams"] if z["espn_team_id"]==tid),
                              "espn_overall":official(t),"derived":{k:ar[tid][k] for k in ("wins","losses","ties","points_for","points_against")}})
        ds=next(s for s in DRAFT["seasons"] if s["year"]==year)
        ids=[p["player_id"] for p in ds["picks"]]
        full={}; diagnostics=[]
        for variant in ("history_kona","history_card","season_players","league_default"):
            source,details=get_pool(year,cookie,ids,variant)
            found,size=find_players(source)
            matched={i:found[i] for i in ids if i in found}
            diagnostics.append({"route":variant,**details,"returned_entries":size,"matching_draft_ids":len(matched)})
            for i,record in matched.items():
                if i not in full:full[i]={**record,"source_route":variant}
        missing=[i for i in ids if i not in full]
        result={"year":year,"league_id":LEAGUE,"scoring":rules,"standings":standings,
                "draft_player_lookup":{"matched":len(full),"missing":len(missing),"negative_id_count":sum(i<0 for i in ids),
                  "diagnostics":diagnostics,"players":list(full.values()),"missing_ids":missing}}
        allresult["seasons"].append(result)
        print(f"{year}: scoring_items={rules['item_count']}, official_record_count={sum(bool(t['espn_overall']) for t in standings)}, drafted_player_names={len(full)}/170")
        print(f"{year} routes "+json.dumps(diagnostics,separators=(",",":")))
        for row in standings:print(f"STANDING {year} slot={row['team_id']} source="+json.dumps(row["espn_overall"],separators=(",",":"))+" derived="+json.dumps(row["derived"],separators=(",",":")))
    (OUT/"source_review.json").write_text(json.dumps(allresult,ensure_ascii=False,indent=2)+"\n")
    print("Sanitized source review exported (no member, owner, credential or raw ESPN response).")
if __name__=="__main__":
    try:main()
    except (ValueError,TypeError,KeyError) as e:raise SystemExit("SAFE ERROR: "+str(e))
