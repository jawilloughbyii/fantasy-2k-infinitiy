#!/usr/bin/env python3
"""Private 2026 source-evidence preview. Safe aggregate report; NEVER publishes mix.

Reuses the existing original-year authenticated retrieval. Raw responses and
stable player/transaction identifiers stay in process and are never saved.
"""
import collections
import datetime as dt
import json
import math
import os
import pathlib
from backfill_acquisition_provenance import audit, transaction_check
from probe_acquisition_provenance import fetch
from reconcile_acquisition_2026 import validate_draft

ROOT = pathlib.Path(__file__).resolve().parents[1]
YEAR = 2026
LEAGUE = 418244680


def draft_check(raw, reference):
    """Exact draft identity verification; returns counts/status, not source IDs."""
    details = raw.get("draftDetail") if isinstance(raw,dict) else None
    actual = details.get("picks") if isinstance(details,dict) else None
    if not isinstance(actual,list):
        return {"original_draft_retrieved":False,"draft_picks":0,
                "draft_matches_approved_reference":False}
    try:
        actual_rows=[{"player_id":p.get("playerId"),"espn_team_id":p.get("teamId")} for p in actual]
        canonical=[{"player_id":p["player_id"],"espn_team_id":p["espn_team_id"]} for p in reference]
        a,b=validate_draft(actual_rows),validate_draft(canonical)
        match=a==b
    except (ValueError,KeyError,AttributeError,TypeError):
        match=False
    return {"original_draft_retrieved":True,"draft_picks":len(actual),
            "draft_matches_approved_reference":match}


def transaction_evidence(raw, period_records):
    """No claim that ESPN's default feed is full/complete merely because it returned."""
    summary, all_ids=transaction_check(raw)
    statuses=collections.Counter()
    types=collections.Counter()
    items=collections.Counter()
    dated=0
    executed_actions=collections.Counter()
    executed_fields=collections.Counter()
    executed_value_shapes=collections.Counter()
    records=raw.get("transactions") if isinstance(raw,dict) else None
    for tx in records if isinstance(records,list) else []:
        if not isinstance(tx,dict):continue
        statuses[str(tx.get("status","missing"))]+=1
        types[str(tx.get("type","missing"))]+=1
        if isinstance(tx.get("processDate"),(int,float)) and math.isfinite(tx["processDate"]) and tx["processDate"]>0:
            dated+=1
        for item in tx.get("items") or []:
            if isinstance(item,dict):
                action=str(item.get("type","missing"))
                items[action]+=1
                if tx.get("status")=="EXECUTED":
                    executed_actions[str(tx.get("type","missing"))+"/"+action]+=1
                    for key in ("teamId","fromTeamId","toTeamId","playerId","lineupSlotId"):
                        executed_fields[action+"/"+key]+=int(key in item)
                        value=item.get(key)
                        shape="league_team" if type(value) is int and 1<=value<=10 else "unassigned" if value is None or value in (0,-1) else "other"
                        if key in ("fromTeamId","toTeamId"):
                            executed_value_shapes[action+"/"+key+"/"+shape]+=1
    # All per-period transaction records must be present unchanged in an
    # unscoped feed, but this condition is NECESSARY, never sufficient.
    merged={}
    conflicts=0
    periods_valid=0
    for values in period_records:
        if values is None:continue
        periods_valid+=1
        for key,payload in values.items():
            if key in merged and merged[key]!=payload:conflicts+=1
            merged[key]=payload
    subset=bool(all_ids is not None and periods_valid==len(period_records) and
                conflicts==0 and all(all_ids.get(k)==v for k,v in merged.items()))
    return {"unscoped_transaction_status":summary["status"],
            "unscoped_transaction_records":summary["records"],
            "unscoped_malformed_records":summary["malformed"],
            "period_transaction_lists_observed":periods_valid,
            "distinct_period_transaction_records":len(merged),
            "conflicting_repeated_records":conflicts,
            "unscoped_contains_period_records":subset,
            "executed_date_fields_present":dated,
            "status_counts":dict(sorted(statuses.items())),
            "transaction_type_counts":dict(sorted(types.items())),
            "item_action_counts":dict(sorted(items.items())),
            "executed_transaction_actions":dict(sorted(executed_actions.items())),
            "executed_item_field_coverage":dict(sorted(executed_fields.items())),
            "executed_team_value_shapes":dict(sorted(executed_value_shapes.items())),
            "chain_completeness_verified":False}


def score_check(weekly_boxscores, published, team_map):
    """Independent finalized matchup PF comparison against approved data."""
    expected={(w["week"],team_map[str(t["id"])]):(w["pf"], team_map[str(w["opp"])])
              for t in published["teams"] for w in t["weeks"]}
    matched=set()
    for week, raw in weekly_boxscores.items():
        schedule=raw.get("schedule") if isinstance(raw,dict) else None
        games=[g for g in schedule if isinstance(g,dict) and g.get("matchupPeriodId")==week] if isinstance(schedule,list) else []
        if len(games)!=5:return False
        for game in games:
            for side,other in (("home","away"),("away","home")):
                row,peer=game.get(side),game.get(other)
                if not isinstance(row,dict) or not isinstance(peer,dict):return False
                key=(week,row.get("teamId"))
                points=row.get("totalPoints")
                if key not in expected or key in matched or type(points) not in (int,float) or not math.isfinite(points):
                    return False
                approved_pf,approved_opponent=expected[key]
                if abs(approved_pf-points)>.011 or approved_opponent!=peer.get("teamId"):return False
                matched.add(key)
    return len(matched)==10*published["completedThrough"] and matched==set(expected)


def preview(request, published, reference, team_map):
    weeks=published["completedThrough"]
    if type(weeks)!=int or weeks<1 or weeks>14 or len(published["teams"])!=10:
        raise ValueError("Invalid approved completed-week boundary")
    # Only an independently approved completed period may enter the preview.
    coverage=audit(YEAR,request=request)
    if coverage["regular_season_periods_checked"]!=list(range(1,weeks+1)):
        raise ValueError("Acquisition preview week boundary disagrees with approved data")
    draft_raw,draft_status=request(YEAR,"mDraftDetail",week=None)
    draft=draft_check(draft_raw,reference) if draft_status.get("status")=="ok" else draft_check(None,reference)
    # Fetch week-scoped and unscoped transaction feeds separately, compare
    # identities in memory and emit only aggregate counts/status information.
    period_ids=[]
    for week in range(1,weeks+1):
        raw,status=request(YEAR,"mTransactions2",week=week)
        _,ids=transaction_check(raw if status.get("status")=="ok" else None)
        period_ids.append(ids)
    all_raw,all_status=request(YEAR,"mTransactions2",week=None)
    tx=transaction_evidence(all_raw if all_status.get("status")=="ok" else None,period_ids)
    box={}
    for week in range(1,weeks+1):
        filt={"schedule":{"filterMatchupPeriodIds":{"value":[week]}}}
        raw,status=request(YEAR,"mBoxscore",week=week,filter_=filt)
        box[week]=raw if status.get("status")=="ok" else None
    scores=score_check(box,published,team_map)
    flags={
        "original_draft_matches_reference":draft["draft_matches_approved_reference"],
        "full_weekly_rosters":coverage["full_period_roster_structure"],
        "independent_lineup_agreement":coverage["matchup_comparisons_agree"],
        "verified_original_week_pf":scores,
        "observed_transaction_feed_consistency":tx["unscoped_contains_period_records"],
        "complete_executed_ownership_chain":False,
        "verified_draft_execution_timestamp":False,
        "verified_individual_nfl_game_locks":False,
        "starter_source_attribution":False,
    }
    # Source metrics require ALL independent gates, even when source endpoint
    # structure and per-week final PF have passed. Never guess remaining gates.
    return {"status":"PRIVATE_2026_PROVENANCE_RESEARCH_ONLY",
            "season":YEAR,"approved_through_week":weeks,
            "expected_occupied_starts":90*weeks,
            "structurally_observed_starts":coverage["occupied_starter_appearances"],
            "draft":draft,"transaction_evidence":tx,"gates":flags,
            "ready_for_attribution":False,
            "ready_for_publication":False,
            "source_mix":None,"source_yield":None,
            "no_public_snapshot_changes":True,
            "next_actions":["Corroborate executed-event chronology against opening and final rosters",
                            "Recover and verify draft effective timestamp and every player game lock",
                            "Run private chain replay and reconcile all 90 occupied starts per approved week"]}


def main():
    s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: existing Actions ESPN secrets required")
    cookie=f"espn_s2={s2}; SWID={swid}"
    def request(year,view,week=None,filter_=None,cookie_unused=None,cookie=None):
        return fetch(year,view,cookie=secret,week=week,filter_=filter_)
    # Avoid storing any raw ESPN response or credential in artifacts.
    secret=cookie
    approved=json.loads((ROOT/"data/league.json").read_text())
    seasons=json.loads((ROOT/"reference/historical_draft_picks.json").read_text())["seasons"]
    draft=next(s for s in seasons if s["year"]==YEAR)
    mapping=json.loads((ROOT/"reference/team_id_map.json").read_text())["baseline_to_espn"]
    report=preview(request,approved,draft["picks"],mapping)
    output=ROOT/"output/acquisition-2026-private/coverage.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"through_week":report["approved_through_week"],
        "draft_reconciled":report["draft"]["draft_matches_approved_reference"],
        "rosters":report["gates"]["full_weekly_rosters"],
        "matchup_lineups":report["gates"]["independent_lineup_agreement"],
        "pf_reconciled":report["gates"]["verified_original_week_pf"],
        "transaction_feed_consistent":report["gates"]["observed_transaction_feed_consistency"],
        "transaction_status_counts":report["transaction_evidence"]["status_counts"],
        "transaction_type_counts":report["transaction_evidence"]["transaction_type_counts"],
        "item_action_counts":report["transaction_evidence"]["item_action_counts"],
        "executed_transaction_actions":report["transaction_evidence"]["executed_transaction_actions"],
        "executed_item_field_coverage":report["transaction_evidence"]["executed_item_field_coverage"],
        "executed_team_value_shapes":report["transaction_evidence"]["executed_team_value_shapes"],
        "ready_for_publication":False},sort_keys=True))

if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError,StopIteration) as exc:
        raise SystemExit("SAFE ERROR: 2026 source-evidence preview could not be reconciled ("+type(exc).__name__+")")
