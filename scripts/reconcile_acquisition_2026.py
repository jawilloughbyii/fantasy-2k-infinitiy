#!/usr/bin/env python3
"""Private 2026 acquisition chain replay. Never publish candidate player-level rows.

Inputs must be independently verified original-season evidence. This module does
not fetch ESPN or infer that a transaction endpoint is complete. Only a caller
with explicit source gates may request attribution; otherwise it fails closed.
"""
from collections import Counter
from datetime import datetime
import math

SOURCES = ("draft", "trade", "waiver", "free_agent", "other")
DEPARTURES = ("drop", "release")
SLOTS = Counter({0: 1, 2: 2, 4: 2, 6: 1, 23: 1, 17: 1, 16: 1})
TEAMS = set(range(1, 11))


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("Missing independently evidenced timestamp")
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Invalid timestamp") from exc
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("Timestamp must carry timezone")
    return at.timestamp()


def validate_draft(picks):
    """Original 2026 ESPN IDs, ten source teams, unique picks; no name matching."""
    if not isinstance(picks, list) or len(picks) != 160:
        raise ValueError("Incomplete original 2026 160-pick draft")
    owned = {}
    per_team = Counter()
    for pick in picks:
        if not isinstance(pick, dict):
            raise ValueError("Malformed draft pick")
        pid, tid = pick.get("player_id"), pick.get("espn_team_id")
        if type(pid) is not int or pid == 0 or type(tid) is not int or tid not in TEAMS or pid in owned:
            raise ValueError("Invalid or duplicate draft identity")
        owned[pid] = tid
        per_team[tid] += 1
    if any(per_team[t] != 16 for t in TEAMS):
        raise ValueError("Draft team pick coverage incomplete")
    return owned


def validate_starters(starters, weeks, corroborated):
    """Corroborated final occupied starts; a vacancy is never an unknown player."""
    if not isinstance(weeks, list) or not weeks or weeks != list(range(1, weeks[-1] + 1)):
        raise ValueError("Completed weeks must be contiguous")
    if not corroborated or not isinstance(starters, list):
        raise ValueError("Independent original-week lineup corroboration required")
    by_week = {}
    for w in weeks:
        found = [r for r in starters if r.get("week") == w]
        by_team = {t: [] for t in TEAMS}
        by_player = set()
        for r in found:
            p, t, s = r.get("player_id"), r.get("espn_team_id"), r.get("slot")
            if type(p) is not int or p == 0 or type(t) is not int or t not in TEAMS or type(s) is not int:
                raise ValueError("Invalid final starter identity")
            if p in by_player:
                raise ValueError("Duplicate player across a league-week")
            by_player.add(p)
            by_team[t].append((p, s))
        if any(Counter(s for _, s in by_team[t]) != SLOTS for t in TEAMS):
            raise ValueError("Incomplete nine-slot 2026 finalized roster")
        by_week[w] = by_team
    if len(starters) != 90 * len(weeks):
        raise ValueError("Extra or missing completed-week starters")
    return by_week


def validate_events(events, draft_at):
    """Normalize already verified executed records. Reject ambiguous simultaneous events."""
    start = timestamp(draft_at)
    if not isinstance(events, list):
        raise ValueError("Complete executed-event list required")
    seen = set()
    normalized = []
    for row in events:
        if not isinstance(row, dict):
            raise ValueError("Malformed executed event")
        pid, action = row.get("player_id"), row.get("action")
        team, key = row.get("espn_team_id"), row.get("event_key")
        if type(pid) is not int or pid == 0 or type(team) is not int or team not in TEAMS:
            raise ValueError("Event player or franchise identity invalid")
        if action not in (*SOURCES[1:], *DEPARTURES):
            raise ValueError("Unsupported or unverified acquisition action")
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError("Missing or duplicated original event identity")
        seen.add(key)
        at = timestamp(row.get("effective_at"))
        if at < start:
            raise ValueError("Transaction predates verified draft")
        from_team = row.get("from_team_id")
        if action == "trade":
            if type(from_team) is not int or from_team not in TEAMS or from_team == team:
                raise ValueError("Trade requires explicit original source and destination")
        elif from_team is not None:
            raise ValueError("Unexpected transfer source")
        normalized.append((at, key, pid, action, team, from_team))
    normalized.sort(key=lambda v: (v[0], v[1]))
    if len({(e[0], e[2]) for e in normalized}) != len(normalized):
        raise ValueError("Ambiguous simultaneous player actions")
    return start, normalized


def replay(picks, draft_at, events, starters, weeks, locks, *,
           complete_transaction_feed=False, independently_corroborated=False,
           verified_player_locks=False, score_reconciled=False,
           source_event_schema_verified=False):
    """Full starter attribution only after all external evidence gates hold.

    No call with default gates can produce acquisition metrics. The returned
    detailed starter rows are private in-memory evidence, never for publication.
    """
    draft = validate_draft(picks)
    final = validate_starters(starters, weeks, independently_corroborated)
    start, ordered = validate_events(events, draft_at)
    if not all((complete_transaction_feed, independently_corroborated,
                verified_player_locks, score_reconciled, source_event_schema_verified)):
        raise ValueError("Full evidence gates not independently satisfied")
    if not isinstance(locks, dict) or len(locks) != len(starters):
        raise ValueError("Per-player individual game-lock coverage incomplete")
    checks = []
    for r in starters:
        w, pid, tid = r["week"], r["player_id"], r["espn_team_id"]
        key = (w, pid)
        if key not in locks:
            raise ValueError("Missing individual game lock")
        at = timestamp(locks[key])
        if at <= start:
            raise ValueError("Starter lock before the original draft")
        checks.append((at, w, pid, tid, r["slot"]))
    checks.sort()
    ownership = dict(draft)
    origin = {pid: "draft" for pid in draft}
    pointer = 0
    result = []
    for lock, w, pid, tid, slot in checks:
        # At the exact lock timestamp, a same-time acquisition is ambiguous:
        # lock and transaction ordering must be independently established.
        if pointer < len(ordered) and ordered[pointer][0] == lock:
            raise ValueError("Ambiguous transaction at player lock")
        while pointer < len(ordered) and ordered[pointer][0] < lock:
            at, key, player, action, target, source_team = ordered[pointer]
            if action in DEPARTURES:
                if ownership.get(player) != target:
                    raise ValueError("Departure contradicts ownership chain")
                del ownership[player]
                del origin[player]
            elif action == "trade":
                if ownership.get(player) != source_team:
                    raise ValueError("Trade contradicts documented source owner")
                ownership[player] = target
                origin[player] = "trade"
            else:
                if player in ownership:
                    raise ValueError("Addition conflicts with an existing owner")
                ownership[player] = target
                origin[player] = action
            pointer += 1
        if ownership.get(pid) != tid or origin.get(pid) not in SOURCES:
            raise ValueError("Finalized starter contradicts pre-lock ownership")
        result.append({"week": w, "player_id": pid, "espn_team_id": tid,
                       "slot": slot, "source": origin[pid]})
    return result


def private_summary(rows, expected_week_count):
    """Safe, aggregate-only preview; never emit player, roster, owner or event IDs."""
    if len(rows) != 90 * expected_week_count:
        raise ValueError("Starter coverage incomplete")
    by_team = Counter(r["espn_team_id"] for r in rows)
    if any(by_team[t] != 9 * expected_week_count for t in TEAMS):
        raise ValueError("Starter franchise coverage incomplete")
    return {"status": "PRIVATE_RECONCILED_CANDIDATE_NOT_PUBLISHED",
            "weeks": expected_week_count, "occupied_starter_appearances": len(rows),
            "source_counts": dict(sorted(Counter(r["source"] for r in rows).items())),
            "ready_for_publication": False}
