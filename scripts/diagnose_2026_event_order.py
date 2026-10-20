#!/usr/bin/env python3
"""Private diagnostic for within-period repeated pair movements.

This does not establish ESPN effective ordering. Exact repeated record copies
are removed in memory; same-time and proposed-only action order is unverified.
No player IDs, owner data, transaction fingerprints or raw data leave the job.
"""
import collections
import datetime as dt
from conserve_2026_period_events import digest
from probe_2026_opening_evidence import compare_rosters
from report_acquisition_2026_exceptions import valid_ms

def review(windows,picks,rosters):
    _,snapshots=compare_rosters(rosters,picks)
    baseline={(p["espn_team_id"],p["player_id"]) for p in picks}
    seen=set();groups=collections.defaultdict(list);period_counts={}
    for period in range(1,6):
        raw,status=windows.get(period,(None,{}))
        if status.get("status")!="ok" or not isinstance((raw or {}).get("transactions"),list):
            raise ValueError("Missing original period movement window")
        counts=collections.Counter()
        for tx in raw["transactions"]:
            if not isinstance(tx,dict):raise ValueError("Malformed source transaction")
            fp=digest(tx)
            if fp in seen:continue
            seen.add(fp)
            if tx.get("status")!="EXECUTED" or tx.get("type")=="DRAFT":continue
            typ=tx.get("type")
            if typ not in ("WAIVER","FREEAGENT","ROSTER","TRADE_ACCEPT"):continue
            if not isinstance(tx.get("items"),list):raise ValueError("Missing executed items")
            process,proposed=tx.get("processDate"),tx.get("proposedDate")
            basis="processDate" if valid_ms(process) else "proposedDate_unverified" if valid_ms(proposed) else "missing"
            at=process if valid_ms(process) else proposed if valid_ms(proposed) else None
            for index,item in enumerate(tx["items"]):
                if not isinstance(item,dict):raise ValueError("Malformed movement")
                action,pid=item.get("type"),item.get("playerId")
                if type(pid) is not int or pid==0:continue
                src,dst=item.get("fromTeamId"),item.get("toTeamId")
                changes=[]
                if action=="ADD" and typ in ("WAIVER","FREEAGENT") and src in (None,0,-1) and type(dst) is int and 1<=dst<=10:changes=[(dst,pid,"add")]
                elif action=="DROP" and typ in ("WAIVER","FREEAGENT","ROSTER") and dst in (None,0,-1) and type(src) is int and 1<=src<=10:changes=[(src,pid,"drop")]
                elif action=="TRADE" and typ=="TRADE_ACCEPT" and type(src) is int and type(dst) is int and 1<=src<=10 and 1<=dst<=10 and src!=dst:changes=[(src,pid,"drop"),(dst,pid,"add")]
                for team,player,verb in changes:
                    groups[(period,team,player)].append((verb,at,basis,fp,index))
                    counts[verb]+=1
        period_counts[str(period)]=dict(counts)
    # Candidate replay is explicitly hypothetical for proposedDate-only events.
    state=set(baseline);out=[]
    for period in range(1,6):
        relevant={k:v for k,v in groups.items() if k[0]==period}
        overlaps={key:rows for key,rows in relevant.items() if {v[0] for v in rows}=={"add","drop"}}
        for key,rows in relevant.items():
            if key in overlaps:continue
            verbs={v[0] for v in rows}
            pair=key[1:]
            if verbs=={"add"}:state.add(pair)
            elif verbs=={"drop"}:state.discard(pair)
        snapshot=snapshots.get("period_"+str(period))
        candidates=[]
        for key,rows in sorted(overlaps.items()):
            pair=key[1:]; ordered=sorted(rows,key=lambda v:(v[1] is None,v[1] or 0,v[3],v[4]))
            definite=all(v[2]=="processDate" for v in rows) and all(v[1] is not None for v in rows) and len({v[1] for v in rows})==len(rows)
            final=ordered[-1][0] if ordered else None
            seen_in=snapshot is not None and pair in snapshot
            candidates.append({"action_count":len(rows),"action_types":dict(collections.Counter(v[0] for v in rows)),
              "timestamp_bases":dict(collections.Counter(v[2] for v in rows)),
              "different_candidate_instants":len({v[1] for v in rows if v[1] is not None})==len(rows),
              "strict_process_time_order_available":definite,
              "candidate_final_action":final if definite else "unverified",
              "present_in_period_roster":seen_in if snapshot is not None else None,
              "provisional_date_order_agrees_with_snapshot":(final=="add")==seen_in if snapshot is not None and final else None,
              "ordering_is_not_verified_by_snapshot":True})
            # Preserve the observed uncertainty in the actual state. Do not pick a winner.
            state.discard(pair)
        out.append({"period":period,"conflicting_pairs":len(overlaps),"candidates":candidates,
          "nonconflict_derived_pair_count":len(state),
          "snapshot_pair_count":len(snapshot) if snapshot is not None else None,
          "snapshot_unresolved_conflict_count":sum(key[1:] in snapshot for key in overlaps) if snapshot is not None else None,
          "all_pairs_in_period_order_verified":False})
    return {"status":"PRIVATE_SAME_PERIOD_ORDER_DIAGNOSTIC_ONLY","periods":out,
      "conflicting_pair_count":sum(p["conflicting_pairs"] for p in out),
      "complete_original_period_coverage":True,"proposed_time_is_execution_time":False,
      "roster_capture_time_verified":False,"ownership_chain_verified":False,
      "ready_for_attribution":False,"ready_for_publication":False}
