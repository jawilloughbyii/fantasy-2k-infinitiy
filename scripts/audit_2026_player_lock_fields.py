#!/usr/bin/env python3
"""Inspect per-starter original ESPN player/game-lock fields without guessing locks.

Returns anonymous field counts. A fantasy scoringPeriodId or last-updated field
is NOT an NFL kickoff or independently verified lineup-lock timestamp.
"""
import collections
from report_acquisition_2026_exceptions import entry_id
SLOTS={0,2,4,6,23,17,16}
CANDIDATE=("proTeamId","proTeam","gameId","gameDate","gameTime","kickoff",
           "kickoffTime","gameStartTime","startTime","lockTime","lineupLockTime",
           "scoringPeriodId","lastUpdated","playerPoolEntry","player")
def inspect(boxes,week_count):
    if set(boxes)!=set(range(1,week_count+1)):raise ValueError("Original-week coverage incomplete")
    fields=collections.Counter();player_fields=collections.Counter()
    meta=collections.Counter();pro_ids=collections.Counter();invalid_pro=collections.Counter();unique=set()
    for week,raw in boxes.items():
        schedule=raw.get("schedule") if isinstance(raw,dict) else None
        games=[g for g in schedule or [] if isinstance(g,dict) and g.get("matchupPeriodId")==week]
        if len(games)!=5:raise ValueError("Incomplete original-week matchups")
        teams=set()
        for g in games:
            for side in ("home","away"):
                obj=g.get(side) or {};tid=obj.get("teamId")
                if type(tid) is not int or tid not in range(1,11) or tid in teams:raise ValueError("Invalid matchup franchise coverage")
                teams.add(tid)
                entries=(obj.get("rosterForCurrentScoringPeriod") or {}).get("entries")
                if not isinstance(entries,list):raise ValueError("Missing starter entry list")
                for e in entries:
                    if not isinstance(e,dict):raise ValueError("Malformed starter")
                    if e.get("lineupSlotId") not in SLOTS:continue
                    pid=entry_id(e)
                    if pid is None or (week,pid) in unique:raise ValueError("Missing or duplicate original starter identity")
                    unique.add((week,pid))
                    pool=e.get("playerPoolEntry") or {}
                    player=pool.get("player") or e.get("player") or {}
                    if not isinstance(player,dict):player={}
                    for key in CANDIDATE:
                        fields["entry/"+key]+=int(key in e)
                        fields["pool/"+key]+=int(key in pool)
                        player_fields[key]+=int(key in player)
                    pro=player.get("proTeamId")
                    if type(pro) is int and pro>0:pro_ids[pro]+=1
                    else:invalid_pro["missing"]+=int(pro is None)
                    if pro is not None and (type(pro) is not int or pro<=0):invalid_pro["nonpositive_or_nonnumeric"]+=1
                    meta["player_pro_team_id_present"]+=int(type(pro) is int and pro>0)
                    meta["pool_scoring_period_present"]+=int("scoringPeriodId" in pool)
                    meta["entry_scoring_period_present"]+=int("scoringPeriodId" in e)
        if len(teams)!=10:raise ValueError("Incomplete league week")
    total=90*week_count
    if len(unique)!=total:raise ValueError("Incomplete occupied-starter coverage")
    # We do not export pro-team identifiers or original player identifiers.
    direct=sum(player_fields[k]+fields["entry/"+k]+fields["pool/"+k] for k in
               ("gameDate","gameTime","kickoff","kickoffTime","gameStartTime","startTime","lockTime","lineupLockTime"))
    return {"status":"PRIVATE_PLAYER_LOCK_SCHEMA_AUDIT_ONLY","approved_completed_weeks":week_count,
            "expected_starter_appearances":total,"observed_starter_appearances":len(unique),
            "unique_nfl_team_ids_observed":len(pro_ids),
            "player_nfl_team_identity_coverage":meta["player_pro_team_id_present"],
            "unusable_nfl_team_id_reasons":dict(sorted(invalid_pro.items())),
            "candidate_direct_time_field_occurrences":direct,
            "selected_field_coverage":{"entry":dict(sorted((k,fields["entry/"+k]) for k in CANDIDATE)),
                                      "player_pool":dict(sorted((k,fields["pool/"+k]) for k in CANDIDATE)),
                                      "player":dict(sorted(player_fields.items()))},
            "verified_nfl_schedule_join":False,"verified_individual_game_locks":False,
            "transaction_before_lock_verified":False,"ready_for_attribution":False,
            "ready_for_publication":False,
            "caution":"No ESPN fantasy scoring period, player update timestamp, or unverified kickoff-like field is promoted to individual NFL game lock."}
