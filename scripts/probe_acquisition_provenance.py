#!/usr/bin/env python3
"""Private ESPN acquisition-DNA feasibility audit. NO production writes.

Only aggregated roster coverage, endpoint status and non-identifying fantasy slot
counts are emitted; never save raw ESPN response, member/owner info or cookies.
Weekly historical roster calls may be ignored by ESPN and MUST be compared before
calling any lineup historical. Transaction fetch is a structural probe, not proof
of completeness or chronological acquisition provenance.
"""
import collections,json,os,pathlib,urllib.error,urllib.parse,urllib.request,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=pathlib.Path("output/acquisition-provenance-audit")
ARCHIVE=json.loads((ROOT/"reference/historical_regular_season_scores.json").read_text())
Y={2014:791996,2015:791996,2016:791996,2017:791996,
   2021:1493036707,2022:1493036707,2023:418244680,
   2024:418244680,2025:418244680,2026:418244680}
PERIODS={2014:[1,2,14],2015:[1,2,14],2016:[1,2,14],2017:[1,2,14],
         2021:[1,2,14],2022:[1,2,14],2023:[1,2,14],2024:[1,2,14],
         2025:[1,2,14],2026:[1,2,4]}
BASE="https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
def fetch(year,view,cookie,week=None,filter_=None):
    league=Y[year]
    if year<=2017:
        base=f"{BASE}/leagueHistory/{league}"
        query=[("seasonId",year)]
    else:
        base=f"{BASE}/seasons/{year}/segments/0/leagues/{league}"
        query=[]
    query.append(("view",view))
    if week is not None:query.append(("scoringPeriodId",week))
    h={"Cookie":cookie,"Accept":"application/json","User-Agent":"Fantasy2K-Provenance-Audit/1.0"}
    if filter_ is not None:h["X-Fantasy-Filter"]=json.dumps(filter_,separators=(",",":"))
    req=urllib.request.Request(base+"?"+urllib.parse.urlencode(query),headers=h)
    try:
        with urllib.request.urlopen(req,timeout=28) as res:raw=json.load(res)
    except urllib.error.HTTPError as e:return None,{"status":"http_error","http_code":e.code}
    except (urllib.error.URLError,TimeoutError,ValueError) as e:return None,{"status":"request_error","kind":type(e).__name__}
    if isinstance(raw,list):raw=raw[0] if len(raw)==1 else None
    if not isinstance(raw,dict):return None,{"status":"invalid_shape"}
    if raw.get("id")!=league or raw.get("seasonId",year)!=year:return None,{"status":"identity_mismatch"}
    return raw,{"status":"ok"}
def roster(raw):
    teams=raw.get("teams")
    if not isinstance(teams,list):return {"status":"no_teams","team_count":0},None
    found={};unknown_entry=0;invalid_id=0;empty=0;source_fields=collections.Counter()
    for team in teams:
        tid=team.get("id")
        if type(tid)!=int or tid not in range(1,11):return {"status":"bad_teams"},None
        ent=(team.get("roster") or {}).get("entries")
        if not isinstance(ent,list):empty+=1;continue
        starters=[];full=[]
        for entry in ent:
            if not isinstance(entry,dict):unknown_entry+=1;continue
            slot=entry.get("lineupSlotId")
            pid=entry.get("playerId")
            if type(pid)!=int:
                pool=entry.get("playerPoolEntry") or {}
                pid=pool.get("id")
                if type(pid)!=int:pid=(pool.get("player") or {}).get("id")
            if type(pid)!=int or pid==0:invalid_id+=1;continue
            if type(slot)!=int:unknown_entry+=1;continue
            full.append((pid,slot))
            if slot not in (20,21):starters.append((pid,slot))  # ESPN 23 is the valid FLEX starter slot
            for k in ("acquisitionType","acquisitionDate","playerPoolEntry"):source_fields[k]+=int(k in entry)
        found[tid]={"all":sorted(full),"starters":sorted(starters),"slot_counts":dict(sorted(collections.Counter(s for _,s in starters).items()))}
    if set(found)!=set(range(1,11)):return {"status":"missing_team_roster","team_count":len(found),"empty_team_rosters":empty},None
    output={"status":"ok","team_count":len(found),"roster_entries":sum(len(x["all"]) for x in found.values()),
      "starters_per_team":sorted(len(x["starters"]) for x in found.values()),
      "starter_slot_patterns":sorted([list(x["slot_counts"].items()) for x in found.values()]),
      "invalid_player_entries":invalid_id,"invalid_slot_entries":unknown_entry,
      "entry_fields_present":dict(source_fields)}
    return output,found
def transaction_summary(raw):
    if raw is None:return {"status":"missing"}
    obj=raw.get("transactions")
    if not isinstance(obj,list):return {"status":"no_transaction_list","present_top_level_keys":sorted(k for k in raw.keys() if k in ("transactions","transactionCounter","status","seasonId","id"))}
    counts=collections.Counter();keys=collections.Counter();items_count=0
    for t in obj:
        if not isinstance(t,dict):continue
        typ=t.get("type");typ=typ if isinstance(typ,str) else "<other>"
        counts[typ]+=1
        for k in ("id","type","status","processDate","proposedDate","executionType","items","bidAmount","relatedTransactionId"):
            keys[k]+=int(k in t)
        items_count+=len(t.get("items") or []) if isinstance(t.get("items"),list) else 0
    type_examples=collections.Counter()
    status_examples=collections.Counter()
    item_key_counts=collections.Counter()
    item_action_counts=collections.Counter()
    effective_dates=[]
    for t in obj:
        if not isinstance(t,dict):continue
        if isinstance(t.get("status"),str):status_examples[t["status"]]+=1
        if isinstance(t.get("type"),str):type_examples[t["type"]]+=1
        for key in ("processDate","proposedDate"):
            if type(t.get(key)) in (int,float) and t[key]>0:
                effective_dates.append((key,datetime.datetime.fromtimestamp(t[key]/1000,datetime.timezone.utc).date().isoformat()))
        for item in t.get("items") or []:
            if not isinstance(item,dict):continue
            for key in item:
                if key in ("type","playerId","teamId","fromTeamId","toTeamId","status","rosterForCurrentScoringPeriod","rosterForFutureScoringPeriod","lineupSlotId"):
                    item_key_counts[key]+=1
            if isinstance(item.get("type"),str):item_action_counts[item["type"]]+=1
    return {"status":"returned","transaction_count":len(obj),"transaction_types":dict(counts),"selected_field_counts":dict(keys),"item_count":items_count,
            "transaction_counter_present":"transactionCounter" in raw,
            "item_fields":dict(item_key_counts),"item_actions":dict(item_action_counts),
            "status_counts":dict(status_examples),
            "date_window":{"min":min((v for k,v in effective_dates),default=None),"max":max((v for k,v in effective_dates),default=None)}}
def main():
    s2=os.getenv("ESPN_S2","").strip();swid=os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: existing Actions ESPN secrets missing")
    cookie=f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True,exist_ok=True)
    all_report=[]
    for year in Y:
        times=[]
        snapshots={}
        for week in PERIODS[year]:
            raw,stat=fetch(year,"mRoster",cookie,week)
            summ,ro=(roster(raw) if raw else ({"status":"unavailable"},None))
            times.append({"week":week,**stat,"roster":summ})
            if ro:snapshots[week]=ro
        compares=[]
        for a,b in zip(PERIODS[year][:-1],PERIODS[year][1:]):
            if a in snapshots and b in snapshots:
                same=sum(snapshots[a][id]["starters"]==snapshots[b][id]["starters"] for id in range(1,11))
                diff=sum(len(set(snapshots[a][id]["starters"])^set(snapshots[b][id]["starters"])) for id in range(1,11))
                compares.append({"weeks":[a,b],"identical_starter_team_slots":same,"changed_starter_player_slot_entries":diff,
                                 "possible_ignored_week_filter":same==10})
        trans=[]
        for view,f in [("mTransactions2",None),("mTransactions2",{"transactions":{"limit":1000}}),("mTransactions",None),("mDraftDetail",None)]:
            raw,stat=fetch(year,view,cookie,filter_=f)
            if view=="mDraftDetail":
                details=(raw or {}).get("draftDetail") or {}
                extra={"status":"retrieved" if raw else "unavailable","pick_count":len(details.get("picks") or []) if isinstance(details.get("picks"),list) else None}
            else:extra=transaction_summary(raw)
            trans.append({"view":view,"filter_provided":f is not None,**stat,"result":extra})
        all_report.append({"year":year,"league_id":Y[year],"rosters":times,"cross_week_checks":compares,"endpoint_probes":trans})
        print(f"{year}: rosters="+json.dumps([{"week":x["week"],"result":x["roster"]["status"],"starters":x["roster"].get("starters_per_team",[])} for x in times],separators=(",",":")))
        print(f"{year}: changed-week-checks="+json.dumps(compares,separators=(",",":")))
        print(f"{year}: transactions="+json.dumps([{"view":x["view"],"filtered":x["filter_provided"],"api":x["status"],"detail":x["result"]["status"],"n":x["result"].get("transaction_count"),"pick_count":x["result"].get("pick_count")} for x in trans],separators=(",",":")))
    report={"status":"RESEARCH_SOURCE_FEASIBILITY_ONLY_NO_PUBLISHED_MIX_OR_YIELD",
        "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "years":all_report,
        "cautions":["A successful mRoster endpoint alone does not establish finalized historical week-specific snapshots.",
          "Identical weekly snapshots may signal ESPN ignores scoringPeriodId; no attribution is approved from this probe.",
          "Transaction endpoint response does not establish complete acquisition chain; no draft/transaction inference is published.",
          "This contains only fantasy roster coverage and transaction counters, no personal/member/owner records."]}
    (OUT/"coverage.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Audit is read-only, sanitized and does not update published Acquisition DNA.")
if __name__=="__main__":
    try:main()
    except (TypeError,ValueError,KeyError) as exc:raise SystemExit("SAFE ERROR: "+str(exc))
