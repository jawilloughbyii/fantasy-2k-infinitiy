#!/usr/bin/env python3
"""Private 2026 pre-week-one ESPN evidence discovery; never alters published data.

Compares roster/transaction response identity across distinct original ESPN
queries. A response for period zero or an early period is NOT a draft-day
snapshot without independent timestamp/selection semantics. Only minimized
coverage and source gaps are saved, no stable player/transaction or owner IDs.
"""
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from probe_acquisition_provenance import fetch, roster
from backfill_acquisition_provenance import transaction_check
from report_acquisition_2026_exceptions import entry_id, fantasy_name, inspect, valid_ms
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
        executed_types=collections.Counter()
        executed_actions=collections.Counter()
        proposed=[]
        processed=[]
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
                if tx.get('status')=='EXECUTED':
                    category=str(tx.get('type','missing'))
                    executed_types[category]+=1
                    for item in tx.get('items') or []:
                        if isinstance(item,dict):executed_actions[category+'/'+str(item.get('type','missing'))]+=1
                    for field,values in (('proposedDate',proposed),('processDate',processed)):
                        v=tx.get(field)
                        if type(v) in (int,float) and v>0:values.append(dt.datetime.fromtimestamp(v/1000,dt.timezone.utc).isoformat())
        if isinstance(observed,list) and all(isinstance(tx,dict) for tx in observed):
            records[label]=collections.Counter(hashlib.sha256(json.dumps(tx,sort_keys=True,separators=(',',':')).encode()).digest() for tx in observed)
        else:
            records[label]=None
        summaries[label]={"api":"ok","structure":result["status"],"returned_records":result["records"],
                          "malformed":result["malformed"],"transaction_schema_counts":dict(sorted(schema.items())),
                          "executed_types":dict(sorted(executed_types.items())),
                          "executed_actions":dict(sorted(executed_actions.items())),
                          "proposed_utc_window":[min(proposed),max(proposed)] if proposed else None,
                          "processed_utc_window":[min(processed),max(processed)] if processed else None}
    main=records.get("mTransactions2_unscoped")
    main_valid=main is not None
    for label,ids in records.items():
        if ids is None or not main_valid:
            summaries[label]["all_records_in_primary_unscoped"]=False
            summaries[label]["additional_distinct_records"]=None
        else:
            summaries[label]["all_records_in_primary_unscoped"]=all(main[k]>=v for k,v in ids.items())
            summaries[label]["additional_distinct_records"]=sum(max(0,v-main[k]) for k,v in ids.items())
    return {"queries":summaries,"comparison_method":"in_memory_canonical_record_fingerprints_not_source_ids",
            "transaction_identity_comparisons_valid":main_valid,
            "full_draft_to_week_one_transaction_history_verified":False}

def focus_gaps(exceptions,roster_snapshots,draft_picks,raw_transactions=None,weekly_boxes=None,period_transactions=None):
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
    early_history=None
    if raw_transactions is not None and weekly_boxes is not None:
        started=set()
        labels=collections.defaultdict(set)
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
                            if type(tid) is int and pid is not None:
                                started.add((tid,pid))
                                label=fantasy_name(e)
                                if label:labels[pid].add(label)
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
        historical=collections.defaultdict(list)
        for view,period,raw,status in period_transactions or []:
            if view!='mTransactions2' or type(period) is not int or period<1 or status.get('status')!='ok':continue
            for tx in raw.get('transactions') or []:
                if not isinstance(tx,dict) or tx.get('status')!='EXECUTED':continue
                typ=tx.get('type')
                if typ not in ('DRAFT','FREEAGENT','WAIVER','TRADE_ACCEPT','ROSTER'):continue
                for item in tx.get('items') or []:
                    if not isinstance(item,dict) or item.get('type') not in ('DRAFT','ADD','DROP','TRADE'):continue
                    pid=item.get('playerId')
                    if type(pid) is not int:continue
                    historical[pid].append((period,typ,item.get('type'),item.get('fromTeamId'),item.get('toTeamId'),valid_ms(tx.get('processDate')),valid_ms(tx.get('proposedDate'))))
        for pick in draft_picks:
            pid=pick.get('player_id');label=pick.get('player_name')
            if type(pid) is int and isinstance(label,str) and label.strip():labels[pid].add(label.strip())
        matched=set(pair[1] for pair in focus)
        history_actions=collections.Counter()
        per_period=collections.Counter()
        players_with_executed_early_action=set()
        for pid in matched:
            for period,typ,action,frm,to,has_process,has_proposed in historical.get(pid,[]):
                history_actions[typ+'/'+action]+=1
                per_period[str(period)]+=1
                players_with_executed_early_action.add(pid)
        details=[]
        for tid,pid in focus:
            names=labels.get(pid,set())
            name=next(iter(names)) if len(names)==1 else ('Name requires manual reconciliation' if names else 'Name unavailable in inspected evidence')
            entries=historical.get(pid,[])
            details.append({'player':name,
                            'events':[{'period':period,'action':typ+'/'+action,
                                       'time_basis':'processDate' if has_process else 'proposedDate_unverified' if has_proposed else 'missing'}
                                      for period,typ,action,frm,to,has_process,has_proposed in entries],
                            'ownership_reconciled':False})
        details.sort(key=lambda x:x['player'])
        early_history={'player_evidence':details,'focus_player_count':len(matched),'players_with_executed_period_1_to_5_action':len(players_with_executed_early_action),
                       'observed_action_counts':dict(sorted(history_actions.items())),
                       'period_action_item_counts':dict(sorted(per_period.items())),
                       'timing_and_ownership_not_yet_replayed':True}
        for label,sets in roster_snapshots.items():
            if sets is not None:
                early[label]={'matched_items_on_same_franchise_roster':sum(pair in sets for pair in focus),
                              'matched_items_on_any_roster':sum(any(pid==pair[1] for tid,pid in sets) for pair in focus),
                              'observation_only_not_draft_day_ownership':True}
    return {"early_period_transaction_evidence":early_history,"early_snapshot_eight_item_coverage":early,"matched_exception_items":len(relevant),
            "draft_origin_counts":dict(sorted(collections.Counter(r["draft_origin"] for r in relevant).items())),
            "prior_movement_items":sum(len(r["prior_executed_movements"]) for r in relevant),
            "recent_unscoped_feed_items_without_prior_movement":sum(not bool(r["prior_executed_movements"]) for r in relevant),
            "opening_ownership_verified":False,
            "note":"Early-period source records now exist for all eight players; no final ownership attribution until timing, movement chronology and game locks are reconciled. Period zero is not approved as draft-day ownership."}

def summarize(rosters,transaction_queries,exceptions,draft_picks,raw_transactions=None,weekly_boxes=None):
    rr,snapshots=compare_rosters(rosters,draft_picks)
    tt=compare_transaction_queries(transaction_queries)
    ff=focus_gaps(exceptions,snapshots,draft_picks,raw_transactions,weekly_boxes,transaction_queries)
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
    from audit_2026_player_lock_fields import inspect as inspect_player_lock_fields
    report["player_lock_field_evidence"]=inspect_player_lock_fields(box,approved["completedThrough"])
    from conserve_2026_period_events import examine
    windows={p:(raw,status) for view,p,raw,status in tx if view=='mTransactions2' and type(p) is int and 1<=p<=5}
    report["period_event_conservation"]=examine(windows,draft["picks"],rosters)
    from audit_2026_roster_movements import audit as movement_audit
    report["movement_roster_comparison"]=movement_audit(windows,draft["picks"],rosters)
    from diagnose_2026_event_order import review as ordering_review
    report["same_period_order_diagnostic"]=ordering_review(windows,draft["picks"],rosters)
    path=ROOT/"output/acquisition-2026-private/preweek1-evidence.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"status":report["status"],"distinct_roster_sets":report["opening_rosters"]["distinct_observed_roster_sets"],
                      "eight_item_early_action_coverage":report["eight_player_gaps"]["early_period_transaction_evidence"]["players_with_executed_period_1_to_5_action"],
                      "transaction_query_coverage":report["transaction_query_comparison"]["queries"],
                      "draft_event_coverage_complete":report["period_event_conservation"]["draft_event_coverage_complete"],
                      "opening_ownership_verified":False,"ready_for_publication":False},sort_keys=True))
if __name__=="__main__":
    try:main()
    except (ValueError,KeyError,TypeError) as exc:
        raise SystemExit("SAFE ERROR: preweek-one source evidence incomplete ("+type(exc).__name__+")")
