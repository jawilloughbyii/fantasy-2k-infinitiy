#!/usr/bin/env python3
"""Research-only 2026 original-period acquisition movement conservation.

Do not claim period roster timing or a proposedDate effective instant. Uses
canonical JSON multiset fingerprints to deduplicate *exact repeats* across
query windows, never invents missing ESPN transaction IDs. No player/owner
identifiers, credentials, raw transactions or per-player rows are exported.
"""
import collections
import hashlib
import json
from probe_2026_opening_evidence import compare_rosters
from report_acquisition_2026_exceptions import valid_ms

KINDS={"DRAFT":{"DRAFT"},"WAIVER":{"ADD","DROP"},"FREEAGENT":{"ADD","DROP"},
       "TRADE_ACCEPT":{"TRADE"},"ROSTER":{"DROP"}}
def digest(tx):
    return hashlib.sha256(json.dumps(tx,sort_keys=True,separators=(",",":")).encode()).digest()

def examine(queries,draft_picks,rosters):
    draft={(p["player_id"],p["espn_team_id"]) for p in draft_picks}
    events=[];seen=collections.Counter();period_counts={};duplicates=0;missing=0
    for period in range(1,6):
        raw,status=queries.get(period,(None,{}))
        if status.get("status")!="ok" or not isinstance((raw or {}).get("transactions"),list):
            raise ValueError("Original-period transaction window unavailable")
        within=collections.Counter();counts=collections.Counter()
        for tx in raw["transactions"]:
            if not isinstance(tx,dict):raise ValueError("Malformed period transaction")
            key=digest(tx);within[key]+=1
            if within[key]<=seen[key]:duplicates+=1;continue
            if tx.get("status")!="EXECUTED":continue
            typ=tx.get("type");items=tx.get("items")
            if typ not in KINDS:continue
            if not isinstance(items,list):raise ValueError("Executed movement has no items")
            for item in items:
                if not isinstance(item,dict):raise ValueError("Invalid movement item")
                action=item.get("type")
                if action not in KINDS[typ]:continue
                pid=item.get("playerId");src=item.get("fromTeamId");dst=item.get("toTeamId")
                if type(pid) is not int or pid==0:raise ValueError("Invalid movement player ID")
                if typ=="DRAFT":
                    team=dst if type(dst) is int and 1<=dst<=10 else src
                    if (pid,team) not in draft:raise ValueError("Draft event conflicts with approved original draft")
                else:
                    if action=="ADD" and (src not in (None,0,-1) or type(dst) is not int or dst not in range(1,11)):raise ValueError("Malformed acquisition")
                    if action=="DROP" and (type(src) is not int or src not in range(1,11) or dst not in (None,0,-1)):raise ValueError("Malformed departure")
                    if action=="TRADE" and (type(src) is not int or type(dst) is not int or src not in range(1,11) or dst not in range(1,11) or src==dst):raise ValueError("Malformed transfer")
                time_field="processDate" if valid_ms(tx.get("processDate")) else "proposedDate_unverified" if valid_ms(tx.get("proposedDate")) else "missing"
                events.append((period,typ,action,pid,src,dst,time_field))
                counts[typ+"/"+action]+=1
                if time_field=="missing":missing+=1
        for key,count in within.items():seen[key]=max(seen[key],count)
        period_counts[str(period)]=dict(sorted(counts.items()))
    observed=collections.Counter((p,t) for period,typ,action,p,src,dst,_ in events if typ=="DRAFT" for t in [dst if type(dst) is int and dst in range(1,11) else src])
    if any(count!=1 or pair not in draft for pair,count in observed.items()):
        raise ValueError("Duplicate or conflicting original draft event")
    roster_summary,snapshots=compare_rosters(rosters,draft_picks)
    # Roster snapshots can differ because of transactions during that scoring
    # period. Count snapshot changes, not purported execution-boundary errors.
    transitions={}
    for period in range(1,5):
        a,b=snapshots.get("period_"+str(period)),snapshots.get("period_"+str(period+1))
        if a is not None and b is not None:
            transitions[str(period)+"_to_"+str(period+1)]={"added_player_team_pairs":len(b-a),"removed_player_team_pairs":len(a-b),
              "snapshot_transition_is_not_lock_time_replay":True}
    by_type=collections.Counter(t+"/"+a for _,t,a,*_ in events)
    time_basis=collections.Counter(e[-1] for e in events)
    return {"status":"PRIVATE_PERIOD_EVENT_CONSERVATION_RESEARCH_ONLY",
       "periods":[1,2,3,4,5],"exact_duplicate_query_records_ignored":duplicates,
       "executed_draft_items_matching_reference":sum(observed.values()),"approved_draft_picks":len(draft),
       "draft_event_coverage_complete":sum(observed.values())==len(draft),
       "observed_movement_item_counts":dict(sorted(by_type.items())),
       "movement_item_count_by_period":period_counts,"timestamp_basis_counts":dict(sorted(time_basis.items())),
       "missing_all_timestamp_fields":missing,"roster_snapshot_transitions":transitions,
       "period_snapshot_semantics_verified":False,"full_ownership_chain_verified":False,
       "individual_game_locks_verified":False,"ready_for_attribution":False,"ready_for_publication":False,
       "caution":"Query event observations are not evidence of execution order when processDate is absent; period roster snapshots are not player-lock snapshots."}
