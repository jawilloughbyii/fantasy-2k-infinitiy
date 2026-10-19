#!/usr/bin/env python3
"""Private 2026 pre-week-one ESPN evidence discovery; never alters published data.

Compares roster/transaction response identity across distinct original ESPN
queries. A response for period zero or an early period is NOT a draft-day
snapshot without independent timestamp/selection semantics. Only minimized
coverage and source gaps are saved, no stable player/transaction or owner IDs.
"""
import collections
import json
import os
from pathlib import Path
from probe_acquisition_provenance import fetch, roster
from backfill_acquisition_provenance import transaction_check
from report_acquisition_2026_exceptions import entry_id, inspect, valid_ms
from audit_acquisition_2026 import ROOT, YEAR

VIEWS=("mTransactions2","mTransactions")
PERIODS=(None,0,1,2,3,4,5)

def compare_rosters(responses, draft_picks):
    summaries={}
    snapshots={}
    draft={(p["espn_team_id"],p["player_id"]) for p in draft_picks}
    for period,(raw,status) in responses.items():
        label="unscoped" if period is None else "period_"+str(period)
        if status.get("status")!="ok":
            summaries[label]={"api":status.get("status"),"usable":False}
            continue
        summ,found=roster(raw)
        valid=found is not None and set(found)==set(range(1,11))
        occupied={(tid,pid) for tid,team in (found or {}).items() for pid,_ in team["all"]}
        snapshots[label]=occupied if valid else None
        summaries[label]={"api":"ok","structure":summ.get("status"),"usable":valid,
                          "entry_count":len(occupied),
                          "original_draft_picks_on_observed_rosters":len(draft & occupied) if valid else None,
                          "non_draft_roster_entries":len(occupied-draft) if valid else None}
    if "unscoped" in snapshots:
        base=snapshots["unscoped"]
        for label,items in snapshots.items():
            summaries[label]["identical_to_unscoped"]=bool(items is not None and base is not None and items==base)
            summaries[label]["symmetric_difference_from_unscoped"]=len(items^base) if items is not None and base is not None else None
    distinct=len({frozenset(x) for x in snapshots.values() if x is not None})
    # Not even a distinct period-zero roster proves its capture was at draft completion.
    return {"queries":summaries,"distinct_observed_roster_sets":distinct,
            "draft_day_opening_roster_verified":False,
            "period_zero_is_not_automatically_draft_day":True},snapshots

def compare_transaction_queries(responses):
    summaries={};records={}
    for view,period,raw,status in responses:
        label=view+("_unscoped" if period is None else "_period_"+str(period))
        if status.get("status")!="ok":
            summaries[label]={"api":status.get("status"),"structure":"unavailable"};continue
        result,ids=transaction_check(raw)
        observed=raw.get('transactions') if isinstance(raw,dict) else None
        schema=collections.Counter()
        if isinstance(observed,list):
            for tx in observed:
                if not isinstance(tx,dict):
                    schema['non_object']+=1
                    continue
                schema['integer_id']+=int(type(tx.get('id')) is int)
                schema['missing_id']+=int(type(tx.get('id')) is not int)
                schema['list_items']+=int(isinstance(tx.get('items'),list))
                schema['missing_items']+=int(not isinstance(tx.get('items'),list))
                schema['executed_status']+=int(tx.get('status')=='EXECUTED')
        records[label]=ids
        summaries[label]={"api":"ok","structure":result["status"],"returned_records":result["records"],
                          "malformed":result["malformed"],"transaction_schema_counts":dict(sorted(schema.items()))}
    main=records.get("mTransactions2_unscoped")
    main_valid=bool(main is not None and summaries["mTransactions2_unscoped"]["malformed"]==0)
    for label,ids in records.items():
        if ids is None or not main_valid or summaries[label]["malformed"]!=0:
            summaries[label]["all_records_in_primary_unscoped"]=False
            summaries[label]["additional_distinct_records"]=None
        else:
            summaries[label]["all_records_in_primary_unscoped"]=all(main.get(k)==v for k,v in ids.items())
            summaries[label]["additional_distinct_records"]=sum(main.get(k)!=v for k,v in ids.items())
    return {"queries":summaries,"transaction_identity_comparisons_valid":main_valid,
            "full_draft_to_week_one_transaction_history_verified":False}

def focus_gaps(exceptions,roster_snapshots,draft_picks,raw_transactions=None,weekly_boxes=None):
    """Use the existing identified eight; match only to full source data in memory.

    Exception export intentionally lacks player IDs, so link by a private
    transaction pass in the caller, never name matching. Here report aggregate
    cross-query differences only, avoiding speculative identity joins.
    """
    relevant=[r for r in exceptions["items"] if r["matched_finalized_starter"]]
    if len(relevant)!=8:raise ValueError("Expected eight matched-starter exceptions; source snapshot changed")
    # Compare the eight players' original ESPN IDs to early snapshots only
    # in-memory. No snapshot row, player ID or owner data is exported.
    # inspect() deliberately strips player IDs; rematch by its exception item
    # order against the executed proposed-only movements before sorting would
    # be unsafe, so this separate probe does not guess missing joins.
    early={}
    if raw_transactions is not None and weekly_boxes is not None:
        started=set()
        for week,raw in weekly_boxes.items():
            for game in raw.get('schedule') or []:
                if game.get('matchupPeriodId')!=week:continue
                for side in ('home','away'):
                    obj=game.get(side) or {}
                    tid=obj.get('teamId')
                    entries=(obj.get('rosterForCurrentScoringPeriod') or {}).get('entries') or []
                    for e in entries:
                        if e.get('lineupSlotId') in (0,2,4,6,23,17,16):
                            pid=entry_id(e)
                            if type(tid) is int and pid is not None:started.add((tid,pid))
        focus=[]
        for tx in raw_transactions.get('transactions') or []:
            if tx.get('status')!='EXECUTED' or tx.get('type') not in ('FREEAGENT','ROSTER'):continue
            if valid_ms(tx.get('processDate')) or not valid_ms(tx.get('proposedDate')):continue
            for e in tx.get('items') or []:
                act=e.get('type')
                if (tx.get('type'),act) not in (('FREEAGENT','ADD'),('FREEAGENT','DROP'),('ROSTER','DROP')):continue
                tid=e.get('toTeamId') if act=='ADD' else e.get('fromTeamId')
                if (tid,e.get('playerId')) in started:focus.append((tid,e['playerId']))
        if len(focus)!=len(relevant):raise ValueError('Original-ID exception join mismatch')
        for label,sets in roster_snapshots.items():
            if sets is not None:
                early[label]={'matched_items_on_same_franchise_roster':sum(pair in sets for pair in focus),
                              'matched_items_on_any_roster':sum(any(pid==pair[1] for tid,pid in sets) for pair in focus),
                              'observation_only_not_draft_day_ownership':True}
    return {"early_snapshot_eight_item_coverage":early,"matched_exception_items":len(relevant),
            "draft_origin_counts":dict(sorted(collections.Counter(r["draft_origin"] for r in relevant).items())),
            "prior_movement_items":sum(len(r["prior_executed_movements"]) for r in relevant),
            "unresolved_prestart_items":sum(not bool(r["prior_executed_movements"]) for r in relevant),
            "opening_ownership_verified":False,
            "note":"No player identity join to period-zero roster is promoted: ESPN period-zero semantics are not independently established."}

def summarize(rosters,transaction_queries,exceptions,draft_picks,raw_transactions=None,weekly_boxes=None):
    rr,snapshots=compare_rosters(rosters,draft_picks)
    tt=compare_transaction_queries(transaction_queries)
    ff=focus_gaps(exceptions,snapshots,draft_picks,raw_transactions,weekly_boxes)
    return {"status":"PRIVATE_PREWEEK1_EVIDENCE_DISCOVERY_ONLY","season":YEAR,
            "opening_rosters":rr,"transaction_query_comparison":tt,"eight_player_gaps":ff,
            "ready_for_attribution":False,"ready_for_publication":False,
            "no_public_snapshot_changes":True}

def main():
    s2=os.getenv("ESPN_S2","").strip();swid=os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: Actions ESPN credentials missing")
    secret=f"espn_s2={s2}; SWID={swid}"
    approved=json.loads((ROOT/"data/league.json").read_text())
    mapping=json.loads((ROOT/"reference/team_id_map.json").read_text())["baseline_to_espn"]
    draft=next(s for s in json.loads((ROOT/"reference/historical_draft_picks.json").read_text())["seasons"] if s["year"]==YEAR)
    rosters={p:fetch(YEAR,"mRoster",cookie=secret,week=p) for p in PERIODS}
    tx=[]
    for view in VIEWS:
        for p in PERIODS:
            raw,status=fetch(YEAR,view,cookie=secret,week=p)
            tx.append((view,p,raw,status))
    original=next((raw for view,p,raw,status in tx if view=="mTransactions2" and p is None and status.get("status")=="ok"),None)
    if original is None:raise ValueError("Primary original transaction feed unavailable")
    box={}
    for w in range(1,approved["completedThrough"]+1):
        filt={"schedule":{"filterMatchupPeriodIds":{"value":[w]}}}
        raw,st=fetch(YEAR,"mBoxscore",cookie=secret,week=w,filter_=filt)
        if st.get("status")!="ok":raise ValueError("Finalized original-week lineup unavailable")
        box[w]=raw
    exception=inspect(original,box,approved,mapping,draft["picks"])
    report=summarize(rosters,tx,exception,draft["picks"],original,box)
    path=ROOT/"output/acquisition-2026-private/preweek1-evidence.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"distinct_roster_sets":report["opening_rosters"]["distinct_observed_roster_sets"],
                      "eight_item_prestart_gaps":report["eight_player_gaps"]["unresolved_prestart_items"],
                      "transaction_query_coverage":report["transaction_query_comparison"]["queries"],
                      "opening_ownership_verified":False,"ready_for_publication":False},sort_keys=True))
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError) as exc:
        raise SystemExit("SAFE ERROR: preweek-one source evidence incomplete ("+type(exc).__name__+")")
