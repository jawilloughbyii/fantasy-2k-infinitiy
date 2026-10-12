#!/usr/bin/env python3
"""Private, read-only historical identity inspection for candidate ESPN league 791996.

Only selected league metadata, fantasy display names, settings and aggregate/final
matchup scores are exported as short-lived GitHub Actions artifacts. ESPN member,
owner, cookie and raw response fields are never logged or retained. Does not
approve source league, infer owners, or publish dashboard data.
"""
import datetime as dt
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ID = 791996
YEARS = (2014, 2015, 2016, 2017)
BASE = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/leagueHistory/{ID}"
VIEWS = ("mTeam", "mSettings", "mMatchup", "mMatchupScore", "mStatus")
OUT = Path("output/research-791996-identity")


def read(year, views, cookie):
    q = urllib.parse.urlencode([("seasonId", year)] + [("view", v) for v in views])
    req = urllib.request.Request(BASE + "?" + q, headers={
        "Cookie": cookie, "Accept": "application/json",
        "User-Agent": "Fantasy2KInfinity-PrivateIdentityResearch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = json.load(res)
    except urllib.error.HTTPError as exc:
        return None, {"status": "http_error", "code": exc.code}
    except (urllib.error.URLError, TimeoutError, ValueError, UnicodeDecodeError) as exc:
        return None, {"status": "request_error", "type": type(exc).__name__}
    if isinstance(raw, list):
        if len(raw) != 1:
            return None, {"status": "unexpected_history_array_length", "length": len(raw)}
        raw = raw[0]
    if not isinstance(raw, dict):
        return None, {"status": "unexpected_payload_shape"}
    try:
        got_id = int(raw.get("id", -1))
        got_year = int(raw["seasonId"]) if raw.get("seasonId") is not None else None
    except (ValueError, TypeError):
        return None, {"status": "invalid_identity"}
    if got_id != ID or (got_year is not None and got_year != year):
        return None, {"status": "league_or_season_mismatch"}
    return raw, {"status": "matching_league_and_season", "returned_year": got_year}


def finite_score(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    return round(float(v), 2)


def team_label(t):
    return str(t.get("name") or " ".join(
        str(t.get(k) or "") for k in ("location", "nickname"))).strip()


def inspect(year, cookie):
    # First try combined; if old ESPN rejects this combination, query individual views.
    raw, diagnostic = read(year, VIEWS, cookie)
    diagnostics = [{"views": list(VIEWS), **diagnostic}]
    partial = False
    if raw is None:
        raw = {}
        partial = True
        successes = 0
        for view in VIEWS:
            src, result = read(year, (view,), cookie)
            diagnostics.append({"views": [view], **result})
            if src is not None:
                successes += 1
                for field in ("name", "settings", "teams", "schedule", "status", "seasonId", "id"):
                    if field in src and src[field] is not None:
                        raw[field] = src[field]
        if not successes:
            return {"season": year, "status": "no_matching_retrieval", "attempts": diagnostics}
    settings = raw.get("settings") or {}
    if not isinstance(settings, dict):
        settings = {}
    teams = raw.get("teams")
    if not isinstance(teams, list):
        teams = []
    safe_teams = []
    seen = set()
    for t in teams:
        if not isinstance(t, dict):
            continue
        tid = t.get("id")
        if not isinstance(tid, int) or tid in seen:
            continue
        seen.add(tid)
        safe_teams.append({"espn_team_id": tid, "display_name": team_label(t),
                           "abbreviation": str(t.get("abbrev") or "")[:20]})
    safe_teams.sort(key=lambda t: t["espn_team_id"])
    schedule_settings = settings.get("scheduleSettings") or {}
    scoring_settings = settings.get("scoringSettings") or {}
    roster_settings = settings.get("rosterSettings") or {}
    draft_settings = settings.get("draftSettings") or {}
    schedule = raw.get("schedule")
    if not isinstance(schedule, list):
        schedule = []
    matches = []
    for game in schedule:
        if not isinstance(game, dict):
            continue
        sides = []
        for side in ("home", "away"):
            src = game.get(side) or {}
            if not isinstance(src, dict) or not isinstance(src.get("teamId"), int):
                continue
            sides.append({"side": side, "espn_team_id": src["teamId"],
                          "points": finite_score(src.get("totalPoints"))})
        matches.append({"matchup_id": game.get("id"), "week": game.get("matchupPeriodId"),
                        "playoff_tier_type": game.get("playoffTierType"),
                        "winner": game.get("winner"), "sides": sides})
    # No member information and no raw scoring items. ESPN slot ID counts are safe.
    result = {
        "season": year, "source_league_id": ID,
        "status": "retrieved_unverified_identity_research",
        "retrieval": "partial_individual_views" if partial else "combined_views",
        "league_name": str(settings.get("name") or raw.get("name") or ""),
        "team_count_setting": settings.get("size"),
        "teams": safe_teams,
        "settings": {
            "regular_season_matchup_period_count": schedule_settings.get("matchupPeriodCount"),
            "playoff_team_count": schedule_settings.get("playoffTeamCount"),
            "playoff_matchup_period_length": schedule_settings.get("playoffMatchupPeriodLength"),
            "scoring_type": scoring_settings.get("scoringType"),
            "scoring_item_count": len(scoring_settings.get("scoringItems") or []),
            "lineup_slot_counts": roster_settings.get("lineupSlotCounts"),
            "draft_type": draft_settings.get("type"),
        },
        "schedule_matchup_count": len(matches),
        "scored_two_sided_matchup_count": sum(
            len(m["sides"]) == 2 and all(s["points"] is not None for s in m["sides"])
            for m in matches),
        "matchups": matches,
        "attempts": diagnostics,
        "publication_status": "PRIVATE_UNVERIFIED_NO_FRANCHISE_MAPPING",
    }
    return result


def main():
    s2, swid = os.getenv("ESPN_S2", "").strip(), os.getenv("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise SystemExit("SAFE ERROR: Existing GitHub ESPN credentials missing")
    cookie = f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True, exist_ok=True)
    years = [inspect(y, cookie) for y in YEARS]
    result = {"candidate_league_id": ID, "years": years,
              "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "disposition": "Research only; do not merge with 2021-2025 or 2026"}
    (OUT / "historical_identity_review.json").write_text(json.dumps(result, indent=2) + "\n")
    for y in years:
        print(f"{y['season']}: {y['status']}; teams={len(y.get('teams', []))}; "
              f"games={y.get('schedule_matchup_count', 0)}; "
              f"scored_games={y.get('scored_two_sided_matchup_count', 0)}")
    print("Private sanitized identity review complete; published sources unchanged.")


if __name__ == "__main__":
    main()
