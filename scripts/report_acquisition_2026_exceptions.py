#!/usr/bin/env python3
"""Review-only, minimized 2026 proposed-only executed movement exceptions.

The short-lived workflow artifact contains public fantasy player/team labels,
proposed timestamp, and matching finalized starter weeks. It contains NO ESPN
cookies, member/owner data, raw responses, or stable player/transaction IDs.
This is *not* proof that proposedDate is the actual acquisition effective time.
"""
import collections
import datetime as dt
import json
import math
import os
import pathlib
from probe_acquisition_provenance import fetch, roster
from backfill_acquisition_provenance import boxscore_starters, roster_check
from audit_acquisition_2026 import YEAR, ROOT

KINDS = {("FREEAGENT","ADD"),("FREEAGENT","DROP"),("ROSTER","DROP")}
SLOTS = {0,2,4,6,23,17,16}

def valid_ms(v):
    return type(v) in (int,float) and math.isfinite(v) and v>0

def instant(v):
    return dt.datetime.fromtimestamp(v/1000,dt.timezone.utc).isoformat()

def entry_id(entry):
    p=entry.get("playerId")
    if type(p) is not int:
        pool=entry.get("playerPoolEntry") or {}
        p=pool.get("id")
        if type(p) is not int:p=(pool.get("player") or {}).get("id")
    return p if type(p) is int and p!=0 else None

def fantasy_name(entry):
    pool=entry.get("playerPoolEntry") or {}
    p=pool.get("player") or entry.get("player") or {}
    label=p.get("fullName") or p.get("name")
    return label.strip() if isinstance(label,str) and label.strip() else None

def inspect(raw_transactions, weekly_boxes, approved, mapping, draft_picks):
    """Strict identity joins in memory only; output does not include join IDs."""
    txs=raw_transactions.get("transactions") if isinstance(raw_transactions,dict) else None
    if not isinstance(txs,list):raise ValueError("Transaction feed missing")
    weeks=approved["completedThrough"]
    if type(weeks) is not int or weeks<1 or weeks>14 or len(weekly_boxes)!=weeks:
        raise ValueError("Approved week coverage missing")
    by_team={int(mapping[str(t["id"])]):t["name"] for t in approved["teams"]}
    if set(by_team)!=set(range(1,11)):raise ValueError("Team identity mapping incomplete")
    starters=collections.defaultdict(list)
    weekly_membership=collections.defaultdict(set)
    names={}
    for w in range(1,weeks+1):
        raw=weekly_boxes.get(w)
        found=boxscore_starters(raw,w,YEAR)
        if found is None or not roster_check(found,YEAR,allow_vacant=True):
            raise ValueError("Missing corroborated original-week matchup starters")
        schedule=raw.get("schedule")
        games=[g for g in schedule if isinstance(g,dict) and g.get("matchupPeriodId")==w]
        if len(games)!=5:raise ValueError("Incomplete original-week games")
        seen=set()
        for game in games:
            for side in ("home","away"):
                obj=game.get(side) or {}
                tid=obj.get("teamId")
                if type(tid) is not int or tid not in by_team or tid in seen:
                    raise ValueError("Duplicate or missing franchise")
                seen.add(tid)
                entries=(obj.get("rosterForCurrentScoringPeriod") or {}).get("entries")
                if not isinstance(entries,list):raise ValueError("Missing roster entries")
                extracted=[]
                for entry in entries:
                    if not isinstance(entry,dict):raise ValueError("Malformed roster entry")
                    pid=entry_id(entry)
                    slot=entry.get("lineupSlotId")
                    if pid is not None and type(slot) is int and slot in (*SLOTS,20,21):
                        weekly_membership[(tid,pid)].add(w)
                    if slot in SLOTS:
                        if pid is None:raise ValueError("Missing stable starter identity")
                        extracted.append((pid,slot))
                        if fantasy_name(entry):names.setdefault(pid,set()).add(fantasy_name(entry))
                if sorted(extracted)!=found[tid]["starters"]:raise ValueError("Mismatch with original-week starters")
                for pid,slot in extracted:starters[(tid,pid)].append(w)
        if seen!=set(by_team):raise ValueError("Missing franchises in matchup evidence")
    for p in draft_picks:
        pid=p.get("player_id");label=p.get("player_name")
        if type(pid) is int and isinstance(label,str) and label.strip():names.setdefault(pid,set()).add(label.strip())
    draft_owner={p["player_id"]:p["espn_team_id"] for p in draft_picks if type(p.get("player_id")) is int and type(p.get("espn_team_id")) is int}
    # A backwards trace is an observed evidence ledger, NOT verified ownership.
    # Collect every executed player movement by ID in memory, without exporting IDs.
    movement={}
    for tx in txs:
        if not isinstance(tx,dict) or tx.get("status")!="EXECUTED":continue
        typ=tx.get("type")
        if typ not in ("FREEAGENT","WAIVER","ROSTER","TRADE_ACCEPT"):continue
        for item in tx.get("items") or []:
            if not isinstance(item,dict) or item.get("type") not in ("ADD","DROP","TRADE"):continue
            pid=item.get("playerId")
            if type(pid) is not int or pid==0:continue
            processed=tx.get("processDate");proposed=tx.get("proposedDate")
            stamp=processed if valid_ms(processed) else proposed if valid_ms(proposed) else None
            movement.setdefault(pid,[]).append((stamp,typ,item.get("type"),item.get("fromTeamId"),item.get("toTeamId"),valid_ms(processed)))
    result=[]
    dedup=set()
    for tx in txs:
        if not isinstance(tx,dict):raise ValueError("Malformed source transaction")
        if tx.get("status")!="EXECUTED":continue
        typ=tx.get("type")
        if typ not in ("FREEAGENT","ROSTER"):
            continue  # e.g. empty administrative TRADE_UPHOLD or unrelated trade
        items=tx.get("items")
        if not isinstance(items,list):raise ValueError("Executed transaction has no item list")
        for idx,item in enumerate(items):
            if not isinstance(item,dict):raise ValueError("Malformed transaction item")
            action=item.get("type")
            if (typ,action) not in KINDS:continue
            process=tx.get("processDate");proposed=tx.get("proposedDate")
            if valid_ms(process) or not valid_ms(proposed):continue
            pid=item.get("playerId")
            source=item.get("fromTeamId");dest=item.get("toTeamId")
            team=dest if action=="ADD" else source
            if type(pid) is not int or pid==0 or type(team) is not int or team not in by_team:
                raise ValueError("Invalid executed exception player/team identity")
            if action=="ADD" and source not in (None,0,-1):raise ValueError("Ambiguous addition")
            if action=="DROP" and dest not in (None,0,-1):raise ValueError("Ambiguous departure")
            key=(tx.get("id"),idx)
            if key in dedup:raise ValueError("Duplicate exception item")
            dedup.add(key)
            labels=names.get(pid,set())
            if len(labels)>1:
                # Differences between original ESPN draft and roster display names
                # must not be silently resolved by matching on text.
                display="Name requires manual reconciliation"
                name_status="conflicting_display_labels"
            elif labels:
                display=next(iter(labels));name_status="source_label"
            else:
                display="Name unavailable in inspected evidence";name_status="not_observed"
            hit=sorted(set(starters.get((team,pid),[])))
            # Exclude the current proposed-only movement by comparing its exact
            # player/action/team/date; list only strictly earlier observed events.
            prior=[]
            for stamp,prior_type,prior_action,frm,to,has_process in movement.get(pid,[]):
                if stamp is None or stamp>=proposed:continue
                prior.append({"action":prior_type+"/"+prior_action,
                              "from_franchise":by_team.get(frm) if type(frm) is int else None,
                              "to_franchise":by_team.get(to) if type(to) is int else None,
                              "observed_at_utc":instant(stamp),
                              "time_basis":"processDate" if has_process else "proposedDate_unverified"})
            prior.sort(key=lambda x:(x["observed_at_utc"],x["action"]))
            original=draft_owner.get(pid)
            members=sorted(weekly_membership.get((team,pid),set()))
            if original==team:
                gap="DRAFT_SAME_FRANCHISE_CONTINUITY_UNVERIFIED"
            elif original in by_team:
                gap="DRAFTED_ELSEWHERE_TRANSFER_UNOBSERVED"
            else:
                gap="UNDRAFTED_PRESTART_ACQUISITION_UNOBSERVED"
            # No draft-day snapshot is supplied by mRoster week-one finals.
            # An absent movement is a genuine evidence gap, not proof of FA source.
            if prior:gap="EARLIER_MOVEMENTS_OBSERVED_REQUIRE_TIMESTAMP_REPLAY"
            result.append({"item_number":len(result)+1,"player":display,
                           "name_status":name_status,"franchise":by_team[team],
                           "action":typ+"/"+action,
                           "proposed_at_utc":instant(proposed),
                           "process_at_utc":None,
                           "finalized_starter_weeks":hit,
                           "matched_finalized_starter":bool(hit),
                           "draft_origin":("same_franchise" if original==team else
                               "another_franchise" if original in by_team else "not_in_verified_draft"),
                           "prior_executed_movements":prior,
                           "observed_roster_weeks":members,
                           "opening_roster_verified":False,
                           "prestart_evidence_gap":gap,
                           "temporal_attribution":"UNVERIFIED_PROPOSED_DATE_NOT_EXECUTION"})
    result.sort(key=lambda x:(x["proposed_at_utc"],x["franchise"],x["action"],x["item_number"]))
    counts=dict(sorted(collections.Counter(r["action"] for r in result).items()))
    return {"status":"PRIVATE_REVIEW_ONLY_NO_ACQUISITION_ASSIGNMENTS",
            "season":YEAR,"approved_through_week":weeks,"exception_item_count":len(result),
            "counts_by_action":counts,"affected_starter_item_count":sum(r["matched_finalized_starter"] for r in result),
            "items":result,"ready_for_attribution":False,"ready_for_publication":False,
            "caution":"Proposed timestamp is not independently verified as execution time. A matched finalized starting week alone does not establish attribution or a lock-time conflict."}

def main():
    s2,swid=os.getenv("ESPN_S2","").strip(),os.getenv("ESPN_SWID","").strip()
    if not s2 or not swid:raise SystemExit("SAFE ERROR: existing GitHub Actions ESPN secrets missing")
    secret=f"espn_s2={s2}; SWID={swid}"
    approved=json.loads((ROOT/"data/league.json").read_text())
    mapping=json.loads((ROOT/"reference/team_id_map.json").read_text())["baseline_to_espn"]
    drafts=json.loads((ROOT/"reference/historical_draft_picks.json").read_text())["seasons"]
    picks=next(s["picks"] for s in drafts if s["year"]==YEAR)
    raw,status=fetch(YEAR,"mTransactions2",cookie=secret)
    if status.get("status")!="ok":raise ValueError("Original transaction view not verified")
    box={}
    for w in range(1,approved["completedThrough"]+1):
        filt={"schedule":{"filterMatchupPeriodIds":{"value":[w]}}}
        data,st=fetch(YEAR,"mBoxscore",cookie=secret,week=w,filter_=filt)
        if st.get("status")!="ok":raise ValueError("Original boxscore view unavailable")
        box[w]=data
    report=inspect(raw,box,approved,mapping,picks)
    out=ROOT/"output/acquisition-2026-private/exceptions.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # No player/franchise labels or individual timestamps in public run logs.
    print(json.dumps({"status":report["status"],"exception_item_count":report["exception_item_count"],
                      "counts_by_action":report["counts_by_action"],
                      "affected_starter_item_count":report["affected_starter_item_count"],
                      "ready_for_publication":False},sort_keys=True))
if __name__=="__main__":
    try:main()
    except (ValueError,TypeError,KeyError,OverflowError,StopIteration) as exc:
        raise SystemExit("SAFE ERROR: exception report unavailable ("+type(exc).__name__+")")
