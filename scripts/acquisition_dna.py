#!/usr/bin/env python3
"""Acquisition DNA: validated regular-season starter-week aggregation.

Pure offline calculator: no ESPN retrieval or acquisition-history inference.
Incomplete coverage must not be published as a verified season.
"""
from collections import Counter, defaultdict
import math

CATEGORIES=("draft","trade","waiver","free_agent","keeper","other","unknown")

def _number(x):
    return type(x) in (int,float) and math.isfinite(x)

def summarize(franchise_id, year, weeks, starters, expected_slots, weight_by_slot=None, ceiling_by_week=None):
    """Summarize ALL finalized starters in EVERY requested completed week.

    Starter record: week, player_id (negative D/ST valid), slot, source (latest
    verified same-franchise acquisition or unknown), optional bool worthy.
    Expected slots are the source-year legal starting positions with duplicates.
    """
    if not isinstance(franchise_id,str) or not franchise_id.strip() or type(year)!=int or year<2000:
        raise ValueError("Invalid franchise/season identity")
    if not isinstance(weeks,list) or not weeks or any(type(w)!=int or w<1 or w>18 for w in weeks):
        raise ValueError("Invalid completed-week coverage")
    if sorted(set(weeks))!=weeks or weeks!=list(range(1,weeks[-1]+1)):
        raise ValueError("Completed weeks must be contiguous and unique starting at one")
    if not isinstance(expected_slots,list) or not expected_slots or any(not isinstance(x,str) or not x for x in expected_slots):
        raise ValueError("Expected season-specific legal starting slots required")
    expected=Counter(expected_slots)
    if not isinstance(starters,list) or len(starters)!=len(weeks)*len(expected_slots):
        raise ValueError("Incomplete starter-week coverage; never treat missing as unknown source")
    seen=defaultdict(set); slots=defaultdict(Counter); by_source=defaultdict(list)
    for row in starters:
        if not isinstance(row,dict):raise ValueError("Malformed starter record")
        w,pid,slot,src=row.get("week"),row.get("player_id"),row.get("slot"),row.get("source")
        if w not in weeks or type(pid)!=int or pid==0 or slot not in expected or src not in CATEGORIES:
            raise ValueError("Invalid source/slot/player/week; never guess acquisition")
        if pid in seen[w]:raise ValueError("Player duplicated in finalized franchise-week")
        seen[w].add(pid);slots[w][slot]+=1
        if "worthy" in row and type(row["worthy"]) is not bool:
            raise ValueError("Starter-worthy value must be verified boolean")
        by_source[src].append(row)
    if any(slots[w]!=expected for w in weeks):
        raise ValueError("Incomplete or invalid original-season slot configuration")
    total=len(starters)
    source_rows=[]; weights=weight_by_slot if isinstance(weight_by_slot,dict) else None
    if weights is not None and (set(weights)!=set(expected) or any(not _number(v) or v<=0 for v in weights.values())):
        raise ValueError("Weights must cover the verified season's exact legal slot set")
    for src in CATEGORIES:
        rows=by_source[src]
        n=len(rows)
        quality_complete=bool(n and weights and all(type(row.get("worthy")) is bool for row in rows))
        opportunities=sum(weights[x["slot"]] for x in rows) if quality_complete else None
        hits=sum(weights[x["slot"]] for x in rows if x["worthy"]) if quality_complete else None
        source_rows.append({"source":src,"starter_weeks":n,"mix_pct":round(100*n/total,2),
                            "yield_status":"verified_finalized_hindsight" if quality_complete else "unavailable",
                            "worthy_weighted_hits":round(hits,2) if quality_complete else None,
                            "eligible_weighted_opportunities":round(opportunities,2) if quality_complete else None,
                            "yield_pct":round(100*hits/opportunities,2) if quality_complete else None})
    unknown=len(by_source["unknown"])
    coverage_status="verified" if unknown==0 else "unavailable" if unknown==total else "partial"
    execution={"status":"unavailable","weighted_hits":None,"attainable_weighted_ceiling":None,"capture_pct":None}
    if ceiling_by_week is not None:
        if not weights or any(type(r.get("worthy")) is not bool for r in starters):
            raise ValueError("Execution requires complete, source-independent season-specific quality observations")
        if not isinstance(ceiling_by_week,dict) or set(ceiling_by_week)!=set(weeks):
            raise ValueError("Execution requires every completed week")
        actual=sum(weights[r["slot"]] for r in starters if r["worthy"])
        ceiling=0.
        for w in weeks:
            top=ceiling_by_week[w]
            subtotal=sum(weights[r["slot"]] for r in starters if r["week"]==w and r["worthy"])
            possible=sum(weights[x] for x in expected_slots)
            if not _number(top) or top<subtotal-1e-6 or top>possible+1e-6:
                raise ValueError("Impossible legal quality ceiling; no blind execution score")
            ceiling+=top
        execution={"status":"verified_finalized_hindsight","weighted_hits":round(actual,2),
                   "attainable_weighted_ceiling":round(ceiling,2),
                   "capture_pct":round(100*actual/ceiling,2) if ceiling>0 else None}
    return {"year":year,"franchise_id":franchise_id,"status":"verified_complete_starter_weeks",
            "weeks":weeks,"starter_slots_per_week":len(expected_slots),"starter_week_count":total,
            "source_coverage":coverage_status,"known_source_starter_weeks":total-unknown,
            "known_source_pct":round(100*(total-unknown)/total,2),
            "mix":source_rows,"execution":execution,
            "caveat":"Mix is exposure, yield is conditional finalized starter quality, execution is independent legal-roster ceiling captured. No causal manager skill attribution."}


def equal_weight_history(seasons):
    """Each COMPLETE season one vote; missing sources never become a fabricated mix."""
    eligible=[s for s in seasons if s.get("status")=="verified_complete_starter_weeks"
              and s.get("source_coverage")=="verified"]
    if not eligible:
        return {"status":"unavailable","verified_seasons":[],"mix":None,"note":"No complete verified source-provenance seasons"}
    years=[s["year"] for s in eligible]
    if len(set(years))!=len(years):raise ValueError("Duplicate franchise season")
    if len({s["franchise_id"] for s in eligible})!=1:raise ValueError("Mixed permanent franchise identities")
    mix={k:round(sum(next(r["mix_pct"] for r in s["mix"] if r["source"]==k) for s in eligible)/len(eligible),2)
         for k in CATEGORIES}
    return {"status":"verified_equal_season_weight","verified_seasons":sorted(years),"mix":mix,
            "note":"Equal weight per complete season. Historical punter-era and nine-slot seasons are not pooled by raw starter count; quality yield remains era-specific."}


def last_verified_source(player_id, franchise_id, locked_at, events, complete_chain=False):
    """Classify latest pre-lock entry; never assume continuous draft ownership.

    Events are sanitized source-verified rows with player_id, franchise_id,
    effective_at (offset-aware ISO string) and action:
    draft/trade/waiver/free_agent/keeper/other/drop.
    Every departure ends the previous source spell. Any unverified or partial
    transaction feed returns unknown instead of attributing a draft pick.
    """
    from datetime import datetime
    if not complete_chain:return "unknown"
    if type(player_id)!=int or player_id==0 or not isinstance(franchise_id,str):
        raise ValueError("Invalid stable player/franchise ID")
    try:
        cutoff=datetime.fromisoformat(locked_at)
        if cutoff.tzinfo is None:raise ValueError("Lock timestamp missing timezone")
    except (ValueError,TypeError):raise ValueError("Invalid original game lock timestamp")
    eligible=[]
    for event in events:
        if event.get("player_id")!=player_id or event.get("franchise_id")!=franchise_id:continue
        at=datetime.fromisoformat(event["effective_at"])
        if at.tzinfo is None:raise ValueError("Transaction has no timezone")
        if at<=cutoff:
            if event.get("action") not in (*CATEGORIES[:-1],"drop"):
                raise ValueError("Unrecognized acquisition action; do not guess")
            eligible.append((at,event["action"]))
    if not eligible:return "unknown"
    eligible.sort()
    latest=eligible[-1][1]
    return "unknown" if latest=="drop" else latest
