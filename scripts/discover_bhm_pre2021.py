#!/usr/bin/env python3
"""Private discovery of BHM ESPN league 1435116 pre-2021 seasons.

Never publishes an unverified season, title, draft, roster rule or owner attribution.
Only year-scoped league/team/score/settings/pick data are retained, no manager IDs.
"""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

LEAGUE_ID = 1435116
YEARS = range(2010, 2021)
VIEWS = ("mTeam", "mMatchup", "mMatchupScore", "mSettings", "mStatus", "mDraftDetail")
OUT = Path("output/bhm-pre2021-discovery")


def fetch(year, cookie):
    base = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
    query = urllib.parse.urlencode([("view", v) for v in VIEWS])
    urls = [
        ("modern", f"{base}/seasons/{year}/segments/0/leagues/{LEAGUE_ID}?{query}"),
        ("leagueHistory", f"{base}/leagueHistory/{LEAGUE_ID}?seasonId={year}&{query}"),
    ]
    attempts = []
    for label, url in (list(reversed(urls)) if year < 2018 else urls):
        req = urllib.request.Request(url, headers={
            "Cookie": cookie, "Accept": "application/json",
            "User-Agent": "Fantasy2KInfinity-ArchivedLeagueProbe/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                source = json.load(response)
            if isinstance(source, list):
                if len(source) != 1:
                    attempts.append({"endpoint": label, "status": "invalid_array_shape"})
                    continue
                source = source[0]
            if not isinstance(source, dict):
                attempts.append({"endpoint": label, "status": "invalid_shape"})
                continue
            if int(source.get("id", -1)) != LEAGUE_ID:
                attempts.append({"endpoint": label, "status": "mismatched_league"})
                continue
            # Reject responses that are actually a different requested year.
            declared = source.get("seasonId")
            if declared is not None and int(declared) != year:
                attempts.append({"endpoint": label, "status": "mismatched_season"})
                continue
            return source, None
        except urllib.error.HTTPError as exc:
            attempts.append({"endpoint": label, "status": "http_error", "code": exc.code})
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            attempts.append({"endpoint": label, "status": "request_error",
                             "error_type": type(exc).__name__})
    return None, {"status": "no_valid_endpoint", "attempts": attempts}


def score(v):
    return round(float(v), 2) if type(v) in (int, float) else None


def clean(year, src):
    if not isinstance(src, dict):
        return {"season": year, "status": "unexpected_payload_shape"}, None
    if int(src.get("id", -1)) != LEAGUE_ID:
        return {"season": year, "status": "league_id_mismatch"}, None

    raw_teams = src.get("teams") or []
    names = {}
    for t in raw_teams:
        tid = t.get("id")
        if type(tid) is not int or tid in names:
            return {"season": year, "status": "invalid_team_ids"}, None
        names[tid] = (t.get("name") or " ".join(str(t.get(k) or "") for k in
                     ("location", "nickname"))).strip()
    settings = src.get("settings") or {}
    schedule_settings = settings.get("scheduleSettings") or {}
    roster = settings.get("rosterSettings") or {}
    scoring = settings.get("scoringSettings") or {}
    draft_settings = settings.get("draftSettings") or {}
    detail = src.get("draftDetail") or {}
    raw_picks = detail.get("picks") or []
    picks = []
    if isinstance(raw_picks, list):
        for q in raw_picks:
            # No user identities or sensitive draft trade metadata.
            picks.append({k: q.get(k) for k in ("playerId", "teamId",
                          "overallPickNumber", "roundId", "roundPickNumber",
                          "bidAmount", "keeper")})
    matchups = []
    for m in src.get("schedule") or []:
        sides = []
        for side in ("home", "away"):
            row = m.get(side) or {}
            tid = row.get("teamId")
            if tid is not None:
                sides.append({"side": side, "team_id": tid,
                              "points": score(row.get("totalPoints"))})
        if sides:
            matchups.append({"matchup_id": m.get("id"),
                             "week": m.get("matchupPeriodId"),
                             "winner": m.get("winner"),
                             "playoff_tier_type": m.get("playoffTierType"),
                             "sides": sides})
    regular_weeks = schedule_settings.get("matchupPeriodCount")
    valid_regular = []
    if isinstance(regular_weeks, int) and 1 <= regular_weeks <= 18:
        valid_regular = [m for m in matchups if isinstance(m["week"], int)
                         and m["week"] <= regular_weeks]
    other = [m for m in matchups if m not in valid_regular]
    summary = {
        "season": year, "status": "retrieved",
        "team_count": len(names), "team_ids": sorted(names),
        "regular_season_weeks": regular_weeks,
        "matchup_count": len(matchups), "regular_matchup_count": len(valid_regular),
        "postseason_or_other_count": len(other),
        "played_regular_games": sum(len(m["sides"]) == 2 and
                              all(s["points"] is not None for s in m["sides"])
                              for m in valid_regular),
        "regular_points_total": score(sum(s["points"] or 0
                               for m in valid_regular for s in m["sides"])),
        "missing_regular_points_sides": sum(s["points"] is None
                                           for m in valid_regular for s in m["sides"]),
        "playoff_team_count": schedule_settings.get("playoffTeamCount"),
        "playoff_round_length": schedule_settings.get("playoffMatchupPeriodLength"),
        "drafted": detail.get("drafted"),
        "draft_type": draft_settings.get("type"),
        "draft_pick_count": len(picks),
        "draft_round_count": len({p["roundId"] for p in picks}),
        "lineup_slot_counts": roster.get("lineupSlotCounts") or {},
        "scoring_type": scoring.get("scoringType"),
        "scoring_category_count": len(scoring.get("scoringItems") or []),
    }
    sanitized = {
        "season": year, "league_id": LEAGUE_ID,
        "status": "discovered_not_approved",
        "teams": [{"espn_team_id": tid, "name": names[tid]}
                  for tid in sorted(names)],
        "metadata": {k:v for k,v in summary.items() if k != "status"},
        "regular_season_matchups": valid_regular,
        "other_matchups": other,
        "draft_picks": picks,
        "scoring_items": [{"stat_id": x.get("statId"), "points": x.get("points")}
                          for x in (scoring.get("scoringItems") or [])],
    }
    return summary, sanitized


def main():
    s2 = os.getenv("ESPN_S2", "").strip()
    swid = os.getenv("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise SystemExit("SAFE ERROR: missing configured ESPN credentials")
    cookie = f"espn_s2={s2}; SWID={swid}"
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for year in reversed(YEARS):
        src, err = fetch(year, cookie)
        if err:
            summary = {"season": year, **err}
            clean_season = None
        else:
            summary, clean_season = clean(year, src)
        results.append(summary)
        if clean_season:
            (OUT / f"season_{year}.json").write_text(
                json.dumps(clean_season, indent=2) + "\n")
        print(f"{year}: {summary['status']} "
              f"teams={summary.get('team_count','?')} "
              f"regular_games={summary.get('played_regular_games','?')} "
              f"picks={summary.get('draft_pick_count','?')} "
              f"weeks={summary.get('regular_season_weeks','?')}")
    report = {
        "league_id": LEAGUE_ID,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "private read-only discovery, not approved for public dashboard",
        "seasons": results,
    }
    (OUT / "coverage_report.json").write_text(json.dumps(report,indent=2)+"\n")
    if any(x["status"] == "access_denied" for x in results):
        print("NOTE: access-denied seasons do not establish absence; check ESPN permissions.")
    print("No historical identities, scores, championships, drafts or DNA published.")


if __name__ == "__main__":
    main()
