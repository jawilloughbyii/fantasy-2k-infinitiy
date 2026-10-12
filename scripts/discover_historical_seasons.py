#!/usr/bin/env python3
"""Read-only ESPN season discovery; outputs private, sanitized Actions artifacts only."""
import argparse
import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

VIEWS = ("mTeam", "mMatchup", "mMatchupScore", "mSettings", "mStatus")
def probe(year, s2, swid, league_id):
    q = urllib.parse.urlencode([("view", v) for v in VIEWS])
    url = (f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/"
           f"seasons/{year}/segments/0/leagues/{league_id}?{q}")
    request = urllib.request.Request(url, headers={
        "Cookie": f"espn_s2={s2}; SWID={swid}",
        "Accept": "application/json", "User-Agent": "Fantasy2KInfinity/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            source = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(f"ESPN access denied for {year} (HTTP {exc.code}); stop and check permissions") from None
        return {"season": year, "status": "http_error", "http_status": exc.code}, None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"season": year, "status": "request_error", "error_type": type(exc).__name__}, None
    if int(source.get("id", -1)) != league_id:
        return {"season": year, "status": "league_id_mismatch"}, None
    teams = [{"espn_team_id": t.get("id"), "name": t.get("name") or
              " ".join(str(t.get(k) or "") for k in ("location", "nickname")).strip()}
             for t in (source.get("teams") or [])]
    matches = []
    for m in source.get("schedule") or []:
        sides = []
        for side in ("home", "away"):
            s = m.get(side) or {}
            if s.get("teamId") is not None:
                sides.append({"side": side, "team_id": s["teamId"],
                              "points": s.get("totalPoints")})
        if sides:
            matches.append({"matchup_id": m.get("id"), "week": m.get("matchupPeriodId"),
                            "winner": m.get("winner"), "sides": sides})
    weeks = sorted({m["week"] for m in matches if isinstance(m["week"], int)})
    complete = sorted({w for w in weeks if len([m for m in matches if m["week"] == w and len(m["sides"]) == 2 and
                    all(isinstance(s["points"], (int, float)) for s in m["sides"])]) == len([m for m in matches if m["week"] == w]) and
                    len([m for m in matches if m["week"] == w]) > 0})
    settings = source.get("settings") or {}
    schedule_settings = settings.get("scheduleSettings") or {}
    scoring_settings = settings.get("scoringSettings") or {}
    safe = {"season": year, "league_id": league_id, "teams": teams, "matchups": matches,
            "metadata": {"team_count": len(teams), "matchup_count": len(matches),
                         "weeks_present": weeks, "fully_scored_weeks": complete,
                         "regular_season_matchup_count": schedule_settings.get("matchupPeriodCount"),
                         "scoring_type": scoring_settings.get("scoringType")}}
    summary = {"season": year, "status": "retrieved", "team_count": len(teams),
               "matchups": len(matches), "weeks_present": weeks, "fully_scored_weeks": complete,
               "missing_points_sides": sum(s["points"] is None for m in matches for s in m["sides"])}
    return summary, safe

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--league-id", type=int, default=418244680)
    p.add_argument("--start-year", type=int, default=2010)
    p.add_argument("--end-year", type=int, default=2025)
    p.add_argument("--output-dir", default="output/historical-discovery")
    args = p.parse_args()
    if args.league_id <= 0:
        p.error("League ID must be a positive integer")
    if not (2000 <= args.start_year <= args.end_year <= 2025):
        p.error("Choose a historical year range between 2000 and 2025")
    s2, swid = os.environ.get("ESPN_S2", "").strip(), os.environ.get("ESPN_SWID", "").strip()
    if not s2 or not swid:
        raise RuntimeError("Missing ESPN Actions credentials")
    out = pathlib.Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for year in range(args.end_year, args.start_year - 1, -1):
        summary, safe = probe(year, s2, swid, args.league_id)
        report.append(summary)
        print(f"{year}: {summary['status']}; teams={summary.get('team_count', 0)}; "
              f"matchups={summary.get('matchups', 0)}")
        if safe:
            (out / f"season_{year}.json").write_text(json.dumps(safe, indent=2) + "\n")
    (out / "coverage_report.json").write_text(json.dumps({
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "league_id": args.league_id, "scope": "private research; not validated or approved for publication",
        "seasons": report}, indent=2) + "\n")
    print("Discovery complete; dashboard and published data unchanged.")

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        raise SystemExit(f"SAFE ERROR: {exc}")
