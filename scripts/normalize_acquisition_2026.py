#!/usr/bin/env python3
"""Normalize explicitly executed 2026 ESPN transaction items privately.

The parser uses audited original ESPN mTransactions2 values. It never treats a
ROSTER/LINEUP edit, a proposal, pending, failed or canceled transaction as an
acquisition. Its output is an unapproved private input to chronological replay:
successful parsing does NOT prove feed completeness or historical ownership.
"""
from collections import Counter
from datetime import datetime, timezone
import math

ASSIGNABLE = { "WAIVER": "waiver", "FREEAGENT": "free_agent" }
UNASSIGNED = (None, 0, -1)
TEAMS = set(range(1,11))

def _team(v):
    return type(v) is int and v in TEAMS

def normalize_executed(raw):
    values=raw.get("transactions") if isinstance(raw,dict) else None
    if not isinstance(values,list):
        raise ValueError("Original unscoped ESPN transaction list missing")
    event_keys=set()
    events=[]
    counts=Counter()
    for tx in values:
        if not isinstance(tx,dict):
            raise ValueError("Malformed transaction record")
        if tx.get("status")!="EXECUTED":
            counts["nonexecuted_ignored"]+=1
            continue
        category=tx.get("type")
        fields=tx.get("items")
        if category=="TRADE_UPHOLD" and not fields:
            # ESPN records a separate empty administrative confirmation; the
            # executed TRADE_ACCEPT player movement is the ownership event.
            counts["empty_trade_uphold_ignored"]+=1
            continue
        if category=="ROSTER" and not fields:
            counts["empty_roster_edit_ignored"]+=1
            continue
        if category not in (*ASSIGNABLE,"ROSTER","TRADE_ACCEPT"):
            raise ValueError("Unsupported executed transaction category")
        txid=tx.get("id")
        if not isinstance(fields,list):
            raise ValueError("Missing original executed transaction items")
        for i,item in enumerate(fields):
            if not isinstance(item,dict):
                raise ValueError("Malformed executed transaction item")
            action=item.get("type")
            if category=="ROSTER" and action=="LINEUP":
                counts["lineup_edits_ignored"]+=1
                continue
            pid=item.get("playerId")
            source,dest=item.get("fromTeamId"),item.get("toTeamId")
            if type(pid) is not int or pid==0:
                raise ValueError("Executed acquisition lacks original player ID")
            if category in ASSIGNABLE and action=="ADD":
                if source not in UNASSIGNED or not _team(dest):
                    raise ValueError("Ambiguous free-agent or waiver entry")
                name=ASSIGNABLE[category]
                team=dest
                origin=None
            elif action=="DROP" and category in (*ASSIGNABLE,"ROSTER"):
                if not _team(source) or dest not in UNASSIGNED:
                    raise ValueError("Ambiguous player departure")
                name="drop"
                team=source
                origin=None
            elif category=="TRADE_ACCEPT" and action=="TRADE":
                if not _team(source) or not _team(dest) or source==dest:
                    raise ValueError("Trade must explicitly identify both franchises")
                name="trade"
                team=dest
                origin=source
            else:
                raise ValueError("Unsupported executed item/action combination")
            process=tx.get("processDate")
            if type(process) not in (int,float) or not math.isfinite(process) or process<=0:
                raise ValueError("No verified executed process time")
            when=datetime.fromtimestamp(process/1000, timezone.utc).isoformat()
            if type(txid) is not int:
                raise ValueError("Acquisition event lacks stable transaction identity")
            key=f"{txid}:{i}"
            if key in event_keys:
                raise ValueError("Duplicate executed event identity")
            event_keys.add(key)
            events.append({"event_key":key,"player_id":pid,"espn_team_id":team,
                           "from_team_id":origin,"effective_at":when,"action":name})
            counts[name]+=1
    return events,dict(sorted(counts.items()))
