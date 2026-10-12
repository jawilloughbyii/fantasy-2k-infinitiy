#!/usr/bin/env python3
"""Private read-only ESPN postseason discovery (2021–2025). No publication or cookies."""
import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

YEARS = range(2021, 2026)
LEAGUES = {2021: 1493036707, 2022: 1493036707,
           2023: 418244680, 2024: 418244680, 2025: 418244680}
VIEWS = ("mTeam", "mMatchup", "mMatchupScore", "mSettings", "mStatus", "mStandings")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "postseason-research"


def fetch(year, league_id, cookie):
    params = urllib.parse.urlencode([("view", v) for v in VIEWS])
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
           f"seasons/{year}/segments/0/leagues/{league_id}?{params}")
    req = urllib.request.Request(url, headers={
        "Cookie": cookie, "Accept": "application/json",
        "User-Agent": "Fantasy2KInfinity-PostseasonDiscovery/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{year}: ESPN HTTP {exc.code}; authorization or endpoint issue") from None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"{year}: ESPN response error ({type(exc).__name__})") from None


def clean_score(value):
    return round(float(value), 2) if type(value) in (int, float) else None


def sanitize(source, year, league_id):
    if int(source.get("id", -1)) != league_id:
        raise ValueError(f"{year}: wrong ESPN league ID")
    settings = source.get("settings") or {}
    schedule_settings = settings.get("scheduleSettings") or {}
    regular_count = schedule_settings.get("matchupPeriodCount")
    if not isinstance(regular_count, int) or not 1 <= regular_count <= 18:
        raise ValueError(f"{year}: cannot identify regular-season boundary")
    teams = source.get("teams") or []
    if len(teams) != 10 or len({int(t["id"]) for t in teams}) != 10:
        raise ValueError(f"{year}: unexpectedly incomplete team coverage")
    names = {}
    seeds = {}
    for t in teams:
        tid = int(t["id"])
        names[str(tid)] = (t.get("name") or " ".join(
            str(t.get(k) or "") for k in ("location", "nickname"))).strip()
        seeds[str(tid)] = t.get("playoffSeed")
    schedule = source.get("schedule")
    if not isinstance(schedule, list):
        raise ValueError(f"{year}: ESPN omitted schedule")
    playoff_matches = []
    for match in schedule:
        period = match.get("matchupPeriodId")
        if not isinstance(period, int) or period <= regular_count:
            continue
        sides = []
        for side in ("home", "away"):
            raw = match.get(side) or {}
            if raw.get("teamId") is None:
                continue
            tid = int(raw["teamId"])
            if str(tid) not in names:
                raise ValueError(f"{year}: postseason matchup references unknown team {tid}")
            sides.append({
                "side": side, "team_id": tid, "team_name": names[str(tid)],
                "points": clean_score(raw.get("totalPoints")),
                "cumulative_score": clean_score(raw.get("cumulativeScore")),
            })
        playoff_matches.append({
            "matchup_period": period, "matchup_id": match.get("id"),
            "playoff_tier_type": match.get("playoffTierType"),
            "winner": match.get("winner"),
            "sides": sides,
            "schedule_field_keys": sorted(match.keys()),
        })
    status = source.get("status") or {}
    meta = {
        "regular_season_matchup_periods": regular_count,
        "playoff_team_count": schedule_settings.get("playoffTeamCount"),
        "playoff_matchup_period_length": schedule_settings.get("playoffMatchupPeriodLength"),
        "playoff_seeding_rule": schedule_settings.get("playoffSeedingRule"),
        "playoff_seeding_rule_by": schedule_settings.get("playoffSeedingRuleBy"),
        "playoff_seed_tiebreaker": schedule_settings.get("playoffSeedTiebreaker"),
        "matchup_periods": schedule_settings.get("matchupPeriods"),
        "schedule_setting_keys": sorted(schedule_settings.keys()),
        "status_final_scoring_period": status.get("finalScoringPeriod"),
        "status_current_matchup_period": status.get("currentMatchupPeriod"),
    }
    return {
        "season": year, "league_id": league_id, "metadata": meta,
        "teams": [{"espn_team_id": int(tid), "team_name": names[tid],
                   "playoff_seed": seeds[tid]} for tid in sorted(names, key=int)],
        "postseason_matchups": playoff_matches,
        "status": "discovery_only_not_approved",
    }


def main():
    s2 = os.environ.get("ESPN_S2", "").strip()
    swid = os.environ.get("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise RuntimeError("Missing GitHub Actions ESPN secrets")
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    for year in YEARS:
        clean = sanitize(fetch(year, LEAGUES[year],
                               f"espn_s2={s2}; SWID={swid}"), year, LEAGUES[year])
        matches = clean["postseason_matchups"]
        two_sided = sum(len(m["sides"]) == 2 for m in matches)
        tier_counts = {}
        for m in matches:
            tier = str(m["playoff_tier_type"])
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        summary = {"season": year, "league_id": LEAGUES[year],
                   "regular_season_matchup_periods": clean["metadata"]["regular_season_matchup_periods"],
                   "playoff_team_count": clean["metadata"]["playoff_team_count"],
                   "total_postseason_matchup_records": len(matches),
                   "two_sided_matchups": two_sided,
                   "playoff_periods": sorted({m["matchup_period"] for m in matches}),
                   "tier_counts": tier_counts,
                   "result": "retrieved_not_validated"}
        summaries.append(summary)
        (OUT / f"season_{year}.json").write_text(json.dumps(clean, indent=2) + "\n")
        print(f"{year}: postseason_records={len(matches)} "
              f"two_sided={two_sided} periods={summary['playoff_periods']} "
              f"tiers={json.dumps(tier_counts, sort_keys=True)}")
    (OUT / "coverage_report.json").write_text(json.dumps({
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "private_only_not_published",
        "seasons": summaries}, indent=2) + "\n")
    print("Discovery complete. No titles, playoff brackets or public data changed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        raise SystemExit("SAFE ERROR: " + str(exc))
