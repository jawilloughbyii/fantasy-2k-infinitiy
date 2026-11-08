#!/usr/bin/env python3
"""Compare original 2026 period transaction *net movements* with roster snapshots.

Research-only: period roster capture time, free-agent effective time and NFL
player locks are NOT assumed. Aggregates only; source IDs and raw events stay
in memory. A discrepancy is evidence for investigation, never auto-corrected.
"""
import collections
from conserve_2026_period_events import digest
from probe_2026_opening_evidence import compare_rosters
from report_acquisition_2026_exceptions import valid_ms

def audit(windows,picks,rosters):
    approved={(p["espn_team_id"],p["player_id"]) for p in picks}
    summary,snapshots=compare_rosters(rosters,picks)
    if len(approved)!=160:raise ValueError("Original draft pair coverage incomplete")
    observed=set(approved); seen=set(); reports={}; timing=collections.Counter()
    for period in range(1,6):
        raw,status=windows.get(period,(None,{}))
        if status.get("status")!="ok" or not isinstance((raw or {}).get("transactions"),list):
            raise ValueError("Incomplete original-period movement window")
        add=set();remove=set();ambiguous=0; movement=collections.Counter()
        for tx in raw["transactions"]:
            if not isinstance(tx,dict):raise ValueError("Malformed transaction")
            h=digest(tx)
            if h in seen:continue
            seen.add(h)
            if tx.get("status")!="EXECUTED":continue
            category=tx.get("type")
            if category not in ("DRAFT","WAIVER","FREEAGENT","ROSTER","TRADE_ACCEPT"):continue
            items=tx.get("items")
            if not isinstance(items,list):raise ValueError("Missing executed transaction items")
            if category=="DRAFT":continue
            basis="processDate" if valid_ms(tx.get("processDate")) else "proposedDate_unverified" if valid_ms(tx.get("proposedDate")) else "missing"
            for item in items:
                if not isinstance(item,dict):raise ValueError("Malformed movement item")
                action=item.get("type");pid=item.get("playerId");source=item.get("fromTeamId");target=item.get("toTeamId")
                if action not in ("ADD","DROP","TRADE"):continue
                if type(pid) is not int or pid==0:raise ValueError("Invalid player movement identity")
                if category=="ROSTER" and action!="DROP":continue
                movement[category+"/"+action]+=1
                timing[basis]+=1
                if action=="ADD":
                    if source not in (None,0,-1) or type(target) is not int or target not in range(1,11):ambiguous+=1;continue
                    add.add((target,pid))
                elif action=="DROP":
                    if target not in (None,0,-1) or type(source) is not int or source not in range(1,11):ambiguous+=1;continue
                    remove.add((source,pid))
                else:
                    if type(source) is not int or type(target) is not int or source not in range(1,11) or target not in range(1,11) or source==target:ambiguous+=1;continue
                    remove.add((source,pid));add.add((target,pid))
        # A within-period drop/readd of the same pair has unknown order; do
        # not invent order or silently claim conservation for that pair.
        overlap=add & remove
        expected=(observed-remove)|add
        snapshot=snapshots.get("period_"+str(period))
        reports[str(period)]={
            "movement_items":dict(sorted(movement.items())),
            "net_add_pair_count":len(add),"net_remove_pair_count":len(remove),
            "same_pair_both_added_and_removed":len(overlap),"malformed_movement_items":ambiguous,
            "derived_pair_count":len(expected),
            "observed_roster_pair_count":len(snapshot) if snapshot is not None else None,
            "derived_missing_from_observed_count":len(expected-snapshot) if snapshot is not None else None,
            "observed_missing_from_derived_count":len(snapshot-expected) if snapshot is not None else None,
            "time_boundary_verified":False,
            "snapshot_match_proves_ownership":False}
        observed=expected
    return {"status":"PRIVATE_NET_MOVEMENT_VS_ROSTER_OBSERVATIONS_ONLY",
        "periods":reports,"movement_timestamp_basis":dict(sorted(timing.items())),
        "opening_basis":"original_verified_draft_picks_not_postdraft_opening_roster",
        "same_period_event_order_verified":False,"period_roster_capture_time_verified":False,
        "ownership_chain_verified":False,"player_lock_verified":False,
        "ready_for_attribution":False,"ready_for_publication":False}
