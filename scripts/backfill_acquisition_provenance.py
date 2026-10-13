#!/usr/bin/env python3
"""Action 6: private, original-season, full-period source feasibility preview.

Never exports raw authenticated ESPN responses, player IDs, team owners, transaction
IDs or item payloads. This scan is NOT approval of an acquisition ownership chain.
"""
import argparse
import collections
import datetime
import json
import pathlib
from probe_acquisition_provenance import fetch, roster, Y

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUPPORTED = (2021, 2022, 2023, 2024, 2025, 2026)
SLOTS = {0:1, 2:2, 4:2, 6:1, 23:1, 17:1, 16:1}
BENCH_IR = (20, 21)


def expected_slots(year):
    slots = dict(SLOTS)
    if year <= 2022:
        slots[18] = 1  # ESPN lineup P slot (defaultPositionId 7 is not lineupSlotId 7)
    return slots


def roster_check(found, year):
    expected = expected_slots(year)
    if not isinstance(found, dict) or set(found) != set(range(1,11)):
        return False
    return all(dict(collections.Counter(slot for _, slot in team["starters"])) == expected
               and len(team["starters"]) == len(set(pid for pid, _ in team["starters"]))
               and len(team["all"]) == len(set(pid for pid, _ in team["all"]))
               and all(slot in (*expected, *BENCH_IR) for _,slot in team["all"])
               for team in found.values())


def boxscore_starters(raw, week, year):
    """Only matchup-scoped original-week lineup entries, no current roster fallback."""
    schedule = raw.get("schedule") if isinstance(raw,dict) else None
    if not isinstance(schedule,list):
        return None
    games=[game for game in schedule if game.get("matchupPeriodId")==week]
    if len(games)!=5:
        return None
    teams={}
    for game in games:
        for side in ("home","away"):
            obj=game.get(side) or {}
            team_id=obj.get("teamId")
            entries=(obj.get("rosterForCurrentScoringPeriod") or {}).get("entries")
            if type(team_id)!=int or team_id in teams or not isinstance(entries,list):
                return None
            pairs=[]
            for entry in entries:
                slot=entry.get("lineupSlotId")
                if slot in BENCH_IR:continue
                pid=entry.get("playerId")
                if type(pid)!=int:
                    pool=entry.get("playerPoolEntry") or {}
                    pid=pool.get("id")
                    if type(pid)!=int:pid=(pool.get("player") or {}).get("id")
                if type(pid)!=int or pid==0 or type(slot)!=int:
                    return None
                pairs.append((pid,slot))
            teams[team_id]={"starters":sorted(pairs),"all":sorted(pairs)}
    return teams if roster_check(teams,year) else None


def transaction_check(raw):
    """Structure only: transactions returned is not proof of a complete chain."""
    values=(raw or {}).get("transactions")
    if not isinstance(values,list):
        return {"status":"missing_list","records":None,"items":None,"malformed":None},None
    seen={};malformed=0;item_count=0
    for tx in values:
        if not isinstance(tx,dict) or type(tx.get("id"))!=int or not isinstance(tx.get("items"),list):
            malformed+=1
            continue
        item_count+=len(tx["items"])
        if any(not isinstance(item,dict) or type(item.get("playerId"))!=int for item in tx["items"]):
            malformed+=1
        encoded=json.dumps(tx,sort_keys=True,separators=(",",":"))
        if tx["id"] in seen and seen[tx["id"]]!=encoded:
            malformed+=1
        seen[tx["id"]]=encoded
    return {"status":"observed_not_chain_verified","records":len(values),
            "items":item_count,"malformed":malformed},seen


def audit(year, request=fetch):
    if year not in SUPPORTED:
        raise ValueError("Original-year provenance endpoint unavailable; no synthetic legacy attribution")
    completed=json.loads((ROOT/"data/league.json").read_text())["completedThrough"] if year==2026 else 14
    if year==2026 and (type(completed)!=int or not 1<=completed<=14):
        raise ValueError("Invalid approved current-week bound")
    rows=[];last=None;all_tx={};conflicts=0
    for week in range(1,completed+1):
        roster_raw,rstat=request(year,"mRoster",week=week,cookie=None)
        rsum,found=roster(roster_raw) if roster_raw is not None else ({"status":"unavailable"},None)
        valid=rstat.get("status")=="ok" and roster_check(found,year)
        changed=None if last is None or not valid else sum(
            found[tid]["starters"]!=last[tid]["starters"] for tid in range(1,11))
        if valid:last=found
        else:last=None
        filt={"schedule":{"filterMatchupPeriodIds":{"value":[week]}}}
        box,bstat=request(year,"mBoxscore",week=week,cookie=None,filter_=filt)
        prior=boxscore_starters(box,week,year) if bstat.get("status")=="ok" else None
        agreement=bool(valid and prior and all(
            prior[tid]["starters"]==found[tid]["starters"] for tid in range(1,11)))
        tx,tstat=request(year,"mTransactions2",week=week,cookie=None)
        tresult,ids=transaction_check(tx if tstat.get("status")=="ok" else None)
        if ids is not None:
            for key,value in ids.items():
                if key in all_tx and all_tx[key]!=value:conflicts+=1
                all_tx[key]=value
        rows.append({"week":week,"roster_ok":valid,"occupied_starters":10*sum(expected_slots(year).values()) if valid else None,
            "changed_team_lineups_from_previous_week":changed,"matchup_scoped_lineup_available":prior is not None,
            "matchup_roster_agreement":agreement,"observed_starter_slot_patterns":rsum.get("starter_slot_patterns") if not valid else None,"transaction_api":tstat.get("status"),
            "transaction_structure":tresult})
    complete_roster=all(r["roster_ok"] for r in rows)
    complete_transaction_structure=all(r["transaction_api"]=="ok" and
        r["transaction_structure"]["status"]=="observed_not_chain_verified" and
        r["transaction_structure"]["malformed"]==0 for r in rows)
    return {
        "status":"RESEARCH_ONLY_NO_ACQUISITION_ASSIGNMENTS",
        "year":year,"original_league_id":Y[year],"regular_season_periods_checked":list(range(1,completed+1)),
        "expected_starter_slots":sum(expected_slots(year).values()),
        "full_period_roster_structure":complete_roster,
        "full_period_transaction_structure":complete_transaction_structure,
        "matchup_comparisons_agree":all(r["matchup_roster_agreement"] for r in rows),
        "conflicting_repeat_transaction_ids":conflicts,
        "periods":rows,
        "ready_for_attribution":False,
        "remaining_gates":["verify full executed draft/add/drop/trade ownership chain with opening rosters",
            "reconcile original-season finalized scores and distinct week lineups",
            "verify each starter's acquisition before actual individual lineup lock",
            "validate season-specific league-wide quality for yield"],
        "no_public_snapshot_changes":True
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--year",type=int,choices=SUPPORTED,required=True)
    parser.add_argument("--output",type=pathlib.Path,default=pathlib.Path("output/acquisition-full-period/coverage.json"))
    args=parser.parse_args()
    import os
    s2=os.getenv("ESPN_S2","").strip();swid=os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: existing Actions ESPN secrets missing")
    cookie=f"espn_s2={s2}; SWID={swid}"
    def request(year,view,week,cookie=None,filter_=None):
        return fetch(year,view,cookie=cookie_value,week=week,filter_=filter_)
    cookie_value=cookie
    report=audit(args.year,request)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"year":args.year,"periods":len(report["periods"]),
        "valid_weekly_rosters":sum(p["roster_ok"] for p in report["periods"]),
        "invalid_week_slot_patterns":[{"week":p["week"],"patterns":p["observed_starter_slot_patterns"]} for p in report["periods"] if not p["roster_ok"]],
        "agreeing_matchup_rosters":sum(p["matchup_roster_agreement"] for p in report["periods"]),
        "period_transaction_lists":sum(p["transaction_structure"]["status"]=="observed_not_chain_verified" for p in report["periods"]),
        "ready_for_attribution":False},sort_keys=True))


if __name__=="__main__":
    try:main()
    except (TypeError,ValueError,KeyError) as exc:raise SystemExit("SAFE ERROR: acquisition source preview incomplete ("+type(exc).__name__+")")
